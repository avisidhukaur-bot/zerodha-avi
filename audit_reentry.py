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

VPS_IP = secrets.get("VPS_IP", "5.75.250.104")
VPS_USER = secrets.get("VPS_USER", "root")
VPS_PASSWORD = secrets.get("VPS_PASSWORD", "")

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(VPS_IP, username=VPS_USER, password=VPS_PASSWORD, timeout=15)

remote_script = '''# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, '/root/BHARAT-SYSTEMS/ZERODHA-OS')
import db
import kite_executor as ke

print("=== 1. ALL ORDERS PLACED AFTER 15:10 IST ===")
try:
    ke.kite_executor.ensure_logged_in()
    kite = ke.kite_executor.kite
    if kite:
        orders = kite.orders()
        for o in orders:
            ts = str(o.get('order_timestamp'))
            if '15:1' in ts or '15:2' in ts or '15:0' in ts:
                print(f"[{ts}] {o.get('tradingsymbol')} | {o.get('transaction_type')} {o.get('quantity')} @ {o.get('average_price')} | Status: {o.get('status')} | Tag: {o.get('tag')} | Msg: {o.get('status_message')}")
except Exception as e:
    print(f"Orders Error: {e}")

print("\\n=== 2. LOGS AFTER 15:12 IST ===")
try:
    with open('/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_engine.log', 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()
        for l in lines[-40:]:
            print(l.strip())
except Exception as e:
    print(f"Log Error: {e}")

print("\\n=== 3. LIVE BROKER POSITIONS RIGHT NOW ===")
try:
    pos = ke.get_positions()
    for p in pos:
        if p.get('quantity', 0) != 0:
            print(f"- {p.get('tradingsymbol')} | Qty: {p.get('quantity')} | PnL: Rs {p.get('pnl', 0):,.2f}")
except Exception as e:
    print(f"Pos Error: {e}")
'''

sftp = client.open_sftp()
with sftp.file("/root/BHARAT-SYSTEMS/ZERODHA-OS/audit_reentry.py", "w") as f:
    f.write(remote_script)
sftp.close()

_, stdout, stderr = client.exec_command("python3 /root/BHARAT-SYSTEMS/ZERODHA-OS/audit_reentry.py")
print(stdout.read().decode(errors='replace'))
err = stderr.read().decode(errors='replace')
if err:
    print("STDERR:", err)
client.close()
