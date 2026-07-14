import paramiko
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import os

secrets = {}
secrets_path = os.path.join(os.path.dirname(__file__), "secrets.txt")
with open(secrets_path, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            secrets[k.strip()] = v.strip()

VPS_IP       = secrets.get("VPS_IP",       "5.75.250.104")
VPS_USER     = secrets.get("VPS_USER",     "root")
VPS_PASSWORD = secrets.get("VPS_PASSWORD", "")

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(VPS_IP, username=VPS_USER, password=VPS_PASSWORD, timeout=15)

print("--- VPS Engine Log (Today's Logs) ---")
_, stdout, stderr = client.exec_command("grep '2026-07-10' /root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_engine.log")
print(stdout.read().decode(errors='replace').strip())

print("\n--- systemctl status ---")
_, stdout, stderr = client.exec_command("systemctl status zerodha_engine.service || systemctl status zerodha_trader.service || pm2 status")
print(stdout.read().decode(errors='replace').strip())

client.close()
