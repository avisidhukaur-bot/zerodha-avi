import paramiko
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

secrets = {}
with open('secrets.txt', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            secrets[k.strip()] = v.strip()

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(secrets['VPS_IP'], username=secrets['VPS_USER'], password=secrets['VPS_PASSWORD'], timeout=10)

py_script = """
import sqlite3
conn = sqlite3.connect('/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_trader.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print('=== ALL BLOCKS ===')
for b in cur.execute('SELECT block_id, block_number, anchor_unit_name, status, expiry_date, current_regime FROM blocks').fetchall():
    print(dict(b))

print('=== ALL STRIKES ===')
for s in cur.execute('SELECT strike_id, block_id, strike_price, option_type, leg_type, status, trade_state FROM strikes').fetchall():
    print(dict(s))

print('=== OS SETTINGS ===')
for st in cur.execute('SELECT key, value FROM settings WHERE key LIKE \"%os_%\"').fetchall():
    print(dict(st))

conn.close()
"""

stdin, stdout, stderr = client.exec_command(f"python3 -c \"{py_script}\"")
print(stdout.read().decode())
print(stderr.read().decode())
client.close()
