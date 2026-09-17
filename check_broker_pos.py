import paramiko
import sys
import os

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
secrets = {}
with open('secrets.txt', encoding='utf-8') as f:
    for l in f:
        if '=' in l and not l.startswith('#'):
            k, v = l.strip().split('=', 1)
            secrets[k.strip()] = v.strip()

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(secrets['VPS_IP'], username=secrets['VPS_USER'], password=secrets['VPS_PASSWORD'], timeout=10)

remote_lines = [
    "import os, sys",
    "sys.path.insert(0, '/root/BHARAT-SYSTEMS/ZERODHA-OS')",
    "import kite_executor as ke",
    "",
    "print('=== LIVE BROKER POSITIONS (via ke.kite_executor) ===')",
    "pos = ke.kite_executor.get_positions()",
    "print(f'Total positions found: {len(pos)}')",
    "for p in pos:",
    "    if p.get('quantity') != 0:",
    "        print(f\"Symbol: {p['tradingsymbol']} | Qty: {p['quantity']} | Buy: {p.get('buy_price')} | Sell: {p.get('sell_price')} | PnL: ₹{p.get('pnl'):,.2f} | LTP: ₹{p.get('last_price'):.2f}\")"
]

remote_content = "\n".join(remote_lines) + "\n"

sftp = c.open_sftp()
f = sftp.file('/tmp/broker_pos_check.py', 'w')
f.write(remote_content)
f.close()
sftp.close()

stdin, stdout, stderr = c.exec_command("python3 /tmp/broker_pos_check.py")
print(stdout.read().decode('utf-8', errors='replace'))
print(stderr.read().decode('utf-8', errors='replace'))
c.close()
