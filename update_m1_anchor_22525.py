import sqlite3
import paramiko
import sys
import os

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

NEW_ANCHOR = 22525.0

print("============================================================")
print(f"Updating M1 Master Anchor Price to: {NEW_ANCHOR}")
print("============================================================")

# 1. LOCAL DB UPDATE
local_db = os.path.join(os.path.dirname(__file__), "zerodha_trader.db")
if os.path.exists(local_db):
    try:
        conn = sqlite3.connect(local_db)
        cur = conn.cursor()
        cur.execute("UPDATE blocks SET master_anchor_price = ? WHERE anchor_unit_name = 'M1' AND status = 'ACTIVE'", (NEW_ANCHOR,))
        conn.commit()
        print(f"✅ Local DB Updated. Rows affected: {cur.rowcount}")
        cur.execute("SELECT block_id, block_number, anchor_unit_name, master_anchor_price, status, expiry_date FROM blocks WHERE anchor_unit_name = 'M1' AND status = 'ACTIVE'")
        print("Local active M1 blocks:", cur.fetchall())
        conn.close()
    except Exception as e:
        print("Local DB error:", e)

# 2. VPS REMOTE DB UPDATE
try:
    secrets = {}
    with open('secrets.txt', encoding='utf-8') as f:
        for line in f:
            if line.strip() and '=' in line and not line.startswith('#'):
                k, v = line.strip().split('=', 1)
                secrets[k.strip()] = v.strip()

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(secrets['VPS_IP'], username=secrets['VPS_USER'], password=secrets['VPS_PASSWORD'], timeout=15)

    vps_code = """
import sqlite3, sys
sys.path.insert(0, '/root/BHARAT-SYSTEMS/ZERODHA-OS')
from kite_executor import kite_executor
import db

conn = sqlite3.connect('/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_trader.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Update M1 block master anchor
cur.execute("UPDATE blocks SET master_anchor_price = 22525.0 WHERE anchor_unit_name = 'M1' AND status = 'ACTIVE'")
conn.commit()
print('VPS Rows updated:', cur.rowcount)

cur.execute("SELECT block_id, block_number, anchor_unit_name, master_anchor_price, current_regime, status, expiry_date FROM blocks WHERE anchor_unit_name = 'M1' AND status = 'ACTIVE'")
m1_block = [dict(r) for r in cur.fetchall()]
print('VPS Active M1 Block:', m1_block)

cur.execute("SELECT strike_id, block_id, strike_price, option_type, leg_type, anchor_price, status, sl_price FROM strikes WHERE block_id = 79")
strikes = [dict(r) for r in cur.fetchall()]
print('VPS M1 Strikes:', strikes)

conn.close()

# Fetch live Nifty Spot
kite_executor.ensure_logged_in()
k = kite_executor.kite
quote = k.quote(['NSE:NIFTY 50'])
spot = quote['NSE:NIFTY 50']['last_price']
print('Current NIFTY 50 Spot:', spot)
print('Distance from Master Anchor (22525.0):', round(spot - 22525.0, 2))
"""

    sftp = client.open_sftp()
    with sftp.file('/tmp/do_update_m1_anchor.py', 'w') as f:
        f.write(vps_code)
    sftp.close()

    stdin, stdout, stderr = client.exec_command('python3 /tmp/do_update_m1_anchor.py')
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    print("\n--- VPS UPDATE OUTPUT ---")
    print(out)
    if err:
        print("VPS STDERR:", err)

    client.close()
    print("✅ VPS Update Completed Successfully!")
except Exception as e:
    print("VPS SSH error:", e)
