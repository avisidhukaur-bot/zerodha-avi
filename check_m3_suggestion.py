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
import sqlite3
import json
from kite_executor import kite_executor

db.load_secrets()
kite_executor.load_session_from_db()
kite_executor.ensure_logged_in()

conn = sqlite3.connect('/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_trader.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=== 1. ALL ACTIVE BLOCKS ===")
cur.execute("SELECT * FROM blocks WHERE status != 'ARCHIVED'")
blocks = [dict(r) for r in cur.fetchall()]
for b in blocks:
    print(f"Block ID: {b.get('block_id')}, Unit: {b.get('anchor_unit_name')}, Anchor: {b.get('master_anchor_price')}, Expiry: {b.get('expiry_date')}, Regime: {b.get('current_regime')}, Status: {b.get('status')}")

print("\\n=== 2. CURRENT NIFTY SPOT ===")
spot_data = kite_executor.get_ltp(["NSE:NIFTY 50"])
spot_ltp = spot_data.get("NSE:NIFTY 50", {}).get("last_price", 0) if spot_data else 0
print(f"NIFTY 50 SPOT LTP: {spot_ltp}")

print("\\n=== 3. KITE MARGINS ===")
try:
    margins = kite_executor.kite.margins('equity')
    print(f"Available Cash: Rs {margins.get('available', {}).get('cash', 0):,.2f}")
    print(f"Net Margin: Rs {margins.get('net', 0):,.2f}")
    print(f"Utilised: Rs {margins.get('utilised', {}).get('debits', 0):,.2f}")
except Exception as e:
    print(f"Margin error: {e}")

print("\\n=== 4. LIVE POSITIONS ===")
pos = kite_executor.get_positions()
pos_list = pos if isinstance(pos, list) else pos.get('net', [])
for p in pos_list:
    if p.get('quantity', 0) != 0:
        print(f"{p.get('tradingsymbol')} | Qty: {p.get('quantity')} | Avg: {p.get('average_price')} | LTP: {p.get('last_price')} | PnL: Rs {p.get('pnl', 0):,.2f}")

print("\\n=== 5. OCTOBER OPTION CHAIN AROUND SPOT ===")
# Let's fetch option symbols around spot
exp_date = "2026-10-27"
cur.execute("SELECT expiry_date FROM blocks ORDER BY block_id DESC LIMIT 1")
r = cur.fetchone()
if r and r['expiry_date']:
    exp_date = r['expiry_date']
print(f"Target Expiry: {exp_date}")

# Let's find instrument symbols from csv or kite
import pandas as pd
try:
    df = pd.read_csv('/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_instruments.csv')
    nifty_df = df[(df['name'] == 'NIFTY') & (df['segment'] == 'NFO-OPT')]
    # print available expiries
    expiries = sorted(nifty_df['expiry'].dropna().unique().tolist())
    print(f"Available NIFTY Option Expiries: {expiries[:8]}")
    
    # Filter for next/current monthly expiry
    target_exp = exp_date if exp_date in expiries else (expiries[0] if expiries else None)
    print(f"Filtering for expiry: {target_exp}")
    if target_exp:
        exp_df = nifty_df[nifty_df['expiry'] == target_exp]
        # strikes around spot (spot +- 1500)
        round_spot = round(spot_ltp / 100) * 100
        strike_df = exp_df[(exp_df['strike'] >= round_spot - 1200) & (exp_df['strike'] <= round_spot + 1200)]
        
        # Build symbols for get_ltp
        symbols = ["NFO:" + sym for sym in strike_df['tradingsymbol'].tolist()]
        # Batch in chunks of 50
        ltp_map = {}
        for i in range(0, len(symbols), 50):
            chunk = symbols[i:i+50]
            res = kite_executor.get_ltp(chunk)
            if res:
                ltp_map.update(res)
        
        # Print table
        strikes_unique = sorted(strike_df['strike'].unique().tolist())
        print(f"\\n--- OPTION CHAIN for {target_exp} (Spot: {spot_ltp}) ---")
        print(f"{'CE Symbol':<24} | {'CE LTP':<8} | {'Strike':<8} | {'PE LTP':<8} | {'PE Symbol':<24}")
        print("-" * 80)
        for stk in strikes_unique:
            ce_row = strike_df[(strike_df['strike'] == stk) & (strike_df['instrument_type'] == 'CE')]
            pe_row = strike_df[(strike_df['strike'] == stk) & (strike_df['instrument_type'] == 'PE')]
            
            ce_sym = ce_row.iloc[0]['tradingsymbol'] if not ce_row.empty else ""
            pe_sym = pe_row.iloc[0]['tradingsymbol'] if not pe_row.empty else ""
            
            ce_ltp = ltp_map.get("NFO:" + ce_sym, {}).get("last_price", 0) if ce_sym else 0
            pe_ltp = ltp_map.get("NFO:" + pe_sym, {}).get("last_price", 0) if pe_sym else 0
            
            print(f"{ce_sym:<24} | {ce_ltp:<8.2f} | {stk:<8} | {pe_ltp:<8.2f} | {pe_sym:<24}")
except Exception as e:
    print(f"Option chain error: {e}")
"""

sftp = client.open_sftp()
with sftp.file("/root/BHARAT-SYSTEMS/ZERODHA-OS/check_m3_query.py", "w") as f:
    f.write(remote_script)
sftp.close()

_, stdout, stderr = client.exec_command("python3 /root/BHARAT-SYSTEMS/ZERODHA-OS/check_m3_query.py")
print(stdout.read().decode(errors='replace'))
err = stderr.read().decode(errors='replace')
if err:
    print("STDERR:", err)

client.close()
