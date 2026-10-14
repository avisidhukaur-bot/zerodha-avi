import paramiko
import sys
import time

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

secrets = {}
with open('secrets.txt', encoding='utf-8') as f:
    for l in f:
        if '=' in l and not l.startswith('#'):
            k, v = l.strip().split('=', 1)
            secrets[k.strip()] = v.strip()

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())

for attempt in range(5):
    try:
        print(f"Connecting to VPS attempt {attempt+1}...")
        c.connect(secrets['VPS_IP'], username=secrets['VPS_USER'], password=secrets['VPS_PASSWORD'], timeout=10)
        print("Connected!")
        break
    except Exception as e:
        print(f"Attempt {attempt+1} failed: {e}")
        time.sleep(1)

clean_sql = '''
import sqlite3
conn = sqlite3.connect('/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_trader.db')
cur = conn.cursor()
cur.execute("UPDATE blocks SET status='CLOSED' WHERE status='ACTIVE'")
cur.execute("UPDATE strikes SET status='CLOSED' WHERE status IN ('ACTIVE', 'PENDING', 'OPEN')")
cur.execute("UPDATE legs SET exit_time=datetime('now') WHERE exit_time IS NULL OR exit_time=''")
conn.commit()
cur.execute("SELECT COUNT(*) FROM blocks WHERE status='ACTIVE'")
print("VPS Active Blocks:", cur.fetchone()[0])
conn.close()
'''

sftp = c.open_sftp()
with sftp.file('/tmp/clean_vps.py', 'w') as f:
    f.write(clean_sql)
sftp.close()

_, out, err = c.exec_command('python3 /tmp/clean_vps.py && systemctl restart zerodha_dashboard.service zerodha_engine.service')
print(out.read().decode(errors='replace'))
e = err.read().decode(errors='replace')
if e:
    print("ERR:", e)

c.close()
print("VPS sync complete!")
