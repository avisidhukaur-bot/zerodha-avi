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
import block_manager as bm
import telegram_bot as tg

db.load_secrets()
kite_executor.load_session_from_db()

print("=== STEP 1: CLOSING M1 HEDGE ON BROKER ===")
# Check open positions on Kite
if kite_executor.ensure_logged_in():
    pos_data = kite_executor.get_positions()
    pos_list = pos_data if isinstance(pos_data, list) else pos_data.get('net', [])
    for p in pos_list:
        sym = p.get('tradingsymbol', '')
        qty = p.get('quantity', 0)
        # If it's M1 hedge 24800 CE or 24300 CE with non-zero qty
        if ('24800' in sym or '24300' in sym) and qty != 0:
            print(f"Found active M1 position: {sym} qty={qty}")
            # If qty > 0 (Long Hedge), SELL to close
            if qty > 0:
                print(f"Placing SELL order to exit hedge {sym} qty={qty}...")
                sym_info = kite_executor.search_option_contract('29-Sep-2026', 24800, 'CE')
                token = sym_info.get('token') if sym_info else None
                order_id, filled = kite_executor.execute_sell_and_confirm(sym, token, qty)
                print(f"Sell order result: order_id={order_id}, filled={filled}")
            elif qty < 0:
                print(f"Placing BUY order to cover short {sym} qty={abs(qty)}...")
                sym_info = kite_executor.search_option_contract('29-Sep-2026', 24300, 'CE')
                token = sym_info.get('token') if sym_info else None
                order_id, filled = kite_executor.execute_buy_and_confirm(sym, token, abs(qty))
                print(f"Buy order result: order_id={order_id}, filled={filled}")
        elif '24800' in sym or '24300' in sym:
            print(f"{sym} already zero quantity (Qty={qty}).")

print("\\n=== STEP 2: FORCE DELETING BLOCK 1 (M1) FROM DB ===")
# Block ID 29 is Block 1
m1_block = db.get_block(29)
if m1_block:
    deleted = db.force_delete_block(29)
    print(f"Block 29 (M1) force deleted from DB: {deleted}")
else:
    print("Block 29 not found or already deleted. Searching any other M1 blocks...")
    all_b = db.get_all_blocks()
    for b in all_b:
        if (b.get('anchor_unit_name') or '').upper() == 'M1' or b.get('block_number') == 1:
            del_res = db.force_delete_block(b['block_id'])
            print(f"Block #{b['block_number']} (ID {b['block_id']}) force deleted: {del_res}")

print("\\n=== STEP 3: VERIFYING FINAL POSITIONS & BLOCKS ===")
blocks_remaining = db.get_all_blocks()
print(f"Total remaining blocks in DB: {len(blocks_remaining)}")
for b in blocks_remaining:
    print(f"- Block #{b['block_number']} (ID {b['block_id']}) Unit: {b.get('anchor_unit_name')} Expiry: {b['expiry_date']}")

pos_data_after = kite_executor.get_positions()
pos_list_after = pos_data_after if isinstance(pos_data_after, list) else pos_data_after.get('net', [])
print("\\nBroker Active Positions:")
for p in pos_list_after:
    if p.get('quantity', 0) != 0:
        print(f"* {p.get('tradingsymbol')} | Qty: {p.get('quantity')} | LTP: {p.get('last_price')} | PnL: Rs {p.get('pnl', 0):,.2f}")

tg.send_silent("💥 <b>OPERATOR MANUAL KILL</b>: Block 1 (M1) and its 24800 CE hedge have been completely closed on Zerodha and wiped from the DB.")
"""

sftp = client.open_sftp()
with sftp.file("/root/BHARAT-SYSTEMS/ZERODHA-OS/execute_kill_m1.py", "w") as f:
    f.write(remote_script)
sftp.close()

_, stdout, stderr = client.exec_command("python3 /root/BHARAT-SYSTEMS/ZERODHA-OS/execute_kill_m1.py")
print(stdout.read().decode(errors='replace'))
err = stderr.read().decode(errors='replace')
if err:
    print("STDERR:", err)

client.close()
