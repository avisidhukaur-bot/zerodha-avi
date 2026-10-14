import paramiko
import sys
import os

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

script = """import sys
sys.path.insert(0, '/root/BHARAT-SYSTEMS/ZERODHA-OS')
import db
import kite_executor as ke

spot = ke.kite_executor.get_ltp('NSE:NIFTY 50')
print('=== NIFTY SPOT PRICE ===')
print('Spot:', spot)

print('\\n=== BLOCKS IN VPS DB ===')
blocks = db.get_all_blocks()
for b in blocks:
    print(f"Block #{b['block_id']} | Unit: {b.get('anchor_unit_name')} | Expiry: {b.get('expiry_date')} | Status: {b.get('status')} | Anchor: {b.get('master_anchor_price')}")
    strikes = db.get_strikes_by_block(b['block_id'])
    for s in strikes:
        print(f"   Strike #{s['strike_id']}: {s['strike_price']} {s['option_type']} {s['leg_type']} | Status: {s['status']} | State: {s.get('trade_state')} | Anchor: {s['anchor_price']} | SL: {s.get('sl_price')} | Entry: {s.get('entry_price')}")

print('\\n=== LIVE POSITIONS ON BROKER ===')
positions = ke.kite_executor.get_positions()
for p in positions:
    if p.get('quantity') != 0:
        print(f"Symbol: {p['tradingsymbol']} | Qty: {p['quantity']} | PnL: ₹{p.get('pnl'):,.2f} | LTP: ₹{p.get('last_price'):.2f}")

print('\\n=== SCAN EXPIRY DATES IN SEC MASTER ===')
insts = ke.kite_executor._instruments
expiries = sorted(list(set(i['expiry'] for i in insts if i['name'] == 'NIFTY' and i['instrument_type'] in ('CE', 'PE') and i['expiry'])))
for e in expiries[:10]:
    print('Expiry:', e)
"""

sftp = c.open_sftp()
f = sftp.file('/tmp/check_custom_status.py', 'w')
f.write(script)
f.close()
sftp.close()

stdin, stdout, stderr = c.exec_command('python3 /tmp/check_custom_status.py')
print(stdout.read().decode('utf-8', errors='replace'))
print(stderr.read().decode('utf-8', errors='replace'))
c.close()
