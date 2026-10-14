import paramiko
import os
import json

secrets = {}
with open('secrets.txt', encoding='utf-8') as f:
    for l in f:
        if '=' in l and not l.startswith('#'):
            k, v = l.strip().split('=', 1)
            secrets[k.strip()] = v.strip()

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(secrets['VPS_IP'], username=secrets['VPS_USER'], password=secrets['VPS_PASSWORD'], timeout=10)

script = r'''
import sys
sys.path.insert(0, '/root/BHARAT-SYSTEMS/ZERODHA-OS')
import db
import json
from kite_executor import kite_executor

db.load_secrets()
kite_executor.load_session_from_db()

conn = db._conn()
cur = conn.cursor()
cur.execute("SELECT * FROM legs WHERE exit_time IS NULL OR exit_time = ''")
cols = [d[0] for d in cur.description]
rows = [dict(zip(cols, r)) for r in cur.fetchall()]
print("--- OPEN LEGS IN DB ---")
print(json.dumps(rows, indent=2, default=str))

cur.execute("SELECT * FROM legs ORDER BY leg_id DESC LIMIT 10")
cols = [d[0] for d in cur.description]
rows = [dict(zip(cols, r)) for r in cur.fetchall()]
print("\n--- RECENT LEGS (LAST 10) ---")
print(json.dumps(rows, indent=2, default=str))

cur.execute("SELECT * FROM trades ORDER BY trade_id DESC LIMIT 10")
cols = [d[0] for d in cur.description]
rows = [dict(zip(cols, r)) for r in cur.fetchall()]
print("\n--- RECENT TRADES (LAST 10) ---")
print(json.dumps(rows, indent=2, default=str))

print("\n--- ACTIVE BLOCKS ---")
cur.execute("SELECT * FROM blocks WHERE status='ACTIVE'")
cols = [d[0] for d in cur.description]
rows = [dict(zip(cols, r)) for r in cur.fetchall()]
print(json.dumps(rows, indent=2, default=str))
'''

sftp = c.open_sftp()
with sftp.file('/root/BHARAT-SYSTEMS/ZERODHA-OS/temp_check.py', 'w') as f:
    f.write(script)
sftp.close()

_, stdout, stderr = c.exec_command("python3 /root/BHARAT-SYSTEMS/ZERODHA-OS/temp_check.py")
print(stdout.read().decode('utf-8', errors='replace'))
err = stderr.read().decode('utf-8', errors='replace')
if err:
    print("STDERR:", err)

c.close()
