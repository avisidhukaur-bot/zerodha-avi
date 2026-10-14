import paramiko
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

secrets = {}
with open('secrets.txt', encoding='utf-8') as f:
    for line in f:
        if line.strip() and '=' in line and not line.startswith('#'):
            k, v = line.strip().split('=', 1)
            secrets[k.strip()] = v.strip()

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(secrets['VPS_IP'], username=secrets['VPS_USER'], password=secrets['VPS_PASSWORD'], timeout=15)

script = """
import sys, json
sys.path.insert(0, '/root/BHARAT-SYSTEMS/ZERODHA-OS')
import os_engine as oe

res = oe.inspect_os_candidates('27-Oct-2026')
print('=== INSPECTION RESULT ===')
print('Action:', res.get('action'))
print('Status Msg:', res.get('status_msg'))
print('CE Qualified:', res.get('ce_qualified'))
if res.get('ce'):
    ce = res['ce']
    print('CE Strike:', ce.get('sell_strike'), 'LTP:', ce.get('sell_ltp'), 'Yest:', ce.get('yesterday_price'), 'Decay%:', ce.get('decay_pct'))
print('PE Qualified:', res.get('pe_qualified'))
if res.get('pe'):
    pe = res['pe']
    print('PE Strike:', pe.get('sell_strike'), 'LTP:', pe.get('sell_ltp'), 'Yest:', pe.get('yesterday_price'), 'Decay%:', pe.get('decay_pct'))
"""

sftp = c.open_sftp()
with sftp.file('/tmp/do_inspect.py', 'w') as f:
    f.write(script)
sftp.close()

stdin, stdout, stderr = c.exec_command('python3 /tmp/do_inspect.py')
out = stdout.read().decode('utf-8', errors='replace')
err = stderr.read().decode('utf-8', errors='replace')
print(out)
if err:
    print("STDERR:", err)
c.close()
