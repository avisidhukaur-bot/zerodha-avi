import paramiko, os

secrets = {}
with open('secrets.txt', encoding='utf-8') as f:
    for line in f:
        if line.strip() and not line.startswith('#') and '=' in line:
            k, v = line.strip().split('=', 1)
            secrets[k.strip()] = v.strip()

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(secrets['VPS_IP'], username=secrets['VPS_USER'], password=secrets['VPS_PASSWORD'])

script = """
import sqlite3
conn = sqlite3.connect('/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_trader.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()
strikes = cur.execute('SELECT * FROM strikes WHERE strike_price=23700').fetchall()
print('STRIKES:')
for s in strikes:
    print(dict(s))
legs = cur.execute('SELECT * FROM legs WHERE strike_id IN (SELECT strike_id FROM strikes WHERE strike_price=23700)').fetchall()
print('LEGS:')
for l in legs:
    print(dict(l))
blocks = cur.execute('SELECT * FROM blocks WHERE status=\"ACTIVE\"').fetchall()
print('ACTIVE BLOCKS:')
for b in blocks:
    print(dict(b))
"""
sftp = client.open_sftp()
with sftp.file('/root/BHARAT-SYSTEMS/ZERODHA-OS/chk_23700.py', 'w') as f:
    f.write(script)
sftp.close()

stdin, stdout, stderr = client.exec_command('python3 /root/BHARAT-SYSTEMS/ZERODHA-OS/chk_23700.py')
print(stdout.read().decode())
print(stderr.read().decode())
client.close()
