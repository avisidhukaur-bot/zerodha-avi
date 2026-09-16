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

remote_script = """# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, '/root/BHARAT-SYSTEMS/ZERODHA-OS')
import db
from kite_executor import kite_executor
import config as cfg

db.load_secrets()
kite_executor.load_session_from_db()
if kite_executor.ensure_logged_in():
    pos_data = kite_executor.get_positions()
    pos_list = pos_data if isinstance(pos_data, list) else pos_data.get('net', [])
    print("=== ALL NET POSITIONS (INCLUDING QTY 0) ===")
    for p in pos_list:
        print(f"- {p.get('tradingsymbol')} | NetQty: {p.get('quantity')} | BuyQty: {p.get('buy_quantity')} | SellQty: {p.get('sell_quantity')} | BuyAvg: {p.get('buy_price')} | SellAvg: {p.get('sell_price')} | LTP: {p.get('last_price')} | PnL: Rs {p.get('pnl', 0):,.2f}")

    print("\\n=== KITE ORDERS TODAY ===")
    orders = kite_executor.get_orders() if hasattr(kite_executor, 'get_orders') else []
    for o in orders:
        print(f"- {o.get('order_timestamp')} | {o.get('tradingsymbol')} | {o.get('transaction_type')} | Qty: {o.get('quantity')} | Price: {o.get('price')} | Status: {o.get('status')} | Reason: {o.get('status_message')}")

    print("\\n=== SPOT LTP ===")
    ltps = kite_executor.get_ltp(["NSE:NIFTY 50", "NFO:NIFTY26SEP24300CE", "NFO:NIFTY26SEP24800CE"]) if hasattr(kite_executor, 'get_ltp') else {}
    print(f"LTP Quotes: {ltps}")
"""

sftp = client.open_sftp()
with sftp.file("/root/BHARAT-SYSTEMS/ZERODHA-OS/check_status_custom.py", "w") as f:
    f.write(remote_script)
sftp.close()

_, stdout, stderr = client.exec_command("python3 /root/BHARAT-SYSTEMS/ZERODHA-OS/check_status_custom.py")
print(stdout.read().decode(errors='replace'))
err = stderr.read().decode(errors='replace')
if err:
    print("STDERR:", err)

client.close()
