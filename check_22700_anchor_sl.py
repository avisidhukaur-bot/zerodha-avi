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
conn = sqlite3.connect('/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_trader.db')
cur = conn.cursor()
print('--- STRIKES ---')
cur.execute('SELECT strike_id, block_id, strike_price, option_type, leg_type, anchor_price, sl_pct, sl_price, trade_state, lots FROM strikes WHERE strike_price IN (22700, 22200)')
for r in cur.fetchall():
    print('STRIKE:', r)

print('--- LEGS ---')
cur.execute('SELECT * FROM legs WHERE strike_id IN (122, 123)')
for r in cur.fetchall():
    print('LEG:', r)

print('--- TRADES ---')
cur.execute('SELECT * FROM trades WHERE strike_id IN (122, 123)')
for r in cur.fetchall():
    print('TRADE:', r)
" """

stdin, stdout, stderr = client.exec_command(cmd)
print(stdout.read().decode())
print(stderr.read().decode())
client.close()
