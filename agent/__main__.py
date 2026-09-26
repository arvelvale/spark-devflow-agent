"""命令行入口。

  python -m agent chat                     交互式对话（默认）
  python -m agent run "把 DAY-5 拆一下"     单轮执行
  python -m agent skills                   列出并校验技能
  python -m agent doctor                   检查模型、JEV、Linear 连通性
  python -m agent memory [list|pending|approve ID|forget ID]
  python -m agent serve [--host 0.0.0.0] [--port 9000]   Web 面板

常用参数：--workspace 路径  --no-jev（基线臂）  --tier local|cloud  --yes（写操作自动确认）  --quiet
"""
from __future__ import annotations

import argparse
import json
import sys
import time

from .config import Config
from .gate import ConfirmRequest


def _utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


def _pct(v) -> str:
    return "—" if v is None else f"{v:.2f}"


def print_event(ev: dict) -> None:
    """把轨迹事件压成一行，演示时一眼看出每个决策。"""
    t, d = ev["type"], ev["data"]
    fb = " ⚠降级" if ev.get("fallback") else ""
    ms = f" {ev['latency_ms']}ms" if "latency_ms" in ev else ""
    if t == "skill.select":
        top = ""
        if "stage1" in d:
            probs = list(d["stage1"]["probabilities"].items())[:3]
            top = " 候选 " + ", ".join(f"{k}={v}" for k, v in probs)
        gate = f" 门控={d['gate']['value']}" if "gate" in d else ""
        line = f"[技能] {d['mode']} → {d['selected'] or '不用技能'}{gate}{top}{ms}{fb}"
    elif t == "route.model":
        line = f"[路由] {d['tier']}（{d['model']}）：{d['reason']}{fb}"
    elif t == "route.escalate":
        line = f"[升级] {d['from']} → {d['to']}：{d['reason']}"
    elif t == "memory.recall":
        if not d["candidates"]:
            return
        line = f"[记忆] 召回 {len(d['candidates'])} 条 → 原文 {d['full']} 摘要 {d['brief']}{fb}"
    elif t == "llm.call":
        calls = ", ".join(d["tool_calls"]) or "回复"
        u = ev.get("usage", {})
        line = f"[模型] {d['endpoint']} 第{d['step']}步 → {calls}（入 {u.get('input_tokens')} 出 {u.get('output_tokens')}）{ms}"
    elif t == "tool.gate":
        if d["permission"] == "read":
            return
        line = (f"[门控] {d['tool']}（{d['permission']}）→ {d['decision']}"
                f" 合理={_pct(d['appropriate'])} 越界={_pct(d.get('collateral'))}"
                + (f" 用户{'同意' if d['confirmed'] else '拒绝'}" if d["decision"] == "confirm" else "") + fb)
    elif t == "tool.call":
        line = f"[工具] {d['tool']} {'✓' if d['ok'] else '✗'}{ms}"
    elif t == "context.compress":
        if d.get("noop"):
            line = f"[压缩] 超预算（{d['before_tokens']} > {d['budget']}×水位）但近几轮受保护，本轮不压"
            print("  " + line, flush=True)
            return
        line = f"[压缩] {d['before_tokens']} → {d['after_tokens']} tokens，块：{[c['verdict'] for c in d['chunks']]}{fb}"
    elif t == "memory.write":
        kept = [i for i in d["items"] if i.get("layer") != "episodic"]
        if not kept:
            return
        line = f"[记忆写入] " + ", ".join(f"{i.get('kind', '')}:{i['status']}" for i in kept)
    elif t == "error":
        line = f"[错误] {d['where']}：{d['message'][:160]}"
    else:
        return
    print("  " + line, flush=True)


def confirm_interactive(req: ConfirmRequest) -> bool:
    print(f"\n  ⚠ 需要确认：{req.tool}（{req.permission}）— {req.reason}")
    for k, v in req.arguments.items():
        text = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
        print(f"      {k}: {text[:400]}{'…' if len(text) > 400 else ''}")
    try:
        return input("  执行吗？[y/N] ").strip().lower() in {"y", "yes", "是"}
    except EOFError:
        return False


def make_agent(args):
    from .kernel import Agent
    cfg = Config.load(args.workspace)
    confirm = (lambda req: True) if args.yes else confirm_interactive
    agent = Agent(cfg, confirm=confirm, use_jev=not args.no_jev, force_tier=args.tier)
    if not args.quiet:
        agent.trace.subscribe(print_event)
    for err in agent.skill_errors:
        print(f"  [技能加载失败] {err}", file=sys.stderr)
    return agent


def cmd_chat(args) -> int:
    agent = make_agent(args)
    print(f"会话 {agent.session}  工作区 {agent.cfg.workspace}  （输入 /exit 退出，/plan 看工作记忆）")
    while True:
        try:
            text = input("\n你> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not text:
            continue
        if text in {"/exit", "/quit"}:
            return 0
        if text == "/plan":
            print(agent.working.render())
            continue
        res = agent.run_turn(text)
        print(f"\n助手> {res.reply}\n  （{res.tier}，{res.steps} 步，{res.latency:.1f}s，tokens {res.tokens}）")


def cmd_run(args) -> int:
    agent = make_agent(args)
    res = agent.run_turn(args.text)
    print(f"\n{res.reply}\n\n（会话 {agent.session}，{res.tier}，{res.steps} 步，{res.latency:.1f}s，"
          f"tokens {res.tokens}，轨迹 var/runs/{agent.session}/trace.jsonl）")
    return 0 if res.stopped == "final" else 1


def cmd_skills(args) -> int:
    from .skills import load_skills
    from .tools import build_registry
    cfg = Config.load(args.workspace)
    reg = build_registry()
    skills, errors = load_skills(cfg.skills_dir, set(reg.names()))
    for s in skills:
        writes = [t for t in s.allowed_tools if reg.get(t).permission.value != "read"]
        print(f"✓ {s.name} v{s.version}  model={s.model}  写权限={writes or '无'}")
        print(f"    {s.description}")
    for e in errors:
        print(f"✗ {e}")
    print(f"\n{len(skills)} 个技能可用，{len(errors)} 个有问题")
    return 1 if errors else 0


def cmd_doctor(args) -> int:
    from .decision import DecisionClient, DecisionUnavailable, noul
    from .llm import LLMClient, LLMError
    from .router import ModelRouter
    from .tools.linear import LinearClient
    from .tools.base import ToolError
    cfg = Config.load(args.workspace)
    ok_all = True
    router = ModelRouter(cfg, None)
    for ep in (cfg.local, cfg.backup, cfg.cloud):
        if not ep.configured:
            print(f"✗ {ep.name:6} {ep.model}：未配置 {ep.api_key_env}")
            ok_all = False
            continue
        if not ep.api_key_env and not router.healthy(ep):
            print(f"✗ {ep.name:6} {ep.model}：{ep.base_url} 连不上")
            ok_all = False
            continue
        t0 = time.monotonic()
        try:
            r = LLMClient(ep).chat([{"role": "user", "content": "只回复两个字：在线"}], max_tokens=64, retries=0,
                                   thinking=False)
            print(f"✓ {ep.name:6} {r.model}：{time.monotonic() - t0:.1f}s 「{r.content[:20]}」")
        except LLMError as exc:
            print(f"✗ {ep.name:6} {ep.model}：{exc}")
            ok_all = False
    dc = DecisionClient(cfg.jev_url, cfg.jev_model, cfg.jev_key, mode="off", use_proxy=cfg.jev_use_proxy)
    try:
        d = dc.ask("今天天气不错", {"q": noul("`state` 是否在谈论天气？")})
        print(f"✓ jev    {d.model}：{d.latency:.1f}s noul={d.noul('q'):.2f}")
    except DecisionUnavailable as exc:
        print(f"✗ jev    {exc}")
        ok_all = False
    if cfg.linear_key:
        try:
            lc = LinearClient(cfg.linear_key, cfg.linear_team_key, cfg.linear_project_name,
                              use_proxy=cfg.linear_use_proxy)
            print(f"✓ linear 团队 {lc.team['name']}，项目「{cfg.linear_project_name}」")
        except ToolError as exc:
            print(f"✗ linear {exc}")
            ok_all = False
    else:
        print("- linear 未配置 LINEAR_API_KEY")
    ws = cfg.workspace
    print(f"{'✓' if (ws / '.git').exists() else '✗'} 工作区 {ws}"
          + ("" if (ws / ".git").exists() else "（不存在，先运行 python demo/seed/make_workspace.py）"))
    return 0 if ok_all else 1


def cmd_memory(args) -> int:
    from .memory import MemoryStore
    cfg = Config.load(args.workspace)
    store = MemoryStore(cfg.data_dir / "memory.sqlite")
    action = args.action or "list"
    if action in {"list", "pending"}:
        items = store.list("active" if action == "list" else "pending")
        for m in items:
            print(f"{m.id}  {m.layer:9} {m.kind:10} {m.privacy:9} {m.content[:100]}")
        print(f"共 {len(items)} 条")
    elif action == "approve" and args.id:
        print("已生效" if store.set_status(args.id, "active") else "没找到")
    elif action == "forget" and args.id:
        print("已删除" if store.delete(args.id) else "没找到")
    else:
        print("用法：memory [list|pending|approve ID|forget ID]")
        return 1
    return 0


def cmd_serve(args) -> int:
    from .server import serve
    serve(Config.load(args.workspace), args.host, args.port, no_auth=args.dev_no_auth, public_url=args.public_url)
    return 0


def main(argv: list[str] | None = None) -> int:
    _utf8()
    p = argparse.ArgumentParser(prog="python -m agent", description="DGX Spark 开发流 agent")
    p.add_argument("--workspace", help="被操作的仓库路径（默认 var/workspace/tinyledger）")
    p.add_argument("--no-jev", action="store_true", help="关闭 JEV 决策层（A/B 的基线臂）")
    p.add_argument("--tier", choices=["local", "cloud"], help="强制模型档位")
    p.add_argument("--yes", action="store_true", help="写操作自动确认（仅限沙盒演示）")
    p.add_argument("--quiet", action="store_true", help="不打印决策轨迹")
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("chat")
    r = sub.add_parser("run")
    r.add_argument("text")
    sub.add_parser("skills")
    sub.add_parser("doctor")
    m = sub.add_parser("memory")
    m.add_argument("action", nargs="?")
    m.add_argument("id", nargs="?")
    s = sub.add_parser("serve", help="启动 Web 面板（口令从 AGENT_WEB_TOKEN 读，没有就随机生成并打印）")
    s.add_argument("--host", default="127.0.0.1", help="默认只听回环地址；公网映射端口用 0.0.0.0")
    s.add_argument("--port", type=int, default=9000)
    s.add_argument("--dev-no-auth", action="store_true", help="开发用：免登录，只允许配合回环地址")
    s.add_argument("--public-url", help="启动提示里显示的公网地址（端口映射由组委会决定，进程自己推不出来）")
    args = p.parse_args(argv)
    handlers = {None: cmd_chat, "chat": cmd_chat, "run": cmd_run, "skills": cmd_skills,
                "doctor": cmd_doctor, "memory": cmd_memory, "serve": cmd_serve}
    return handlers[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
