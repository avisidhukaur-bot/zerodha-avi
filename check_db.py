import paramiko
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Load secrets
secrets = {}
secrets_path = r"c:\Users\pc\Desktop\BHARAT-SYSTEMS\ZERODHA OS\secrets.txt"
with open(secrets_path, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            secrets[k.strip()] = v.strip()

VPS_IP       = secrets.get("VPS_IP",       "46.224.133.16")
VPS_USER     = secrets.get("VPS_USER",     "root")
VPS_PASSWORD = secrets.get("VPS_PASSWORD", "")

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(VPS_IP, username=VPS_USER, password=VPS_PASSWORD, timeout=15)

# Python script to run on VPS
vps_code = """
import sqlite3
conn = sqlite3.connect('/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_trader.db')
conn.row_factory = sqlite3.Row
print("--- SETTINGS ---")
cur = conn.execute('SELECT key, value FROM settings')
for r in cur.fetchall():
    print(f"{r['key']} = {r['value']}")
print("\\n--- BLOCKS ---")
cur = conn.execute('SELECT * FROM blocks')
for r in cur.fetchall():
    print(dict(r))
print("\\n--- STRIKES ---")
cur = conn.execute('SELECT * FROM strikes')
for r in cur.fetchall():
    print(dict(r))
conn.close()
"""

# Upload python code to a temp file and execute it
sftp = client.open_sftp()
with sftp.file("/tmp/vps_check_db.py", "w") as f:
    f.write(vps_code)
sftp.close()

print("--- Database Settings Table on VPS ---")
_, stdout, stderr = client.exec_command("python3 /tmp/vps_check_db.py")
print(stdout.read().decode(errors='replace').strip())
print("-" * 50)

# Clean up
client.exec_command("rm -f /tmp/vps_check_db.py")
client.close()
