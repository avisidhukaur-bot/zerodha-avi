import paramiko
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

secrets = {}
secrets_path = os.path.join(os.path.dirname(__file__), "secrets.txt")
with open(secrets_path, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            secrets[k.strip()] = v.strip()

VPS_IP       = secrets.get("VPS_IP", "5.75.250.104")
VPS_USER     = secrets.get("VPS_USER", "root")
VPS_PASSWORD = secrets.get("VPS_PASSWORD", "")

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(VPS_IP, username=VPS_USER, password=VPS_PASSWORD, timeout=15)

def run(cmd):
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    return out + ("\nERR: " + err if err else "")

print(run("""python3 -c "
import sqlite3
conn = sqlite3.connect('/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_trader.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute('SELECT * FROM strikes')
rows = cur.fetchall()
print(f'TOTAL STRIKES IN DB: {len(rows)}')
for r in rows:
    d = dict(r)
    print(f\"ID:{d.get('id')} | Block:{d.get('block_id')} | Opt:{d.get('opt_type')} | Strike:{d.get('strike_price')} | State:{d.get('trade_state')} | Status:{d.get('status')} | Hedge:{d.get('is_hedge')} | Entry:{d.get('entry_price')} | SL_Price:{d.get('stop_loss_price')} | SL_Pct:{d.get('stop_loss_pct')} | ExitPrice:{d.get('exit_price')} | ExitReason:{d.get('exit_reason')} | ExitTime:{d.get('exit_time')}\")
" """))
