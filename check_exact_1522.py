import paramiko

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
import sqlite3

conn = sqlite3.connect('/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_trader.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print('=== ALL BLOCKS ===')
for row in cur.execute("SELECT * FROM blocks").fetchall():
    print(dict(row))

print('\\n=== STRIKES FOR BLOCK 75 (OS1) ===')
for row in cur.execute("SELECT * FROM strikes WHERE block_id = 75").fetchall():
    print(dict(row))

print('\\n=== STRIKES FOR BLOCK 74 (M1) ===')
for row in cur.execute("SELECT * FROM strikes WHERE block_id = 74").fetchall():
    print(dict(row))

print('\\n=== ALL ORDERS FOR BLOCK 75 ===')
for row in cur.execute("SELECT * FROM orders ORDER BY order_id DESC LIMIT 10").fetchall():
    print(dict(row))


print('\\n=== ENGINE LOG AROUND 15:22 ===')
with open('/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_engine.log', 'r') as f:
    for line in f:
        if '15:22' in line or '15:23' in line or 'ANTI-COLLISION' in line or 'deploy' in line.lower() or 'execute' in line.lower() or 'blocked' in line.lower():
            print(line.strip())
"""

sftp = c.open_sftp()
with sftp.file('/tmp/check_exact_db.py', 'w') as f:
    f.write(script)
sftp.close()

_, stdout, stderr = c.exec_command('python3 /tmp/check_exact_db.py')
print(stdout.read().decode('utf-8', errors='replace'))
print(stderr.read().decode('utf-8', errors='replace'))
c.close()
