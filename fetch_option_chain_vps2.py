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
import db
import kite_executor as ke
import pandas as pd

ke.kite_executor.load_session_from_db()
kite = ke.kite_executor.kite
spot = ke.kite_executor.get_ltp('NSE:NIFTY 50')
print(f"=== CURRENT NIFTY SPOT: {spot} ===")

# Check security master / instruments CSV
csv_path = '/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_instruments.csv'
df = pd.read_csv(csv_path)
nifty_df = df[(df['name'] == 'NIFTY') & (df['instrument_type'].isin(['CE', 'PE']))]

expiries = sorted(list(nifty_df['expiry'].dropna().unique()))
print("\\n=== AVAILABLE EXPIRIES IN MASTER ===")
for e in expiries:
    print(" -", e)

# Let's inspect November expiry
nov_exp = [e for e in expiries if '-11-' in str(e) or 'NOV' in str(e).upper() or 'Nov' in str(e)]
print("\\nNovember expiries found:", nov_exp)

target_exp = nov_exp[0] if nov_exp else (expiries[1] if len(expiries)>1 else expiries[0])
print(f"\\nTarget Expiry: {target_exp}")

opt_subset = nifty_df[nifty_df['expiry'] == target_exp]
strikes = sorted(opt_subset['strike'].unique())
print("Available strikes count:", len(strikes))

# Query quotes for strikes around spot (22000 to 24500)
query_syms = []
for _, row in opt_subset.iterrows():
    if 22000 <= row['strike'] <= 24600 and row['strike'] % 100 == 0:
        query_syms.append(f"NFO:{row['tradingsymbol']}")

print("Querying quotes for", len(query_syms), "symbols...")
quotes = {}
if kite:
    quotes = kite.quote(query_syms)

print(f"\\n{'Strike':<8} | {'CE Symbol':<22} | {'CE LTP':<8} | {'PE Symbol':<22} | {'PE LTP':<8}")
print("-" * 75)

for st in range(22200, 24600, 100):
    ce_row = opt_subset[(opt_subset['strike'] == st) & (opt_subset['instrument_type'] == 'CE')]
    pe_row = opt_subset[(opt_subset['strike'] == st) & (opt_subset['instrument_type'] == 'PE')]
    
    ce_sym = ce_row['tradingsymbol'].values[0] if len(ce_row) > 0 else ""
    pe_sym = pe_row['tradingsymbol'].values[0] if len(pe_row) > 0 else ""
    
    ce_ltp = quotes.get(f"NFO:{ce_sym}", {}).get('last_price', 0.0) if ce_sym else 0.0
    pe_ltp = quotes.get(f"NFO:{pe_sym}", {}).get('last_price', 0.0) if pe_sym else 0.0
    
    print(f"{st:<8} | {ce_sym:<22} | {ce_ltp:<8.2f} | {pe_sym:<22} | {pe_ltp:<8.2f}")
"""

sftp = c.open_sftp()
f = sftp.file('/tmp/fetch_option_chain2.py', 'w')
f.write(script)
f.close()
sftp.close()

stdin, stdout, stderr = c.exec_command('python3 /tmp/fetch_option_chain2.py')
print(stdout.read().decode('utf-8', errors='replace'))
print(stderr.read().decode('utf-8', errors='replace'))
c.close()
