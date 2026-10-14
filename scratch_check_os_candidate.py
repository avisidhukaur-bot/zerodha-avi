import paramiko
import sys
import json

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
secrets = {}
with open('secrets.txt', encoding='utf-8') as f:
    for line in f:
        if line.strip() and not line.startswith('#') and '=' in line:
            k, v = line.strip().split('=', 1)
            secrets[k.strip()] = v.strip()

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(secrets['VPS_IP'], username=secrets['VPS_USER'], password=secrets['VPS_PASSWORD'], timeout=10)

script = """import sys
sys.path.append('/root/BHARAT-SYSTEMS/ZERODHA-OS')
import db
from kite_executor import kite_executor
import os_engine

db.load_secrets()
kite_executor.load_session_from_db()
kite_executor.ensure_logged_in()

spot = kite_executor.get_nifty_spot()
print(f"=== CURRENT NIFTY SPOT: {spot} ===")

expiry = "2026-10-27"
target_prem = 160.0
step_size = "STRICT 500"

print("\\n--- HUNTING CE STRIKE ---")
ce_res = os_engine.hunt_os_strike(
    option_type="CE",
    expiry_date=expiry,
    target_premium=target_prem,
    hedge_dist=500,
    sl_multiplier=1.382,
    step_size=step_size
)
print("CE Candidate Result:")
print(ce_res)

print("\\n--- HUNTING PE STRIKE ---")
pe_res = os_engine.hunt_os_strike(
    option_type="PE",
    expiry_date=expiry,
    target_premium=target_prem,
    hedge_dist=500,
    sl_multiplier=1.382,
    step_size=step_size
)
print("PE Candidate Result:")
print(pe_res)

print("\\n--- PREVIEW OS SETUP (BOTH SIDES) ---")
preview_res = os_engine.preview_os_setup(
    expiry_date=expiry,
    target_premium=target_prem,
    step_size=step_size,
    lots=3
)
print("Preview Result:")
print(preview_res)

# Check occupied strikes
occupied = os_engine.get_occupied_strikes(expiry)
print("\\nOccupied Strikes currently:", occupied)
"""

sftp = client.open_sftp()
with sftp.file('/tmp/check_os_candidate.py', 'wb') as f:
    f.write(script.replace('\r\n', '\n').encode('utf-8'))
sftp.close()

_, stdout, stderr = client.exec_command('python3 /tmp/check_os_candidate.py')
print("=== STDOUT ===")
print(stdout.read().decode('utf-8', errors='replace'))
err = stderr.read().decode('utf-8', errors='replace')
if err:
    print("=== STDERR ===")
    print(err)

client.close()
