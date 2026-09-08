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

remote_script = """# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, '/root/BHARAT-SYSTEMS/ZERODHA-OS')
import kite_executor as ke
import db

print("=== 1. KITE AUTH & PROFILE ===")
kite = None
try:
    kite = ke.get_kite()
    if kite:
        profile = kite.profile()
        print("User ID: " + str(profile.get('user_id')))
        print("User Name: " + str(profile.get('user_name')))
        print("Email: " + str(profile.get('email')))
        print("Broker: " + str(profile.get('broker')))
        print("User Type: " + str(profile.get('user_type')))
        print("Status: VALID AND ACTIVE")
    else:
        print("Kite Auth: get_kite() returned None")
except Exception as e:
    print("Kite Auth Error: " + str(e))

print("\\n=== 2. MARGINS & FUNDS ===")
if kite:
    try:
        margins = kite.margins('equity')
        cash = margins.get('available', {}).get('cash', 0)
        net = margins.get('net', 0)
        utilised = margins.get('utilised', {}).get('debits', 0)
        print("Available Cash: Rs " + format(cash, ",.2f"))
        print("Net Margin: Rs " + format(net, ",.2f"))
        print("Utilised Margin: Rs " + format(utilised, ",.2f"))
    except Exception as e:
        print("Margin fetch error: " + str(e))

print("\\n=== 3. LIVE KITE POSITIONS ===")
if kite:
    try:
        pos = kite.positions()
        net_pos = pos.get('net', [])
        print("Total Net Positions: " + str(len(net_pos)))
        active_pos_count = 0
        for p in net_pos:
            qty = p.get('quantity', 0)
            if qty != 0:
                active_pos_count += 1
                sym = p.get('tradingsymbol')
                prod = p.get('product')
                m2m = p.get('m2m', 0)
                pnl = p.get('pnl', 0)
                print("- " + str(sym) + " | Qty: " + str(qty) + " | Product: " + str(prod) + " | M2M: Rs " + format(m2m, ",.2f") + " | PnL: Rs " + format(pnl, ",.2f"))
        if active_pos_count == 0:
            print("No open positions on broker.")
    except Exception as e:
        print("Positions fetch error: " + str(e))

print("\\n=== 4. DATABASE ACTIVE BLOCKS & STRIKES ===")
try:
    blocks = db.get_active_blocks()
    print("Active Blocks in DB: " + str(len(blocks)))
    for b in blocks:
        print("Block #" + str(b['block_number']) + " (ID " + str(b['block_id']) + ") | Expiry: " + str(b['expiry_date']) + " | Regime: " + str(b['current_regime']) + " | Master Anchor: " + str(b['master_anchor_price']))
        strikes = db.get_strikes_by_block(b['block_id'])
        for s in strikes:
            print("   -> Strike " + str(s['strike_price']) + " " + str(s['option_type']) + " (" + str(s['leg_type']) + ") | Status: " + str(s['status']) + " | Anchor: " + str(s['anchor_price']) + " | Lots: " + str(s['lots']))
except Exception as e:
    print("DB fetch error: " + str(e))

print("\\n=== 5. TODAY RECENT ORDERS ===")
if kite:
    try:
        orders = kite.orders()
        print("Total orders today: " + str(len(orders)))
        for o in orders[-5:]:
            ts = str(o.get('order_timestamp'))
            sym = str(o.get('tradingsymbol'))
            tx = str(o.get('transaction_type'))
            st = str(o.get('status'))
            msg = str(o.get('status_message', ''))
            print("- " + ts + " | " + sym + " | " + tx + " | " + st + " | " + msg)
    except Exception as e:
        print("Orders fetch error: " + str(e))
"""

sftp = client.open_sftp()
with sftp.file("/root/BHARAT-SYSTEMS/ZERODHA-OS/check_acc.py", "w") as f:
    f.write(remote_script)
sftp.close()

_, stdout, stderr = client.exec_command("python3 /root/BHARAT-SYSTEMS/ZERODHA-OS/check_acc.py")
print(stdout.read().decode(errors='replace'))
err = stderr.read().decode(errors='replace')
if err:
    print("STDERR:", err)

client.close()
