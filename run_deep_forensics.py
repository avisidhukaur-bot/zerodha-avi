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
import sqlite3
import pprint

conn = sqlite3.connect('/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_trader.db')
conn.row_factory = sqlite3.Row

print("=== 1. ALL ACTIVE & RECENT BLOCKS ===")
blocks = conn.execute("SELECT * FROM blocks WHERE status != 'DELETED' ORDER BY block_id DESC LIMIT 10").fetchall()
for b in blocks:
    print(f"Block #{b['block_number']} (ID {b['block_id']}) | Unit: {b['anchor_unit_name']} | Expiry: {b['expiry_date']} | Status: {b['status']} | Regime: {b['current_regime']} | Anchor: {b['master_anchor_price']}")

print("\\n=== 2. ALL STRIKES IN ACTIVE BLOCKS ===")
strikes = conn.execute("""
    SELECT s.*, b.anchor_unit_name, b.block_number 
    FROM strikes s 
    JOIN blocks b ON s.block_id = b.block_id 
    WHERE b.status = 'ACTIVE' 
    ORDER BY s.block_id, s.strike_id
""").fetchall()
for s in strikes:
    print(f"Strike #{s['strike_id']} (Block {s['block_number']} [{s['anchor_unit_name']}]) | {s['strike_price']} {s['option_type']} {s['leg_type']} | Status: {s['status']} | TradeState: {s['trade_state']} | Lots: {s['lots']} | Anchor: {s['anchor_price']} | SL: {s['sl_price']} | PairedHedge: {s['hedge_strike_id']}")

print("\\n=== 3. ALL OPEN LEGS IN DB ===")
legs = conn.execute("""
    SELECT l.*, s.strike_price, s.option_type, s.leg_type, b.anchor_unit_name
    FROM legs l
    JOIN strikes s ON l.strike_id = s.strike_id
    JOIN blocks b ON s.block_id = b.block_id
    WHERE l.exit_time IS NULL OR l.exit_time = ''
""").fetchall()
for l in legs:
    print(f"Open Leg #{l['leg_id']} | Strike #{l['strike_id']} ({l['anchor_unit_name']} {l['strike_price']} {l['option_type']} {l['leg_type']}) | Entry: {l['entry_price']} | Order: {l['order_id']} | Time: {l['entry_time']}")

print("\\n=== 4. TODAY'S TRADES TABLE ENTRIES ===")
trades = conn.execute("SELECT * FROM trades WHERE created_at LIKE '2026-09-21%' ORDER BY trade_id ASC").fetchall()
for t in trades:
    print(f"Trade #{t['trade_id']} | Block {t['block_id']} | Strike {t['strike_id']} | Action: {t['action']} | Price: {t['price']} | Status: {t['order_status']} | Time: {t['created_at']} | Notes: {t['notes']}")

conn.close()
'''

sftp = client.open_sftp()
with sftp.file("/root/BHARAT-SYSTEMS/ZERODHA-OS/deep_forensic_check.py", "w") as f:
    f.write(remote_script)
sftp.close()

_, stdout, stderr = client.exec_command("python3 /root/BHARAT-SYSTEMS/ZERODHA-OS/deep_forensic_check.py")
print(stdout.read().decode(errors='replace'))
err = stderr.read().decode(errors='replace')
if err:
    print("STDERR:", err)
client.close()
