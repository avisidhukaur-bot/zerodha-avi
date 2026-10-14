import paramiko
import sys
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

script = r'''
import subprocess

print("=== 1. SEARCHING 23700 / 24200 IN ALL SYSTEMD LOGS TODAY ===")
cmd1 = "journalctl --since '2026-09-17 09:00:00' --no-pager | grep -iE '23700|24200|placed|order|reenter|execute' | head -n 40"
print(subprocess.getoutput(cmd1))

print("\n=== 2. KITE LOGS / ORDERS VIA PYTHON EXECUTOR LOGS ===")
cmd2 = "journalctl -u zerodha_dashboard.service --since '2026-09-17 09:15:00' --no-pager"
print(subprocess.getoutput(cmd2))
'''

sftp = c.open_sftp()
with sftp.file('/root/BHARAT-SYSTEMS/ZERODHA-OS/temp_find_order_source.py', 'w') as f:
    f.write(script)
sftp.close()

stdin, stdout, stderr = c.exec_command("python3 /root/BHARAT-SYSTEMS/ZERODHA-OS/temp_find_order_source.py")
print(stdout.read().decode('utf-8', errors='replace'))
err = stderr.read().decode('utf-8', errors='replace')
if err:
    print("STDERR:", err)

c.exec_command("rm -f /root/BHARAT-SYSTEMS/ZERODHA-OS/temp_find_order_source.py")
c.close()
