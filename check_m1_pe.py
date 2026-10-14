import sys
import os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import sqlite3
import db
from kite_executor import kite_executor

db.load_secrets()
kite_executor.load_session_from_db()
kite = kite_executor.kite

print("=== 1. KITE LIVE POSITIONS & ORDERS ===")
try:
    pos = kite.positions()
    net = pos.get('net', [])
    found = False
    for p in net:
        if p.get('quantity') != 0:
            found = True
            print(f"ACTIVE POS: {p.get('tradingsymbol')} | Qty: {p.get('quantity')} | BuyAvg: {p.get('buy_price')} | SellAvg: {p.get('sell_price')} | LTP: {p.get('last_price')} | M2M: {p.get('m2m')} | PnL: {p.get('pnl')}")
    if not found:
        print("No active open positions on broker.")
        
    print("\nRecent Orders Today:")
    orders = kite.orders()
    for o in orders[-10:]:
        print(f"Order: {o.get('order_timestamp')} | {o.get('tradingsymbol')} | {o.get('transaction_type')} {o.get('quantity')} | {o.get('status')} @ {o.get('average_price')} | {o.get('status_message')}")
except Exception as e:
    print('Kite error:', e)

print("\n=== 2. LOCAL DB STRIKES ===")
conn = sqlite3.connect('zerodha_trader.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()
rows = cur.execute('SELECT * FROM strikes ORDER BY strike_id DESC LIMIT 15').fetchall()
for r in rows:
    print(dict(r))

print("\n=== 3. ALL BLOCKS ===")
blocks = cur.execute('SELECT * FROM blocks ORDER BY block_id DESC LIMIT 5').fetchall()
for b in blocks:
    print(dict(b))

print("\n=== 4. RELEVANT SETTINGS ===")
settings = cur.execute("SELECT * FROM settings WHERE key LIKE '%sl%' OR key LIKE '%anchor%' OR key LIKE '%m1%' OR key LIKE '%buffer%'").fetchall()
for s in settings:
    print(dict(s))

conn.close()

# Also check VPS DB just in case VPS has newer trades
print("\n=== 5. CHECK VPS DB / STATE ===")
import paramiko
try:
    secrets = {}
    with open('secrets.txt', encoding='utf-8') as f:
        for l in f:
            if '=' in l and not l.startswith('#'):
                k, v = l.strip().split('=', 1)
                secrets[k.strip()] = v.strip()
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(secrets['VPS_IP'], username=secrets['VPS_USER'], password=secrets['VPS_PASSWORD'], timeout=10)
    
    _, out, _ = c.exec_command("sqlite3 /root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_trader.db 'SELECT strike_id, block_id, strike_price, option_type, leg_type, status, entry_price, sl_price, sl_percent, anchor_price FROM strikes ORDER BY strike_id DESC LIMIT 10;'")
    print("VPS DB Strikes:\n", out.read().decode())
    
    _, out, _ = c.exec_command("sqlite3 /root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_trader.db 'SELECT block_id, block_number, current_regime, anchor_price, status FROM blocks ORDER BY block_id DESC LIMIT 5;'")
    print("VPS DB Blocks:\n", out.read().decode())
    c.close()
except Exception as e:
    print("VPS DB check error:", e)
