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

script = """
import os
print("=== JOURNALCTL FROM 15:00 IST (09:30 UTC) ===")
os.system("journalctl -u zerodha_engine.service --since '09:30:00' --until '09:45:00' --no-pager | grep -E 'AUTO-ENTRY|RE-ENTRY|3PM|CONTINUED|CLOSED|EXECUTOR|Triggering|ORDER' | head -n 100")
"""

sftp = c.open_sftp()
f = sftp.file('/tmp/fetch_journal_grep.py', 'w')
f.write(script)
f.close()
sftp.close()

stdin, stdout, stderr = c.exec_command('python3 /tmp/fetch_journal_grep.py')
print(stdout.read().decode('utf-8', errors='replace'))
print(stderr.read().decode('utf-8', errors='replace'))
c.close()
