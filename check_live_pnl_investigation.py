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

db.load_secrets()
kite_executor.load_session_from_db()

print("=== VPS DB STRIKES ===")
conn = db._conn()
cur = conn.cursor()
cur.execute("SELECT * FROM strikes WHERE strike_price IN (22700, 22200, 24000, 24500, 24100)")
cols = [d[0] for d in cur.description]
print(json.dumps([dict(zip(cols, r)) for r in cur.fetchall()], indent=2, default=str))

print("\\n=== VPS DB LEGS ===")
cur.execute("SELECT * FROM legs WHERE strike_id IN (SELECT strike_id FROM strikes WHERE strike_price IN (22700, 22200, 24000, 24500, 24100)) ORDER BY leg_id ASC")
cols = [d[0] for d in cur.description]
print(json.dumps([dict(zip(cols, r)) for r in cur.fetchall()], indent=2, default=str))

print("\\n=== KITE ORDERS TODAY ===")
if kite_executor.ensure_logged_in():
    orders = kite_executor.get_orders() if hasattr(kite_executor, 'get_orders') else []
    for o in orders:
        print(f"{o.get('order_timestamp')} | {o.get('tradingsymbol')} | {o.get('transaction_type')} | avg={o.get('average_price')} | qty={o.get('quantity')} | status={o.get('status')}")

print("\\n=== KITE POSITIONS ===")
if kite_executor.ensure_logged_in():
    pos = kite_executor.get_positions()
    net = pos.get('net', []) if pos else []
    for p in net:
        if p.get('tradingsymbol', '').startswith('NIFTY'):
            print(f"{p.get('tradingsymbol')} | qty={p.get('quantity')} | buy_avg={p.get('buy_price')} | sell_avg={p.get('sell_price')} | pnl={p.get('pnl')} | m2m={p.get('m2m')} | realised={p.get('realised')} | unrealised={p.get('unrealised')}")
'''

sftp = c.open_sftp()
with sftp.file('/root/BHARAT-SYSTEMS/ZERODHA-OS/temp_check_pnl.py', 'w') as f:
    f.write(script)
sftp.close()

stdin, stdout, stderr = c.exec_command('python3 /root/BHARAT-SYSTEMS/ZERODHA-OS/temp_check_pnl.py')
print(stdout.read().decode('utf-8', errors='replace'))
print(stderr.read().decode('utf-8', errors='replace'))
c.exec_command('rm -f /root/BHARAT-SYSTEMS/ZERODHA-OS/temp_check_pnl.py')
c.close()
