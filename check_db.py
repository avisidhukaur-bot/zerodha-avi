import paramiko
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import os

# Load secrets
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

# Python script to run on VPS
vps_code = """
import sqlite3
conn = sqlite3.connect('/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_trader.db')
conn.row_factory = sqlite3.Row
print("--- LIVE BROKER POSITIONS ---")
import sys
sys.path.append('/root/BHARAT-SYSTEMS/ZERODHA-OS')
import db
from kite_executor import kite_executor
db.load_secrets()
kite_executor.ensure_logged_in()
positions = kite_executor.get_positions()
for pos in positions:
    symbol = pos.get('tradingsymbol')
    qty = pos.get('quantity')
    if '25000' in symbol or '25100' in symbol or '23000' in symbol:
        print("  Symbol: " + str(symbol) + " | Quantity: " + str(qty))
print("-" * 50)
"""

# Upload python code to a temp file and execute it
sftp = client.open_sftp()
with sftp.file("/tmp/vps_check_db.py", "w") as f:
    f.write(vps_code)
sftp.close()

print("--- Database Settings Table on VPS ---")
_, stdout, stderr = client.exec_command("python3 /tmp/vps_check_db.py")
print(stdout.read().decode(errors='replace').strip())
err = stderr.read().decode(errors='replace').strip()
if err:
    print("VPS ERROR:")
    print(err)
print("-" * 50)

# Clean up
client.exec_command("rm -f /tmp/vps_check_db.py")
client.close()
