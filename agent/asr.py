"""语音转文字：阶跃一次性识别接口（/audio/asr/sse，JSON + base64，SSE 返回文本）。

浏览器录音后在前端转成 16 kHz 单声道 WAV 再上传，这里只做转发。
2026-09-24 实测：stepaudio-2.5-asr 识别一句 8 秒中文约 0.7 s；字母编号会有偏差（"DAY-298" → "DA 298"）。
"""
from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request

from .config import Config

ASR_PATH = "/audio/asr/sse"
MAX_AUDIO_BYTES = 10 * 1024 * 1024
FORMATS = {"wav", "mp3", "ogg"}


class AsrError(Exception):
    pass


def transcribe(cfg: Config, audio: bytes, fmt: str = "wav", language: str = "zh") -> dict:
    """返回 {"text", "usage"}。失败抛 AsrError（给前端看的中文说明，不含密钥）。"""
    if not audio:
        raise AsrError("没有收到音频")
    if len(audio) > MAX_AUDIO_BYTES:
        raise AsrError("录音太长了，请控制在一分钟以内")
    if fmt not in FORMATS:
        raise AsrError(f"不支持的音频格式 {fmt}")
    ep = cfg.cloud
    if not ep.api_key:
        raise AsrError("未配置 STEPFUN_API_KEY")
    body = {"audio": {"data": base64.b64encode(audio).decode("ascii"), "input": {
        "transcription": {"language": language, "model": os.environ.get("AGENT_ASR_MODEL", "stepaudio-2.5-asr"),
                          "enable_itn": True},
        "format": {"type": fmt}}}}
    req = urllib.request.Request(
        ep.base_url.rstrip("/") + ASR_PATH, json.dumps(body).encode("utf-8"),
        {"Authorization": f"Bearer {ep.api_key}", "Content-Type": "application/json", "Accept": "text/event-stream"})
    handlers = [] if ep.use_proxy else [urllib.request.ProxyHandler({})]
    opener = urllib.request.build_opener(*handlers)
    text, usage = "", None
    try:
        with opener.open(req, timeout=60) as resp:
            for raw in resp:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:") or not line[5:].strip():
                    continue
                try:
                    obj = json.loads(line[5:])
                except json.JSONDecodeError:
                    continue
                if obj.get("text"):
                    text = obj["text"]
                if obj.get("usage"):
                    usage = obj["usage"]
    except urllib.error.HTTPError as exc:
        raise AsrError(f"语音识别失败（HTTP {exc.code}）")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise AsrError(f"语音识别服务连不上：{getattr(exc, 'reason', exc)}")
    return {"text": text.strip(), "usage": usage}
