import paramiko, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
with open(r'c:\Users\Dell\Desktop\cheenna zerodha\secrets.txt', encoding='utf-8', errors='ignore') as f:
    sec = dict(line.strip().split('=', 1) for line in f if '=' in line and not line.startswith('#'))

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(sec['VPS_IP'], username=sec['VPS_USER'], password=sec['VPS_PASSWORD'])

py_code = """import sys
sys.path.insert(0, '/root/BHARAT-SYSTEMS/ZERODHA-OS')
from kite_executor import kite_executor
import db

kite_executor.access_token = None
kite_executor.is_logged_in = False
success = kite_executor.login()
print(f"Login Result: {success}")
if success:
    db.set("kite_login_status", "OK")
    print(f"Profile: {kite_executor.kite.profile().get('user_name')}")
else:
    print("Headless login could not authenticate. Manual token needed.")
"""

sftp = c.open_sftp()
with sftp.file('/root/BHARAT-SYSTEMS/ZERODHA-OS/test_headless_login.py', 'w') as f:
    f.write(py_code)
sftp.close()

stdin, stdout, stderr = c.exec_command("python3 /root/BHARAT-SYSTEMS/ZERODHA-OS/test_headless_login.py")
print(stdout.read().decode('utf-8', errors='replace'))
print(stderr.read().decode('utf-8', errors='replace'))
c.close()

