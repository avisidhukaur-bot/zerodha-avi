import paramiko
import os
import json

secrets = {}
with open('secrets.txt', encoding='utf-8') as f:
    for l in f:
        if '=' in l and not l.startswith('#'):
            k, v = l.strip().split('=', 1)
            secrets[k.strip()] = v.strip()

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(secrets['VPS_IP'], username=secrets['VPS_USER'], password=secrets['VPS_PASSWORD'], timeout=10)

script = r'''
import sys
sys.path.insert(0, '/root/BHARAT-SYSTEMS/ZERODHA-OS')
import db
import pnl_engine as pe
from kite_executor import kite_executor

db.load_secrets()
kite_executor.load_session_from_db()

print("--- 1. PNL ENGINE FUNCTIONS ---")
print([f for f in dir(pe) if not f.startswith('_')])

print("\n--- 2. ACTIVE BLOCKS & STRIKES IN DB ---")
blocks = db.get_all_blocks()
for b in blocks:
    if b.get('status') == 'ACTIVE':
        print(f"Block #{b['block_number']} ID:{b['block_id']} Unit:{b.get('anchor_unit_name')} Status:{b.get('status')} Regime:{b.get('current_regime')}")
        strikes = db.get_strikes_by_block(b['block_id'])
        for s in strikes:
            ltp = pe.fetch_ltp(s) if hasattr(pe, 'fetch_ltp') else None
            print(f"  Strike {s['strike_id']} | {s['strike_price']} {s['option_type']} ({s['leg_type']}) | Status: {s['status']} | State: {s.get('trade_state')} | Anchor: {s['anchor_price']} | SL_Price: {s.get('sl_price')} | LTP: {ltp}")

print("\n--- 3. KITE LIVE POSITIONS ---")
if kite_executor.ensure_logged_in():
    pos = kite_executor.get_positions()
    net = pos.get('net', []) if isinstance(pos, dict) else pos
    for p in net:
        if p.get('quantity') != 0:
            print(f"  {p.get('tradingsymbol')}: Qty={p.get('quantity')}, BuyAvg={p.get('buy_price')}, SellAvg={p.get('sell_price')}, LTP={p.get('last_price')}, MTM={p.get('m2m')}, PnL={p.get('pnl')}")

print("\n--- 4. DASHBOARD SERVICE JOURNAL LOGS (LAST 20) ---")
import subprocess
print(subprocess.getoutput("journalctl -u zerodha_dashboard.service -n 20 --no-pager"))
'''

sftp = c.open_sftp()
with sftp.file('/root/BHARAT-SYSTEMS/ZERODHA-OS/temp_dashboard_check.py', 'w') as f:
    f.write(script)
sftp.close()

_, stdout, stderr = c.exec_command("python3 /root/BHARAT-SYSTEMS/ZERODHA-OS/temp_dashboard_check.py")
print(stdout.read().decode('utf-8', errors='replace'))
err = stderr.read().decode('utf-8', errors='replace')
if err:
    print("STDERR:", err)

c.close()
