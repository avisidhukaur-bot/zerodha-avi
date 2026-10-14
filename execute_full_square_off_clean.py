import json
import sqlite3
from kiteconnect import KiteConnect

def main():
    print("=== STEP 1: LOADING BROKER CREDENTIALS ===")
    with open('/root/BHARAT-SYSTEMS/ZERODHA-OS/access_token.json') as f:
        auth = json.load(f)
    
    kite = KiteConnect(api_key=auth['api_key'])
    kite.set_access_token(auth['access_token'])
    
    print(f"Logged in as: {auth.get('user_name', 'Kite User')} ({auth.get('user_id', '')})")
    
    print("\n=== STEP 2: FETCHING LIVE POSITIONS TO SQUARE OFF ===")
    pos = kite.positions()
    net_positions = pos.get('net', [])
    
    for p in net_positions:
        sym = p.get('tradingsymbol')
        qty = p.get('quantity', 0)
        prod = p.get('product', 'NRML')
        exch = p.get('exchange', 'NFO')
        
        if qty != 0:
            tx_type = 'BUY' if qty < 0 else 'SELL'
            order_qty = abs(qty)
            print(f"Squaring off {sym}: Placed {tx_type} order for {order_qty} qty (Product: {prod})...")
            
            try:
                order_id = kite.place_order(
                    variety=kite.VARIETY_REGULAR,
                    exchange=exch,
                    tradingsymbol=sym,
                    transaction_type=tx_type,
                    quantity=order_qty,
                    product=prod,
                    order_type=kite.ORDER_TYPE_MARKET,
                    tag="CLOSE_ALL"
                )
                print(f"✅ Square-off Order Placed! Order ID: {order_id}")
            except Exception as e:
                print(f"❌ Error placing square off order for {sym}: {e}")

    print("\n=== STEP 3: VERIFYING NET POSITIONS ARE NOW 0 ===")
    pos_after = kite.positions()
    open_count = 0
    for p in pos_after.get('net', []):
        if p.get('quantity', 0) != 0:
            print(f"Remaining Open: {p.get('tradingsymbol')} Qty: {p.get('quantity')}")
            open_count += 1
            
    if open_count == 0:
        print("🎉 SUCCESS! Broker terminal has ZERO (0) open positions. All squared off!")
    else:
        print(f"Warning: {open_count} positions still open.")

    print("\n=== STEP 4: CLEARING DATABASE TABLES (CLEAN SLATE) ===")
    db_path = '/root/BHARAT-SYSTEMS/ZERODHA-OS/zerodha_trader.db'
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM legs")
        cursor.execute("DELETE FROM strikes")
        cursor.execute("DELETE FROM blocks")
        conn.commit()
    print("✅ Database cleared: blocks, strikes, legs are reset to clean state.")

if __name__ == '__main__':
    main()
