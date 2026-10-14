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
    "import sqlite3, os",
    "conn = sqlite3.connect('/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_trader.db')",
    "conn.row_factory = sqlite3.Row",
    "cur = conn.cursor()",
    "print('=== BLOCKS ===')",
    "for b in cur.execute('SELECT * FROM blocks').fetchall():",
    "    print(dict(b))",
    "print('=== STRIKES ===')",
    "for s in cur.execute('SELECT * FROM strikes').fetchall():",
    "    print(dict(s))",
    "print('=== LEGS ===')",
    "for l in cur.execute('SELECT * FROM legs').fetchall():",
    "    print(dict(l))",
    "print('=== TODAY ORDERS VIA KITE ===')",
    "try:",
    "    import sys",
    "    sys.path.insert(0, '/root/BHARAT-SYSTEMS/ZERODHA-OS')",
    "    from kite_executor import kite_executor",
    "    kite_executor.ensure_logged_in()",
    "    orders = kite_executor.kite.orders()",
    "    for o in orders:",
    "        print(o.get('order_timestamp'), o.get('tradingsymbol'), o.get('transaction_type'), o.get('quantity'), o.get('average_price'), o.get('status'), o.get('status_message'))",
    "except Exception as e:",
    "    print('Kite order check error:', e)"
]

remote_content = "\n".join(remote_lines) + "\n"

sftp = c.open_sftp()
f = sftp.file('/tmp/dump_all_details.py', 'w')
f.write(remote_content)
f.close()
sftp.close()

stdin, stdout, stderr = c.exec_command("python3 /tmp/dump_all_details.py")
print(stdout.read().decode('utf-8', errors='replace'))
print(stderr.read().decode('utf-8', errors='replace'))

stdin2, stdout2, stderr2 = c.exec_command("grep -i -C 3 '22400' /root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_engine.log | tail -n 30")
print("=== GREP LOG FOR 22400 ===")
print(stdout2.read().decode('utf-8', errors='replace'))

c.close()
