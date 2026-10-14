import paramiko
import sys
import os

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

script = """# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, '/root/BHARAT-SYSTEMS/ZERODHA-OS')
import db
import regime_engine as re_eng
from kite_executor import kite_executor

db.load_secrets()
kite_executor.load_session_from_db()
kite_executor.ensure_logged_in()
kite = kite_executor.kite

spot = re_eng.get_current_nifty_spot()
print(f"=== CURRENT NIFTY SPOT: {spot} ===")

insts = kite.instruments('NFO')
nifty_insts = [i for i in insts if i['name'] == 'NIFTY' and i['instrument_type'] in ('CE', 'PE')]

target_expiry = '2026-10-27'
contracts = [i for i in nifty_insts if str(i['expiry']) == str(target_expiry)]

query_symbols = []
for c_item in contracts:
    if 21000 <= c_item['strike'] <= 23500 and c_item['strike'] % 100 == 0:
        query_symbols.append(f"NFO:{c_item['tradingsymbol']}")

quotes = {}
for i in range(0, len(query_symbols), 50):
    chunk = query_symbols[i:i+50]
    q = kite.quote(chunk)
    if q:
        quotes.update(q)

print(f"\\n=== OTM PUTS & CALLS FOR {target_expiry} (Spot: {spot}) ===")
print(f"{'Strike':<8} | {'PE Symbol':<20} | {'PE LTP':<8} | {'PE Hedge (500pt)':<20} | {'Hedge LTP':<8}")
print("-" * 75)

for strike in range(21200, 22600, 100):
    pe_sym = next((i['tradingsymbol'] for i in contracts if i['strike'] == strike and i['instrument_type'] == 'PE'), None)
    pe_ltp = quotes.get(f"NFO:{pe_sym}", {}).get('last_price', 0.0) if pe_sym else 0.0
    
    pe_h_strike = strike - 500
    pe_h_sym = next((i['tradingsymbol'] for i in contracts if i['strike'] == pe_h_strike and i['instrument_type'] == 'PE'), None)
    pe_h_ltp = quotes.get(f"NFO:{pe_h_sym}", {}).get('last_price', 0.0) if pe_h_sym else 0.0
    
    print(f"{strike:<8} | {str(pe_sym):<20} | {pe_ltp:<8.2f} | {str(pe_h_sym):<20} | {pe_h_ltp:<8.2f}")

print(f"\\n=== OTM CALLS FOR {target_expiry} (Spot: {spot}) ===")
print(f"{'Strike':<8} | {'CE Symbol':<20} | {'CE LTP':<8} | {'CE Hedge (500pt)':<20} | {'Hedge LTP':<8}")
print("-" * 75)

for strike in range(22600, 24000, 100):
    ce_sym = next((i['tradingsymbol'] for i in contracts if i['strike'] == strike and i['instrument_type'] == 'CE'), None)
    ce_ltp = quotes.get(f"NFO:{ce_sym}", {}).get('last_price', 0.0) if ce_sym else 0.0
    
    ce_h_strike = strike + 500
    ce_h_sym = next((i['tradingsymbol'] for i in contracts if i['strike'] == ce_h_strike and i['instrument_type'] == 'CE'), None)
    ce_h_ltp = quotes.get(f"NFO:{ce_h_sym}", {}).get('last_price', 0.0) if ce_h_sym else 0.0
    
    print(f"{strike:<8} | {str(ce_sym):<20} | {ce_ltp:<8.2f} | {str(ce_h_sym):<20} | {ce_h_ltp:<8.2f}")
"""

sftp = c.open_sftp()
f = sftp.file('/tmp/fetch_otm_chain.py', 'w')
f.write(script)
f.close()
sftp.close()

stdin, stdout, stderr = c.exec_command('python3 /tmp/fetch_otm_chain.py')
print(stdout.read().decode('utf-8', errors='replace'))
print(stderr.read().decode('utf-8', errors='replace'))
c.close()
