import paramiko
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

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

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(VPS_IP, username=VPS_USER, password=VPS_PASSWORD, timeout=15)

remote_script = """# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, '/root/BHARAT-SYSTEMS/ZERODHA-OS')
import db
import json
import regime_engine as re_eng
import os_engine
from kite_executor import kite_executor

db.load_secrets()
kite_executor.load_session_from_db()
kite_executor.ensure_logged_in()

spot = re_eng.get_current_nifty_spot()
print(f"=== CURRENT NIFTY SPOT: {spot} ===")

expiries = os_engine.get_categorized_expiries()
print("Available Expiries:", expiries)

# Target October monthly expiry 2026-10-27 and next weekly
for target_exp in ['2026-10-27', '2026-10-06']:
    if target_exp not in expiries['all']:
        continue
    print(f"\\n=======================================================")
    print(f"   OS ENGINE CANDIDATE SCAN FOR EXPIRY: {target_exp}")
    print(f"=======================================================")
    
    # Hunt CE
    ce_res = os_engine.hunt_os_strike(
        option_type="CE",
        expiry_date=target_exp,
        target_premium=150.0,
        step_size="100"
    )
    print("\\n--- CALL CANDIDATE (CE) ---")
    print(json.dumps(ce_res, indent=2, default=str))
    
    # Hunt PE
    pe_res = os_engine.hunt_os_strike(
        option_type="PE",
        expiry_date=target_exp,
        target_premium=150.0,
        step_size="100"
    )
    print("\\n--- PUT CANDIDATE (PE) ---")
    print(json.dumps(pe_res, indent=2, default=str))

# Also print detailed scan around spot for 2026-10-27
print("\\n=======================================================")
print("   DETAILED DECAY SCAN (2026-10-27 Monthly)")
print("=======================================================")

kite = kite_executor.kite
insts = kite.instruments('NFO')
contracts = [i for i in insts if i['name'] == 'NIFTY' and str(i['expiry']) == '2026-10-27']

query_syms = []
for c in contracts:
    if 21400 <= c['strike'] <= 23600 and c['strike'] % 100 == 0:
        query_syms.append(f"NFO:{c['tradingsymbol']}")

quotes = {}
for i in range(0, len(query_syms), 50):
    chunk = query_syms[i:i+50]
    q = kite.quote(chunk)
    if q:
        quotes.update(q)

print(f"{'Type':<4} | {'Strike':<6} | {'Symbol':<20} | {'Prev Close':<10} | {'LTP':<8} | {'Decay (Rs)':<10} | {'Decay %':<8} | {'Qualified (<PrevClose)?'}")
print("-" * 95)

# CE strikes
for stk in range(22600, 23600, 100):
    ce_c = next((c for c in contracts if c['strike'] == stk and c['instrument_type'] == 'CE'), None)
    if ce_c:
        sym = ce_c['tradingsymbol']
        q_data = quotes.get(f"NFO:{sym}", {})
        ltp = q_data.get('last_price', 0.0)
        prev_close = q_data.get('ohlc', {}).get('close', 0.0)
        diff = prev_close - ltp
        pct = (diff / prev_close * 100) if prev_close > 0 else 0
        qual = "YES (DECAYING)" if diff > 0 and 50 <= ltp <= 180 else ("NO (Rising/Out)" if diff <= 0 else "High/Low Premium")
        print(f"CE   | {stk:<6} | {sym:<20} | {prev_close:<10.2f} | {ltp:<8.2f} | {diff:<10.2f} | {pct:<7.1f}% | {qual}")

print("-" * 95)
# PE strikes
for stk in range(21500, 22500, 100):
    pe_c = next((c for c in contracts if c['strike'] == stk and c['instrument_type'] == 'PE'), None)
    if pe_c:
        sym = pe_c['tradingsymbol']
        q_data = quotes.get(f"NFO:{sym}", {})
        ltp = q_data.get('last_price', 0.0)
        prev_close = q_data.get('ohlc', {}).get('close', 0.0)
        diff = prev_close - ltp
        pct = (diff / prev_close * 100) if prev_close > 0 else 0
        qual = "YES (DECAYING)" if diff > 0 and 50 <= ltp <= 180 else ("NO (Rising/Out)" if diff <= 0 else "High/Low Premium")
        print(f"PE   | {stk:<6} | {sym:<20} | {prev_close:<10.2f} | {ltp:<8.2f} | {diff:<10.2f} | {pct:<7.1f}% | {qual}")
"""

sftp = client.open_sftp()
with sftp.file("/root/BHARAT-SYSTEMS/ZERODHA-OS/find_os_candidates.py", "w") as f:
    f.write(remote_script)
sftp.close()

_, stdout, stderr = client.exec_command("python3 /root/BHARAT-SYSTEMS/ZERODHA-OS/find_os_candidates.py")
print(stdout.read().decode(errors='replace'))
err = stderr.read().decode(errors='replace')
if err:
    print("STDERR:", err)

client.close()
