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

remote_script = """# -*- coding: utf-8 -*-
import sqlite3
import subprocess

db_path = '/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_trader.db'
conn = sqlite3.connect(db_path)
cur = conn.cursor()

print("=== 1. PURGING / DELETING ALL M2 BLOCKS & STRIKES FROM ENGINE ===")

# Find all blocks with unit M2 or block_id 30, 31 or block_number 2, 3
m2_blocks = cur.execute("SELECT block_id, block_number, anchor_unit_name, notes FROM blocks WHERE anchor_unit_name='M2' OR block_id IN (30, 31) OR block_number IN (2, 3) OR notes LIKE '%M2%'").fetchall()

for b in m2_blocks:
    b_id = b[0]
    print(f"Deleting M2 Block ID {b_id} (No: {b[1]}, Unit: {b[2]}, Notes: {b[3]})...")
    
    # Get strike IDs for this block
    s_ids = [r[0] for r in cur.execute("SELECT strike_id FROM strikes WHERE block_id=?", (b_id,)).fetchall()]
    for s_id in s_ids:
        cur.execute("DELETE FROM legs WHERE strike_id=?", (s_id,))
        cur.execute("DELETE FROM strikes WHERE strike_id=?", (s_id,))
        print(f"  -> Deleted Strike ID {s_id} and all its legs.")
    
    cur.execute("DELETE FROM blocks WHERE block_id=?", (b_id,))
    print(f"  -> Block {b_id} completely deleted from database.")

conn.commit()

# Verify remaining blocks
print("\\n=== 2. REMAINING ACTIVE BLOCKS IN ENGINE ===")
rem_blocks = cur.execute("SELECT block_id, block_number, anchor_unit_name, status, notes FROM blocks").fetchall()
for r in rem_blocks:
    print("Block:", r)

conn.close()

# Restart services so Streamlit UI cache and engine cache immediately reload cleanly
print("\\n=== 3. RESTARTING ENGINE & DASHBOARD SERVICES ===")
try:
    subprocess.run(["systemctl", "restart", "zerodha_engine.service"], check=False)
    subprocess.run(["systemctl", "restart", "zerodha_dashboard.service"], check=False)
    print("✅ Services restarted successfully!")
except Exception as e:
    print("Service restart note:", e)
"""

sftp = client.open_sftp()
with sftp.file("/root/BHARAT-SYSTEMS/ZERODHA-OS/purge_m2_complete.py", "w") as f:
    f.write(remote_script)
sftp.close()

_, stdout, stderr = client.exec_command("python3 /root/BHARAT-SYSTEMS/ZERODHA-OS/purge_m2_complete.py")
print(stdout.read().decode(errors='replace'))
err = stderr.read().decode(errors='replace')
if err:
    print("STDERR:", err)

client.close()
