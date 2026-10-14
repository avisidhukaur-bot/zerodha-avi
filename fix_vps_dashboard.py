import paramiko
import sys
import time

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

secrets = {}
with open('secrets.txt', encoding='utf-8') as f:
    for l in f:
        if '=' in l and not l.startswith('#'):
            k, v = l.strip().split('=', 1)
            secrets[k.strip()] = v.strip()

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(secrets['VPS_IP'], username=secrets['VPS_USER'], password=secrets['VPS_PASSWORD'], timeout=15)

def run(cmd):
    print("=== RUNNING:", cmd)
    _, out, err = c.exec_command(cmd)
    stdout_str = out.read().decode('utf-8', errors='replace')
    stderr_str = err.read().decode('utf-8', errors='replace')
    if stdout_str:
        print(stdout_str)
    if stderr_str:
        print("ERR:", stderr_str)

# 1. Write .streamlit/config.toml
toml_content = """[server]
port = 9007
headless = true
enableCORS = false
enableXsrfProtection = false
address = "0.0.0.0"

[browser]
serverAddress = "5.75.250.104"
serverPort = 9007
gatherUsageStats = false
"""

sftp = c.open_sftp()
try:
    sftp.mkdir("/root/BHARAT-SYSTEMS/ZERODHA-OS/.streamlit")
except Exception:
    pass

with sftp.file("/root/BHARAT-SYSTEMS/ZERODHA-OS/.streamlit/config.toml", "w") as f:
    f.write(toml_content)

# 2. Update service file
service_content = """[Unit]
Description=Zerodha OS Streamlit Dashboard (Port 9007)
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/BHARAT-SYSTEMS/ZERODHA-OS
ExecStart=/root/BHARAT-SYSTEMS/ZERODHA-OS/venv/bin/streamlit run /root/BHARAT-SYSTEMS/ZERODHA-OS/app.py --server.port 9007 --server.address 0.0.0.0 --server.headless true --server.enableCORS false --server.enableXsrfProtection false --browser.gatherUsageStats false
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
"""

with sftp.file("/etc/systemd/system/zerodha_dashboard.service", "w") as f:
    f.write(service_content)

sftp.close()

run("systemctl daemon-reload && systemctl restart zerodha_dashboard.service")
time.sleep(3)
run("systemctl status zerodha_dashboard.service --no-pager")
run("journalctl -u zerodha_dashboard.service -n 25 --no-pager")

c.close()
print("Fix script completed successfully.")
