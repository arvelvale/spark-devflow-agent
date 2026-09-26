"""agent 内核：把一轮 turn 串起来（架构 2.1 时序）。

  输入 → 技能选择（JEV 两级 / 主模型自选）→ 模型路由（本地 / step-5）→ 记忆精选
       → 规划循环：[压缩检查 → 主模型 → 工具门控 → 执行 → 回填] × N → 回复
       → 记忆写回 → 轨迹收尾

任何一个外部依赖失败都走降级，不让整轮崩掉；降级都会在轨迹里标 fallback。
"""
from __future__ import annotations

import dataclasses
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

from .config import Config, Endpoint
from .context import ArchiveStore, Compressor, Conversation, WorkingState, estimate_tokens, render_messages
from .decision import DecisionClient, clip
from .gate import ConfirmRequest, ToolGate
from .llm import LLMClient, LLMError
from .memory import MemoryManager, MemorySelection, MemoryStore
from .prompts import render_skill, render_system
from .router import ModelRouter, Route
from .skills import Selection, SkillSelector, load_skills
from .tools import Permission, ToolContext, ToolError, build_registry, truncate
from .tools.linear import LinearClient
from .trace import Trace


TRUNCATION_NUDGE = ("（系统提示）上一条输出太长被截断了。不要在回复里贴大段代码或完整文件，"
                    "直接调用 edit_file / write_file 等工具修改文件；每次只改一处，改完再汇报。")


def new_session_id() -> str:
    return f"s-{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:4]}"


@dataclass
class TurnResult:
    reply: str
    turn: int
    skills: list[str]
    tier: str
    steps: int
    stopped: str
    tool_log: list[dict] = field(default_factory=list)
    tokens: dict = field(default_factory=dict)
    latency: float = 0.0


class LocalFirst:
    """辅助任务（摘要、记忆抽取、基线选技能）用的模型：只用私有模型，隐私内容不出自己的机器。
    主力和备用都被换成了外部 API 时，这里直接报不可用，调用方各自降级（摘要走规则、不抽取记忆）。"""

    def __init__(self, agent: "Agent"):
        self.agent = agent

    def chat(self, messages: list[dict], tools=None, **kw):
        errors = []
        for ep in (self.agent.cfg.local, self.agent.cfg.backup):
            if not ep.is_private or not self.agent.router.healthy(ep):
                continue
            try:
                return self.agent.clients[ep.name].chat(messages, tools, **kw)
            except LLMError as exc:
                errors.append(str(exc))
                self.agent.router.mark_down(ep)
        raise LLMError("没有可用的私有模型" + (f"：{errors[-1]}" if errors else ""))

    def complete(self, prompt: str, max_tokens: int = 800) -> str:
        """辅助任务：关思考、温度 0。"""
        return self.chat([{"role": "user", "content": prompt}], temperature=0, max_tokens=max_tokens,
                         thinking=False).content


class Agent:
    def __init__(
        self,
        cfg: Config,
        *,
        session: str | None = None,
        confirm: Callable[[ConfirmRequest], bool] | None = None,
        use_jev: bool = True,
        force_tier: str | None = None,
        decision: DecisionClient | None = None,
        clients: dict[str, LLMClient] | None = None,
    ):
        self.cfg = cfg
        self.th = cfg.thresholds
        self.session = session or new_session_id()
        run_dir = cfg.data_dir / "runs" / self.session
        self.trace = Trace(self.session, run_dir / "trace.jsonl")
        self.archive = ArchiveStore(run_dir / "archive.jsonl")
        self.use_jev = use_jev
        self.force_tier = force_tier
        if decision is not None:
            self.decision: DecisionClient | None = decision
        elif use_jev:
            self.decision = DecisionClient(cfg.jev_url, cfg.jev_model, cfg.jev_key,
                                           cache_path=cfg.data_dir / "cache" / "jev.sqlite",
                                           use_proxy=cfg.jev_use_proxy)
        else:
            self.decision = None
        self.clients = clients or {ep.name: LLMClient(ep) for ep in (cfg.local, cfg.backup, cfg.cloud)}
        self.registry = build_registry()
        skills, self.skill_errors = load_skills(cfg.skills_dir, set(self.registry.names()))
        self.router = ModelRouter(cfg, self.decision)
        self.local = LocalFirst(self)
        self.selector = SkillSelector(skills, self.th, self.decision, self.local)
        self.gate = ToolGate(self.th, self.decision, confirm)
        self.working = WorkingState()
        self.conv = Conversation(archive=self.archive)
        self.compressor = Compressor(self.th, self.decision, self.local.complete, self.trace)
        self.memory_store = MemoryStore(cfg.data_dir / "memory.sqlite")
        self.memory = MemoryManager(self.memory_store, self.th, self.decision,
                                    self.local.complete if cfg.memory_extract else None, self.trace, self.session)
        linear = (LinearClient(cfg.linear_key, cfg.linear_team_key, cfg.linear_project_name,
                               use_proxy=cfg.linear_use_proxy) if cfg.linear_key else None)
        self.ctx = ToolContext(workspace=cfg.workspace, vault=cfg.vault_dir, working=self.working,
                               archive=self.archive, memory=self.memory_store, linear=linear,
                               shell_allow=cfg.shell_allow)
        self.ratio = 1.0  # token 估算校准倍率 = 真实 prompt_tokens / 估算值

    # ------------------------------------------------------------------
    def _usage_snapshot(self) -> dict:
        snap = {name: dict(c.totals) for name, c in self.clients.items()}
        if self.decision:
            snap["jev"] = dict(self.decision.totals)
        return snap

    @staticmethod
    def _usage_delta(before: dict, after: dict) -> dict:
        out = {}
        for name, tot in after.items():
            prev = before.get(name, {})
            d = {k: tot.get(k, 0) - prev.get(k, 0) for k in ("input_tokens", "output_tokens")}
            if any(d.values()):
                out[name] = d
        return out

    def _system(self, sel: Selection, mem: MemorySelection, private: bool) -> str:
        if not private:  # 非私有模型再过滤一遍隐私记忆（轮内升级时 mem 是按主力选的）
            mem = MemorySelection([m for m in mem.full if m.privacy != "local"],
                                  [m for m in mem.brief if m.privacy != "local"])
        return render_system(
            skill_index="\n".join(s.index_line() for s in self.selector.skills),
            skill_blocks="\n\n".join(render_skill(s.name, s.body, s.scripts) for s in sel.skills),
            working=self.working.render(),
            memories=mem.render(),
            summaries=self.conv.render_summaries(),
            workspace=self.cfg.workspace.name,
        )

    def _next_endpoint(self, current: Endpoint, tried: set[str]) -> Endpoint | None:
        order = {"local": ["backup", "cloud"], "backup": ["cloud", "local"], "cloud": ["local", "backup"]}
        for name in order[current.name]:
            ep = getattr(self.cfg, name)
            if name not in tried and self.router.healthy(ep):
                return ep
        return None

    def _resolve_tool(self, tool, args: dict):
        """技能脚本的实际权限按技能 frontmatter 的声明：read → 只读直接跑；write_local → 走门控。
        声明本身就是技能作者给的白名单，所以已声明的脚本视同在 allowed-tools 里。未声明的脚本由工具自己拒绝。"""
        if tool.name != "run_skill_script":
            return tool, False
        spec = self.ctx.skill_scripts.get(str(args.get("skill", "")), {}).get(str(args.get("script", "")))
        if spec is None:
            return tool, False
        perm = Permission.READ if spec.permission == "read" else Permission.WRITE_LOCAL
        return dataclasses.replace(tool, permission=perm), True

    def _run_tool(self, call, allowed_write: set[str], request: str, tool_log: list[dict]) -> str:
        tool = self.registry.get(call.name)
        if call.parse_error:
            self.trace.emit("tool.call", {"tool": call.name, "ok": False, "error": call.parse_error})
            tool_log.append({"tool": call.name, "ok": False})
            return f"[未执行] {call.parse_error}。请用合法的 JSON 对象重新调用 {call.name}。"
        if tool is None:
            self.trace.emit("tool.call", {"tool": call.name, "ok": False, "error": "未知工具"})
            tool_log.append({"tool": call.name, "ok": False})
            if call.name in self.selector.by_name:
                return f"[未执行] {call.name} 是技能不是工具：它的步骤已经在系统提示里，直接按步骤用工具执行。"
            return f"[未执行] 没有叫 {call.name} 的工具。"
        tool, declared = self._resolve_tool(tool, call.arguments)
        allowed = tool.permission == Permission.READ or tool.name in allowed_write or declared
        g = self.gate.check(tool, call.arguments, allowed=allowed, goal=self.working.goal, request=request,
                            plan=[t["item"] for t in self.working.todo])
        self.trace.emit("tool.gate", {
            "tool": tool.name, "permission": tool.permission.value, "decision": g.decision, "reason": g.reason,
            "appropriate": None if g.appropriate is None else round(g.appropriate, 3), "threshold": g.threshold,
            "collateral": None if g.collateral is None else round(g.collateral, 3),
            "confirmed": g.confirmed, "args": call.arguments}, fallback=g.fallback)
        if not g.execute:
            tool_log.append({"tool": tool.name, "ok": False, "denied": True})
            if g.decision == "confirm":
                return "[未执行] 用户拒绝了这个操作。不要换别的工具绕过，向用户说明即可。"
            return f"[未执行] {g.reason}"
        t0 = time.monotonic()
        try:
            out, ok = tool.handler(call.arguments, self.ctx), True
        except ToolError as exc:
            out, ok = f"[失败] {exc}", False
        except Exception as exc:  # 工具实现的 bug 也不能打断整轮
            out, ok = f"[失败] 工具内部错误 {type(exc).__name__}: {exc}", False
        out, cut = truncate(out, tool.max_chars or self.cfg.tool_result_chars)
        self.trace.emit("tool.call", {"tool": tool.name, "args": call.arguments, "ok": ok,
                                      "result_chars": len(out), "truncated": cut},
                        latency_ms=(time.monotonic() - t0) * 1000)
        tool_log.append({"tool": tool.name, "ok": ok})
        if ok and tool.permission != Permission.READ:  # 写操作自动记为关键证据（受保护，不会被压缩）
            self.working.update(evidence=[f"{tool.name}：{clip(out.splitlines()[0] if out else '', 120)}"])
        return out

    # ------------------------------------------------------------------
    def run_turn(self, text: str, source: str = "text") -> TurnResult:
        t_start = time.monotonic()
        self.trace.turn += 1
        turn = self.trace.turn
        before = self._usage_snapshot()
        self.trace.emit("turn.start", {"input": text, "source": source})
        recent = render_messages(self.conv.messages[-6:], 1200)
        self.conv.add({"role": "user", "content": text}, turn)
        if not self.working.goal:
            self.working.update(goal=clip(text, 200))

        sel = self.selector.select(text, recent, mode="jev" if self.use_jev else "baseline")
        self.trace.emit("skill.select", {"mode": sel.mode, "selected": sel.names, "reason": sel.reason, **sel.detail},
                        latency_ms=sel.latency * 1000, provider="jev" if sel.mode == "jev" and not sel.fallback else "local",
                        usage=sel.usage, fallback=sel.fallback)

        route: Route = self.router.route(text, sel.skills, self.force_tier)
        self.trace.emit("route.model", {"tier": route.tier, "endpoint": route.endpoint.name,
                                        "model": route.endpoint.model, "reason": route.reason,
                                        "scores": route.scores}, fallback=route.fallback)

        mem = self.memory.select(text, self.working.goal, "local" if route.endpoint.is_private else "cloud")

        allowed_write: set[str] = set()
        for s in sel.skills:
            allowed_write.update(s.allowed_tools)
        has_scripts = any(s.scripts for s in sel.skills)
        exposed = [n for n in self.registry.names()
                   if self.registry.get(n).permission == Permission.READ or n in allowed_write
                   or (n == "run_skill_script" and has_scripts)]
        schemas = self.registry.schemas(exposed)
        self.ctx.skill_dirs = {s.name: s.path.parent for s in sel.skills}
        self.ctx.skill_scripts = {s.name: {x.name: x for x in s.scripts} for s in sel.skills}

        ep, tier = route.endpoint, route.tier
        tried = {ep.name}
        malformed, escalated, truncated_once = 0, False, False
        tool_log: list[dict] = []
        reply, stopped, steps = "", "max_steps", 0
        for step in range(1, self.cfg.max_steps + 1):
            steps = step
            system = self._system(sel, mem, ep.is_private)
            if self.compressor.maybe_compress(self.conv, estimate_tokens(system), self.working, turn, self.ratio):
                system = self._system(sel, mem, ep.is_private)
            messages = [{"role": "system", "content": system}] + self.conv.messages
            est = estimate_tokens(system) + self.conv.tokens()
            try:
                res = self.clients[ep.name].chat(messages, schemas, max_tokens=ep.max_tokens,
                                                 thinking=self.cfg.local_thinking or ep.name == "cloud")
            except LLMError as exc:
                if not ep.needs_key:
                    self.router.mark_down(ep)
                nxt = self._next_endpoint(ep, tried)
                self.trace.emit("error", {"where": "llm", "message": str(exc), "handled": nxt is not None})
                if nxt is None:
                    reply, stopped = f"模型服务都不可用，这一轮没能完成：{exc}", "error"
                    break
                self.trace.emit("route.escalate", {"from": ep.name, "to": nxt.name, "reason": "模型调用失败"},
                                fallback=True)
                ep, tier = nxt, ("cloud" if nxt.name == "cloud" else "local")
                tried.add(ep.name)
                continue
            if res.usage.get("prompt_tokens") and est:
                self.ratio = min(max(res.usage["prompt_tokens"] / est, 0.5), 2.5)
            self.trace.emit("llm.call", {"tier": tier, "endpoint": ep.name, "step": step,
                                         "finish_reason": res.finish_reason,
                                         "content_chars": len(res.content), "reasoning_chars": len(res.reasoning),
                                         "tool_calls": [c.name for c in res.tool_calls],
                                         "prompt_tokens_est": int(est * self.ratio)},
                            latency_ms=res.latency * 1000, provider=ep.name, model=res.model, usage=res.usage)
            if res.tool_calls:
                self.conv.add(res.assistant_message(), turn)
                bad = 0
                for call in res.tool_calls:
                    content = self._run_tool(call, allowed_write, text, tool_log)
                    self.conv.add({"role": "tool", "tool_call_id": call.id, "content": content}, turn)
                    bad += bool(call.parse_error)
                malformed = malformed + 1 if bad else 0
                if (malformed >= self.th.malformed_before_escalate and tier == "local" and not escalated
                        and "cloud" not in tried and self.router.healthy(self.cfg.cloud)):
                    self.trace.emit("route.escalate", {"from": ep.name, "to": "cloud",
                                                       "reason": f"本地模型连续 {malformed} 次给出非法工具参数"})
                    ep, tier, escalated = self.cfg.cloud, "cloud", True
                    tried.add("cloud")
                continue
            if res.finish_reason == "length" and not truncated_once:
                # 输出超长被截断：常见原因是把代码贴进回复而不是用工具改文件。提示一次后继续
                truncated_once = True
                if res.content:
                    self.conv.add({"role": "assistant", "content": clip(res.content, 2000)}, turn)
                self.conv.add({"role": "user", "content": TRUNCATION_NUDGE}, turn)
                self.trace.emit("error", {"where": "llm", "message": "输出超长被截断，已提示改用工具后继续",
                                          "handled": True})
                continue
            reply = res.content or ("（输出被截断）" if res.finish_reason == "length" else "（模型没有给出回复）")
            stopped = "final"
            break
        if stopped == "max_steps":
            open_items = "；".join(self.working.open_items()) or "无"
            reply = f"已达到单轮步数上限（{self.cfg.max_steps} 步），先停在这里。未完成：{open_items}"
        self.conv.add({"role": "assistant", "content": reply}, turn)

        try:
            start, end = self.conv.turn_span(turn)
            self.memory.write_back(text, sel.names, tool_log, reply,
                                   render_messages(self.conv.messages[start:end], 5000))
        except Exception as exc:  # 记忆写回失败不影响本轮结果
            self.trace.emit("error", {"where": "memory.write", "message": str(exc), "handled": True})

        tokens = self._usage_delta(before, self._usage_snapshot())
        latency = time.monotonic() - t_start
        self.trace.emit("turn.end", {"stopped": stopped, "steps": steps, "reply_chars": len(reply),
                                     "tokens": tokens, "tools": tool_log}, latency_ms=latency * 1000)
        return TurnResult(reply, turn, sel.names, tier, steps, stopped, tool_log, tokens, latency)
