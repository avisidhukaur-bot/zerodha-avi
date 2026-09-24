import paramiko

secrets = {}
with open('secrets.txt', encoding='utf-8') as f:
    for line in f:
        if line.strip() and '=' in line and not line.startswith('#'):
            k, v = line.strip().split('=', 1)
            secrets[k.strip()] = v.strip()

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(secrets['VPS_IP'], username=secrets['VPS_USER'], password=secrets['VPS_PASSWORD'], timeout=10)

cmd = """python3 -c "
import sqlite3
import sys
sys.path.append('/root/BHARAT-SYSTEMS/ZERODHA-OS')
from kite_executor import kite_executor

kite_executor.load_session_from_db()
kite_executor.ensure_logged_in()
pos = kite_executor.get_positions()
pos_list = pos if isinstance(pos, list) else pos.get('net', [])

conn = sqlite3.connect('/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_trader.db')
cur = conn.cursor()
print('=== ALL STRIKES IN DB ===')
cur.execute('SELECT strike_id, block_id, strike_price, option_type, leg_type, anchor_price, sl_pct, sl_price, trade_state, lots FROM strikes')
for r in cur.fetchall():
    print(r)

print('=== LIVE KITE POSITIONS ===')
for p in pos_list:
    if p.get('quantity', 0) != 0:
        print(p.get('tradingsymbol'), '| Qty:', p.get('quantity'), '| Entry/Avg:', p.get('average_price'), '| LTP:', p.get('last_price'), '| PnL:', p.get('pnl'))
" """

stdin, stdout, stderr = client.exec_command(cmd)
print(stdout.read().decode())
print(stderr.read().decode())
client.close()
