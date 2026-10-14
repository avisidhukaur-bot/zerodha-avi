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

print("=== FIND ALL DB FILES AND LOGS ON VPS ===")
print(run("find /root/BHARAT-SYSTEMS -name '*.db' -o -name '*.log'"))

print("\n=== SYSTEMCTL STATUS OF SERVICES ===")
print(run("systemctl status zerodha_engine zerodha_dashboard --no-pager"))

print("\n=== KITE POSITIONS & ORDERS DIRECT CHECK ===")
cmd = '''python3 -c "
import os, sys
sys.path.insert(0, '/root/BHARAT-SYSTEMS/ZERODHA-OS')
from kite_executor import kite_executor
kite_executor.ensure_logged_in()
k = kite_executor.kite
if k:
    print('ORDERS:')
    for o in k.orders():
        print(o.get('order_timestamp'), o.get('tradingsymbol'), o.get('transaction_type'), o.get('quantity'), o.get('average_price'), o.get('status'), o.get('status_message'))
    print('\nPOSITIONS:')
    for p in k.positions().get('net', []):
        print(p.get('tradingsymbol'), p.get('quantity'), p.get('buy_price'), p.get('sell_price'), p.get('last_price'), p.get('pnl'), p.get('m2m'))
"'''
print(run(cmd))
