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
try:
    c.connect(secrets['VPS_IP'], username=secrets['VPS_USER'], password=secrets['VPS_PASSWORD'], timeout=15)
    print("Connected to VPS!")
except Exception as e:
    print("Connection failed:", e)
    sys.exit(1)

remote_script = """
import sys
sys.path.insert(0, '/root/BHARAT-SYSTEMS/ZERODHA-OS')
import json
import db
from kite_executor import kite_executor
import pandas as pd

db.load_secrets()
kite_executor.load_session_from_db()

print('========================================')
print('1. ZERODHA ACCOUNT & FUNDS')
print('========================================')
kite = kite_executor.kite
if not kite:
    print('Kite not initialized, attempting login...')
    kite_executor.ensure_logged_in()
    kite = kite_executor.kite

try:
    profile = kite.profile()
    print(f"User: {profile.get('user_name')} ({profile.get('user_id')})")
    print(f"Email: {profile.get('email')}")
    print(f"Broker: Zerodha")
except Exception as e:
    print('Profile error:', e)

try:
    margins = kite.margins('equity')
    cash = margins.get('available', {}).get('cash', 0)
    net = margins.get('net', 0)
    utilised = margins.get('utilised', {}).get('debits', 0)
    print(f"Available Cash: Rs {cash:,.2f}")
    print(f"Net Margin: Rs {net:,.2f}")
    print(f"Utilised Margin: Rs {utilised:,.2f}")
except Exception as e:
    print('Margins error:', e)

print('\\n========================================')
print('2. LIVE POSITIONS & ORDERS')
print('========================================')
try:
    pos = kite.positions()
    net = pos.get('net', [])
    open_pos = [p for p in net if p.get('quantity', 0) != 0]
    print(f"Total Open Positions: {len(open_pos)}")
    for p in open_pos:
        print(f" - {p.get('tradingsymbol')} | Qty: {p.get('quantity')} | LTP: {p.get('last_price')} | PnL: Rs {p.get('pnl', 0):,.2f}")
    if not open_pos:
        print(" >> No active open positions on broker.")
except Exception as e:
    print('Positions error:', e)

try:
    orders = kite.orders()
    today_orders = [o for o in orders if o.get('status') in ['COMPLETE', 'OPEN', 'TRIGGER PENDING', 'REJECTED']]
    print(f"\\nTotal Orders Today: {len(today_orders)}")
    for o in orders[-5:]:
        print(f" - {o.get('order_timestamp')} | {o.get('tradingsymbol')} | {o.get('transaction_type')} {o.get('quantity')} | {o.get('status')} @ {o.get('average_price')}")
except Exception as e:
    print('Orders error:', e)

print('\\n========================================')
print('3. NIFTY SPOT & OPTION CHAIN SCAN')
print('========================================')
try:
    spot_quote = kite.quote(['NSE:NIFTY 50'])
    spot_ltp = spot_quote.get('NSE:NIFTY 50', {}).get('last_price', 0)
    spot_ohlc = spot_quote.get('NSE:NIFTY 50', {}).get('ohlc', {})
    print(f"NIFTY 50 Live Spot: Rs {spot_ltp:,.2f} | Prev Close: Rs {spot_ohlc.get('close', 0):,.2f} | Open: Rs {spot_ohlc.get('open', 0):,.2f}")
    print(f"High: Rs {spot_ohlc.get('high', 0):,.2f} | Low: Rs {spot_ohlc.get('low', 0):,.2f}")
except Exception as e:
    print('Spot quote error:', e)
    spot_ltp = 0

try:
    df = pd.read_csv('/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_instruments.csv')
    nifty_opts = df[(df['name'] == 'NIFTY') & (df['instrument_type'].isin(['CE', 'PE']))].copy()
    expiries = sorted(list(nifty_opts['expiry'].dropna().unique()))
    print(f"Available Expiries: {expiries[:6]}")
    
    # Let's inspect nearest monthly or weekly expiry
    oct_exp = [exp for exp in expiries if '2026-10' in str(exp) or '2026-11' in str(exp)]
    print(f"Relevant Expiries: {oct_exp}")
    
    target_expiry = oct_exp[0] if oct_exp else expiries[0]
    print(f"\\n--- OPTION CHAIN FOR EXPIRY: {target_expiry} ---")
    sub = nifty_opts[nifty_opts['expiry'] == target_expiry]
    
    # Filter strikes near spot +- 1000
    if spot_ltp > 0:
        base_strike = round(spot_ltp / 100) * 100
        nearby_strikes = [base_strike + i*100 for i in range(-10, 11)]
        sub = sub[sub['strike'].isin(nearby_strikes)]
    
    symbols = ['NFO:' + s for s in sub['tradingsymbol'].tolist()]
    quotes = {}
    for i in range(0, len(symbols), 100):
        batch = symbols[i:i+100]
        q = kite.quote(batch)
        quotes.update(q)
    
    rows = []
    for strike in sorted(sub['strike'].unique()):
        ce_row = sub[(sub['strike'] == strike) & (sub['instrument_type'] == 'CE')]
        pe_row = sub[(sub['strike'] == strike) & (sub['instrument_type'] == 'PE')]
        ce_sym = ce_row.iloc[0]['tradingsymbol'] if len(ce_row) > 0 else ''
        pe_sym = pe_row.iloc[0]['tradingsymbol'] if len(pe_row) > 0 else ''
        ce_ltp = quotes.get('NFO:' + ce_sym, {}).get('last_price', 0) if ce_sym else 0
        pe_ltp = quotes.get('NFO:' + pe_sym, {}).get('last_price', 0) if pe_sym else 0
        rows.append({
            'strike': int(strike),
            'ce_sym': ce_sym,
            'ce_ltp': ce_ltp,
            'pe_sym': pe_sym,
            'pe_ltp': pe_ltp
        })
    
    print(f"{'STRIKE':<8} | {'CE SYMBOL':<22} | {'CE LTP':<8} | {'PE SYMBOL':<22} | {'PE LTP':<8}")
    print('-'*76)
    for r in rows:
        print(f"{r['strike']:<8} | {r['ce_sym']:<22} | Rs {r['ce_ltp']:<6.2f} | {r['pe_sym']:<22} | Rs {r['pe_ltp']:<6.2f}")

except Exception as e:
    print('Option chain error:', e)

print('\\n========================================')
print('4. LOCAL DB ACTIVE BLOCKS & UNITS')
print('========================================')
try:
    blocks = db.get_active_blocks() if hasattr(db, 'get_active_blocks') else []
    print(f"Active Blocks in DB: {len(blocks)}")
    for b in blocks:
        print(f"Block #{b.get('block_number')} (ID {b.get('block_id')}) | Regime: {b.get('current_regime')} | Expiry: {b.get('expiry_date')}")
except Exception as e:
    print('DB error:', e)

"""

sftp = c.open_sftp()
with sftp.file("/root/BHARAT-SYSTEMS/ZERODHA-OS/check_account_and_market_remote.py", "w") as f:
    f.write(remote_script)
sftp.close()

stdin, stdout, stderr = c.exec_command("/usr/bin/python3 /root/BHARAT-SYSTEMS/ZERODHA-OS/check_account_and_market_remote.py")
out = stdout.read().decode('utf-8', errors='replace')
err = stderr.read().decode('utf-8', errors='replace')
print(out)
if err:
    print("STDERR:", err)

c.close()
