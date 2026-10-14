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
c.connect(secrets['VPS_IP'], username=secrets['VPS_USER'], password=secrets['VPS_PASSWORD'], timeout=10)

script = """import sys
sys.path.insert(0, '/root/BHARAT-SYSTEMS/ZERODHA-OS')
import kite_executor as ke

kite = ke.kite_executor.kite
spot = ke.kite_executor.get_ltp('NSE:NIFTY 50')
print(f"=== CURRENT NIFTY SPOT: {spot} ===")

# Let's inspect all NIFTY instruments
insts = kite.instruments('NFO')
nifty_insts = [i for i in insts if i['name'] == 'NIFTY' and i['instrument_type'] in ('CE', 'PE')]

expiries = sorted(list(set(str(i['expiry']) for i in nifty_insts if i['expiry'])))
print("\\n=== AVAILABLE NIFTY EXPIRIES ===")
for e in expiries:
    print(" -", e)

# Filter for September expiry
sep_expiries = [e for e in expiries if '-09-' in e or 'Sep' in e or 'SEP' in e]
print("\\n=== SEPTEMBER EXPIRIES ===", sep_expiries)

target_expiry = sep_expiries[-1] if sep_expiries else expiries[0]
print(f"\\n=== OPTION CHAIN FOR EXPIRY: {target_expiry} ===")

contracts = [i for i in nifty_insts if str(i['expiry']) == str(target_expiry)]
strikes_available = sorted(list(set(i['strike'] for i in contracts)))
print("Strikes count:", len(strikes_available), "Range:", min(strikes_available), "to", max(strikes_available))

query_symbols = []
for c_item in contracts:
    if 22400 <= c_item['strike'] <= 24500 and c_item['strike'] % 100 == 0:
        query_symbols.append(f"NFO:{c_item['tradingsymbol']}")

quotes = kite.quote(query_symbols)
print(f"\\n=== KEY STRIKES FOR {target_expiry} ===")
print(f"{'Strike':<8} | {'CE Symbol':<22} | {'CE LTP':<8} | {'PE Symbol':<22} | {'PE LTP':<8}")
print("-" * 75)

for strike in range(23100, 24300, 100):
    ce_sym = next((i['tradingsymbol'] for i in contracts if i['strike'] == strike and i['instrument_type'] == 'CE'), None)
    pe_sym = next((i['tradingsymbol'] for i in contracts if i['strike'] == strike and i['instrument_type'] == 'PE'), None)
    
    ce_ltp = quotes.get(f"NFO:{ce_sym}", {}).get('last_price', 0.0) if ce_sym else 0.0
    pe_ltp = quotes.get(f"NFO:{pe_sym}", {}).get('last_price', 0.0) if pe_sym else 0.0
    
    print(f"{strike:<8} | {str(ce_sym):<22} | {ce_ltp:<8.2f} | {str(pe_sym):<22} | {pe_ltp:<8.2f}")
"""

sftp = c.open_sftp()
f = sftp.file('/tmp/fetch_option_chain.py', 'w')
f.write(script)
f.close()
sftp.close()

stdin, stdout, stderr = c.exec_command('python3 /tmp/fetch_option_chain.py')
print(stdout.read().decode('utf-8', errors='replace'))
print(stderr.read().decode('utf-8', errors='replace'))
c.close()
