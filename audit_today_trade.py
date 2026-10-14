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

script = r'''
import sys
sys.path.insert(0, '/root/BHARAT-SYSTEMS/ZERODHA-OS')
import db
import json
from kite_executor import kite_executor

db.load_secrets()
kite_executor.load_session_from_db()

print("=== 1. RECENT ORDERS FROM KITE (TODAY 17-SEP) ===")
if kite_executor.ensure_logged_in():
    orders = kite_executor.get_orders() if hasattr(kite_executor, 'get_orders') else []
    for o in orders:
        ts = str(o.get('order_timestamp', ''))
        if '2026-09-17' in ts or True:
            print(f"Order ID: {o.get('order_id')} | Time: {ts} | Symbol: {o.get('tradingsymbol')} | Tx: {o.get('transaction_type')} | Type: {o.get('order_type')} | Price: {o.get('price')} | AvgPrice: {o.get('average_price')} | Qty: {o.get('quantity')} | Status: {o.get('status')} | Tag: {o.get('tag')}")

print("\n=== 2. LEGS ENTERED TODAY ===")
conn = db._conn()
cur = conn.cursor()
cur.execute("SELECT * FROM legs WHERE entry_time LIKE '2026-09-17%' ORDER BY leg_id ASC")
cols = [d[0] for d in cur.description]
legs = [dict(zip(cols, r)) for r in cur.fetchall()]
print(json.dumps(legs, indent=2, default=str))

print("\n=== 3. TRADES RECORDED TODAY ===")
cur.execute("SELECT * FROM trades WHERE timestamp LIKE '2026-09-17%' ORDER BY trade_id ASC")
cols = [d[0] for d in cur.description]
trades = [dict(zip(cols, r)) for r in cur.fetchall()]
print(json.dumps(trades, indent=2, default=str))

print("\n=== 4. ENGINE LOG AROUND 09:20 ===")
import subprocess
print(subprocess.getoutput("grep -n '2026-09-17 09:20' /root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_engine.log"))
'''

sftp = c.open_sftp()
with sftp.file('/root/BHARAT-SYSTEMS/ZERODHA-OS/temp_audit_trade.py', 'w') as f:
    f.write(script)
sftp.close()

stdin, stdout, stderr = c.exec_command("python3 /root/BHARAT-SYSTEMS/ZERODHA-OS/temp_audit_trade.py")
print(stdout.read().decode('utf-8', errors='replace'))
err = stderr.read().decode('utf-8', errors='replace')
if err:
    print("STDERR:", err)

# Cleanup
c.exec_command("rm -f /root/BHARAT-SYSTEMS/ZERODHA-OS/temp_audit_trade.py")
c.close()
