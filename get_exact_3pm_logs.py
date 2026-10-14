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

remote_script = '''# -*- coding: utf-8 -*-
with open('/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_engine.log', 'r', encoding='utf-8', errors='replace') as f:
    lines = f.readlines()

print("=== LOG ENTRIES FROM 14:58 TO 15:05 ===")
for line in lines:
    if "2026-09-21 14:58" in line or "2026-09-21 14:59" in line or "2026-09-21 15:00" in line or "2026-09-21 15:01" in line or "2026-09-21 15:02" in line or "2026-09-21 15:03" in line or "2026-09-21 15:04" in line:
        print(line.strip())
'''

sftp = client.open_sftp()
with sftp.file("/root/BHARAT-SYSTEMS/ZERODHA-OS/get_exact_logs.py", "w") as f:
    f.write(remote_script)
sftp.close()

_, stdout, stderr = client.exec_command("python3 /root/BHARAT-SYSTEMS/ZERODHA-OS/get_exact_logs.py")
print(stdout.read().decode(errors='replace'))
client.close()
