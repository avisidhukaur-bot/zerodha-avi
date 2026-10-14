import sqlite3
import paramiko
import sys
import os
import json

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

print("=== 1. LOCAL DATABASE INSPECTION ===")
local_db = os.path.join(os.path.dirname(__file__), "zerodha_trader.db")
conn = sqlite3.connect(local_db)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

blocks = cur.execute("SELECT * FROM blocks WHERE status='ACTIVE'").fetchall()
print(f"Local Active Blocks: {len(blocks)}")
for b in blocks:
    print(dict(b))
    cur.execute("SELECT * FROM strikes WHERE block_id=?", (b['block_id'],))
    for s in cur.fetchall():
        print("  Strike:", dict(s))

legs = cur.execute("SELECT * FROM legs").fetchall()
print(f"Local Legs Count: {len(legs)}")
for l in legs[-5:]:
    print("  Leg:", dict(l))

orders = cur.execute("SELECT * FROM orders ORDER BY order_id DESC LIMIT 5").fetchall() if 'orders' in [t[0] for t in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()] else []
print(f"Local Orders: {len(orders)}")

# Check settings/config
settings = {r['key']: r['value'] for r in cur.execute("SELECT key, value FROM settings").fetchall()}
print("Local Settings:", json.dumps(settings, indent=2))
conn.close()

print("\n=== 2. VPS DATABASE INSPECTION ===")
secrets = {}
with open('secrets.txt', encoding='utf-8') as f:
    for l in f:
        if '=' in l and not l.startswith('#'):
            k, v = l.strip().split('=', 1)
            secrets[k.strip()] = v.strip()

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    c.connect(secrets['VPS_IP'], username=secrets['VPS_USER'], password=secrets['VPS_PASSWORD'], timeout=10)
    
    script = """
import sqlite3
import json
conn = sqlite3.connect('/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_trader.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()
blocks = [dict(b) for b in cur.execute("SELECT * FROM blocks WHERE status='ACTIVE'").fetchall()]
print("VPS Active Blocks:", json.dumps(blocks, indent=2))
for b in blocks:
    strikes = [dict(s) for s in cur.execute("SELECT * FROM strikes WHERE block_id=?", (b['block_id'],)).fetchall()]
    print("VPS Strikes for Block", b['block_id'], ":", json.dumps(strikes, indent=2))

settings = {r['key']: r['value'] for r in cur.execute("SELECT key, value FROM settings").fetchall()}
print("VPS Settings:", json.dumps(settings, indent=2))
"""
    sftp = c.open_sftp()
    with sftp.file('/tmp/check_trade.py', 'w') as f:
        f.write(script)
    sftp.close()
    
    _, out, err = c.exec_command("python3 /tmp/check_trade.py && journalctl -u zerodha_engine.service -n 25 --no-pager")
    print(out.read().decode(errors='replace'))
    e = err.read().decode(errors='replace')
    if e:
        print("ERR:", e)
    c.close()
except Exception as e:
    print("VPS SSH error:", e)
