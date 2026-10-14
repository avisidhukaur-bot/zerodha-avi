import paramiko
import sys
import os

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

script = '''
import sqlite3
import json

conn = sqlite3.connect('/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_trader.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=== ACTIVE BLOCKS ===")
for r in cur.execute("SELECT * FROM blocks ORDER BY block_id DESC LIMIT 5").fetchall():
    print(dict(r))

print("\\n=== RECENT STRIKES ===")
for r in cur.execute("SELECT * FROM strikes ORDER BY strike_id DESC LIMIT 10").fetchall():
    print(dict(r))

print("\\n=== RECENT ORDERS ===")
for r in cur.execute("SELECT * FROM orders ORDER BY order_id DESC LIMIT 10").fetchall():
    print(dict(r))
'''

sftp = c.open_sftp()
f = sftp.file('/tmp/check_db_status.py', 'w')
f.write(script)
f.close()
sftp.close()

stdin, stdout, stderr = c.exec_command('python3 /tmp/check_db_status.py && journalctl -u zerodha_engine.service --since "30 minutes ago" --no-pager | tail -n 120')
print(stdout.read().decode('utf-8', errors='replace'))
print(stderr.read().decode('utf-8', errors='replace'))
c.close()
