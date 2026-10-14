import sqlite3
import paramiko
import sys
import json

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

print("=== CHECKING ALL RECENT BLOCKS LOCAL ===")
conn = sqlite3.connect('zerodha_trader.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()
for b in cur.execute("SELECT * FROM blocks ORDER BY block_id DESC LIMIT 5").fetchall():
    print(dict(b))
    for s in cur.execute("SELECT * FROM strikes WHERE block_id=?", (b['block_id'],)).fetchall():
        print("   Strike:", dict(s))
conn.close()

print("\n=== CHECKING ALL RECENT BLOCKS ON VPS ===")
secrets = {}
with open('secrets.txt', encoding='utf-8') as f:
    for l in f:
        if '=' in l and not l.startswith('#'):
            k, v = l.strip().split('=', 1)
            secrets[k.strip()] = v.strip()

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(secrets['VPS_IP'], username=secrets['VPS_USER'], password=secrets['VPS_PASSWORD'], timeout=10)

check_vps = """
import sqlite3
import json
conn = sqlite3.connect('/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_trader.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()
for b in cur.execute("SELECT * FROM blocks ORDER BY block_id DESC LIMIT 5").fetchall():
    print(dict(b))
    for s in cur.execute("SELECT * FROM strikes WHERE block_id=?", (b['block_id'],)).fetchall():
        print("   Strike:", dict(s))
"""
sftp = c.open_sftp()
with sftp.file('/tmp/check_all_b.py', 'w') as f:
    f.write(check_vps)
sftp.close()

_, out, err = c.exec_command("python3 /tmp/check_all_b.py")
print(out.read().decode(errors='replace'))
c.close()
