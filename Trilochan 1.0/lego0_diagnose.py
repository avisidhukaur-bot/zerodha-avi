"""
lego0_diagnose.py — Zerodha Option Selling App | VPS Live Diagnosis
Connects to VPS via SSH to run system diagnostics for the Zerodha Option Selling services.
Usage: python lego0_diagnose.py
"""
import paramiko
import os
import sys

# Fix terminal encoding issues on Windows
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ── Load secrets ──────────────────────────────────────────────
secrets = {}
secrets_path = os.path.join(os.path.dirname(__file__), "secrets.txt")
if not os.path.exists(secrets_path):
    print(f"[ERROR] secrets.txt not found at {secrets_path}. Please create it first.")
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

if not VPS_PASSWORD:
    print("[ERROR] VPS_PASSWORD not found in secrets.txt.")
    sys.exit(1)

# ── SSH connect ───────────────────────────────────────────────
print(f"\n{'='*60}")
print(f"  LEGO 0 — ZERODHA OPTION SELLING VPS DIAGNOSIS")
print(f"  Connecting to {VPS_USER}@{VPS_IP} ...")
print(f"{'='*60}\n")

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    client.connect(VPS_IP, username=VPS_USER, password=VPS_PASSWORD, timeout=15)
    print("✅ SSH Connected Successfully!\n")
except Exception as e:
    print(f"❌ SSH Connection Failed: {e}")
    sys.exit(1)

def run(cmd, label):
    print(f"{'─'*60}")
    print(f"📋 {label}")
    print(f"{'─'*60}")
    _, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode(errors='replace').strip()
    err = stderr.read().decode(errors='replace').strip()
    if out:
        print(out)
    else:
        print("(No output)")
    if err:
        print(f"[STDERR] {err}")
    print()

# 1. Check BHARAT-SYSTEMS folder on VPS
run("ls -la /root/BHARAT-SYSTEMS/", "DIRECTORIES IN BHARAT-SYSTEMS")

# 2. Check Zerodha directory specifically
run("ls -la /root/BHARAT-SYSTEMS/ZERODHA-OS/ 2>/dev/null || echo 'Zerodha directory not found yet'", "ZERODHA-OS DIRECTORY CONTENTS")

# 3. Check running Zerodha/Kite python processes
run("ps aux | grep -iE 'zerodha|kite' | grep -v grep", "ZERODHA OS PYTHON PROCESSES")

# 4. Check service status
run("systemctl status zerodha_engine.service zerodha_dashboard.service 2>/dev/null || echo 'Services not installed yet'", "SYSTEMD SERVICES STATUS")

# 5. Check port 9007
run("ss -tlnp | grep -E '900[0-9]'", "PORTS 9000-9009 STATUS (Including 9007)")

# 6. Check VPN / current public IP
run("curl -s https://api.ipify.org", "CURRENT PUBLIC IP (Must be 5.75.250.104)")

# 7. Last 30 lines of Zerodha engine log
run("tail -30 /root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_engine.log 2>/dev/null || echo 'Log file not found yet'", "ZERODHA ENGINE LOG (Last 30 lines)")

# 8. Journalctl logs for services
run("journalctl -u zerodha_dashboard.service -n 50 --no-pager", "ZERODHA DASHBOARD SERVICE SYSTEMD LOGS")
run("journalctl -u zerodha_engine.service -n 50 --no-pager", "ZERODHA ENGINE SERVICE SYSTEMD LOGS")

client.close()
print(f"{'='*60}")
print("✅ DIAGNOSIS COMPLETE")
print(f"{'='*60}\n")
