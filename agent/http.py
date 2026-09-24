"""带退避重试的 JSON POST（只用标准库，节点上零安装）。

代理规则：use_proxy=False 时显式绕过所有代理（本地模型服务在 127.0.0.1，
不能被 https_proxy 带进隧道）；True 时按环境变量 https_proxy 走。
"""
from __future__ import annotations

import json
import random
import socket
import time
import urllib.error
import urllib.request

RETRY_STATUS = {429, 500, 502, 503, 504, 529}

_NO_PROXY_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
_ENV_PROXY_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler())


class HttpError(Exception):
    def __init__(self, status: int | None, message: str, body: str = ""):
        super().__init__(f"HTTP {status}: {message}" if status else message)
        self.status = status
        self.body = body

    @property
    def retryable(self) -> bool:
        return self.status is None or self.status in RETRY_STATUS


def _retry_after(err: urllib.error.HTTPError) -> float | None:
    raw = err.headers.get("Retry-After") if err.headers else None
    try:
        return float(raw) if raw else None
    except ValueError:
        return None


def post_json(
    url: str,
    body: dict,
    headers: dict[str, str] | None = None,
    *,
    timeout: float = 60.0,
    use_proxy: bool = False,
    retries: int = 3,
    backoff: float = 1.0,
) -> tuple[dict, float]:
    """POST JSON，返回 (响应, 最后一次尝试的耗时秒)。可重试错误按指数退避，尊重 Retry-After。"""
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    hdrs = {"Content-Type": "application/json", **(headers or {})}
    opener = _ENV_PROXY_OPENER if use_proxy else _NO_PROXY_OPENER
    last: HttpError | None = None
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, data=data, headers=hdrs, method="POST")
        start = time.monotonic()
        wait: float | None = None
        try:
            with opener.open(req, timeout=timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
                return payload, time.monotonic() - start
        except urllib.error.HTTPError as err:
            text = err.read().decode("utf-8", "replace")[:2000]
            last = HttpError(err.code, text[:300] or err.reason, text)
            wait = _retry_after(err)
        except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError) as err:
            reason = getattr(err, "reason", err)
            last = HttpError(None, f"连接失败：{reason}")
        except json.JSONDecodeError as err:
            last = HttpError(None, f"响应不是 JSON：{err}")
        if not last.retryable or attempt == retries:
            break
        delay = wait if wait is not None else backoff * (2 ** attempt)
        time.sleep(min(delay, 30.0) + random.uniform(0, 0.3))
    assert last is not None
    raise last
