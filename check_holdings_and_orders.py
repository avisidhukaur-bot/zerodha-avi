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

print("=== HOLDINGS IN KITE API ===")
holdings = kite.holdings()
print(f"Total Holdings Count: {len(holdings)}")
for h in holdings:
    print(f"  {h.get('tradingsymbol')} | Qty: {h.get('quantity')} | PnL: {h.get('pnl')}")

print("\\n=== ORDERS RAW JSON ===")
orders = kite.orders()
print(json.dumps(orders, indent=2, default=str))
"""

sftp = c.open_sftp()
with sftp.file("/tmp/check_holdings_and_orders.py", "w") as f:
    f.write(script)
sftp.close()

_, stdout, stderr = c.exec_command("/root/BHARAT-SYSTEMS/ZERODHA-OS/venv/bin/python3 /tmp/check_holdings_and_orders.py")
print(stdout.read().decode(errors='replace'))
err = stderr.read().decode(errors='replace')
if err:
    print("STDERR:", err)

c.close()
