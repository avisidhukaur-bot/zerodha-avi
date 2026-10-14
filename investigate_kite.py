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
import sys
sys.path.insert(0, '/root/BHARAT-SYSTEMS/ZERODHA-OS')
import db
from kite_executor import kite_executor
import json

db.load_secrets()
kite_executor.load_session_from_db()
kite = kite_executor.kite

print("=== 1. PROFILE ===")
prof = kite.profile()
print(json.dumps(prof, indent=2))

print("\\n=== 2. ALL ORDERS TODAY ===")
orders = kite.orders()
print(f"Total orders: {len(orders)}")
for o in orders:
    print(f"Order #{o.get('order_id')} | Time: {o.get('order_timestamp')} | Symbol: {o.get('tradingsymbol')} | Type: {o.get('transaction_type')} | Qty: {o.get('quantity')} | Status: {o.get('status')} | Product: {o.get('product')}")

print("\\n=== 3. POSITIONS (DAY) ===")
pos = kite.positions()
print("DAY POSITIONS:", json.dumps(pos.get('day', []), indent=2))

print("\\n=== 4. POSITIONS (NET) ===")
print("NET POSITIONS:", json.dumps(pos.get('net', []), indent=2))
"""

sftp = c.open_sftp()
with sftp.file("/tmp/investigate_kite.py", "w") as f:
    f.write(script)
sftp.close()

_, stdout, stderr = c.exec_command("/root/BHARAT-SYSTEMS/ZERODHA-OS/venv/bin/python3 /tmp/investigate_kite.py")
print(stdout.read().decode('utf-8', errors='replace'))
err = stderr.read().decode('utf-8', errors='replace')
if err:
    print("STDERR:", err)

c.close()
