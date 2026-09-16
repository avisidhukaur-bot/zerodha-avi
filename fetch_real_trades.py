import paramiko, os, json

secrets = {}
with open('secrets.txt', encoding='utf-8') as f:
    for line in f:
        if line.strip() and not line.startswith('#') and '=' in line:
            k, v = line.strip().split('=', 1)
            secrets[k.strip()] = v.strip()

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(secrets['VPS_IP'], username=secrets['VPS_USER'], password=secrets['VPS_PASSWORD'])

remote_script = """
import sys
from kite_executor import kite_executor
import json

kite_executor.load_session_from_db()
kite_executor.ensure_logged_in()

print("--- POSITIONS ---")
try:
    pos = kite_executor.kite.positions()
    for p in pos.get('net', []):
        print(f"SYMBOL: {p['tradingsymbol']} | QTY: {p['quantity']} | BUY_AVG: {p['buy_price']} | SELL_AVG: {p['sell_price']} | REALISED: {p['realised']} | UNREALISED: {p['unrealised']} | M2M: {p['m2m']}")
except Exception as e:
    print(f"Pos error: {e}")

print("--- TRADES TODAY ---")
try:
    trades = kite_executor.kite.trades()
    for t in trades:
        print(f"TIME: {t.get('trade_timestamp')} | SYM: {t.get('tradingsymbol')} | TYPE: {t.get('transaction_type')} | QTY: {t.get('quantity')} | PRICE: {t.get('average_price')} | ORDER_ID: {t.get('order_id')}")
except Exception as e:
    print(f"Trades error: {e}")
"""

sftp = client.open_sftp()
with sftp.file('/root/BHARAT-SYSTEMS/ZERODHA-OS/get_pnl_data.py', 'w') as f:
    f.write(remote_script)
sftp.close()

stdin, stdout, stderr = client.exec_command('python3 /root/BHARAT-SYSTEMS/ZERODHA-OS/get_pnl_data.py')
out = stdout.read().decode()
err = stderr.read().decode()
print("OUTPUT:\n", out)
if err:
    print("ERROR:\n", err)

client.close()
