"""验证 SSH 反向隧道：节点 127.0.0.1:17890 → 本机代理，让节点上的进程按需访问境外 API。
只影响显式设置了代理变量的命令，不改节点任何系统/网络配置。"""
import os, select, socket, sys, threading
from pathlib import Path
import openpyxl, paramiko

ROOT = Path(__file__).resolve().parents[1]
LOCAL_PROXY = ("127.0.0.1", int(os.environ.get("LOCAL_PROXY_PORT", "10090")))
REMOTE_PORT = 17890
rows = list(openpyxl.load_workbook(ROOT / "登录信息表.xlsx", read_only=True, data_only=True).active.values)
values = {str(r[0]): r[1] for r in rows if r[0] is not None}
host, port = rows[3][1].rsplit(":", 1)
assert int(port) == 6006
client = paramiko.SSHClient()
client.load_host_keys(str(ROOT / ".ssh_known_hosts"))
client.connect(host, port=6006, username=values["用户名"], password=values["密码"], timeout=20, look_for_keys=False, allow_agent=False)

def pipe(chan):
    sock = socket.create_connection(LOCAL_PROXY)
    while True:
        r, _, _ = select.select([sock, chan], [], [])
        if sock in r:
            data = sock.recv(65536)
            if not data: break
            chan.sendall(data)
        if chan in r:
            data = chan.recv(65536)
            if not data: break
            sock.sendall(data)
    chan.close(); sock.close()

transport = client.get_transport()
transport.request_port_forward("127.0.0.1", REMOTE_PORT, lambda ch, o, d: threading.Thread(target=pipe, args=(ch,), daemon=True).start())
cmd = sys.argv[1] if len(sys.argv) > 1 else ""
_, out, err = client.exec_command(f"export https_proxy=http://127.0.0.1:{REMOTE_PORT} http_proxy=http://127.0.0.1:{REMOTE_PORT}; {cmd}", timeout=120)
print(out.read().decode("utf-8", "replace")); print(err.read().decode("utf-8", "replace"))
client.close()
