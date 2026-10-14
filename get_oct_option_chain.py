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
print(f"=== CURRENT NIFTY SPOT (regime_engine): {spot} ===")

# Also try kite quote directly
spot_quote = kite.quote(['NSE:NIFTY 50'])
print(f"Direct NIFTY 50 Quote: {spot_quote.get('NSE:NIFTY 50', {}).get('last_price')}")

insts = kite.instruments('NFO')
nifty_insts = [i for i in insts if i['name'] == 'NIFTY' and i['instrument_type'] in ('CE', 'PE')]

expiries = sorted(list(set(str(i['expiry']) for i in nifty_insts if i['expiry'])))
print("\\n=== AVAILABLE NIFTY EXPIRIES ===")
for e in expiries:
    print(" -", e)

# Target October monthly expiry
oct_expiries = [e for e in expiries if '-10-' in e or 'Oct' in e or 'OCT' in e]
print("\\n=== OCTOBER EXPIRIES ===", oct_expiries)

target_expiry = oct_expiries[-1] if oct_expiries else expiries[0]
print(f"\\n=== OPTION CHAIN FOR EXPIRY: {target_expiry} ===")

contracts = [i for i in nifty_insts if str(i['expiry']) == str(target_expiry)]
strikes_available = sorted(list(set(int(i['strike']) for i in contracts)))

query_symbols = []
for c_item in contracts:
    if 22000 <= c_item['strike'] <= 24500 and c_item['strike'] % 100 == 0:
        query_symbols.append(f"NFO:{c_item['tradingsymbol']}")

quotes = {}
# Chunk into 50s
for i in range(0, len(query_symbols), 50):
    chunk = query_symbols[i:i+50]
    q = kite.quote(chunk)
    if q:
        quotes.update(q)

print(f"\\n=== KEY STRIKES FOR {target_expiry} (Spot: {spot}) ===")
print(f"{'CE Hedge':<18} | {'CE Sell':<18} | {'CE LTP':<8} | {'Strike':<8} | {'PE LTP':<8} | {'PE Sell':<18} | {'PE Hedge':<18}")
print("-" * 110)

for strike in range(22200, 24200, 100):
    ce_sym = next((i['tradingsymbol'] for i in contracts if i['strike'] == strike and i['instrument_type'] == 'CE'), None)
    pe_sym = next((i['tradingsymbol'] for i in contracts if i['strike'] == strike and i['instrument_type'] == 'PE'), None)
    
    ce_ltp = quotes.get(f"NFO:{ce_sym}", {}).get('last_price', 0.0) if ce_sym else 0.0
    pe_ltp = quotes.get(f"NFO:{pe_sym}", {}).get('last_price', 0.0) if pe_sym else 0.0
    
    # 500 pt hedges
    ce_hedge_sym = next((i['tradingsymbol'] for i in contracts if i['strike'] == (strike + 500) and i['instrument_type'] == 'CE'), "")
    pe_hedge_sym = next((i['tradingsymbol'] for i in contracts if i['strike'] == (strike - 500) and i['instrument_type'] == 'PE'), "")
    
    print(f"{str(ce_hedge_sym):<18} | {str(ce_sym):<18} | {ce_ltp:<8.2f} | {strike:<8} | {pe_ltp:<8.2f} | {str(pe_sym):<18} | {str(pe_hedge_sym):<18}")
"""

sftp = c.open_sftp()
f = sftp.file('/tmp/fetch_oct_chain.py', 'w')
f.write(script)
f.close()
sftp.close()

stdin, stdout, stderr = c.exec_command('python3 /tmp/fetch_oct_chain.py')
print(stdout.read().decode('utf-8', errors='replace'))
print(stderr.read().decode('utf-8', errors='replace'))
c.close()
