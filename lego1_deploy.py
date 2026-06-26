"""
lego1_deploy.py — Zerodha Option Selling App | VPS SSH Deployment Script
Uploads codebase to VPS, wipes old installation, and restarts services fresh.
Usage: python lego1_deploy.py
"""
import paramiko
import os
import sys
import time

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ── Load secrets ──────────────────────────────────────────────
secrets = {}
secrets_path = os.path.join(os.path.dirname(__file__), "secrets.txt")
if not os.path.exists(secrets_path):
    print(f"[ERROR] secrets.txt not found at {secrets_path}.")
    sys.exit(1)

with open(secrets_path, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            secrets[k.strip()] = v.strip()

VPS_IP       = secrets.get("VPS_IP",       "5.75.250.104")
VPS_USER     = secrets.get("VPS_USER",     "root")
VPS_PASSWORD = secrets.get("VPS_PASSWORD", "")

# ── Files list to deploy ──────────────────────────────────────
LOCAL_DIR  = os.path.dirname(os.path.abspath(__file__))
REMOTE_DIR = "/root/BHARAT-SYSTEMS/ZERODHA-OS"

FILES = [
    "config.py",
    "db.py",
    "block_manager.py",
    "kite_executor.py",
    "pnl_engine.py",
    "telegram_bot.py",
    "main.py",
    "utils.py",
    "app.py",
    "requirements.txt",
    "secrets.txt",
    "ZERODHA_SETUP_GUIDE.md",
    "memory.md",
]

print("=" * 60)
print("  LEGO 1 — ZERODHA OPTION SELLING DEPLOY")
print(f"  Target: {VPS_USER}@{VPS_IP}:{REMOTE_DIR}")
print("  Dashboard Port: 9007")
print("=" * 60)

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    client.connect(VPS_IP, username=VPS_USER, password=VPS_PASSWORD, timeout=15)
    sftp = client.open_sftp()
    print("✅ Connected to VPS via SSH & SFTP!\n")
except Exception as e:
    print(f"❌ SSH Connection Failed: {e}")
    sys.exit(1)

# ── SSH Run command helper ────────────────────────────────────
def run_ssh(cmd, label):
    print(f"\n[{label}]")
    _, out, err = client.exec_command(cmd)
    o = out.read().decode(errors='replace').strip()
    e = err.read().decode(errors='replace').strip()
    if o: print(o)
    if e and "warning" not in e.lower() and "created a tmpdir" not in e.lower():
        print(f"STDERR: {e}")

# ── STEP 0: Stop old services ─────────
print("[0/3] Stopping old Zerodha services...")
run_ssh("systemctl stop zerodha_engine.service zerodha_dashboard.service 2>/dev/null || true", "Stopping old services")

# ── Create remote directory ───────────────────────────────────
try:
    sftp.mkdir("/root/BHARAT-SYSTEMS")
except Exception:
    pass
try:
    sftp.mkdir(REMOTE_DIR)
    print(f"Created remote directory {REMOTE_DIR}")
except Exception:
    pass

# ── STEP 1: Upload files ──────────────────────────────────────
print("\n[1/3] Uploading codebase to VPS...")
for fname in FILES:
    local  = os.path.join(LOCAL_DIR, fname)
    remote = f"{REMOTE_DIR}/{fname}"
    if os.path.exists(local):
        if fname == "secrets.txt":
            try:
                sftp.stat(remote)
                print(f"  [--] {fname} already exists on VPS, skipping to preserve remote secrets")
                continue
            except IOError:
                pass
        sftp.put(local, remote)
        print(f"  [UP] {fname} -> {remote}")
    else:
        print(f"  [--] {fname} not found locally, skipping")
sftp.close()

# ── Install dependencies ──────────────────────────────────────
run_ssh(f"pip3 install -r {REMOTE_DIR}/requirements.txt", "Installing Dependencies on VPS")

# ── STEP 2: Create systemd service files ─────────────────────
engine_service_code = f"""[Unit]
Description=Zerodha Option Selling Engine
After=network.target

[Service]
Type=simple
WorkingDirectory={REMOTE_DIR}
ExecStart=/usr/bin/python3 -u main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
"""

dash_service_code = f"""[Unit]
Description=Zerodha Option Selling Dashboard
After=network.target

[Service]
Type=simple
WorkingDirectory={REMOTE_DIR}
ExecStart=/usr/local/bin/streamlit run app.py --server.port 9007 --server.address 0.0.0.0
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
"""

print("\n[2/3] Writing systemd service files...")

# Write engine service via heredoc to avoid quoting issues
write_engine_cmd = f"cat > /etc/systemd/system/zerodha_engine.service << 'SVCEOF'\n{engine_service_code}\nSVCEOF"
client.exec_command(write_engine_cmd)
time.sleep(1)

# Write dashboard service
write_dash_cmd = f"cat > /etc/systemd/system/zerodha_dashboard.service << 'SVCEOF'\n{dash_service_code}\nSVCEOF"
client.exec_command(write_dash_cmd)
time.sleep(1)

run_ssh("systemctl daemon-reload", "Reloading systemd daemon")
run_ssh("systemctl enable zerodha_engine.service zerodha_dashboard.service", "Enabling Services")

# ── STEP 3: Start services ────────────────────────────────────
print("\nStarting Zerodha Option Selling services...")
run_ssh("systemctl start zerodha_engine.service && echo 'zerodha_engine started'", "Starting Engine service")
run_ssh("systemctl start zerodha_dashboard.service && echo 'zerodha_dashboard started'", "Starting Dashboard service")

time.sleep(5)

# ── Verify ───────────────────────────────────────────────────
print("\n[3/3] Verifying services state...")
run_ssh("systemctl is-active zerodha_engine.service zerodha_dashboard.service", "Services active check")
run_ssh("ss -tlnp | grep 9007", "Port 9007 listening check")

client.close()
print("\n" + "=" * 60)
print("  ZERODHA OS DEPLOYMENT SUCCESSFUL!")
print("  Dashboard: http://5.75.250.104:9007")
print("=" * 60)
