import paramiko

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
from kite_executor import kite_executor
import pandas as pd

kite_executor.load_session_from_db()
kite = kite_executor.kite
df = pd.read_csv('/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_instruments.csv')

strikes_to_fetch = [21300, 21400, 21500, 21600, 21700, 21800, 21900, 22000, 22100, 22200, 22300, 22400, 22500, 22600, 22700, 22800, 22900, 23000, 23100, 23200, 23300, 23400, 23500]

sub = df[(df['name'] == 'NIFTY') & (df['expiry'] == '2026-10-27') & (df['strike'].isin(strikes_to_fetch))]
symbols = ['NFO:' + s for s in sub['tradingsymbol'].tolist()]
quotes = {}
for i in range(0, len(symbols), 100):
    quotes.update(kite.quote(symbols[i:i+100]))

for s in strikes_to_fetch:
    ce_sym = sub[(sub['strike'] == s) & (sub['instrument_type'] == 'CE')]['tradingsymbol'].values
    pe_sym = sub[(sub['strike'] == s) & (sub['instrument_type'] == 'PE')]['tradingsymbol'].values
    ce_ltp = quotes.get('NFO:' + ce_sym[0], {}).get('last_price', 0) if len(ce_sym) else 0
    pe_ltp = quotes.get('NFO:' + pe_sym[0], {}).get('last_price', 0) if len(pe_sym) else 0
    print(f"Strike {s:5d} | CE: {ce_ltp:6.2f} ({ce_sym[0] if len(ce_sym) else ''}) | PE: {pe_ltp:6.2f} ({pe_sym[0] if len(pe_sym) else ''})")
"""

sftp = c.open_sftp()
with sftp.file("/root/BHARAT-SYSTEMS/ZERODHA-OS/fetch_exact_quotes.py", "w") as f:
    f.write(script)
sftp.close()

_, stdout, stderr = c.exec_command("/usr/bin/python3 /root/BHARAT-SYSTEMS/ZERODHA-OS/fetch_exact_quotes.py")
print(stdout.read().decode('utf-8', errors='replace'))
c.close()
