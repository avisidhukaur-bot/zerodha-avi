import paramiko
import os
import sys

# Fix terminal encoding issues on Windows
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
import pnl_engine
from datetime import datetime
import pytz

IST = pytz.timezone("Asia/Kolkata")
print("==================================================")
print(f"  ZERODHA OS LIVE SYSTEM AUDIT | {datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S IST')}")
print("==================================================")

print("\\n=== 1. KITE BROKER SESSION & PROFILE ===")
try:
    ke.kite_executor.ensure_logged_in()
    kite = ke.kite_executor.kite
    if kite and ke.kite_executor.is_logged_in:
        prof = kite.profile()
        print(f"User: {prof.get('user_name')} ({prof.get('user_id')}) | Broker: {prof.get('broker')} | Status: LOGGED IN & ACTIVE")
    else:
        print("Kite login status: NOT LOGGED IN")
except Exception as e:
    print(f"Kite Error: {e}")

print("\\n=== 2. MARGINS & LIVE FUNDS ===")
try:
    if ke.kite_executor.kite:
        m = ke.kite_executor.kite.margins('equity')
        avail = m.get('available', {}).get('cash', 0)
        net = m.get('net', 0)
        util = m.get('utilised', {}).get('debits', 0)
        print(f"Available Cash: Rs {avail:,.2f} | Net Margin: Rs {net:,.2f} | Utilised: Rs {util:,.2f}")
except Exception as e:
    print(f"Margin Error: {e}")

print("\\n=== 3. LIVE BROKER POSITIONS ===")
try:
    pos = ke.get_positions()
    net_pos = [p for p in pos if p.get('quantity', 0) != 0]
    print(f"Active Open Positions on Zerodha: {len(net_pos)}")
    for p in net_pos:
        print(f"  - {p.get('tradingsymbol')} | Qty: {p.get('quantity')} | Product: {p.get('product')} | PnL: Rs {p.get('pnl', 0):,.2f} | M2M: Rs {p.get('m2m', 0):,.2f}")
    if not net_pos:
        print("  (No open positions)")
except Exception as e:
    print(f"Positions Error: {e}")

print("\\n=== 4. DATABASE ACTIVE BLOCKS & STRIKES ===")
try:
    blocks = db.get_all_blocks(status_filter='ACTIVE')
    print(f"Active Blocks in DB: {len(blocks)}")
    for b in blocks:
        print(f"\\nBlock #{b['block_number']} [{b.get('anchor_unit_name', 'M?')}] (ID {b['block_id']}) | Expiry: {b['expiry_date']} | Regime: {b['current_regime']} | Master Anchor: Rs {b['master_anchor_price']}")
        strikes = db.get_strikes_by_block(b['block_id'])
        for s in strikes:
            if s['status'] != 'CLOSED':
                print(f"   -> Strike {s['strike_price']} {s['option_type']} ({s['leg_type']}) | Status: {s['status']} | Anchor: Rs {s['anchor_price']} | SL: Rs {s.get('sl_trigger_price', 0)} | Lots: {s['lots']}")
except Exception as e:
    print(f"DB Error: {e}")

print("\\n=== 5. ENGINE LIVE DATA & SPOT PRICE ===")
try:
    spot = ke.get_nifty_spot(force_refresh=True)
    print(f"NIFTY Spot LTP: Rs {spot:.2f}")
except Exception as e:
    print(f"Spot Error: {e}")

print("\\n=== 6. ENGINE HEARTBEAT & LAST LOGS ===")
try:
    with open('/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_engine.log', 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()
        print(f"Total Log Lines: {len(lines)}")
        print("Last 10 Log lines:")
        for line in lines[-10:]:
            print("  " + line.strip())
except Exception as e:
    print(f"Log Read Error: {e}")
'''

sftp = client.open_sftp()
with sftp.file("/root/BHARAT-SYSTEMS/ZERODHA-OS/check_full_status.py", "w") as f:
    f.write(remote_script)
sftp.close()

_, stdout, stderr = client.exec_command("python3 /root/BHARAT-SYSTEMS/ZERODHA-OS/check_full_status.py")
print(stdout.read().decode(errors='replace'))
err = stderr.read().decode(errors='replace')
if err:
    print("STDERR:", err)
client.close()
