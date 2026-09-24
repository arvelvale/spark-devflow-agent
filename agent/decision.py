"""JEV 决策客户端：所有结构化判断的唯一出入口（架构 3.1）。

- 同一 state 的问题一次请求发完（fan-out）
- 结果缓存：key = 模型 + state + questions 的哈希；replay 模式只读缓存，评估可离线重放
- 失败抛 DecisionUnavailable，调用方各自走降级链路（架构 3.4）
- JEV 的已知短板（不会算数、字面阅读、大 state 掉精度）由调用方在出题时绕开，见 docs/agent架构设计.md 1.3
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from .http import HttpError, post_json


class DecisionUnavailable(Exception):
    """JEV 不可用（无 key、网络不通、限流重试耗尽、replay 缓存未命中）。"""


@dataclass
class Decision:
    answers: dict
    model: str
    usage: dict
    latency: float
    cached: bool

    def noul(self, name: str) -> float:
        return float(self.answers[name]["noul"])

    def choice(self, name: str) -> tuple[str, float, dict[str, float]]:
        ans = self.answers[name]
        return ans["choice"], float(ans.get("confidence", 0.0)), {k: float(v) for k, v in ans["probabilities"].items()}

    def score(self, name: str) -> tuple[float, float, dict[int, float]]:
        ans = self.answers[name]
        probs = {int(k): float(v) for k, v in ans["probabilities"].items()}
        return float(ans["score"]), float(ans.get("confidence", 0.0)), probs


def noul(instructions: str) -> dict:
    return {"type": "noul", "instructions": instructions}


def choice(instructions: str, criteria: dict[str, str]) -> dict:
    return {"type": "choice", "instructions": instructions, "criteria": criteria}


def score(instructions: str, levels: list[str]) -> dict:
    return {"type": "score", "instructions": instructions, "criteria": levels}


@dataclass
class DecisionClient:
    url: str
    model: str
    api_key: str
    cache_path: Path | None = None
    mode: str = "live"          # live：缓存命中就用，否则真实调用 | replay：只读缓存 | off：不用缓存
    use_proxy: bool = True
    timeout: float = 30.0
    totals: dict = field(default_factory=lambda: {"calls": 0, "cached": 0, "input_tokens": 0, "output_tokens": 0, "failures": 0})

    def __post_init__(self) -> None:
        self._lock = threading.Lock()
        self._db: sqlite3.Connection | None = None
        if self.cache_path and self.mode != "off":
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._db = sqlite3.connect(str(self.cache_path), check_same_thread=False)
            self._db.execute("CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, response TEXT, created REAL)")

    @property
    def available(self) -> bool:
        return bool(self.api_key) or self.mode == "replay"

    def _key(self, state, questions: dict) -> str:
        blob = json.dumps({"m": self.model, "s": state, "q": questions}, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def ask(self, state, questions: dict[str, dict]) -> Decision:
        """一次请求问完一组问题。state 可以是字符串或对象（对象里用反引号路径引用字段）。"""
        key = self._key(state, questions)
        if self._db is not None:
            with self._lock:
                row = self._db.execute("SELECT response FROM cache WHERE key=?", (key,)).fetchone()
            if row:
                data = json.loads(row[0])
                self.totals["cached"] += 1
                return Decision(data["answers"], data.get("model", self.model), {}, 0.0, True)
        if self.mode == "replay":
            raise DecisionUnavailable("replay 模式下缓存未命中")
        if not self.api_key:
            raise DecisionUnavailable("未配置 TYPESAFE_API_KEY")
        body = {"model": self.model, "state": state, "questions": questions}
        try:
            data, latency = post_json(
                self.url, body, {"Authorization": f"Bearer {self.api_key}"},
                timeout=self.timeout, use_proxy=self.use_proxy, retries=3,
            )
        except HttpError as exc:
            self.totals["failures"] += 1
            raise DecisionUnavailable(f"JEV 调用失败：{exc}") from exc
        answers = data.get("answers")
        if not isinstance(answers, dict) or set(answers) != set(questions):
            self.totals["failures"] += 1
            raise DecisionUnavailable(f"JEV 返回缺少答案：{str(data)[:200]}")
        usage = data.get("usage") or {}
        self.totals["calls"] += 1
        self.totals["input_tokens"] += int(usage.get("input_tokens") or 0)
        self.totals["output_tokens"] += int(usage.get("output_tokens") or 0)
        if self._db is not None:
            with self._lock:
                self._db.execute(
                    "INSERT OR REPLACE INTO cache VALUES (?,?,?)",
                    (key, json.dumps({"answers": answers, "model": data.get("model")}, ensure_ascii=False), time.time()),
                )
                self._db.commit()
        return Decision(answers, data.get("model", self.model), usage, latency, False)


def clip(text: str, limit: int) -> str:
    """送进 JEV state 前截短（大 state 混无关内容会掉精度，见 jaggedness #5）。"""
    text = text or ""
    return text if len(text) <= limit else text[:limit] + f"…[共 {len(text)} 字]"
