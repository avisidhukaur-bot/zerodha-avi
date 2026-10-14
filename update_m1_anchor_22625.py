import sqlite3
import paramiko
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

NEW_ANCHOR = 22625.0

print(f"Updating M1 Master Anchor Price to: {NEW_ANCHOR}")

# 1. LOCAL DB UPDATE
try:
    conn = sqlite3.connect('zerodha_trader.db')
    cur = conn.cursor()
    cur.execute("UPDATE blocks SET master_anchor_price = ? WHERE anchor_unit_name = 'M1' AND status = 'ACTIVE'", (NEW_ANCHOR,))
    conn.commit()
    print(f"✅ Local DB Updated. Rows affected: {cur.rowcount}")
    cur.execute("SELECT block_id, anchor_unit_name, master_anchor_price, status FROM blocks WHERE anchor_unit_name = 'M1' AND status = 'ACTIVE'")
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
    client.connect(secrets['VPS_IP'], username=secrets['VPS_USER'], password=secrets['VPS_PASSWORD'], timeout=10)

    cmd = f"""python3 -c "
import sqlite3
conn = sqlite3.connect('/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_trader.db')
cur = conn.cursor()
cur.execute(\\"UPDATE blocks SET master_anchor_price = {NEW_ANCHOR} WHERE anchor_unit_name = 'M1' AND status = 'ACTIVE'\\")
conn.commit()
print('VPS Rows updated:', cur.rowcount)
cur.execute(\\"SELECT block_id, anchor_unit_name, master_anchor_price, status, expiry_date FROM blocks WHERE anchor_unit_name = 'M1' AND status = 'ACTIVE'\\")
print('VPS Active M1 Block after update:', cur.fetchall())
" """
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode()
    err = stderr.read().decode()
    print("\n--- VPS UPDATE OUTPUT ---")
    print(out)
    if err:
        print("VPS STDERR:", err)
    client.close()
except Exception as e:
    print("VPS SSH error:", e)
