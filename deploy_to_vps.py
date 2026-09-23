import os
import sys
import paramiko

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

secrets = {}
secrets_path = os.path.join(os.path.dirname(__file__), "secrets.txt")
with open(secrets_path, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            secrets[k.strip()] = v.strip()

vps_ip = secrets.get("VPS_IP", "5.75.250.104")
vps_user = secrets.get("VPS_USER", "root")
vps_pass = secrets.get("VPS_PASSWORD", "")

print(f"Connecting to VPS at {vps_ip} as {vps_user}...")
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(vps_ip, username=vps_user, password=vps_pass, timeout=20)

sftp = client.open_sftp()

files_to_deploy = [
    "config.py",
    "utils.py",
    "db.py",
    "kite_executor.py",
    "pnl_engine.py",
    "block_manager.py",
    "regime_engine.py",
    "os_engine.py",
    "main.py",
    "app.py",
    "telegram_bot.py",
    "commodity_engine.py",
    "commodity_executor.py",
    "equity_200dma_engine.py",
    "test_os_engine.py",
    "test_os_strike_shield.py",
    "test_v5_old_and_gold.py",
    "test_strict_regime_execution_guard.py",
    "OS_OPTION_SELLING_PROPOSAL.html",
]

local_base = os.path.dirname(os.path.abspath(__file__))
remote_base = "/root/BHARAT-SYSTEMS/ZERODHA-OS"

print("--- UPLOADING UPDATED FILES VIA SFTP ---")
for fn in files_to_deploy:
    local_path = os.path.join(local_base, fn)
    if os.path.exists(local_path):
        remote_path = f"{remote_base}/{fn}"
        print(f"Uploading {fn} -> {remote_path}...")
        sftp.put(local_path, remote_path)
    else:
        print(f"Skipping {fn} (not found locally)")
print("All files uploaded successfully!")

sftp.close()

def run_cmd(cmd, desc):
    print(f"\n=======================================================\n  {desc}\n=======================================================")
    _, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode(errors='replace')
    err = stderr.read().decode(errors='replace')
    if out:
        print(out)
    if err:
        print("STDERR:", err)

# 1. Run unit tests on VPS
run_cmd(f"cd {remote_base} && python3 -m unittest test_os_engine.py test_os_strike_shield.py test_v5_old_and_gold.py", "RUN UNIT TESTS ON VPS")

# 2. Restart services
run_cmd("systemctl restart zerodha_engine && systemctl restart zerodha_dashboard", "RESTART SYSTEMD SERVICES")

# 3. Check service statuses
run_cmd("systemctl status zerodha_engine --no-pager -l", "CHECK ENGINE STATUS")
run_cmd("systemctl status zerodha_dashboard --no-pager -l", "CHECK DASHBOARD STATUS")

# 4. Check listening port 9007
run_cmd("ss -tulpn | grep 9007", "CHECK PORT 9007 LISTENING")

client.close()
print("\nDeployment and VPS verification complete!")
