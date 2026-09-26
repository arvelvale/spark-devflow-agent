"""节点操作：同步代码、带隧道执行命令。凭据只从本地登录表读取，不打印。

  python scripts/node.py sync                 # 把仓库（含未提交改动，不含 var/ 与被忽略文件）同步到节点 ~/dgx-agent
  python scripts/node.py run "python3 -m agent doctor"
  python scripts/node.py run --no-tunnel "nvidia-smi"
  python scripts/node.py serve                # 在节点上起 Web 面板，并把本机 127.0.0.1:9000 转发过去

隧道：节点 127.0.0.1:<随机端口> → SSH → 本机代理（从 HTTPS_PROXY 读，默认 127.0.0.1:10090）。
节点直连不了境外（JEV、Linear），agent 进程靠 https_proxy 走这条隧道；StepFun 与本地模型直连不受影响。
只影响本次执行的命令，不改节点任何系统或网络配置。
"""
from __future__ import annotations

import argparse
import io
import os
import select
import shlex
import socket
import subprocess
import sys
import tarfile
import threading
from pathlib import Path
from urllib.parse import urlparse

import openpyxl
import paramiko

ROOT = Path(__file__).resolve().parents[1]
REMOTE_DIR = "dgx-agent"


def local_proxy() -> tuple[str, int]:
    raw = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or "http://127.0.0.1:10090"
    u = urlparse(raw)
    return u.hostname or "127.0.0.1", u.port or 10090


def _sheet() -> tuple[str, int, dict]:
    rows = list(openpyxl.load_workbook(ROOT / "登录信息表.xlsx", read_only=True, data_only=True).active.values)
    values = {str(r[0]): r[1] for r in rows if r[0] is not None}
    host, port = rows[3][1].rsplit(":", 1)
    return host, int(port), values


# 组委会的端口映射：节点内端口 → 公网端口前缀，后两位跟 SSH 公网端口一致（本节点 SSH 6006 → 服务 7006/8006/9006）
PUBLIC_PREFIX = {7000: 7000, 8888: 8000, 9000: 9000}


def public_url(node_port: int) -> str | None:
    """节点内端口在公网上的地址；这个端口没做映射就返回 None。"""
    host, ssh_port, _ = _sheet()
    if node_port not in PUBLIC_PREFIX:
        return None
    return f"http://{host}:{PUBLIC_PREFIX[node_port] + ssh_port % 100}"


def connect() -> paramiko.SSHClient:
    host, port, values = _sheet()
    if port != 6006:
        raise RuntimeError("登录表里的端口不是指定的 6006")
    client = paramiko.SSHClient()
    client.load_host_keys(str(ROOT / ".ssh_known_hosts"))  # 首次连接时由 node_admin.py 记录
    client.connect(host, port=6006, username=values["用户名"], password=values["密码"], timeout=20,
                   look_for_keys=False, allow_agent=False)
    client.get_transport().set_keepalive(30)
    return client


def _pipe(chan, target):
    try:
        sock = socket.create_connection(target, timeout=10)
    except OSError:
        chan.close()
        return
    try:
        while True:
            r, _, _ = select.select([sock, chan], [], [], 60)
            if not r:
                continue
            if sock in r:
                data = sock.recv(65536)
                if not data:
                    break
                chan.sendall(data)
            if chan in r:
                data = chan.recv(65536)
                if not data:
                    break
                sock.sendall(data)
    finally:
        chan.close()
        sock.close()


def open_tunnel(client: paramiko.SSHClient) -> int:
    """在节点回环地址上开反向转发，端口由节点分配（多个会话并行也不冲突），返回端口号。"""
    target = local_proxy()
    return client.get_transport().request_port_forward(
        "127.0.0.1", 0,
        lambda ch, origin, dest: threading.Thread(target=_pipe, args=(ch, target), daemon=True).start())


def forward_local(client: paramiko.SSHClient, local_port: int, remote_port: int) -> None:
    """本机 127.0.0.1:local_port → 节点 127.0.0.1:remote_port（相当于 ssh -L）。"""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", local_port))
    server.listen(32)

    def accept_loop():
        while True:
            try:
                sock, peer = server.accept()
                chan = client.get_transport().open_channel("direct-tcpip", ("127.0.0.1", remote_port), peer)
            except Exception:
                continue
            threading.Thread(target=_bridge, args=(sock, chan), daemon=True).start()

    threading.Thread(target=accept_loop, daemon=True).start()


def _bridge(sock: socket.socket, chan) -> None:
    try:
        while True:
            r, _, _ = select.select([sock, chan], [], [], 60)
            if sock in r:
                data = sock.recv(65536)
                if not data:
                    break
                chan.sendall(data)
            if chan in r:
                data = chan.recv(65536)
                if not data:
                    break
                sock.sendall(data)
    except OSError:
        pass
    finally:
        chan.close()
        sock.close()


def run(cmd: str, tunnel: bool = True, cwd: str = REMOTE_DIR, timeout: int = 3600,
        pty: bool = False, client: paramiko.SSHClient | None = None) -> int:
    client = client or connect()
    try:
        prefix = f"cd ~/{cwd} 2>/dev/null || cd ~; export PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8; "
        if tunnel:
            p = f"http://127.0.0.1:{open_tunnel(client)}"
            prefix += f"export https_proxy={p} http_proxy={p} no_proxy=127.0.0.1,localhost; "
        chan = client.get_transport().open_session()
        if pty:  # 有 pty 时 SSH 断开会给远端进程发 SIGHUP，服务跟着退出，不会遗留在节点上
            chan.get_pty()
        chan.set_combine_stderr(True)
        chan.settimeout(timeout)
        chan.exec_command(prefix + cmd)
        out = sys.stdout.buffer
        while True:
            data = chan.recv(4096)
            if not data:
                break
            out.write(data)
            out.flush()
        return chan.recv_exit_status()
    finally:
        client.close()


def sync() -> None:
    files = subprocess.run(["git", "ls-files", "-co", "--exclude-standard", "-z"], cwd=ROOT, capture_output=True,
                           check=True).stdout.decode("utf-8").split("\0")
    dist = ROOT / "web" / "dist"  # 前端构建产物不入库，但节点上要用（节点没有 node）
    if dist.exists():
        files += [p.relative_to(ROOT).as_posix() for p in dist.rglob("*") if p.is_file()]
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for rel in filter(None, files):
            path = ROOT / rel
            if path.is_file():
                tar.add(path, arcname=rel)
    client = connect()
    try:
        sftp = client.open_sftp()
        client.exec_command(f"mkdir -p ~/{REMOTE_DIR}")[1].channel.recv_exit_status()
        home = sftp.normalize(".")
        remote_tar = f"{home}/{REMOTE_DIR}/.sync.tar.gz"
        buf.seek(0)
        sftp.putfo(buf, remote_tar)
        env_file = ROOT / ".env"
        if env_file.exists():
            with sftp.open(f"{home}/{REMOTE_DIR}/.env", "w") as fh:
                fh.write(env_file.read_bytes())
            sftp.chmod(f"{home}/{REMOTE_DIR}/.env", 0o600)
        # 只覆盖同步的文件，不删节点上的 var/（记忆库、轨迹、工作区）
        _, out, err = client.exec_command(
            f"cd ~/{REMOTE_DIR} && rm -rf web/dist && tar xzf .sync.tar.gz && rm .sync.tar.gz && echo synced $(find . -path ./var -prune -o -type f -print | wc -l) files")
        print(out.read().decode().strip(), err.read().decode().strip())
    finally:
        client.close()


def main() -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("sync")
    r = sub.add_parser("run")
    r.add_argument("--no-tunnel", action="store_true")
    r.add_argument("command")
    sv = sub.add_parser("serve")
    sv.add_argument("--port", type=int, default=9000, help="节点上的端口")
    sv.add_argument("--local-port", type=int, default=9000, help="本机转发端口")
    sv.add_argument("--public", action="store_true", help="监听 0.0.0.0（公网映射端口，必须有口令）")
    sv.add_argument("--dev-no-auth", action="store_true", help="开发用免登录（不能和 --public 一起用）")
    args = p.parse_args()
    if args.cmd == "sync":
        sync()
        return 0
    if args.cmd == "serve":
        client = connect()
        forward_local(client, args.local_port, args.port)
        host = "0.0.0.0" if args.public else "127.0.0.1"
        print(f"本机访问：http://127.0.0.1:{args.local_port}（Ctrl+C 结束，节点上的服务随之退出）", flush=True)
        extra = " --dev-no-auth" if args.dev_no_auth else ""
        if args.public:
            url = public_url(args.port)
            if url:
                print(f"公网访问：{url}", flush=True)
                extra += f" --public-url {shlex.quote(url)}"
            else:
                print(f"提醒：节点端口 {args.port} 没有公网映射（只有 7000 / 8888 / 9000 有），外网打不开", flush=True)
        return run(f"python3 -m agent serve --host {host} --port {args.port}{extra}", tunnel=True, pty=True,
                   client=client)
    return run(args.command, tunnel=not args.no_tunnel)


if __name__ == "__main__":
    sys.exit(main())
