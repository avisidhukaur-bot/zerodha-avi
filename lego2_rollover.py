"""
lego2_rollover.py — Zerodha Option Selling App | Laptop SSH Hedge Rollover Script
Connects to VPS via SSH to query open SELL positions and execute hedge rollovers.
Usage: python lego2_rollover.py
"""
import paramiko
import os
import sys
import ast

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
print(f"  LEGO 2 — ZERODHA OPTION SELLING HEDGE ROLLOVER")
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


def run_vps_python(cmd):
    """Runs a Python snippet on the VPS and returns stdout."""
    vps_cmd = f"python3 -c \"{cmd}\""
    _, stdout, stderr = client.exec_command(vps_cmd)
    out = stdout.read().decode(errors='replace').strip()
    err = stderr.read().decode(errors='replace').strip()
    if err and "warning" not in err.lower() and "created a tmpdir" not in err.lower():
        print(f"[VPS ERROR] {err}", file=sys.stderr)
    return out


# ── STEP 1: Query open SELL strikes with active linked hedges ──
print("🔍 Querying active open SELL strikes with open hedges on VPS...")

query_code = """
import sys
sys.path.append('/root/BHARAT-SYSTEMS/ZERODHA-OS')
import db
active_sells = []
blocks = db.get_all_blocks(status_filter='ACTIVE')
for b in blocks:
    strikes = db.get_strikes_by_block(b['block_id'], status_filter='OPEN')
    for s in strikes:
        if s['leg_type'] == 'SELL' and s.get('hedge_strike_id'):
            h = db.get_strike(s['hedge_strike_id'])
            if h and h['status'] == 'OPEN':
                active_sells.append({
                    'block_num': b['block_number'],
                    'sell_id': s['strike_id'],
                    'sell_price': s['strike_price'],
                    'sell_type': s['option_type'],
                    'lots': s['lots'],
                    'hedge_id': h['strike_id'],
                    'hedge_price': h['strike_price'],
                    'hedge_expiry': h.get('expiry_date') or ''
                })
print(repr(active_sells))
"""

res_str = run_vps_python(query_code.replace("\n", " "))
if not res_str:
    print("❌ No active open SELL strikes found or unable to fetch from VPS.")
    client.close()
    sys.exit(0)

try:
    active_sells = ast.literal_eval(res_str)
except Exception as e:
    print(f"❌ Failed to parse VPS response: {e}")
    print(f"Raw response: {res_str}")
    client.close()
    sys.exit(1)

if not active_sells:
    print("ℹ️ No active open SELL legs with open linked hedges found on the VPS database.")
    client.close()
    sys.exit(0)

print(f"\nFound {len(active_sells)} active open SELL leg(s) with open hedges:\n")
for idx, s in enumerate(active_sells, 1):
    print(f" [{idx}] Block {s['block_num']} | SELL: {s['sell_price']} {s['sell_type']} Lots: {s['lots']} (ID: {s['sell_id']})")
    print(f"     └─ Current Hedge: {s['hedge_price']} {s['sell_type']} Expiry: {s['hedge_expiry']} (ID: {s['hedge_id']})")
    print()

# Select strike to roll over
try:
    sel_idx_str = input(f"Select a leg to roll over (1-{len(active_sells)}): ").strip()
    sel_idx = int(sel_idx_str)
    if sel_idx < 1 or sel_idx > len(active_sells):
        raise ValueError
except (ValueError, KeyboardInterrupt):
    print("\n❌ Invalid selection or cancelled.")
    client.close()
    sys.exit(1)

selected = active_sells[sel_idx - 1]

# ── STEP 2: Query sorted nifty expiries from VPS ──
print("\n🔍 Fetching available expiries from VPS Security Master...")
expiry_query = """
import sys
sys.path.append('/root/BHARAT-SYSTEMS/ZERODHA-OS')
import app
print(repr(app.get_sorted_nifty_expiries()))
"""
exp_res_str = run_vps_python(expiry_query.replace("\n", " "))
try:
    exp_list = ast.literal_eval(exp_res_str)
except Exception:
    exp_list = []

if not exp_list:
    print("⚠️ Unable to fetch expiries. Will require manual entry.")
else:
    print("Available expiries:")
    for idx, exp in enumerate(exp_list, 1):
        print(f"  [{idx}] {exp}")

# Prompt for inputs
try:
    # 1. New Strike
    default_strike = selected['hedge_price']
    strike_input = input(f"\nEnter New Hedge Strike Price (default {default_strike}): ").strip()
    new_strike = int(strike_input) if strike_input else default_strike
    
    # 2. Expiry
    if exp_list:
        default_exp_idx = 1 if len(exp_list) > 1 else 0
        exp_input_str = input(f"Select New Expiry Number (1-{len(exp_list)}, default {default_exp_idx + 1}): ").strip()
        if exp_input_str:
            new_expiry = exp_list[int(exp_input_str) - 1]
        else:
            new_expiry = exp_list[default_exp_idx]
    else:
        new_expiry = input("Enter New Expiry Date (dd-MMM-yyyy): ").strip()
        if not new_expiry:
            print("❌ Expiry date is required.")
            client.close()
            sys.exit(1)

    # 3. Lots
    default_lots = selected['lots']
    lots_input = input(f"Enter New Hedge Lots (default {default_lots}): ").strip()
    new_lots = int(lots_input) if lots_input else default_lots

except (ValueError, KeyboardInterrupt, IndexError):
    print("\n❌ Invalid input or cancelled.")
    client.close()
    sys.exit(1)

print(f"\n{'─'*60}")
print(f"🚀 ROLLING OVER HEDGE FOR SELL STRIKE #{selected['sell_id']}...")
print(f"   SELL Strike: {selected['sell_price']} {selected['sell_type']}")
print(f"   New Hedge  : {new_strike} {selected['sell_type']}")
print(f"   New Expiry : {new_expiry}")
print(f"   Lots       : {new_lots}")
print(f"{'─'*60}\n")

# Run rollover function on VPS
rollover_cmd = f"""
import sys
sys.path.append('/root/BHARAT-SYSTEMS/ZERODHA-OS')
import block_manager as bm
res = bm.rollover_hedge(
    sell_strike_id={selected['sell_id']},
    new_hedge_strike_price={new_strike},
    new_hedge_expiry='{new_expiry}',
    new_hedge_lots={new_lots},
    new_hedge_option_type='{selected['sell_type']}'
)
print(repr(res))
"""

result_str = run_vps_python(rollover_cmd.replace("\n", " "))
try:
    result = ast.literal_eval(result_str)
except Exception as e:
    print(f"❌ Failed to parse execution result: {e}")
    print(f"Raw response: {result_str}")
    client.close()
    sys.exit(1)

if result.get("ok"):
    print(f"✅ SUCCESS: {result.get('message')}")
else:
    print(f"❌ FAILURE: {result.get('message')}")

client.close()
print(f"\n{'='*60}")
print("✅ ROLLOVER SCRIPT RUN COMPLETE")
print(f"{'='*60}\n")
