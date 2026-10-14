import paramiko
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

secrets = {}
with open('secrets.txt', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            secrets[k.strip()] = v.strip()

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(secrets['VPS_IP'], username=secrets['VPS_USER'], password=secrets['VPS_PASSWORD'], timeout=10)

def run(cmd):
    stdin, stdout, stderr = client.exec_command(cmd)
    return stdout.read().decode(errors='replace').strip()

print("--- SQLITE BLOCKS ON VPS ---")
print(run('sqlite3 /root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_trader.db "SELECT block_id, block_number, anchor_unit_name, status, expiry_date FROM blocks;"'))

print("\n--- SQLITE STRIKES ON VPS ---")
print(run('sqlite3 /root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_trader.db "SELECT strike_id, block_id, strike_price, option_type, leg_type, status, trade_state FROM strikes;"'))

print("\n--- KITE POSITIONS ON VPS ---")
script_pos = """
import sys
sys.path.insert(0, '/root/BHARAT-SYSTEMS/ZERODHA-OS')
from kite_executor import kite_executor
kite_executor.load_session_from_db()
pos = kite_executor.kite.positions().get('net', [])
for p in pos:
    if p.get('quantity') != 0:
        print(p.get('tradingsymbol'), 'Qty:', p.get('quantity'), 'PnL:', p.get('pnl'), 'Avg:', p.get('average_price'), 'LTP:', p.get('last_price'))
"""
stdin, stdout, stderr = client.exec_command(f"python3 -c \"{script_pos}\"")
print(stdout.read().decode(errors='replace').strip())

print("\n--- OS SETTINGS ON VPS ---")
print(run('sqlite3 /root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_trader.db "SELECT key, value FROM settings WHERE key LIKE \'%os_%\';"'))

client.close()
