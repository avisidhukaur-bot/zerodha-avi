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

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(VPS_IP, username=VPS_USER, password=VPS_PASSWORD, timeout=10)

remote_lines = [
    "import os, sys",
    "sys.path.insert(0, '/root/BHARAT-SYSTEMS/ZERODHA-OS')",
    "from kite_executor import kite_executor",
    "import sqlite3",
    "kite_executor.ensure_logged_in()",
    "k = kite_executor.kite",
    "",
    "print('=== LIVE KITE NET POSITIONS ===')",
    "try:",
    "    pos = k.positions().get('net', [])",
    "    for p in pos:",
    "        if p.get('quantity') != 0:",
    "            print(f\"{p.get('tradingsymbol')} | Qty: {p.get('quantity')} | Buy: {p.get('buy_price')} | Sell: {p.get('sell_price')} | LTP: {p.get('last_price')} | PnL: Rs {p.get('pnl', 0):,.2f}\")",
    "except Exception as e:",
    "    print('Pos error:', e)",
    "",
    "print('\\n=== TODAY LATEST KITE ORDERS ===')",
    "try:",
    "    orders = k.orders()",
    "    for o in orders[-10:]:",
    "        print(f\"{o.get('order_timestamp')} | {o.get('tradingsymbol')} | {o.get('transaction_type')} | Qty: {o.get('quantity')} | AvgPrice: {o.get('average_price')} | Status: {o.get('status')}\")",
    "except Exception as e:",
    "    print('Order fetch error:', e)",
    "",
    "print('\\n=== DATABASE BLOCKS & STRIKES ===')",
    "conn = sqlite3.connect('/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_trader.db')",
    "conn.row_factory = sqlite3.Row",
    "cur = conn.cursor()",
    "print('--- BLOCKS ---')",
    "for b in cur.execute('SELECT * FROM blocks WHERE status=\"ACTIVE\"').fetchall():",
    "    print(dict(b))",
    "print('--- STRIKES OPEN OR ORPHAN ---')",
    "for s in cur.execute('SELECT * FROM strikes WHERE status=\"OPEN\"').fetchall():",
    "    print(dict(s))",
    "conn.close()"
]

remote_content = "\n".join(remote_lines) + "\n"

sftp = c.open_sftp()
f = sftp.file('/tmp/check_os_trade_status.py', 'w')
f.write(remote_content)
f.close()
sftp.close()

stdin, stdout, stderr = c.exec_command("python3 /tmp/check_os_trade_status.py")
print(stdout.read().decode('utf-8', errors='replace'))
print(stderr.read().decode('utf-8', errors='replace'))
c.close()
