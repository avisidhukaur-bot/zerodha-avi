import sqlite3
import paramiko
import os
import sys

# Fix Windows terminal encoding
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

print("=== 1. LOCAL DATABASE INSPECTION (zerodha_trader.db) ===")
local_db = os.path.join(os.path.dirname(__file__), "zerodha_trader.db")
if os.path.exists(local_db):
    conn = sqlite3.connect(local_db)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM blocks")
    blocks = c.fetchall()
    print(f"Local Blocks count: {len(blocks)}")
    for b in blocks:
        d = dict(b)
        print(f"  Block #{d.get('block_number')} (ID: {d.get('block_id')}):")
        print(f"    - Expiry Date: {d.get('expiry_date')}")
        print(f"    - Side: {d.get('side_type')}")
        print(f"    - Master Anchor Price: {d.get('master_anchor_price')}")
        print(f"    - Current Regime: {d.get('current_regime')}")
        print(f"    - Regime Buffer: {d.get('regime_buffer')}")
        print(f"    - Status: {d.get('status')}")
        print(f"    - Auto Regime Enabled: {d.get('auto_regime_enabled')}")

    c.execute("SELECT * FROM strikes")
    strikes = c.fetchall()
    print(f"\nLocal Strikes count: {len(strikes)}")
    for s in strikes:
        d = dict(s)
        print(f"  Strike ID {d.get('strike_id')} | Block {d.get('block_id')} | {d.get('strike_price')} {d.get('option_type')} ({d.get('leg_type')}) | Anchor: {d.get('anchor_price')} | Status: {d.get('status')} | Lots: {d.get('lots')}")

    c.execute("SELECT * FROM settings")
    settings = c.fetchall()
    print("\nLocal Settings:")
    for row in settings:
        k, v = row['key'], row['value']
        if "secret" in k.lower() or "pass" in k.lower() or "token" in k.lower() or "totp" in k.lower():
            v = "***"
        print(f"  {k} = {v}")
    conn.close()
else:
    print("Local DB not found.")

print("\n=== 2. VPS LIVE DATABASE INSPECTION ===")
secrets = {}
secrets_path = os.path.join(os.path.dirname(__file__), "secrets.txt")
with open(secrets_path, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            secrets[k.strip()] = v.strip()

VPS_IP = secrets.get("VPS_IP", "5.75.250.104")
VPS_USER = secrets.get("VPS_USER", "root")
VPS_PASSWORD = secrets.get("VPS_PASSWORD", "")

try:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(VPS_IP, username=VPS_USER, password=VPS_PASSWORD, timeout=15)

    vps_inspect_code = """
import sqlite3
conn = sqlite3.connect('/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_trader.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

print("--- VPS BLOCKS ---")
c.execute("SELECT * FROM blocks")
blocks = c.fetchall()
for b in blocks:
    d = dict(b)
    print(f"Block #{d.get('block_number')} (ID: {d.get('block_id')}): Master Anchor = {d.get('master_anchor_price')} | Expiry = {d.get('expiry_date')} | Regime = {d.get('current_regime')} | Side = {d.get('side_type')} | Status = {d.get('status')} | Unit = {d.get('anchor_unit_name')}")

print("\\n--- VPS STRIKES ---")
c.execute("SELECT * FROM strikes")
strikes = c.fetchall()
for s in strikes:
    d = dict(s)
    print(f"Strike {d.get('strike_price')} {d.get('option_type')} ({d.get('leg_type')}) | Anchor = {d.get('anchor_price')} | Status = {d.get('status')} | Lots = {d.get('lots')} | SL = {d.get('sl_price')}")

print("\\n--- VPS RECENT TRADES ---")
c.execute("SELECT * FROM trades ORDER BY trade_id DESC LIMIT 10")
trades = c.fetchall()
for t in trades:
    d = dict(t)
    print(f"{d.get('timestamp')} | Action: {d.get('action')} | Price: {d.get('price')} | Lots: {d.get('lots')} | Status: {d.get('order_status')}")

conn.close()
"""
    sftp = client.open_sftp()
    with sftp.file("/root/BHARAT-SYSTEMS/ZERODHA-OS/quick_inspect.py", "w") as f:
        f.write(vps_inspect_code)
    sftp.close()

    _, stdout, stderr = client.exec_command("python3 /root/BHARAT-SYSTEMS/ZERODHA-OS/quick_inspect.py")
    print(stdout.read().decode(errors='replace'))
    err = stderr.read().decode(errors='replace')
    if err:
        print("STDERR:", err)

    client.close()
except Exception as e:
    print(f"SSH Error: {e}")
