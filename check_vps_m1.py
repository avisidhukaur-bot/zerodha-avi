import paramiko
import os
import sys
import json

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

secrets = {}
with open('secrets.txt', encoding='utf-8') as f:
    for line in f:
        if '=' in line and not line.startswith('#'):
            k, v = line.strip().split('=', 1)
            secrets[k.strip()] = v.strip()

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(secrets['VPS_IP'], username=secrets['VPS_USER'], password=secrets['VPS_PASSWORD'], timeout=15)

script = """
import sqlite3, json

conn = sqlite3.connect('/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_trader.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cur.execute('SELECT * FROM blocks ORDER BY block_id DESC')
blocks = [dict(r) for r in cur.fetchall()]
print('=== ALL BLOCKS ON VPS ===')
print(json.dumps(blocks, indent=2, default=str))

cur.execute('SELECT * FROM strikes ORDER BY strike_id DESC')
strikes = [dict(r) for r in cur.fetchall()]
print('\\n=== ALL STRIKES ON VPS ===')
print(json.dumps(strikes, indent=2, default=str))

cur.execute('SELECT * FROM settings WHERE key LIKE "%anchor%"')
settings = [dict(r) for r in cur.fetchall()]
print('\\n=== ANCHOR SETTINGS ===')
print(json.dumps(settings, indent=2, default=str))
"""

sftp = c.open_sftp()
with sftp.file('/tmp/check_all_blocks.py', 'w') as f:
    f.write(script)
sftp.close()

stdin, stdout, stderr = c.exec_command('python3 /tmp/check_all_blocks.py')
print(stdout.read().decode('utf-8', errors='replace'))
err = stderr.read().decode('utf-8', errors='replace')
if err:
    print("STDERR:", err)
c.close()
