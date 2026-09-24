"""测试夹具：假 JEV、假模型、临时工作区。单元测试不访问任何网络。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Callable

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent.config import Config, Endpoint, Thresholds  # noqa: E402
from agent.decision import Decision, DecisionUnavailable  # noqa: E402
from agent.llm import ChatResult, LLMError, ToolCall  # noqa: E402


class FakeDecision:
    """按问题名返回预设答案。responder(name, question, state) → 答案 dict；返回 None 用默认值。"""

    def __init__(self, responder: Callable | None = None, *, fail: bool = False, noul_default: float = 0.5):
        self.responder = responder
        self.fail = fail
        self.noul_default = noul_default
        self.available = True
        self.calls: list[tuple] = []
        self.totals = {"calls": 0, "input_tokens": 0, "output_tokens": 0}

    def ask(self, state, questions):
        self.calls.append((state, questions))
        if self.fail:
            raise DecisionUnavailable("测试：JEV 不可用")
        answers = {}
        for name, q in questions.items():
            ans = self.responder(name, q, state) if self.responder else None
            if ans is None:
                if q["type"] == "noul":
                    ans = {"type": "noul", "noul": self.noul_default}
                elif q["type"] == "choice":
                    keys = list(q["criteria"])
                    probs = {k: (1.0 if k == keys[0] else 0.0) for k in keys}
                    ans = {"type": "choice", "choice": keys[0], "confidence": 1.0, "probabilities": probs}
                else:
                    n = len(q["criteria"])
                    probs = {str(i): (1.0 if i == 1 else 0.0) for i in range(n)}
                    ans = {"type": "score", "score": 1.0, "confidence": 1.0, "probabilities": probs}
            answers[name] = ans
        self.totals["calls"] += 1
        self.totals["input_tokens"] += 100
        return Decision(answers, "jev-test", {"input_tokens": 100, "output_tokens": 10}, 0.01, False)


def noul_ans(v: float) -> dict:
    return {"type": "noul", "noul": v}


def choice_ans(probs: dict[str, float]) -> dict:
    top = max(probs, key=probs.get)
    return {"type": "choice", "choice": top, "confidence": probs[top], "probabilities": probs}


def score_ans(level: int, n: int = 3) -> dict:
    probs = {str(i): (1.0 if i == level else 0.0) for i in range(n)}
    return {"type": "score", "score": float(level), "confidence": 1.0, "probabilities": probs}


def reply(content: str = "", calls: list[tuple] | None = None, raw_args: dict | None = None) -> ChatResult:
    """造一条模型回复。calls = [(工具名, 参数 dict)]；raw_args 可指定某个工具的非法原始参数串。"""
    tcs = []
    for i, (name, args) in enumerate(calls or []):
        raw = (raw_args or {}).get(name)
        tcs.append(ToolCall(id=f"call_{i}_{name}", name=name, arguments=args if raw is None else {},
                            raw_arguments=raw or "{}", parse_error="参数不是合法 JSON" if raw else None))
    return ChatResult(content=content, tool_calls=tcs, reasoning="", usage={"prompt_tokens": 100, "completion_tokens": 20},
                      model="fake", latency=0.01, finish_reason="tool_calls" if tcs else "stop", endpoint="fake")


class FakeLLM:
    """按顺序吐出预设回复；元素是异常时抛出。记录每次收到的消息。"""

    def __init__(self, name: str, script: list | None = None, default: ChatResult | None = None):
        self.name = name
        self.script = list(script or [])
        self.default = default
        self.received: list[list[dict]] = []
        self.tools_seen: list[list[str]] = []
        self.totals = {"calls": 0, "input_tokens": 0, "output_tokens": 0}

    def chat(self, messages, tools=None, **kw):
        self.received.append(messages)
        self.tools_seen.append([t["function"]["name"] for t in tools or []])
        self.totals["calls"] += 1
        self.totals["input_tokens"] += 100
        if self.script:
            item = self.script.pop(0)
        elif self.default is not None:
            item = self.default
        else:
            raise LLMError(f"{self.name}: 脚本用完了")
        if isinstance(item, Exception):
            raise item
        return item


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True,
                          encoding="utf-8").stdout


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "README.md").write_text("# demo\n用法：demo add\n", encoding="utf-8")
    (ws / "AGENTS.md").write_text("# 约定\n1. 提交说明用中文\n", encoding="utf-8")
    (ws / "app.py").write_text("def total(xs):\n    return sum(xs)\n", encoding="utf-8")
    git(ws, "init", "-q", "-b", "main")
    git(ws, "-c", "user.name=t", "-c", "user.email=t@t", "add", "-A")
    git(ws, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "初始化")
    return ws


@pytest.fixture
def cfg(tmp_path: Path, workspace: Path) -> Config:
    vault = tmp_path / "vault"
    (vault / "会议纪要").mkdir(parents=True)
    (vault / "会议纪要" / "周会.md").write_text("# 周会\n- [ ] 修复精度\n", encoding="utf-8")
    return Config(
        local=Endpoint("local", "http://127.0.0.1:1/v1", "fake-local"),
        backup=Endpoint("backup", "http://127.0.0.1:2/v1", "fake-backup"),
        cloud=Endpoint("cloud", "http://127.0.0.1:3/v1", "fake-cloud"),
        jev_url="http://127.0.0.1:4", jev_model="jev-test", jev_use_proxy=False,
        linear_use_proxy=False, linear_team_key="DAY", linear_project_name="演示",
        data_dir=tmp_path / "var", skills_dir=ROOT / "skills", vault_dir=vault, workspace=workspace,
        thresholds=Thresholds(), memory_extract=False,
    )
