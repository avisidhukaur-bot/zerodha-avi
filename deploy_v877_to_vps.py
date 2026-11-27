# -*- coding: utf-8 -*-
import paramiko
import sys
import time

secrets = {}
with open(r'c:\Users\Dell\Desktop\cheenna zerodha\secrets.txt', encoding='utf-8', errors='replace') as f:
    for line in f:
        line = line.strip()
        if '=' in line and not line.startswith('#'):
            k, v = line.split('=', 1)
            secrets[k.strip()] = v.strip()

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(secrets['VPS_IP'], username=secrets['VPS_USER'], password=secrets['VPS_PASSWORD'], timeout=20)

sftp = client.open_sftp()
files_to_sync = [
    ('kite_executor.py', '/root/BHARAT-SYSTEMS/ZERODHA-OS/kite_executor.py'),
    ('block_manager.py', '/root/BHARAT-SYSTEMS/ZERODHA-OS/block_manager.py'),
    ('GEMINI.md', '/root/BHARAT-SYSTEMS/ZERODHA-OS/GEMINI.md'),
    ('memory.md', '/root/BHARAT-SYSTEMS/ZERODHA-OS/memory.md'),
    ('PRODUCT_UPGRADATION_MARKETABLE_LIMIT_CHASER_BLUEPRINT.md', '/root/BHARAT-SYSTEMS/ZERODHA-OS/PRODUCT_UPGRADATION_MARKETABLE_LIMIT_CHASER_BLUEPRINT.md'),
    ('test_marketable_limit_chaser.py', '/root/BHARAT-SYSTEMS/ZERODHA-OS/test_marketable_limit_chaser.py')
]

for local_f, remote_f in files_to_sync:
    print(f"Uploading {local_f} -> {remote_f}...")
    sftp.put(local_f, remote_f)
sftp.close()
print("All files synced to VPS.")

cmd = '''
cd /root/BHARAT-SYSTEMS/ZERODHA-OS
find . -name "*.pyc" -delete
find . -name "__pycache__" -type d -exec rm -rf {} +
python3 -m py_compile kite_executor.py block_manager.py
python3 test_marketable_limit_chaser.py
systemctl restart zerodha_engine.service
systemctl restart zerodha_dashboard.service
sleep 4
systemctl is-active zerodha_engine.service zerodha_dashboard.service
'''

stdin, stdout, stderr = client.exec_command(cmd)
print("VPS DEPLOY OUTPUT:\n", stdout.read().decode('utf-8', errors='replace'))
print("ERRORS:\n", stderr.read().decode('utf-8', errors='replace'))
client.close()
