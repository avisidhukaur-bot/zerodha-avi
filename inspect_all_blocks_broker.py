import paramiko
import sys
import json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

secrets = {}
with open('secrets.txt', encoding='utf-8') as f:
    for l in f:
        if '=' in l and not l.startswith('#'):
            k, v = l.strip().split('=', 1)
            secrets[k.strip()] = v.strip()

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(secrets['VPS_IP'], username=secrets['VPS_USER'], password=secrets['VPS_PASSWORD'], timeout=10)

script = '''
import sys
sys.path.insert(0, '/root/BHARAT-SYSTEMS/ZERODHA-OS')
import db
import json
from kite_executor import kite_executor
import block_manager as bm

db.load_secrets()
kite_executor.load_session_from_db()

print("=== ALL BLOCKS IN DB ===")
blocks = db.get_all_blocks()
for b in blocks:
    print(f"Block ID: {b.get('block_id')} | Num: {b.get('block_number')} | Unit: {b.get('anchor_unit_name')} | Status: {b.get('status')} | Expiry: {b.get('expiry_date')}")
    strikes = db.get_strikes_by_block(b['block_id'])
    for s in strikes:
        print(f"   Strike {s.get('strike_id')} | {s.get('strike_price')} {s.get('option_type')} ({s.get('leg_type')}) | Lots: {s.get('lots')} | Status: {s.get('status')} | State: {s.get('trade_state')}")

print("\\n=== BROKER OPEN POSITIONS ===")
if kite_executor.ensure_logged_in():
    pos = kite_executor.get_positions()
    net = pos.get('net', []) if isinstance(pos, dict) else (pos if isinstance(pos, list) else [])
    for p in net:
        qty = p.get('quantity', 0)
        if qty != 0:
            print(f"OPEN: {p.get('tradingsymbol')} | Qty: {qty} | Avg: {p.get('average_price') or p.get('buy_price') or p.get('sell_price')} | LTP: {p.get('last_price')} | PnL: {p.get('pnl')}")
        else:
            print(f"CLOSED: {p.get('tradingsymbol')} | Qty: 0 | PnL: {p.get('pnl')}")
'''

sftp = c.open_sftp()
with sftp.file('/root/BHARAT-SYSTEMS/ZERODHA-OS/temp_inspect_all.py', 'w') as f:
    f.write(script)
sftp.close()

stdin, stdout, stderr = c.exec_command('python3 /root/BHARAT-SYSTEMS/ZERODHA-OS/temp_inspect_all.py')
print(stdout.read().decode('utf-8', errors='replace'))
print(stderr.read().decode('utf-8', errors='replace'))
c.exec_command('rm -f /root/BHARAT-SYSTEMS/ZERODHA-OS/temp_inspect_all.py')
c.close()
