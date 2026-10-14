import sys
import os

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import db
from kite_executor import kite_executor
import block_manager as bm

db.load_secrets()
kite_executor.load_session_from_db()

print("=== 1. LIVE BROKER (ZERODHA KITE) POSITIONS ===")
kite = kite_executor.kite
if kite:
    try:
        pos = kite.positions()
        net = pos.get('net', [])
        open_count = 0
        for p in net:
            if p.get('quantity') != 0:
                open_count += 1
                print(f"BROKER OPEN: {p.get('tradingsymbol')} | Qty: {p.get('quantity')} | LTP: {p.get('last_price')} | PnL: {p.get('pnl')}")
        if open_count == 0:
            print("✅ ZERO OPEN POSITIONS ON BROKER TERMINAL. (All positions closed on Friday as you said!)")
    except Exception as e:
        print("Broker positions error:", e)

print("\n=== 2. LOCAL DATABASE ACTIVE BLOCKS & STRIKES ===")
conn = db._conn()
cur = conn.cursor()
cur.execute("SELECT block_id, expiry_date, status, notes, master_anchor_price FROM blocks WHERE status='ACTIVE'")
active_blocks = cur.fetchall()
print(f"Active Blocks in DB: {len(active_blocks)}")
for b in active_blocks:
    print(f"Block ID {b[0]} | Expiry: {b[1]} | Status: {b[2]} | Notes: {b[3]} | Anchor: {b[4]}")
    cur.execute("SELECT strike_id, option_type, strike_price, role, status, trade_state, executed_price FROM strikes WHERE block_id=?", (b[0],))
    strikes = cur.fetchall()
    for s in strikes:
        print(f"   Strike ID {s[0]}: {s[1]} {s[2]} ({s[3]}) | Status: {s[4]} | Trade State: {s[5]} | Exec Price: {s[6]}")

print("\n=== 3. OPEN LEGS IN DB ===")
cur.execute("SELECT leg_id, strike_id, symbol, side, qty, status FROM legs WHERE exit_time IS NULL OR exit_time=''")
open_legs = cur.fetchall()
print(f"Open legs in DB: {len(open_legs)}")
for l in open_legs:
    print(f"   Leg ID {l[0]}: {l[2]} ({l[3]}) | Qty: {l[4]} | Status: {l[5]}")
