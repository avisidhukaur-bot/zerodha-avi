# -*- coding: utf-8 -*-
"""
deploy_3pulse_cadence.py
Deploys Gurjeet Mamu's 3-Pulse Cadence (11:00, 13:00, 14:57 IST) & ±15-pt Buffer upgrade
to HostAsia Linux VPS (5.75.250.104).
Performs bytecode purge and dual-service restart:
  - zerodha_engine.service
  - zerodha_dashboard.service (Port 9007)
"""
import paramiko
import sys
import time

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

secrets = {}
with open(r'c:\Users\Dell\Desktop\cheenna zerodha\secrets.txt', encoding='utf-8', errors='replace') as f:
    for line in f:
        line = line.strip()
        if '=' in line and not line.startswith('#'):
            k, v = line.split('=', 1)
            secrets[k.strip()] = v.strip()

print(f"Connecting to VPS at {secrets['VPS_IP']}...")
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(secrets['VPS_IP'], username=secrets['VPS_USER'], password=secrets['VPS_PASSWORD'], timeout=20)
print("Connected via SSH.")

sftp = client.open_sftp()
files_to_deploy = [
    "config.py",
    "block_manager.py",
    "telegram_bot.py",
    "main.py",
    "app.py",
    "test_3pulse_cadence_v8_3.py",
    "GEMINI.md",
    "memory.md"
]

remote_dir = "/root/BHARAT-SYSTEMS/ZERODHA-OS"

for fname in files_to_deploy:
    local_path = f"c:\\Users\\Dell\\Desktop\\cheenna zerodha\\{fname}"
    remote_path = f"{remote_dir}/{fname}"
    print(f"Uploading {fname} -> {remote_path}...")
    sftp.put(local_path, remote_path)

sftp.close()
print("All 8 files uploaded successfully via SFTP.")

# Clean pycache, run test suite on VPS, and restart dual services
cmd = """
cd /root/BHARAT-SYSTEMS/ZERODHA-OS
find . -name "*.pyc" -delete
find . -name "__pycache__" -type d -exec rm -rf {} +
python3 test_3pulse_cadence_v8_3.py
systemctl restart zerodha_engine.service
systemctl restart zerodha_dashboard.service
sleep 3
echo "=== zerodha_engine.service status ==="
systemctl is-active zerodha_engine.service
echo "=== zerodha_dashboard.service status ==="
systemctl is-active zerodha_dashboard.service
curl -s -o /dev/null -w "HTTP Response Code: %{http_code}\n" http://127.0.0.1:9007/
"""

stdin, stdout, stderr = client.exec_command(cmd)
out = stdout.read().decode('utf-8', errors='replace')
err = stderr.read().decode('utf-8', errors='replace')

print("\nVPS Execution Output:\n", out)
if err.strip():
    print("VPS Errors (if any):\n", err)

client.close()
print("Deployment and verification completed successfully.")
