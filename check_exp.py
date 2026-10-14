import paramiko
import sys

secrets = {}
with open('secrets.txt', encoding='utf-8') as f:
    for l in f:
        if '=' in l and not l.startswith('#'):
            k, v = l.strip().split('=', 1)
            secrets[k.strip()] = v.strip()

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(secrets['VPS_IP'], username=secrets['VPS_USER'], password=secrets['VPS_PASSWORD'], timeout=15)

script = """
import sys
sys.path.insert(0, '/root/BHARAT-SYSTEMS/ZERODHA-OS')
import db
from kite_executor import kite_executor
import pandas as pd

kite_executor.load_session_from_db()
kite = kite_executor.kite
df = pd.read_csv('/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_instruments.csv')
nifty_opts = df[(df['name'] == 'NIFTY') & (df['instrument_type'].isin(['CE', 'PE']))].copy()

for target_expiry in ['2026-10-13', '2026-10-27']:
    print(f'=== EXPIRY: {target_expiry} ===')
    sub = nifty_opts[nifty_opts['expiry'] == target_expiry]
    nearby_strikes = [21800, 21900, 22000, 22100, 22200, 22300, 22400, 22500, 22600, 22700, 22800, 22900, 23000]
    sub = sub[sub['strike'].isin(nearby_strikes)]
    symbols = ['NFO:' + s for s in sub['tradingsymbol'].tolist()]
    quotes = {}
    for i in range(0, len(symbols), 100):
        quotes.update(kite.quote(symbols[i:i+100]))
    
    print(f"{'STRIKE':<8} | {'CE SYMBOL':<20} | {'CE LTP':<8} | {'PE SYMBOL':<20} | {'PE LTP':<8}")
    for strike in sorted(sub['strike'].unique()):
        ce_row = sub[(sub['strike'] == strike) & (sub['instrument_type'] == 'CE')]
        pe_row = sub[(sub['strike'] == strike) & (sub['instrument_type'] == 'PE')]
        ce_sym = ce_row.iloc[0]['tradingsymbol'] if len(ce_row) > 0 else ''
        pe_sym = pe_row.iloc[0]['tradingsymbol'] if len(pe_row) > 0 else ''
        ce_ltp = quotes.get('NFO:' + ce_sym, {}).get('last_price', 0) if ce_sym else 0
        pe_ltp = quotes.get('NFO:' + pe_sym, {}).get('last_price', 0) if pe_sym else 0
        print(f"{strike:<8} | {ce_sym:<20} | Rs {ce_ltp:<6.2f} | {pe_sym:<20} | Rs {pe_ltp:<6.2f}")
    print()
"""

sftp = c.open_sftp()
with sftp.file("/root/BHARAT-SYSTEMS/ZERODHA-OS/check_exp_remote.py", "w") as f:
    f.write(script)
sftp.close()

_, stdout, stderr = c.exec_command("/usr/bin/python3 /root/BHARAT-SYSTEMS/ZERODHA-OS/check_exp_remote.py")
print(stdout.read().decode('utf-8', errors='replace'))
c.close()
