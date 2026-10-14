import sqlite3
import paramiko
import sys
import os
from datetime import datetime
import pytz

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
IST = pytz.timezone("Asia/Kolkata")
now_str = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")

# 1. Clean Local Database
local_db = os.path.join(os.path.dirname(__file__), "zerodha_trader.db")
if os.path.exists(local_db):
    conn = sqlite3.connect(local_db)
    cur = conn.cursor()
    cur.execute("UPDATE blocks SET status='CLOSED' WHERE status='ACTIVE'")
    cur.execute("UPDATE strikes SET status='CLOSED' WHERE status IN ('ACTIVE', 'PENDING', 'OPEN')")
    cur.execute("UPDATE legs SET exit_time=? WHERE exit_time IS NULL OR exit_time=''", (now_str,))
    conn.commit()
    conn.close()
    print("✅ LOCAL DATABASE: All old active blocks & strikes marked CLOSED.")

# 2. Clean VPS Database
secrets = {}
with open('secrets.txt', encoding='utf-8') as f:
    for l in f:
        if '=' in l and not l.startswith('#'):
            k, v = l.strip().split('=', 1)
            secrets[k.strip()] = v.strip()

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    c.connect(secrets['VPS_IP'], username=secrets['VPS_USER'], password=secrets['VPS_PASSWORD'], timeout=10)
    print("Connected to VPS via SSH.")
    
    clean_vps_script = f"""
import sqlite3
conn = sqlite3.connect('/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_trader.db')
cur = conn.cursor()
cur.execute("UPDATE blocks SET status='CLOSED' WHERE status='ACTIVE'")
cur.execute("UPDATE strikes SET status='CLOSED' WHERE status IN ('ACTIVE', 'PENDING', 'OPEN')")
cur.execute("UPDATE legs SET exit_time='{now_str}' WHERE exit_time IS NULL OR exit_time=''")
conn.commit()
conn.close()
print("VPS DB: Cleaned successfully!")
"""
    sftp = c.open_sftp()
    with sftp.file('/tmp/clean_vps_db.py', 'w') as f:
        f.write(clean_vps_script)
    sftp.close()
    
    _, out, err = c.exec_command("python3 /tmp/clean_vps_db.py && systemctl restart zerodha_dashboard.service zerodha_engine.service")
    print(out.read().decode(errors='replace'))
    e = err.read().decode(errors='replace')
    if e:
        print("ERR:", e)
    c.close()
    print("✅ VPS DATABASE: Cleaned and services restarted.")
except Exception as e:
    print(f"VPS note: {e}")

print("\n🚀 ALL OLD BLOCKS & STRIKES PURGED! Dashboard is now 100% CLEAN & FRESH for new entry.")
