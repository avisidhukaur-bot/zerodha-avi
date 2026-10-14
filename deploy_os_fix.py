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

sftp = client.open_sftp()
local_os = os.path.join(os.path.dirname(__file__), "os_engine.py")
sftp.put(local_os, "/root/BHARAT-SYSTEMS/ZERODHA-OS/os_engine.py")
sftp.close()
print("✅ os_engine.py uploaded to VPS.")

client.exec_command("systemctl restart zerodha_engine.service zerodha_dashboard.service")
print("✅ Services restarted successfully.")
client.close()
