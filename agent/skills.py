"""技能：加载、校验、选择。文件格式契约见 docs/接口/01-技能文件格式.md。

选择有两种模式，对应 A/B 两臂：
- jev：两级 JEV（架构 3.3a，对标官方 skill_suggestion）
    第一级  Choice 在全部技能里宽排 + 3 个门控 Noul，gate < skill_gate → 不用技能
    第二级  前 k 个候选加载描述与正文开头，逐个问 fits；最高 fits < skill_fit → 全部拒绝；
            其余 fits ≥ skill_multi 的一起加载（组合技能）
- baseline：主模型看技能清单自己选（输出 JSON），也是 JEV 不可用时的降级
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from .decision import DecisionClient, DecisionUnavailable, choice, clip, noul
from .llm import LLMClient, LLMError, extract_json

if TYPE_CHECKING:
    from .config import Thresholds

NAME_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
MODEL_CHOICES = {"auto", "local", "cloud"}


class SkillFormatError(Exception):
    pass


@dataclass
class Skill:
    name: str
    description: str
    version: str
    allowed_tools: list[str]
    triggers: list[str]
    not_for: list[str]
    body: str
    path: Path
    model: str = "auto"
    argument_hint: str = ""
    tags: list[str] = field(default_factory=list)
    internal: bool = False

    @property
    def key(self) -> str:
        """JEV 选项名（下划线形式）。"""
        return self.name.replace("-", "_")

    def index_line(self) -> str:
        return f"- {self.name}：{self.description}"

    def head(self, n: int = 700) -> str:
        return clip(self.body, n)


def parse_skill(path: Path) -> Skill:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.S)
    if not m:
        raise SkillFormatError(f"{path}: 缺少 --- 包围的 frontmatter")
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError as exc:
        raise SkillFormatError(f"{path}: frontmatter 不是合法 YAML：{exc}")
    body = m.group(2).strip()
    problems = []
    name = str(meta.get("name", ""))
    if not NAME_RE.match(name):
        problems.append("name 必须是 kebab-case")
    if name != path.parent.name:
        problems.append(f"name（{name}）必须等于目录名（{path.parent.name}）")
    desc = " ".join(str(meta.get("description", "")).split())
    if not desc or len(desc) > 300:
        problems.append(f"description 必须非空且 ≤ 300 字（现在 {len(desc)} 字）")
    version = str(meta.get("version", ""))
    if not VERSION_RE.match(version):
        problems.append("version 必须是 x.y.z")
    model = str(meta.get("model", "auto"))
    if model not in MODEL_CHOICES:
        problems.append(f"model 只能是 {sorted(MODEL_CHOICES)}")
    tools = meta.get("allowed-tools")
    if not isinstance(tools, list):
        problems.append("allowed-tools 必须是列表（可以为空）")
        tools = []
    triggers = meta.get("triggers") or []
    not_for = meta.get("not-for") or []
    if not isinstance(triggers, list) or len(triggers) < 2:
        problems.append("triggers 至少 2 条")
    if not isinstance(not_for, list) or len(not_for) < 1:
        problems.append("not-for 至少 1 条")
    if not body:
        problems.append("正文为空")
    if problems:
        raise SkillFormatError(f"{path}: " + "；".join(problems))
    return Skill(
        name=name, description=desc, version=version, allowed_tools=[str(t) for t in tools],
        triggers=[str(t) for t in triggers], not_for=[str(t) for t in not_for], body=body, path=path,
        model=model, argument_hint=str(meta.get("argument-hint", "")),
        tags=[str(t) for t in meta.get("tags") or []], internal=bool(meta.get("internal", False)),
    )


def load_skills(skills_dir: Path, known_tools: set[str] | None = None) -> tuple[list[Skill], list[str]]:
    """返回 (合法技能, 错误列表)。单个技能坏了不影响其它技能加载。"""
    skills, errors = [], []
    for path in sorted(skills_dir.glob("*/SKILL.md")):
        try:
            s = parse_skill(path)
        except SkillFormatError as exc:
            errors.append(str(exc))
            continue
        unknown = [t for t in s.allowed_tools if known_tools is not None and t not in known_tools]
        if unknown:
            errors.append(f"{path}: allowed-tools 里有未注册的工具 {unknown}")
            continue
        skills.append(s)
    return skills, errors


@dataclass
class Selection:
    skills: list[Skill]
    mode: str                 # jev / baseline
    fallback: bool = False
    reason: str = ""
    detail: dict = field(default_factory=dict)
    usage: dict = field(default_factory=dict)
    latency: float = 0.0

    @property
    def names(self) -> list[str]:
        return [s.name for s in self.skills]


NONE_KEY = "none"
NONE_DESC = "以上技能都不适用：闲聊、概念解释、一般性问答，或请求不在任何技能的职责内"

BASELINE_PROMPT = """你是技能路由器。根据下面的技能清单，为用户请求选择 0 个或多个技能。
规则：只有技能职责直接覆盖请求的主要目标时才选；一般性问答、概念解释选空列表；确实需要多个技能配合才多选。
只输出 JSON：{{"skills": ["技能名", ...]}}

技能清单：
{roster}

最近对话：
{recent}

用户请求：{request}"""


class SkillSelector:
    def __init__(self, skills: list[Skill], thresholds: "Thresholds",
                 decision: DecisionClient | None, baseline_llm: LLMClient | None):
        self.skills = [s for s in skills if not s.internal]
        self.by_key = {s.key: s for s in self.skills}
        self.by_name = {s.name: s for s in self.skills}
        self.th = thresholds
        self.decision = decision
        self.baseline_llm = baseline_llm

    def select(self, request: str, recent: str = "", mode: str = "jev") -> Selection:
        if not self.skills:
            return Selection([], mode, reason="没有可用技能")
        if mode == "jev":
            if self.decision and self.decision.available:
                try:
                    return self._select_jev(request, recent)
                except DecisionUnavailable as exc:
                    sel = self._select_baseline(request, recent)
                    sel.fallback, sel.reason = True, f"JEV 不可用，降级为主模型自选：{exc}"
                    return sel
            sel = self._select_baseline(request, recent)
            sel.fallback, sel.reason = True, "未配置 JEV，降级为主模型自选"
            return sel
        return self._select_baseline(request, recent)

    # ---------- JEV 两级 ----------
    def _select_jev(self, request: str, recent: str) -> Selection:
        t0 = time.monotonic()
        state = {"request": clip(request, 1000), "recent": clip(recent, 1200) or "（无）"}
        criteria = {s.key: s.description for s in self.skills}
        criteria[NONE_KEY] = NONE_DESC
        q1 = {
            "skill": choice("`request` 是用户本轮的请求，`recent` 是最近的对话。哪个技能最适合处理这个请求？"
                            "没有技能适用时选 none。", criteria),
            "acts": noul("`request` 是否要求针对用户的仓库、文件、任务系统或笔记做具体的事"
                         "（读取后整理、生成文档、修改、同步状态），而不只是回答一个概念性问题？"),
            "procedure": noul("一位谨慎的资深工程师处理 `request` 时，是否会遵循团队既定的流程或模板"
                              "（例如拆任务规范、计划模板、日志规范、审查清单）？"),
            "prose": noul("不读取也不改动任何仓库、任务或笔记，只凭通用知识直接用文字回答，是否就能完全满足 `request`？"),
        }
        d1 = self.decision.ask(state, q1)
        top, conf, probs = d1.choice("skill")
        acts, proc, prose = d1.noul("acts"), d1.noul("procedure"), d1.noul("prose")
        gate = (acts + proc + (1 - prose)) / 3  # prose 是反向题
        usage = dict(d1.usage)
        detail: dict = {
            "stage1": {"top": top, "confidence": round(conf, 3),
                       "probabilities": {k: round(v, 3) for k, v in sorted(probs.items(), key=lambda x: -x[1])}},
            "gate": {"acts": round(acts, 3), "procedure": round(proc, 3), "prose": round(prose, 3),
                     "value": round(gate, 3), "threshold": self.th.skill_gate},
            "cached": d1.cached,  # 命中 JEV 结果缓存时耗时接近 0，面板据此标注
        }
        if gate < self.th.skill_gate:
            return Selection([], "jev", reason=f"门控值 {gate:.2f} < {self.th.skill_gate}，不需要技能",
                             detail=detail, usage=usage, latency=time.monotonic() - t0)
        p_none = probs.get(NONE_KEY, 0.0)
        if p_none >= self.th.skill_none:
            return Selection([], "jev", reason=f"第一级判定无技能适用（P(none)={p_none:.2f} ≥ {self.th.skill_none}）",
                             detail=detail, usage=usage, latency=time.monotonic() - t0)
        cands = [k for k, p in sorted(probs.items(), key=lambda x: -x[1])
                 if k != NONE_KEY and k in self.by_key and p >= 0.02][: self.th.skill_stage2_topk]
        if not cands:
            return Selection([], "jev", reason="第一级没有候选技能", detail=detail, usage=usage,
                             latency=time.monotonic() - t0)
        state2 = {"request": state["request"], "recent": state["recent"], "candidates": {
            k: {"description": self.by_key[k].description, "instructions": self.by_key[k].head(700)} for k in cands}}
        q2 = {f"fits_{k}": noul(f"`candidates.{k}` 描述的技能是否适合处理 `request`？"
                                f"只有当它的职责直接覆盖请求的主要目标时才回答是；只是沾边的回答否。") for k in cands}
        d2 = self.decision.ask(state2, q2)
        for k, v in d2.usage.items():
            usage[k] = usage.get(k, 0) + v
        fits = {k: d2.noul(f"fits_{k}") for k in cands}
        detail["cached"] = d1.cached and d2.cached
        detail["stage2"] = {k: round(v, 3) for k, v in fits.items()}
        best = max(fits, key=fits.get)
        if fits[best] < self.th.skill_fit:
            return Selection([], "jev", reason=f"最高 fits {fits[best]:.2f} < {self.th.skill_fit}，全部拒绝",
                             detail=detail, usage=usage, latency=time.monotonic() - t0)
        chosen = [best] + [k for k in cands if k != best and fits[k] >= self.th.skill_multi]
        return Selection([self.by_key[k] for k in chosen], "jev", reason="两级选择命中", detail=detail,
                         usage=usage, latency=time.monotonic() - t0)

    # ---------- 基线：主模型自选 ----------
    def _select_baseline(self, request: str, recent: str) -> Selection:
        t0 = time.monotonic()
        if self.baseline_llm is None:
            return Selection([], "baseline", fallback=True, reason="没有可用模型做技能选择")
        roster = "\n".join(s.index_line() for s in self.skills)
        prompt = BASELINE_PROMPT.format(roster=roster, recent=clip(recent, 1200) or "（无）", request=request)
        try:
            res = self.baseline_llm.chat([{"role": "user", "content": prompt}], temperature=0, max_tokens=512,
                                         thinking=False)
        except LLMError as exc:
            return Selection([], "baseline", fallback=True, reason=f"模型不可用：{exc}")
        data = extract_json(res.content)
        names = data.get("skills", []) if isinstance(data, dict) else []
        chosen = [self.by_name[n] for n in names if isinstance(n, str) and n in self.by_name]
        return Selection(chosen, "baseline", reason="主模型自选", detail={"raw": clip(res.content, 300)},
                         usage=res.usage, latency=time.monotonic() - t0)
