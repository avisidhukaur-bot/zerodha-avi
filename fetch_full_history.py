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

script = r'''
import sys
sys.path.insert(0, '/root/BHARAT-SYSTEMS/ZERODHA-OS')
import db
import json

db.load_secrets()
conn = db._conn()
cur = conn.cursor()

print("=== 1. BLOCK DETAILS ===")
cur.execute("SELECT * FROM blocks WHERE block_id=32")
cols = [d[0] for d in cur.description]
print(json.dumps([dict(zip(cols, r)) for r in cur.fetchall()], indent=2, default=str))

print("\n=== 2. ALL LEGS IN BLOCK 32 (HISTORY) ===")
cur.execute("""
    SELECT l.leg_id, l.strike_id, s.strike_price, s.option_type, s.leg_type, 
           l.entry_price, l.exit_price, l.entry_time, l.exit_time, l.realized_pnl, l.order_id
    FROM legs l
    JOIN strikes s ON l.strike_id = s.strike_id
    WHERE s.block_id = 32
    ORDER BY l.leg_id ASC
""")
cols = [d[0] for d in cur.description]
print(json.dumps([dict(zip(cols, r)) for r in cur.fetchall()], indent=2, default=str))

print("\n=== 3. ALL TRADES IN BLOCK 32 (HISTORY) ===")
cur.execute("SELECT * FROM trades WHERE block_id=32 ORDER BY trade_id ASC")
cols = [d[0] for d in cur.description]
print(json.dumps([dict(zip(cols, r)) for r in cur.fetchall()], indent=2, default=str))

print("\n=== 4. WHAT UNITS EXIST IN DB ===")
cur.execute("SELECT block_id, block_number, anchor_unit_name, status, expiry_date, master_anchor_price FROM blocks")
cols = [d[0] for d in cur.description]
print(json.dumps([dict(zip(cols, r)) for r in cur.fetchall()], indent=2, default=str))
'''

sftp = c.open_sftp()
with sftp.file('/root/BHARAT-SYSTEMS/ZERODHA-OS/temp_full_history.py', 'w') as f:
    f.write(script)
sftp.close()

stdin, stdout, stderr = c.exec_command("python3 /root/BHARAT-SYSTEMS/ZERODHA-OS/temp_full_history.py")
print(stdout.read().decode('utf-8', errors='replace'))
err = stderr.read().decode('utf-8', errors='replace')
if err:
    print("STDERR:", err)

c.exec_command("rm -f /root/BHARAT-SYSTEMS/ZERODHA-OS/temp_full_history.py")
c.close()
