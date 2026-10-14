import paramiko
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

secrets = {}
with open('secrets.txt', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            secrets[k.strip()] = v.strip()

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(secrets['VPS_IP'], username=secrets['VPS_USER'], password=secrets['VPS_PASSWORD'], timeout=15)

def run(cmd):
    stdin, stdout, stderr = client.exec_command(cmd)
    return stdout.read().decode(errors='replace')

print("=== 1. SEARCH FOR BLOCK 80 IN LOGS ===")
print(run("grep -i 'Block #80\\|Block 80\\|M1' /root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_engine.log | tail -n 30"))

print("\n=== 2. JOURNALCTL AROUND 04:15 UTC (09:45 IST) ===")
print(run("journalctl -u zerodha_dashboard.service --since '04:10:00' --until '04:25:00' --no-pager | tail -n 40"))

print("\n=== 3. JOURNALCTL ENGINE AROUND 04:15 UTC ===")
print(run("journalctl -u zerodha_engine.service --since '04:10:00' --until '04:25:00' --no-pager | tail -n 40"))

print("\n=== 4. HOW PENDING CE WING IS HANDLED IN OS_ENGINE ===")
print(run("grep -i -C 3 'autonomous' /root/BHARAT-SYSTEMS/ZERODHA-OS/os_engine.py /root/BHARAT-SYSTEMS/ZERODHA-OS/block_manager.py | head -n 30"))

client.close()
