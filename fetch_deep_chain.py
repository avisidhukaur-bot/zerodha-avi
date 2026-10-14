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
df = pd.read_csv('/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_instruments.csv')
nov_df = df[(df['name'] == 'NIFTY') & (df['expiry'] == '2026-11-23')]

# CE Range 24000 to 25500
ce_syms = [f"NFO:{s}" for s in nov_df[(nov_df['instrument_type']=='CE') & (nov_df['strike'].between(24000, 25500))]['tradingsymbol']]
pe_syms = [f"NFO:{s}" for s in nov_df[(nov_df['instrument_type']=='PE') & (nov_df['strike'].between(21000, 22600))]['tradingsymbol']]

quotes = kite.quote(ce_syms + pe_syms)

print("=== CE OPTIONS (CALL WING) ===")
for s in range(24000, 25500, 100):
    sym = nov_df[(nov_df['strike']==s) & (nov_df['instrument_type']=='CE')]['tradingsymbol'].values
    if len(sym) > 0:
        sym_name = sym[0]
        ltp = quotes.get(f"NFO:{sym_name}", {}).get('last_price', 0.0)
        print(f"CE Strike {s}: {sym_name} | LTP: ₹{ltp:.2f}")

print("\\n=== PE OPTIONS (PUT WING) ===")
for s in range(21200, 22700, 100):
    sym = nov_df[(nov_df['strike']==s) & (nov_df['instrument_type']=='PE')]['tradingsymbol'].values
    if len(sym) > 0:
        sym_name = sym[0]
        ltp = quotes.get(f"NFO:{sym_name}", {}).get('last_price', 0.0)
        print(f"PE Strike {s}: {sym_name} | LTP: ₹{ltp:.2f}")
"""

sftp = c.open_sftp()
f = sftp.file('/tmp/fetch_deep_chain.py', 'w')
f.write(script)
f.close()
sftp.close()

stdin, stdout, stderr = c.exec_command('python3 /tmp/fetch_deep_chain.py')
print(stdout.read().decode('utf-8', errors='replace'))
print(stderr.read().decode('utf-8', errors='replace'))
c.close()
