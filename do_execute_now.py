import sys
import json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import db
from kite_executor import kite_executor
import block_manager as bm

db.load_secrets()
kite_executor.load_session_from_db()

print("🚀 EXECUTING CALL WING (23500 CE HEDGE + 23000 CE SELL) ON ZERODHA KITE...")
res = bm.execute_strike(155)
print("Execution Result:", json.dumps(res, indent=2, default=str))

print("\n=== VERIFYING POSITIONS ON KITE BROKER ===")
pos = kite_executor.kite.positions()
net = pos.get('net', [])
for p in net:
    if p.get('quantity') != 0:
        print(f"BROKER LIVE: {p.get('tradingsymbol')} | Qty: {p.get('quantity')} | BuyPrice: {p.get('buy_price')} | SellPrice: {p.get('sell_price')} | LTP: {p.get('last_price')} | PnL: {p.get('pnl')}")
