import paramiko
import sys
import json

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

secrets = {}
with open('secrets.txt', encoding='utf-8') as f:
    for l in f:
        if '=' in l and not l.startswith('#'):
            k, v = l.strip().split('=', 1)
            secrets[k.strip()] = v.strip()

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
connected = False
for attempt in range(5):
    try:
        print(f"Connecting to VPS ({secrets['VPS_IP']}) attempt {attempt+1}...")
        c.connect(secrets['VPS_IP'], username=secrets['VPS_USER'], password=secrets['VPS_PASSWORD'], timeout=10)
        connected = True
        print("Connected to VPS!")
        break
    except Exception as e:
        print("Attempt failed:", e)

if not connected:
    sys.exit(1)

# Upload the DB with Block 57
print("Uploading latest DB with Block 57 to VPS...")
sftp = c.open_sftp()
sftp.put("zerodha_trader.db", "/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_trader.db")
sftp.close()

vps_exec_script = """
import sys
sys.path.insert(0, '/root/BHARAT-SYSTEMS/ZERODHA-OS')
import db
from kite_executor import kite_executor
import block_manager as bm
import json

db.load_secrets()
kite_executor.load_session_from_db()

print('=== EXECUTING TRADE FROM WHITELISTED VPS IP (5.75.250.104) ===')
# Execute Call Wing (Strike 155 -> 23000 CE SELL + 23500 CE HEDGE_BUY)
res = bm.execute_strike(155)
print('Execution Result:', json.dumps(res, indent=2, default=str))

print('\\n=== LIVE POSITIONS ON KITE BROKER ===')
try:
    pos = kite_executor.kite.positions()
    net = pos.get('net', [])
    for p in net:
        if p.get('quantity') != 0:
            print(f"LIVE: {p.get('tradingsymbol')} | Qty: {p.get('quantity')} | BuyPrice: {p.get('buy_price')} | SellPrice: {p.get('sell_price')} | LTP: {p.get('last_price')} | PnL: {p.get('pnl')}")
except Exception as e:
    print('Positions error:', e)
"""

sftp = c.open_sftp()
with sftp.file("/root/BHARAT-SYSTEMS/ZERODHA-OS/run_exec.py", "w") as f:
    f.write(vps_exec_script)
sftp.close()

_, stdout, stderr = c.exec_command("/root/BHARAT-SYSTEMS/ZERODHA-OS/venv/bin/python3 /root/BHARAT-SYSTEMS/ZERODHA-OS/run_exec.py")
print(stdout.read().decode('utf-8', errors='replace'))
err = stderr.read().decode('utf-8', errors='replace')
if err:
    print("STDERR:", err)

# Sync DB back to local
sftp = c.open_sftp()
sftp.get("/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_trader.db", "zerodha_trader.db")
sftp.close()

c.close()
print("Trade execution on VPS complete and local DB synced!")
