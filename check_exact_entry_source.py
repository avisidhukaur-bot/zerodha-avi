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

stdin, stdout, stderr = c.exec_command('grep -E "22700|22200|AUTO-ENTRY|PENDING-ENTRY" /root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_engine.log | tail -n 40')
print("=== LOG ENTRIES FOR 22700/22200 PE ===")
print(stdout.read().decode('utf-8', errors='replace'))

stdin2, stdout2, stderr2 = c.exec_command('python3 -c "import kite_executor as ke; [print(o) for o in ke.kite_executor.get_all_orders() if \'22700\' in str(o) or \'22200\' in str(o)]"')
print("\n=== BROKER ORDER BOOK DETAILS ===")
print(stdout2.read().decode('utf-8', errors='replace'))

c.close()
