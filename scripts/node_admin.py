"""Use credentials from the local allocation sheet without logging them."""
import argparse
import base64
from pathlib import Path
import openpyxl
import paramiko

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('command')
parser.add_argument('--python-file')
args = parser.parse_args()
rows = list(openpyxl.load_workbook(ROOT / '登录信息表.xlsx', read_only=True, data_only=True).active.values)
values = {str(r[0]): r[1] for r in rows if r[0] is not None}
endpoint = rows[3][1]
host, port = endpoint.rsplit(':', 1)
if int(port) != 6006:
    raise RuntimeError('Expected assigned SSH port 6006')
client = paramiko.SSHClient()
client.load_system_host_keys()
known = ROOT / '.ssh_known_hosts'
if known.exists():
    client.load_host_keys(str(known))
class RecordAssignedHost(paramiko.MissingHostKeyPolicy):
    def missing_host_key(self, client, hostname, key):
        client.get_host_keys().add(hostname, key.get_name(), key)
        client.save_host_keys(str(known))
client.set_missing_host_key_policy(RecordAssignedHost())
try:
    client.connect(host, port=int(port), username=values['用户名'], password=values['密码'], timeout=20, auth_timeout=20, look_for_keys=False, allow_agent=False)
    command = args.command
    if args.python_file:
        payload = base64.b64encode(Path(args.python_file).read_bytes()).decode('ascii')
        command = 'python3 -c "import base64; exec(base64.b64decode(\'' + payload + '\'))"'
    stdin, stdout, stderr = client.exec_command(command, timeout=240)
    print(stdout.read().decode('utf-8', errors='replace'))
    print(stderr.read().decode('utf-8', errors='replace'))
    raise SystemExit(stdout.channel.recv_exit_status())
finally:
    client.close()
