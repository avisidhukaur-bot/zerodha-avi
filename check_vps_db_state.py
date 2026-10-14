import sqlite3
import paramiko
import sys
import json

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

secrets = {}
with open('secrets.txt', encoding='utf-8') as f:
    for l in f:
        if '=' in l and not l.startswith('#'):
            k, v = l.strip().split('=', 1)
            secrets[k.strip()] = v.strip()

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(secrets['VPS_IP'], username=secrets['VPS_USER'], password=secrets['VPS_PASSWORD'], timeout=10)

script = """
import sqlite3
import json

conn = sqlite3.connect('/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_trader.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=== VPS DB STRIKES FOR ACTIVE BLOCK ===")
for b in cur.execute("SELECT * FROM blocks WHERE status='ACTIVE'").fetchall():
    print(dict(b))
    for s in cur.execute("SELECT * FROM strikes WHERE block_id=?", (b['block_id'],)).fetchall():
        print("  Strike:", dict(s))
        for l in cur.execute("SELECT * FROM legs WHERE strike_id=?", (s['strike_id'],)).fetchall():
            print("    Leg:", dict(l))

conn.close()
"""

sftp = c.open_sftp()
with sftp.file('/tmp/check_vps_db_state.py', 'w') as f:
    f.write(script)
sftp.close()

_, stdout, stderr = c.exec_command("/root/BHARAT-SYSTEMS/ZERODHA-OS/venv/bin/python3 /tmp/check_vps_db_state.py")
print(stdout.read().decode(errors='replace'))
c.close()
