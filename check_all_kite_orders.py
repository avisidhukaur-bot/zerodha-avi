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

remote_lines = [
    "import os, sys",
    "sys.path.insert(0, '/root/BHARAT-SYSTEMS/ZERODHA-OS')",
    "import kite_executor as ke",
    "ke.kite_executor.ensure_logged_in()",
    "kite = ke.kite_executor.kite",
    "if kite:",
    "    orders = kite.orders()",
    "    print(f'Total orders today: {len(orders)}')",
    "    for o in orders:",
    "        print(f\"ID: {o.get('order_id')} | Time: {o.get('order_timestamp')} | Symbol: {o.get('tradingsymbol')} | Type: {o.get('transaction_type')} | Qty: {o.get('quantity')} | Status: {o.get('status')} | Price: {o.get('average_price') or o.get('price')} | Tag: {o.get('tag')}\")",
    "else:",
    "    print('Kite client not initialized.')"
]

remote_content = "\n".join(remote_lines) + "\n"

sftp = c.open_sftp()
f = sftp.file('/tmp/all_orders.py', 'w')
f.write(remote_content)
f.close()
sftp.close()

stdin, stdout, stderr = c.exec_command("python3 /tmp/all_orders.py")
print("=== ZERODHA KITE ALL ORDERS TODAY ===")
print(stdout.read().decode('utf-8', errors='replace'))
print(stderr.read().decode('utf-8', errors='replace'))
c.close()
