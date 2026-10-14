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

VPS_IP       = secrets.get("VPS_IP", "5.75.250.104")
VPS_USER     = secrets.get("VPS_USER", "root")
VPS_PASSWORD = secrets.get("VPS_PASSWORD", "")

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(VPS_IP, username=VPS_USER, password=VPS_PASSWORD, timeout=15)

def run(cmd):
    stdin, stdout, stderr = client.exec_command(cmd)
    return stdout.read().decode('utf-8', errors='replace')

print("=== ALL KITE ORDERS PLACED TODAY VIA VPS ===")
kite_cmd = '''python3 -c "
import sys
sys.path.append('/root/BHARAT-SYSTEMS/ZERODHA-OS')
from kite_executor import kite_executor
kite_executor.ensure_logged_in()
kite = kite_executor.kite
if kite:
    orders = kite.orders()
    print(f'Total orders today: {len(orders)}')
    for o in orders:
        print(f\"{o.get('order_timestamp')} | {o.get('tradingsymbol')} | {o.get('transaction_type')} | Qty: {o.get('quantity')} | AvgPrice: {o.get('average_price')} | Price: {o.get('price')} | Trigger: {o.get('trigger_price')} | Status: {o.get('status')} | Tag/Reason: {o.get('tag') or o.get('status_message')}\")
"'''
print(run(kite_cmd))

print("\n=== RECENT STRIKES IN VPS DB ===")
db_cmd = '''python3 -c "
import sqlite3
conn = sqlite3.connect('/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_trader.db')
conn.row_factory = sqlite3.Row
for r in conn.execute('SELECT * FROM strikes ORDER BY id DESC LIMIT 15').fetchall():
    print(dict(r))
"'''
print(run(db_cmd))

print("\n=== RECENT BLOCKS IN VPS DB ===")
db_cmd2 = '''python3 -c "
import sqlite3
conn = sqlite3.connect('/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_trader.db')
conn.row_factory = sqlite3.Row
for r in conn.execute('SELECT * FROM blocks ORDER BY id DESC LIMIT 5').fetchall():
    print(dict(r))
"'''
print(run(db_cmd2))

print("\n=== RECENT ENGINE LOGS WITH SL / EXIT / TRADE / M1 ===")
print(run("grep -E 'M1|SL|Exit|Trigger|22400|23|22' /root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_engine.log | tail -n 30"))
