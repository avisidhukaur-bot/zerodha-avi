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
import sqlite3

conn = sqlite3.connect('/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_trader.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=== CURRENT BLOCK 73 STRIKES ===")
strikes = cur.execute("SELECT * FROM strikes WHERE block_id=73").fetchall()
for s in strikes:
    print(dict(s))

ke.kite_executor.ensure_logged_in()
kite = ke.kite_executor.kite

# Fetch quotes for 22000 PE and 21500 PE
symbols = ["NFO:NIFTY26OCT22000PE", "NFO:NIFTY26OCT21500PE", "NFO:NIFTY26OCT22200PE"]
quotes = kite.quote(symbols)
print("\\n=== LIVE QUOTES ===")
for sym, q in quotes.items():
    print(f"{sym} -> LTP: ₹{q.get('last_price')} | High: ₹{q.get('ohlc', {}).get('high')} | Low: ₹{q.get('ohlc', {}).get('low')}")
'''

sftp = c.open_sftp()
f = sftp.file('/tmp/check_22000_pe.py', 'w')
f.write(script)
f.close()
sftp.close()

stdin, stdout, stderr = c.exec_command('python3 /tmp/check_22000_pe.py')
print(stdout.read().decode('utf-8', errors='replace'))
print(stderr.read().decode('utf-8', errors='replace'))
c.close()
