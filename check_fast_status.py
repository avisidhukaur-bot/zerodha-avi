import sys
import os

# Fix encoding for Windows terminal
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import db
from kite_executor import kite_executor

def check_status():
    print("=== CHECKING ZERODHA ACCOUNT STATUS ===")
    logged_in = kite_executor.ensure_logged_in()
    kite = kite_executor.kite
    
    if not logged_in or not kite:
        print("[ERROR] Failed to authenticate with Zerodha Kite Connect.")
        return

    try:
        profile = kite.profile()
        print(f"Logged In User: {profile.get('user_name')} ({profile.get('user_id')})")
        print(f"Email: {profile.get('email')}")
    except Exception as e:
        print(f"Profile fetch error: {e}")

    # Margins
    try:
        margins = kite.margins('equity')
        cash = margins.get('available', {}).get('cash', 0)
        net = margins.get('net', 0)
        utilised = margins.get('utilised', {}).get('debits', 0)
        print(f"\n--- Margins & Funds ---")
        print(f"Available Cash: Rs {cash:,.2f}")
        print(f"Net Margin: Rs {net:,.2f}")
        print(f"Utilised Margin: Rs {utilised:,.2f}")
    except Exception as e:
        print(f"Margins error: {e}")

    # Positions
    try:
        pos = kite.positions()
        net_pos = pos.get('net', [])
        day_pos = pos.get('day', [])
        print(f"\n--- Open / Net Positions (Total: {len(net_pos)}) ---")
        open_count = 0
        for p in net_pos:
            qty = p.get('quantity', 0)
            if qty != 0:
                open_count += 1
                sym = p.get('tradingsymbol')
                prod = p.get('product')
                pnl = p.get('pnl', 0)
                m2m = p.get('m2m', 0)
                ltp = p.get('last_price', 0)
                buy_price = p.get('buy_price', 0)
                sell_price = p.get('sell_price', 0)
                print(f" [ACTIVE] {sym} | Product: {prod} | Qty: {qty} | LTP: {ltp} | M2M: Rs {m2m:,.2f} | PnL: Rs {pnl:,.2f}")
        
        if open_count == 0:
            print(" >> NO LIVE OPEN POSITIONS (Koi open position / trade nahi chal rahi hai).")
        else:
            print(f" >> TOTAL ACTIVE POSITIONS: {open_count}")

        # Closed positions today if any
        closed_count = 0
        for p in net_pos:
            qty = p.get('quantity', 0)
            if qty == 0 and (p.get('buy_quantity', 0) > 0 or p.get('sell_quantity', 0) > 0):
                if closed_count == 0:
                    print("\n--- Closed / Completed Positions Today ---")
                closed_count += 1
                sym = p.get('tradingsymbol')
                pnl = p.get('pnl', 0)
                print(f" [CLOSED] {sym} | Realised PnL: Rs {pnl:,.2f}")

    except Exception as e:
        print(f"Positions error: {e}")

    # Orders Today
    try:
        orders = kite.orders()
        print(f"\n--- Today's Orders (Total: {len(orders)}) ---")
        if not orders:
            print(" >> No orders placed today.")
        else:
            for o in orders[-10:]:
                ts = str(o.get('order_timestamp'))
                sym = str(o.get('tradingsymbol'))
                tx = str(o.get('transaction_type'))
                qty = str(o.get('quantity'))
                st = str(o.get('status'))
                avg_p = str(o.get('average_price'))
                msg = str(o.get('status_message') or '')
                print(f" - {ts} | {sym} | {tx} {qty} qty | {st} @ {avg_p} | {msg}")
    except Exception as e:
        print(f"Orders error: {e}")

    # Database state
    try:
        blocks = db.get_active_blocks()
        print(f"\n--- Database Engine Blocks ---")
        print(f"Active Blocks in Local DB: {len(blocks)}")
        for b in blocks:
            print(f"Block #{b.get('block_number')} (ID {b.get('block_id')}) | Regime: {b.get('current_regime')} | Expiry: {b.get('expiry_date')}")
            strikes = db.get_strikes_by_block(b.get('block_id'))
            for s in strikes:
                print(f"   -> {s.get('strike_price')} {s.get('option_type')} ({s.get('leg_type')}) | Status: {s.get('status')} | Lots: {s.get('lots')}")
    except Exception as e:
        print(f"DB error: {e}")

if __name__ == '__main__':
    check_status()
