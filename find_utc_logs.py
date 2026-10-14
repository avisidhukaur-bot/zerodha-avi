import paramiko
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

secrets = {}
secrets_path = os.path.join(os.path.dirname(__file__), "secrets.txt")
with open(secrets_path, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            secrets[k.strip()] = v.strip()

VPS_IP = secrets.get("VPS_IP", "5.75.250.104")
VPS_USER = secrets.get("VPS_USER", "root")
VPS_PASSWORD = secrets.get("VPS_PASSWORD", "")

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(VPS_IP, username=VPS_USER, password=VPS_PASSWORD, timeout=15)

def run(cmd, label):
    print(f"=== {label} ===")
    _, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode(errors='replace').strip()
    if out:
        print(out)
    else:
        print("(No output)")
    print()

run("journalctl -u zerodha_dashboard.service --since '09:40:00' -n 60 --no-pager", "DASHBOARD LOGS (UTC 09:40+)")
run("journalctl -u zerodha_engine.service --since '09:40:00' -n 60 --no-pager", "ENGINE LOGS (UTC 09:40+)")

client.close()
