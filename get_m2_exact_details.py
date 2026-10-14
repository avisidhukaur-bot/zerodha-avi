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
import regime_engine as re_eng

conn = db._conn()
cur = conn.cursor()
cur.execute("SELECT * FROM blocks WHERE anchor_unit_name='M2'")
cols = [d[0] for d in cur.description]
b = [dict(zip(cols, r)) for r in cur.fetchall()]
print("=== M2 BLOCK ===")
print(json.dumps(b, indent=2, default=str))

cur.execute("SELECT * FROM strikes WHERE block_id IN (SELECT block_id FROM blocks WHERE anchor_unit_name='M2')")
cols = [d[0] for d in cur.description]
s = [dict(zip(cols, r)) for r in cur.fetchall()]
print("\\n=== M2 STRIKES ===")
print(json.dumps(s, indent=2, default=str))

spot = re_eng.get_current_nifty_spot()
print(f"\\nCurrent Nifty Spot: {spot}")
'''

sftp = c.open_sftp()
with sftp.file('/root/BHARAT-SYSTEMS/ZERODHA-OS/temp_get_m2_detail.py', 'w') as f:
    f.write(script)
sftp.close()

stdin, stdout, stderr = c.exec_command('python3 /root/BHARAT-SYSTEMS/ZERODHA-OS/temp_get_m2_detail.py')
print(stdout.read().decode('utf-8', errors='replace'))
print(stderr.read().decode('utf-8', errors='replace'))
c.exec_command('rm -f /root/BHARAT-SYSTEMS/ZERODHA-OS/temp_get_m2_detail.py')
c.close()
