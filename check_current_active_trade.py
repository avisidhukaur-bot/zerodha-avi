import paramiko
import sys
import sqlite3

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

print("--- LOCAL DB CHECK ---")
try:
    conn = sqlite3.connect('zerodha_trader.db')
    cur = conn.cursor()
    cur.execute("SELECT block_id, anchor_unit_name, master_anchor_price, expiry_date, status, created_at FROM blocks ORDER BY block_id DESC LIMIT 5")
    rows = cur.fetchall()
    for r in rows:
        print("Block:", r)
    cur.execute("SELECT strike_id, block_id, strike_price, option_type, leg_type, anchor_price, sl_price, trade_state, filled_price FROM strikes ORDER BY strike_id DESC LIMIT 10")
    for s in cur.fetchall():
        print("Strike:", s)
    conn.close()
except Exception as e:
    print("Local DB error:", e)

print("\n--- VPS REMOTE DB CHECK ---")
try:
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
cur.execute('SELECT block_id, anchor_unit_name, master_anchor_price, expiry_date, status, created_at FROM blocks ORDER BY block_id DESC LIMIT 5')
for r in cur.fetchall():
    print('VPS BLOCK:', r)

cur.execute('SELECT strike_id, block_id, strike_price, option_type, leg_type, anchor_price, sl_price, trade_state, filled_price FROM strikes ORDER BY strike_id DESC LIMIT 10')
for s in cur.fetchall():
    print('VPS STRIKE:', s)
" """
    stdin, stdout, stderr = client.exec_command(cmd)
    print(stdout.read().decode())
    client.close()
except Exception as e:
    print("VPS Error:", e)
