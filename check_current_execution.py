import paramiko
import sys

secrets = {}
with open('secrets.txt', encoding='utf-8') as f:
    for l in f:
        if '=' in l and not l.startswith('#'):
            k, v = l.strip().split('=', 1)
            secrets[k.strip()] = v.strip()

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(secrets['VPS_IP'], username=secrets['VPS_USER'], password=secrets['VPS_PASSWORD'], timeout=10)

script = """
import sys
sys.path.insert(0, '/root/BHARAT-SYSTEMS/ZERODHA-OS')
import db
import kite_executor as ke

ke.kite_executor.load_session_from_db()
kite = ke.kite_executor.kite

print('=== RECENT ORDERS FROM KITE ===')
try:
    orders = kite.orders()
    for o in orders[-10:]:
        print(f"{o.get('order_timestamp')} | {o.get('tradingsymbol')} | {o.get('transaction_type')} | Qty: {o.get('quantity')} | Status: {o.get('status')} | Price: {o.get('average_price')} | Tag: {o.get('tag')}")
except Exception as e:
    print('Order fetch error:', e)

print('\\n=== NET POSITIONS ON KITE ===')
try:
    pos = kite.positions().get('net', [])
    for p in pos:
        if p.get('quantity', 0) != 0:
            print(f"{p.get('tradingsymbol')} | Qty: {p.get('quantity')} | BuyAvg: {p.get('buy_price')} | SellAvg: {p.get('sell_price')} | LTP: {p.get('last_price')} | PnL: {p.get('pnl'):.2f}")
except Exception as e:
    print('Pos fetch error:', e)

print('\\n=== DB BLOCKS AND STRIKES ===')
try:
    conn = db._get_conn()
    c_cur = conn.cursor()
    c_cur.execute("SELECT * FROM blocks")
    rows = c_cur.fetchall()
    for r in rows:
        print("Block:", dict(r) if hasattr(r, 'keys') else r)
    c_cur.execute("SELECT * FROM strikes")
    s_rows = c_cur.fetchall()
    for s in s_rows:
        print("Strike:", dict(s) if hasattr(s, 'keys') else s)
except Exception as e:
    print('DB read error:', e)

print('\\n=== RECENT ENGINE LOGS (LAST 60 LINES) ===')
try:
    with open('/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_engine.log', 'r') as f:
        lines = f.readlines()
        for l in lines[-60:]:
            print(l.strip())
except Exception as e:
    print('Log error:', e)


"""

sftp = c.open_sftp()
with sftp.file('/tmp/check_os_execution_now.py', 'w') as f:
    f.write(script)
sftp.close()

_, stdout, stderr = c.exec_command('python3 /tmp/check_os_execution_now.py')
print(stdout.read().decode('utf-8', errors='replace'))
print(stderr.read().decode('utf-8', errors='replace'))
c.close()
