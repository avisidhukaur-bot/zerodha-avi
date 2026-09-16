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
import sqlite3

conn = sqlite3.connect('/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_trader.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=== DETAILED BLOCK STATUS ===")
blocks = cur.execute('SELECT * FROM blocks WHERE status="ACTIVE"').fetchall()
for b in blocks:
    print(f"Block ID: {b['block_id']} | No: {b['block_number']} | Unit: {b['anchor_unit_name']} | SideType: {b['side_type']} | Regime: {b['current_regime']} | Created: {b['created_at']}")
    strikes = cur.execute('SELECT * FROM strikes WHERE block_id=?', (b['block_id'],)).fetchall()
    for s in strikes:
        legs = cur.execute('SELECT * FROM legs WHERE strike_id=?', (s['strike_id'],)).fetchall()
        print(f"  -> Strike ID {s['strike_id']}: {s['strike_price']} {s['option_type']} ({s['leg_type']}) | Status: {s['status']} | Anchor: ₹{s['anchor_price']} | SL: ₹{s['sl_price']} | TradeState: {s['trade_state']}")
        for l in legs:
            print(f"      Leg {l['leg_id']}: Entry=₹{l['entry_price']} Exit=₹{l['exit_price']} EntryTime={l['entry_time']} ExitTime={l['exit_time']} PnL=₹{l['realized_pnl']}")
"""

sftp = client.open_sftp()
with sftp.file("/root/BHARAT-SYSTEMS/ZERODHA-OS/chk_detailed_audit.py", "w") as f:
    f.write(remote_script)
sftp.close()

_, stdout, stderr = client.exec_command("python3 /root/BHARAT-SYSTEMS/ZERODHA-OS/chk_detailed_audit.py")
print(stdout.read().decode(errors='replace'))
err = stderr.read().decode(errors='replace')
if err:
    print("STDERR:", err)

client.close()
