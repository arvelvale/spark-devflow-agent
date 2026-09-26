"""模型路由：本地为主，难题升级 step-5（2026-09-24 决策）。

判定顺序（先命中先生效）：
1. 命令行强制（--tier）
2. 技能 frontmatter 的 model: local / cloud
3. JEV：难度 Choice（simple / moderate / hard）+ 需要写代码 Noul
     P(hard) ≥ route_cloud                                  → cloud
     writes_code ≥ route_code 且 P(simple) < route_code_simple_max → cloud
     否则                                                    → local
4. JEV 不可用：本地
最后按可用性修正：本地主模型挂了 → 本地备用（Qwen）→ 云端；云端没 key → 本地。
轮内还有一次"失败升级"，在 kernel 里做。
"""
from __future__ import annotations

import time
import urllib.request
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .config import Config, Endpoint
from .decision import DecisionClient, DecisionUnavailable, choice, clip, noul

if TYPE_CHECKING:
    from .skills import Skill

DIFFICULTY = {
    "simple": "查询、汇总、格式化、按固定模板写文档，一两步就能完成",
    "moderate": "需要多步操作，但每一步都明确，不需要设计取舍",
    "hard": "需要编写或修改较多代码、跨多个文件推理、调试失败的测试，或需要做设计取舍",
}


@dataclass
class Route:
    tier: str               # local / cloud
    endpoint: Endpoint
    reason: str
    scores: dict = field(default_factory=dict)
    fallback: bool = False


class ModelRouter:
    def __init__(self, cfg: Config, decision: DecisionClient | None):
        self.cfg = cfg
        self.th = cfg.thresholds
        self.decision = decision
        self._health: dict[str, tuple[float, bool]] = {}

    def healthy(self, ep: Endpoint, ttl: float = 60.0) -> bool:
        """免 Key 的服务探活（GET /models，1.5 秒超时，结果缓存 ttl 秒）。要 Key 的只看 Key 在不在。"""
        if ep.needs_key:
            return ep.configured
        cached = self._health.get(ep.name)
        if cached and time.monotonic() - cached[0] < ttl:
            return cached[1]
        opener = urllib.request.build_opener(*([] if ep.use_proxy else [urllib.request.ProxyHandler({})]))
        try:
            with opener.open(ep.base_url.rstrip("/") + "/models", timeout=1.5) as resp:
                ok = resp.status == 200
        except Exception:
            ok = False
        self._health[ep.name] = (time.monotonic(), ok)
        return ok

    def mark_down(self, ep: Endpoint) -> None:
        self._health[ep.name] = (time.monotonic(), False)

    def local_endpoint(self) -> Endpoint | None:
        for ep in (self.cfg.local, self.cfg.backup):
            if self.healthy(ep):
                return ep
        return None

    def route(self, request: str, skills: list["Skill"], forced: str | None = None) -> Route:
        tier, reason, scores, fallback = self._decide(request, skills, forced)
        local = self.local_endpoint()
        cloud_ok = self.healthy(self.cfg.cloud)
        if tier == "local" and local is None:
            if cloud_ok:
                return Route("cloud", self.cfg.cloud, reason + "；本地模型不可用，改走云端", scores, True)
        if tier == "cloud" and not cloud_ok:
            if local is not None:
                return Route("local", local, reason + "；云端未配置，改走本地", scores, True)
        if tier == "local":
            ep = local or self.cfg.local
            if ep is not self.cfg.local:
                reason += "；本地主模型不可用，用备用模型"
                fallback = True
            return Route("local", ep, reason, scores, fallback)
        return Route("cloud", self.cfg.cloud, reason, scores, fallback)

    def _decide(self, request: str, skills: list["Skill"], forced: str | None) -> tuple[str, str, dict, bool]:
        if forced in ("local", "cloud"):
            return forced, "命令行指定", {}, False
        pinned = {s.model for s in skills} - {"auto"}
        if "cloud" in pinned:
            return "cloud", "技能要求云端模型", {}, False
        if "local" in pinned:
            return "local", "技能要求本地模型", {}, False
        if not (self.decision and self.decision.available):
            return "local", "JEV 不可用，默认本地", {}, True
        state = {"request": clip(request, 1000), "skills": [s.name for s in skills] or ["（无）"]}
        try:
            d = self.decision.ask(state, {
                "difficulty": choice("完成 `request` 的难度属于哪一档？", DIFFICULTY),
                "writes_code": noul("完成 `request` 是否需要编写或修改源代码（文档、日志、计划不算）？"),
            })
        except DecisionUnavailable:
            return "local", "JEV 不可用，默认本地", {}, True
        _, _, probs = d.choice("difficulty")
        code = d.noul("writes_code")
        scores = {"difficulty": {k: round(v, 3) for k, v in probs.items()}, "writes_code": round(code, 3)}
        if probs.get("hard", 0) >= self.th.route_cloud:
            return "cloud", f"难度高（P(hard)={probs['hard']:.2f}）", scores, False
        if code >= self.th.route_code and probs.get("simple", 0) < self.th.route_code_simple_max:
            return "cloud", f"需要写代码（{code:.2f}）且不是简单任务", scores, False
        return "local", "日常任务走本地", scores, False
