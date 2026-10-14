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
    return stdout.read().decode('utf-8', errors='replace')

cmd = '''python3 -c "
import sqlite3, json

conn = sqlite3.connect('/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_trader.db')
conn.row_factory = sqlite3.Row

print('=== 22400 PE STRIKES ROWS ===')
for r in conn.execute(\"SELECT * FROM strikes WHERE strike_price=22400 OR opt_type='PE'\").fetchall():
    print(dict(r))

print('\n=== ALL ACTIVE/CLOSED STRIKES ===')
for r in conn.execute(\"SELECT id, block_id, opt_type, strike_price, trade_state, status, is_hedge, entry_price, current_ltp, stop_loss_price, stop_loss_pct, exit_price, exit_reason, exit_time, created_at, updated_at FROM strikes\").fetchall():
    print(dict(r))

print('\n=== ALL BLOCKS ===')
for b in conn.execute(\"SELECT * FROM blocks\").fetchall():
    print(dict(b))
"'''

print(run(cmd))

print("\n=== SEARCH LOG FOR 22400 PE EXIT EVENT ===")
print(run("grep -i -C 5 '22400' /root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_engine.log | grep -i -C 5 'SL\|exit\|Trigger' | tail -n 40"))
