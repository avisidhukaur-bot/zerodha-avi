import paramiko
import sys

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
import sqlite3
import sys
sys.path.insert(0, '/root/BHARAT-SYSTEMS/ZERODHA-OS')
import kite_executor as ke

conn = sqlite3.connect('/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_trader.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=== ACTIVE BLOCK 73 CONFIGURATION ===")
block = cur.execute("SELECT * FROM blocks WHERE block_id=73").fetchone()
if block:
    for k, v in dict(block).items():
        print(f"  {k}: {v}")
else:
    print("Block 73 not found!")

print("\\n=== STRIKES IN BLOCK 73 ===")
strikes = cur.execute("SELECT * FROM strikes WHERE block_id=73").fetchall()
for s in strikes:
    print(f"  Strike ID: {s['strike_id']} | Strike: {s['strike_price']} {s['option_type']} | Type: {s['leg_type']} | Anchor: {s['anchor_price']} | Status: {s['status']} | TradeState: {s['trade_state']} | SL: {s['sl_price']} ({s['sl_pct']}%)")

print("\\n=== CURRENT SPOT & REGIME STATUS ===")
ke.kite_executor.ensure_logged_in()
spot = ke.kite_executor.get_spot_price("NIFTY 50")
print(f"Current NIFTY 50 Spot Price: ₹{spot}")

'''

sftp = c.open_sftp()
f = sftp.file('/tmp/check_m1_pe_rules.py', 'w')
f.write(script)
f.close()
sftp.close()

stdin, stdout, stderr = c.exec_command('python3 /tmp/check_m1_pe_rules.py')
print(stdout.read().decode('utf-8', errors='replace'))
print(stderr.read().decode('utf-8', errors='replace'))
c.close()
