"""Web 面板后端：标准库 HTTP + SSE，节点上零安装。

  python -m agent serve                          # 127.0.0.1:9000，经 SSH 隧道访问
  python -m agent serve --host 0.0.0.0           # 公网映射端口，必须带 token（默认就强制）

接口（除登录外都要登录 cookie）：
  POST   /api/login                        {token} → 设置 HttpOnly cookie
  GET    /api/status                       服务状态、技能清单
  GET    /api/sessions                     历史会话（var/runs 下全部，含命令行跑的）
  POST   /api/sessions                     {use_jev, tier} 新建在线会话
  GET    /api/sessions/<id>                轨迹 + 对话 + 工作记忆（在线会话还有待确认项）
  PATCH  /api/sessions/<id>                {tier} 改模型档位
  POST   /api/sessions/<id>/turn           {text, source} 开始一轮（后台执行，进度走 SSE）
  GET    /api/sessions/<id>/stream         SSE：trace / confirm / confirm_resolved / working / turn_done
  POST   /api/sessions/<id>/confirm        {id, approve} 回答写操作确认
  GET    /api/memory?status=active|pending
  POST   /api/memory/<id>/approve    DELETE /api/memory/<id>
  POST   /api/asr?format=wav               请求体是音频字节 → {text}

SSE 推送的 trace 事件就是决策轨迹原样（docs/接口/03-决策轨迹格式.md），面板和 A/B 读的是同一份数据。
"""
from __future__ import annotations

import hmac
import json
import mimetypes
import os
import queue
import re
import secrets
import sys
import threading
import time
import uuid
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .asr import AsrError, transcribe
from .config import ROOT, Config
from .gate import ConfirmRequest
from .kernel import Agent
from .memory import MemoryStore
from .router import ModelRouter
from .skills import load_skills
from .tools import build_registry

COOKIE = "dgx_session"
SESSION_ID = re.compile(r"^s-[\w-]{4,64}$")
CONFIRM_TIMEOUT = 600          # 秒；超时按拒绝处理
MAX_JSON = 1 * 1024 * 1024
MAX_AUDIO = 12 * 1024 * 1024
INTERNAL_PREFIX = "（系统提示）"  # kernel 注入的内部提示，不显示成用户消息
DIST = ROOT / "web" / "dist"


def _clip(text: str, n: int) -> str:
    return text if len(text) <= n else text[:n] + "…"


class LiveSession:
    """一个在线会话：一个 Agent + SSE 订阅者 + 等待网页回答的写操作确认。"""

    def __init__(self, cfg: Config, use_jev: bool, tier: str | None, factory=Agent):
        self.subs: list[queue.Queue] = []
        self.pending: dict[str, dict] = {}
        self.busy = False
        self.use_jev = use_jev
        self._lock = threading.Lock()
        self.agent = factory(cfg, confirm=self._confirm, use_jev=use_jev, force_tier=tier)
        self.agent.trace.subscribe(self._on_trace)

    @property
    def id(self) -> str:
        return self.agent.session

    def publish(self, kind: str, data) -> None:
        for q in list(self.subs):
            try:
                q.put_nowait((kind, data))
            except queue.Full:
                pass

    def _on_trace(self, ev: dict) -> None:
        self.publish("trace", ev)
        if ev["type"] in ("tool.call", "turn.end", "context.compress"):
            self.publish("working", self.agent.working.to_dict())

    def _confirm(self, req: ConfirmRequest) -> bool:
        cid = uuid.uuid4().hex[:10]
        done = threading.Event()
        item = {"id": cid, "turn": self.agent.trace.turn, "tool": req.tool, "permission": req.permission,
                "arguments": req.arguments, "reason": req.reason, "in_scope": req.appropriate,
                "collateral": req.collateral, "created": time.time()}
        self.pending[cid] = {"public": item, "done": done, "answer": False}
        self.publish("confirm", item)
        answered = done.wait(CONFIRM_TIMEOUT)
        answer = bool(self.pending.pop(cid, {}).get("answer")) if answered else False
        self.pending.pop(cid, None)
        self.publish("confirm_resolved", {"id": cid, "approve": answer, "timeout": not answered})
        return answer

    def answer(self, cid: str, approve: bool) -> bool:
        item = self.pending.get(cid)
        if not item:
            return False
        item["answer"] = approve
        item["done"].set()
        return True

    def start_turn(self, text: str, source: str) -> bool:
        with self._lock:
            if self.busy:
                return False
            self.busy = True

        def work():
            try:
                res = self.agent.run_turn(text, source)
                self.publish("turn_done", {"turn": res.turn, "reply": res.reply, "tier": res.tier, "steps": res.steps,
                                           "stopped": res.stopped, "tokens": res.tokens,
                                           "latency": round(res.latency, 2), "skills": res.skills})
            except Exception as exc:  # 内核异常也要让前端知道这一轮结束了
                self.publish("turn_done", {"turn": self.agent.trace.turn, "error": f"{type(exc).__name__}: {exc}"})
            finally:
                self.busy = False
                self.publish("working", self.agent.working.to_dict())

        threading.Thread(target=work, daemon=True, name=f"turn-{self.id}").start()
        return True


def load_history(data_dir: Path, sid: str) -> dict | None:
    run = data_dir / "runs" / sid
    trace = run / "trace.jsonl"
    if not SESSION_ID.match(sid) or not trace.exists():
        return None
    events = []
    for line in trace.read_text(encoding="utf-8").splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    messages = []
    archive = run / "archive.jsonl"
    if archive.exists():
        for line in archive.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("kind") != "msg":
                continue
            msg, turn = rec["payload"]["message"], rec["payload"]["turn"]
            content = msg.get("content") or ""
            if msg["role"] == "user" and not content.startswith(INTERNAL_PREFIX):
                messages.append({"turn": turn, "role": "user", "content": content})
            elif msg["role"] == "assistant" and content and not msg.get("tool_calls"):
                messages.append({"turn": turn, "role": "assistant", "content": content})
    return {"id": sid, "events": events, "messages": messages}


def list_history(data_dir: Path, live: dict[str, LiveSession], limit: int = 60) -> list[dict]:
    runs = data_dir / "runs"
    out = []
    if runs.exists():
        dirs = sorted((d for d in runs.iterdir() if d.is_dir() and SESSION_ID.match(d.name)),
                      key=lambda d: d.stat().st_mtime, reverse=True)[:limit]
        for d in dirs:
            title, turns = "", 0
            trace = d / "trace.jsonl"
            if trace.exists():
                with trace.open(encoding="utf-8") as fh:
                    for line in fh:
                        if '"turn.start"' not in line:
                            continue
                        turns += 1
                        if not title:
                            try:
                                title = json.loads(line)["data"].get("input", "")
                            except (json.JSONDecodeError, KeyError):
                                pass
            if turns == 0 and d.name not in live:
                continue  # 评估脚本等只建了目录没对话的会话，不列出来
            out.append({"id": d.name, "updated": d.stat().st_mtime, "turns": turns,
                        "title": _clip(title, 40) or ("新对话" if d.name in live else "（空会话）"), "live": d.name in live})
    for sid, s in live.items():  # 刚建、还没写轨迹的在线会话
        if not any(o["id"] == sid for o in out):
            out.insert(0, {"id": sid, "updated": time.time(), "turns": 0, "title": "新对话", "live": True})
    return out


class App:
    def __init__(self, cfg: Config, token: str, no_auth: bool = False):
        self.cfg = cfg
        self.token = token
        self.no_auth = no_auth  # 仅开发：只允许在回环地址上开启（serve() 里强制检查）
        self.cookies: set[str] = set()
        self.live: dict[str, LiveSession] = {}
        self.router = ModelRouter(cfg, None)
        self.memory = MemoryStore(cfg.data_dir / "memory.sqlite")
        self.agent_factory = Agent  # 测试里换成带假模型的工厂
        self._lock = threading.Lock()

    def status(self) -> dict:
        cfg = self.cfg
        reg = build_registry()
        skills, errors = load_skills(cfg.skills_dir, set(reg.names()))
        return {
            "services": {
                "local": {"ok": self.router.healthy(cfg.local), "model": cfg.local.model},
                "backup": {"ok": self.router.healthy(cfg.backup), "model": cfg.backup.model},
                "cloud": {"ok": cfg.cloud.configured, "model": cfg.cloud.model},
                "jev": {"ok": bool(cfg.jev_key), "model": cfg.jev_model},
                "linear": {"ok": bool(cfg.linear_key), "model": cfg.linear_project_name},
            },
            "workspace": cfg.workspace.name,
            "workspace_ready": (cfg.workspace / ".git").exists(),
            "skills": [{"name": s.name, "description": s.description, "model": s.model,
                        "writes": [t for t in s.allowed_tools if reg.get(t).permission.value != "read"]}
                       for s in skills],
            "skill_errors": errors,
        }

    def new_session(self, use_jev: bool, tier: str | None) -> LiveSession:
        s = LiveSession(self.cfg, use_jev, tier if tier in ("local", "cloud") else None, self.agent_factory)
        with self._lock:
            self.live[s.id] = s
        return s


def make_handler(app: App):
    class Handler(BaseHTTPRequestHandler):
        server_version = "dgx-agent"
        sys_version = ""

        def log_message(self, fmt, *args):  # 只记方法、路径、状态，不记 cookie 和请求体
            sys.stderr.write(f"[web] {self.command} {urlparse(self.path).path} {args[1] if len(args) > 1 else ''}\n")

        # ---------- 工具方法 ----------
        def _send(self, status: int, body: bytes, ctype: str, extra: dict | None = None) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _json(self, data, status: int = 200, extra: dict | None = None) -> None:
            self._send(status, json.dumps(data, ensure_ascii=False).encode("utf-8"),
                       "application/json; charset=utf-8", {"Cache-Control": "no-store", **(extra or {})})

        def _error(self, status: int, message: str) -> None:
            self._json({"error": message}, status)

        def _body(self, limit: int) -> bytes | None:
            length = int(self.headers.get("Content-Length") or 0)
            if length > limit:
                self._error(413, "请求体太大")
                return None
            return self.rfile.read(length) if length else b""

        def _json_body(self) -> dict | None:
            if "application/json" not in (self.headers.get("Content-Type") or ""):
                self._error(415, "需要 application/json")
                return None
            raw = self._body(MAX_JSON)
            if raw is None:
                return None
            try:
                data = json.loads(raw or b"{}")
            except json.JSONDecodeError:
                self._error(400, "请求体不是合法 JSON")
                return None
            if not isinstance(data, dict):
                self._error(400, "请求体必须是对象")
                return None
            return data

        def _authed(self) -> bool:
            if app.no_auth:
                return True
            cookie = SimpleCookie(self.headers.get("Cookie") or "")
            value = cookie[COOKIE].value if COOKIE in cookie else ""
            return bool(value) and any(hmac.compare_digest(value, c) for c in app.cookies)

        def _live(self, sid: str) -> LiveSession | None:
            s = app.live.get(sid)
            if s is None:
                self._error(404, "这个会话不在线（历史会话只能查看）")
            return s

        # ---------- 路由 ----------
        def do_GET(self):
            self._dispatch("GET")

        def do_HEAD(self):
            self._dispatch("GET")

        def do_POST(self):
            self._dispatch("POST")

        def do_PATCH(self):
            self._dispatch("PATCH")

        def do_DELETE(self):
            self._dispatch("DELETE")

        def _dispatch(self, method: str) -> None:
            url = urlparse(self.path)
            path = url.path
            try:
                if not path.startswith("/api/"):
                    return self._static(path) if method == "GET" else self._error(405, "不支持")
                if path == "/api/login" and method == "POST":
                    return self._login()
                if not self._authed():
                    return self._error(401, "请先登录")
                parts = path.strip("/").split("/")[1:]  # 去掉 api
                return self._api(method, parts, parse_qs(url.query))
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception as exc:  # 兜底：不把堆栈给前端
                sys.stderr.write(f"[web] 未处理异常 {type(exc).__name__}: {exc}\n")
                try:
                    self._error(500, "服务器内部错误")
                except OSError:
                    pass

        def _login(self) -> None:
            data = self._json_body()
            if data is None:
                return
            given = str(data.get("token", ""))
            if not hmac.compare_digest(given.encode(), app.token.encode()):
                time.sleep(1.0)  # 拖慢暴力尝试
                return self._error(401, "访问口令不对")
            value = secrets.token_urlsafe(32)
            app.cookies.add(value)
            self._json({"ok": True}, extra={
                "Set-Cookie": f"{COOKIE}={value}; HttpOnly; SameSite=Strict; Path=/; Max-Age={7 * 86400}"})

        def _api(self, method: str, parts: list[str], query: dict) -> None:
            head = parts[0] if parts else ""
            if head == "status" and method == "GET":
                return self._json(app.status())
            if head == "sessions":
                return self._sessions(method, parts[1:])
            if head == "memory":
                return self._memory(method, parts[1:], query)
            if head == "asr" and method == "POST":
                return self._asr(query)
            if head == "logout" and method == "POST":
                cookie = SimpleCookie(self.headers.get("Cookie") or "")
                if COOKIE in cookie:
                    app.cookies.discard(cookie[COOKIE].value)
                return self._json({"ok": True}, extra={"Set-Cookie": f"{COOKIE}=; Path=/; Max-Age=0"})
            return self._error(404, "没有这个接口")

        def _sessions(self, method: str, rest: list[str]) -> None:
            if not rest:
                if method == "GET":
                    return self._json(list_history(app.cfg.data_dir, app.live))
                if method == "POST":
                    data = self._json_body()
                    if data is None:
                        return
                    s = app.new_session(bool(data.get("use_jev", True)), data.get("tier"))
                    return self._json({"id": s.id}, 201)
                return self._error(405, "不支持")
            sid = rest[0]
            if not SESSION_ID.match(sid):
                return self._error(400, "会话编号不合法")
            action = rest[1] if len(rest) > 1 else ""
            if action == "" and method == "GET":
                hist = load_history(app.cfg.data_dir, sid) or {"id": sid, "events": [], "messages": []}
                s = app.live.get(sid)
                if s is None and not hist["events"]:
                    return self._error(404, "没有这个会话")
                hist.update({
                    "live": s is not None,
                    "busy": bool(s and s.busy),
                    "use_jev": s.use_jev if s else None,
                    "tier": (s.agent.force_tier or "auto") if s else None,
                    "working": s.agent.working.to_dict() if s else None,
                    "pending": [p["public"] for p in s.pending.values()] if s else [],
                })
                return self._json(hist)
            s = self._live(sid)
            if s is None:
                return
            if action == "" and method == "PATCH":
                data = self._json_body()
                if data is None:
                    return
                tier = data.get("tier")
                s.agent.force_tier = tier if tier in ("local", "cloud") else None
                return self._json({"tier": s.agent.force_tier or "auto"})
            if action == "turn" and method == "POST":
                data = self._json_body()
                if data is None:
                    return
                text = str(data.get("text", "")).strip()
                if not text:
                    return self._error(400, "说点什么再发送吧")
                if len(text) > 8000:
                    return self._error(413, "一次说的内容太长了")
                source = "voice" if data.get("source") == "voice" else "text"
                if not s.start_turn(text, source):
                    return self._error(409, "上一轮还在进行，稍等一下")
                return self._json({"ok": True}, 202)
            if action == "confirm" and method == "POST":
                data = self._json_body()
                if data is None:
                    return
                ok = s.answer(str(data.get("id", "")), bool(data.get("approve")))
                return self._json({"ok": ok}) if ok else self._error(404, "这个确认已经处理过或超时了")
            if action == "stream" and method == "GET":
                return self._stream(s)
            return self._error(404, "没有这个接口")

        def _stream(self, s: LiveSession) -> None:
            q: queue.Queue = queue.Queue(maxsize=2000)
            s.subs.append(q)
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
            try:
                self.wfile.write(b": connected\n\n")
                self.wfile.flush()
                while True:
                    try:
                        kind, data = q.get(timeout=15)
                        payload = json.dumps(data, ensure_ascii=False)
                        self.wfile.write(f"event: {kind}\ndata: {payload}\n\n".encode("utf-8"))
                    except queue.Empty:
                        self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            finally:
                if q in s.subs:
                    s.subs.remove(q)

        def _memory(self, method: str, rest: list[str], query: dict) -> None:
            if not rest and method == "GET":
                status = (query.get("status") or ["active"])[0]
                if status not in ("active", "pending"):
                    return self._error(400, "status 只能是 active 或 pending")
                items = app.memory.list(status)
                return self._json([{"id": m.id, "layer": m.layer, "kind": m.kind, "content": m.content,
                                    "privacy": m.privacy, "status": m.status, "created": m.created_at,
                                    "used": m.use_count} for m in items])
            if len(rest) == 2 and rest[1] == "approve" and method == "POST":
                return self._json({"ok": app.memory.set_status(rest[0], "active")})
            if len(rest) == 1 and method == "DELETE":
                return self._json({"ok": app.memory.delete(rest[0])})
            return self._error(404, "没有这个接口")

        def _asr(self, query: dict) -> None:
            fmt = (query.get("format") or ["wav"])[0]
            audio = self._body(MAX_AUDIO)
            if audio is None:
                return
            try:
                result = transcribe(app.cfg, audio, fmt)
            except AsrError as exc:
                return self._error(502, str(exc))
            return self._json(result)

        def _static(self, path: str) -> None:
            if not DIST.exists():
                return self._send(503, "面板还没构建：在 web/ 目录运行 npm run build".encode("utf-8"),
                                  "text/plain; charset=utf-8")
            rel = path.lstrip("/") or "index.html"
            target = (DIST / rel).resolve()
            if DIST.resolve() not in target.parents or not target.is_file():
                target = DIST / "index.html"  # 单页应用回退
            ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
                ctype += "; charset=utf-8"
            cache = "no-cache" if target.name == "index.html" else "public, max-age=31536000, immutable"
            extra = {"Cache-Control": cache}
            if target.name == "index.html":
                extra["Content-Security-Policy"] = (
                    "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
                    "media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'")
            self._send(200, target.read_bytes(), ctype, extra)

    return Handler


def serve(cfg: Config, host: str, port: int, token: str | None = None, no_auth: bool = False) -> None:
    if no_auth and host not in ("127.0.0.1", "localhost", "::1"):
        raise SystemExit("--dev-no-auth 只能配合回环地址使用；监听公网地址必须登录")
    token = token or os.environ.get("AGENT_WEB_TOKEN") or secrets.token_urlsafe(18)
    app = App(cfg, token, no_auth)
    httpd = ThreadingHTTPServer((host, port), make_handler(app))
    httpd.daemon_threads = True
    public = host not in ("127.0.0.1", "localhost", "::1")
    print(f"面板已启动：http://{'<公网地址>' if public else host}:{port}", flush=True)
    if no_auth:
        print("开发模式：免登录（只听回环地址，经 SSH 隧道访问）", flush=True)
    else:
        print(f"访问口令：{token}", flush=True)
    if public:
        print("注意：监听在非回环地址，任何知道地址的人都能打开登录页；口令不要外传，用完及时关闭。", flush=True)
    if not DIST.exists():
        print("提醒：web/dist 不存在，先在 web/ 目录 npm run build。", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
