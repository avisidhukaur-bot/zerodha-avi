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
import sys
sys.path.insert(0, '/root/BHARAT-SYSTEMS/ZERODHA-OS')
import kite_executor as ke
import db

ke.kite_executor.ensure_logged_in()
q = ke.kite_executor.kite.quote("NSE:NIFTY 50")
spot = q.get("NSE:NIFTY 50", {}).get("last_price", 0.0)
anchor = db.get_master_nifty_anchor()

print(f"=== CURRENT MARKET STATE ===")
print(f"Current NIFTY Spot: ₹{spot:.2f}")
print(f"Master Anchor: ₹{anchor:.2f}")

conn = db._conn()
cur = conn.cursor()
block = cur.execute("SELECT * FROM blocks WHERE block_id=73").fetchone()
if block:
    print(f"Block 73 Regime: {block['current_regime']} | Anchor: {block['master_anchor_price']}")
'''

sftp = c.open_sftp()
f = sftp.file('/tmp/check_mkt.py', 'w')
f.write(script)
f.close()
sftp.close()

stdin, stdout, stderr = c.exec_command('python3 /tmp/check_mkt.py')
print(stdout.read().decode('utf-8', errors='replace'))
print(stderr.read().decode('utf-8', errors='replace'))
c.close()
