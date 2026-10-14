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

remote_script = """
import sqlite3, sys, json
sys.path.insert(0, '/root/BHARAT-SYSTEMS/ZERODHA-OS')
from kite_executor import kite_executor

conn = sqlite3.connect('/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_trader.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cur.execute('SELECT * FROM strikes WHERE strike_id = 211')
row = cur.fetchone()
s = dict(row) if row else {}
print('=== DB STRIKE 211 ===')
print(json.dumps(s, indent=2))

kite_executor.ensure_logged_in()
k = kite_executor.kite
quote = k.quote(['NFO:NIFTY26OCT22700CE', 'NFO:NIFTY26OCT23200CE', 'NSE:NIFTY 50'])
print('\\n=== LIVE QUOTE ===')
for sym, q in quote.items():
    print(f"{sym} -> LTP: {q.get('last_price')} | High: {q.get('ohlc', {}).get('high')} | Low: {q.get('ohlc', {}).get('low')} | NetChange: {q.get('net_change')}")

pos = k.positions().get('net', [])
active = [p for p in pos if p.get('quantity') != 0]
print('\\n=== LIVE POSITIONS ===')
for p in active:
    print(f"{p.get('tradingsymbol')} | Qty: {p.get('quantity')} | SellPrice: {p.get('sell_price')} | BuyPrice: {p.get('buy_price')} | LTP: {p.get('last_price')} | PnL: Rs {p.get('pnl'):,.2f}")
"""

sftp = c.open_sftp()
with sftp.file('/tmp/check_strike_details.py', 'w') as f:
    f.write(remote_script)
sftp.close()

stdin, stdout, stderr = c.exec_command('python3 /tmp/check_strike_details.py')
print(stdout.read().decode('utf-8', errors='replace'))
err = stderr.read().decode('utf-8', errors='replace')
if err:
    print("STDERR:", err)
c.close()
