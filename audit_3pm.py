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
from datetime import datetime
import pytz

IST = pytz.timezone("Asia/Kolkata")
print("=== 1. ORDERS PLACED TODAY AFTER 14:50 IST ===")
try:
    ke.kite_executor.ensure_logged_in()
    kite = ke.kite_executor.kite
    if kite:
        orders = kite.orders()
        for o in orders:
            ts = str(o.get('order_timestamp'))
            if '15:' in ts or '14:5' in ts or '14:4' in ts:
                print(f"[{ts}] {o.get('tradingsymbol')} | {o.get('transaction_type')} {o.get('quantity')} @ {o.get('average_price')} | Status: {o.get('status')} | Tag: {o.get('tag')} | Status Msg: {o.get('status_message')}")
except Exception as e:
    print(f"Orders Error: {e}")

print("\\n=== 2. TRADES LOGGED IN DB TODAY ===")
try:
    conn = db._conn()
    trades = conn.execute("SELECT * FROM trades ORDER BY trade_id DESC LIMIT 20").fetchall()
    for t in trades:
        print(f"Trade #{t['trade_id']} | Block {t['block_id']} | Strike {t['strike_id']} | {t['action']} | Price: {t['price']} | PnL: {t['pnl']} | Time: {t['created_at']} | Details: {t['notes']}")
    conn.close()
except Exception as e:
    print(f"DB Trades Error: {e}")

print("\\n=== 3. ENGINE LOGS AROUND 15:00 - 15:08 IST ===")
try:
    with open('/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_engine.log', 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()
        recent = [l for l in lines if '15:0' in l or '15:1' in l or '14:59' in l or '15:00' in l or '15:01' in l or '15:02' in l or '15:03' in l or '15:04' in l or '15:05' in l]
        for l in recent[-60:]:
            print(l.strip())
except Exception as e:
    print(f"Log Error: {e}")

print("\\n=== 4. CURRENT DB STATE OF ACTIVE BLOCKS & STRIKES ===")
try:
    blocks = db.get_all_blocks()
    for b in blocks:
        print(f"\\nBlock #{b['block_number']} [{b.get('anchor_unit_name')}] (ID {b['block_id']}) | Status: {b['status']} | Expiry: {b['expiry_date']} | Regime: {b['current_regime']} | Master Anchor: {b['master_anchor_price']}")
        strikes = db.get_strikes_by_block(b['block_id'])
        for s in strikes:
            print(f"   -> Strike {s['strike_id']}: {s['strike_price']} {s['option_type']} ({s['leg_type']}) | Status: {s['status']} | Anchor: {s['anchor_price']} | SL: {s.get('sl_trigger_price')} | Lots: {s['lots']} | Trade State: {s.get('trade_state')}")
except Exception as e:
    print(f"DB Blocks Error: {e}")
'''

sftp = client.open_sftp()
with sftp.file("/root/BHARAT-SYSTEMS/ZERODHA-OS/audit_3pm_trade.py", "w") as f:
    f.write(remote_script)
sftp.close()

_, stdout, stderr = client.exec_command("python3 /root/BHARAT-SYSTEMS/ZERODHA-OS/audit_3pm_trade.py")
print(stdout.read().decode(errors='replace'))
err = stderr.read().decode(errors='replace')
if err:
    print("STDERR:", err)
client.close()
