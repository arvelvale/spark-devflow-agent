"""节点操作：同步代码、带隧道执行命令。凭据只从本地登录表读取，不打印。

  python scripts/node.py sync                 # 把仓库（含未提交改动，不含 var/ 与被忽略文件）同步到节点 ~/dgx-agent
  python scripts/node.py run "python3 -m agent doctor"
  python scripts/node.py run --no-tunnel "nvidia-smi"

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


def connect() -> paramiko.SSHClient:
    rows = list(openpyxl.load_workbook(ROOT / "登录信息表.xlsx", read_only=True, data_only=True).active.values)
    values = {str(r[0]): r[1] for r in rows if r[0] is not None}
    host, port = rows[3][1].rsplit(":", 1)
    if int(port) != 6006:
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


def run(cmd: str, tunnel: bool = True, cwd: str = REMOTE_DIR, timeout: int = 3600) -> int:
    client = connect()
    try:
        prefix = f"cd ~/{cwd} 2>/dev/null || cd ~; export PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8; "
        if tunnel:
            p = f"http://127.0.0.1:{open_tunnel(client)}"
            prefix += f"export https_proxy={p} http_proxy={p} no_proxy=127.0.0.1,localhost; "
        chan = client.get_transport().open_session()
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
            f"cd ~/{REMOTE_DIR} && tar xzf .sync.tar.gz && rm .sync.tar.gz && echo synced $(find . -path ./var -prune -o -type f -print | wc -l) files")
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
    args = p.parse_args()
    if args.cmd == "sync":
        sync()
        return 0
    return run(args.command, tunnel=not args.no_tunnel)


if __name__ == "__main__":
    sys.exit(main())
