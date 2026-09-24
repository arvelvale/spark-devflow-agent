"""OpenAI 兼容的对话客户端：本地 vLLM（Nemotron）、本地 Ollama（Qwen）、云端 StepFun（step-5）共用。"""
from __future__ import annotations

import json
import threading
import uuid
from dataclasses import dataclass, field

from .config import Endpoint
from .http import HttpError, post_json


class LLMError(Exception):
    """模型服务不可用或返回异常。kernel 据此决定是否切换模型。"""


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict
    raw_arguments: str
    parse_error: str | None = None


@dataclass
class ChatResult:
    content: str
    tool_calls: list[ToolCall]
    reasoning: str
    usage: dict
    model: str
    latency: float
    finish_reason: str
    endpoint: str

    def assistant_message(self) -> dict:
        """写回对话历史的 assistant 消息（不带推理过程，省上下文）。"""
        msg: dict = {"role": "assistant", "content": self.content or ""}
        if self.tool_calls:
            msg["tool_calls"] = [
                {"id": c.id, "type": "function", "function": {"name": c.name, "arguments": c.raw_arguments}}
                for c in self.tool_calls
            ]
        return msg


def _parse_tool_calls(raw_calls: list[dict]) -> list[ToolCall]:
    calls = []
    for raw in raw_calls or []:
        fn = raw.get("function") or {}
        raw_args = fn.get("arguments")
        if isinstance(raw_args, dict):  # 个别服务直接给对象
            raw_args = json.dumps(raw_args, ensure_ascii=False)
        raw_args = raw_args or "{}"
        try:
            args = json.loads(raw_args)
            error = None if isinstance(args, dict) else "参数必须是 JSON 对象"
            if error:
                args = {}
        except json.JSONDecodeError as exc:
            args, error = {}, f"参数不是合法 JSON：{exc}"
        calls.append(ToolCall(
            id=raw.get("id") or f"call_{uuid.uuid4().hex[:12]}",
            name=fn.get("name", ""),
            arguments=args,
            raw_arguments=raw_args,
            parse_error=error,
        ))
    return calls


@dataclass
class LLMClient:
    endpoint: Endpoint
    totals: dict = field(default_factory=lambda: {"calls": 0, "input_tokens": 0, "output_tokens": 0})

    def __post_init__(self) -> None:
        self._sem = threading.Semaphore(self.endpoint.max_concurrency)

    @property
    def name(self) -> str:
        return self.endpoint.name

    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        *,
        temperature: float = 0.2,
        max_tokens: int = 2048,
        retries: int = 2,
        thinking: bool = True,
    ) -> ChatResult:
        ep = self.endpoint
        if not ep.configured:
            raise LLMError(f"{ep.name} 未配置密钥（{ep.api_key_env}）")
        body: dict = {
            "model": ep.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **ep.extra,
        }
        if not thinking:
            body.update(ep.no_think)
        if tools:
            body["tools"] = tools
        headers = {"Authorization": f"Bearer {ep.api_key}"} if ep.api_key else {}
        with self._sem:
            try:
                data, latency = post_json(
                    ep.base_url.rstrip("/") + "/chat/completions", body, headers,
                    timeout=ep.timeout, use_proxy=ep.use_proxy, retries=retries,
                )
            except HttpError as exc:
                raise LLMError(f"{ep.name}（{ep.model}）调用失败：{exc}") from exc
        try:
            choice = data["choices"][0]
            msg = choice["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"{ep.name} 返回格式异常：{str(data)[:200]}") from exc
        usage = data.get("usage") or {}
        self.totals["calls"] += 1
        self.totals["input_tokens"] += int(usage.get("prompt_tokens") or 0)
        self.totals["output_tokens"] += int(usage.get("completion_tokens") or 0)
        return ChatResult(
            content=(msg.get("content") or "").strip(),
            tool_calls=_parse_tool_calls(msg.get("tool_calls") or []),
            reasoning=msg.get("reasoning_content") or msg.get("reasoning") or "",
            usage=usage,
            model=data.get("model", ep.model),
            latency=latency,
            finish_reason=choice.get("finish_reason") or "",
            endpoint=ep.name,
        )


def extract_json(text: str) -> dict | list | None:
    """从模型输出里取第一个完整 JSON 对象/数组（容忍 ```json 包裹和前后废话）。"""
    if not text:
        return None
    # 从先出现的那个括号开始解析：输出 [{...}] 时不能只拿到数组里的第一个对象
    pairs = sorted((("{", "}"), ("[", "]")), key=lambda p: (text.find(p[0]) == -1, text.find(p[0])))
    for opener, closer in pairs:
        start = text.find(opener)
        while start != -1:
            depth, in_str, escape = 0, False, False
            for i in range(start, len(text)):
                ch = text[i]
                if in_str:
                    if escape:
                        escape = False
                    elif ch == "\\":
                        escape = True
                    elif ch == '"':
                        in_str = False
                    continue
                if ch == '"':
                    in_str = True
                elif ch == opener:
                    depth += 1
                elif ch == closer:
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(text[start:i + 1])
                        except json.JSONDecodeError:
                            break
            start = text.find(opener, start + 1)
    return None
