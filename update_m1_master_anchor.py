import paramiko
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

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

# Update Master Anchor Price for Block 56 (M1) to 23225.0
cur.execute('UPDATE blocks SET master_anchor_price = 23225.0 WHERE block_id = 56')
conn.commit()

cur.execute('SELECT block_id, anchor_unit_name, master_anchor_price, regime_buffer, current_regime, expiry_date, status FROM blocks WHERE block_id = 56')
updated_block = cur.fetchone()
print('UPDATED_BLOCK:', updated_block)
conn.close()
" """

stdin, stdout, stderr = client.exec_command(cmd)
print(stdout.read().decode())
print(stderr.read().decode())
client.close()
