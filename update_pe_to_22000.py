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

# Update Strike 195 to 22000 PE
cur.execute("""
    UPDATE strikes 
    SET strike_price = 22000,
        anchor_price = 161.00,
        sl_price = 201.25,
        sl_pct = 25.0,
        status = 'PENDING',
        trade_state = 'PENDING',
        hedge_strike_id = 194
    WHERE strike_id = 195
""")

# Update Strike 194 to 21500 PE Hedge
cur.execute("""
    UPDATE strikes 
    SET strike_price = 21500,
        anchor_price = 74.70,
        status = 'PENDING',
        trade_state = 'PENDING',
        hedge_strike_id = 195
    WHERE strike_id = 194
""")

conn.commit()

print("=== VERIFYING UPDATED STRIKES IN BLOCK 73 ===")
strikes = cur.execute("SELECT * FROM strikes WHERE block_id=73").fetchall()
for s in strikes:
    print(f"Strike ID: {s['strike_id']} | Strike: {s['strike_price']} {s['option_type']} | Leg: {s['leg_type']} | Anchor: ₹{s['anchor_price']} | SL: ₹{s['sl_price']} ({s['sl_pct']}%) | Status: {s['status']} | Linked Hedge ID: {s['hedge_strike_id']}")

'''

sftp = c.open_sftp()
f = sftp.file('/tmp/update_to_22000_pe.py', 'w')
f.write(script)
f.close()
sftp.close()

stdin, stdout, stderr = c.exec_command('python3 /tmp/update_to_22000_pe.py')
print(stdout.read().decode('utf-8', errors='replace'))
print(stderr.read().decode('utf-8', errors='replace'))
c.close()
