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

kite_executor.load_session_from_db()
print(f"Kite Logged In Flag: {kite_executor.is_logged_in}")
try:
    p = kite_executor.kite.profile()
    print(f"User Profile: {p.get('user_name')} | ID: {p.get('user_id')}")
    print("KITE_TOKEN_STATUS: VALID")
except Exception as e:
    print(f"KITE_TOKEN_STATUS: EXPIRED_OR_ERROR -> {e}")
"""

sftp = c.open_sftp()
with sftp.file('/root/BHARAT-SYSTEMS/ZERODHA-OS/check_morning_token_remote.py', 'w') as f:
    f.write(py_code)
sftp.close()

stdin, stdout, stderr = c.exec_command("python3 /root/BHARAT-SYSTEMS/ZERODHA-OS/check_morning_token_remote.py")
print(stdout.read().decode('utf-8', errors='replace'))
print(stderr.read().decode('utf-8', errors='replace'))
c.close()
