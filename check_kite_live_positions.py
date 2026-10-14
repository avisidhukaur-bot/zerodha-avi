import json
from kiteconnect import KiteConnect

def main():
    with open('/root/BHARAT-SYSTEMS/ZERODHA-OS/access_token.json') as f:
        auth = json.load(f)
    k = KiteConnect(api_key=auth['api_key'])
    k.set_access_token(auth['access_token'])
    
    profile = k.profile()
    print("LOGGED IN USER:", profile.get('user_name'), "USER ID:", profile.get('user_id'), "EMAIL:", profile.get('email'))
    
    pos = k.positions()
    print("\n=== KITE NET POSITIONS ===")
    print("Net positions count:", len(pos.get('net', [])))
    for p in pos.get('net', []):
        print(f"Symbol: {p.get('tradingsymbol')} | Qty: {p.get('quantity')} | BuyQty: {p.get('buy_quantity')} | SellQty: {p.get('sell_quantity')} | PnL: {p.get('pnl')} | Product: {p.get('product')}")
    
    print("\n=== KITE DAY POSITIONS ===")
    print("Day positions count:", len(pos.get('day', [])))
    for p in pos.get('day', []):
        print(f"Symbol: {p.get('tradingsymbol')} | Qty: {p.get('quantity')} | BuyQty: {p.get('buy_quantity')} | SellQty: {p.get('sell_quantity')} | PnL: {p.get('pnl')}")

    orders = k.orders()
    print(f"\n=== TODAY ORDERS (Total: {len(orders)}) ===")
    for o in orders[-15:]:
        print(f"Time: {o.get('order_timestamp')} | {o.get('tradingsymbol')} | {o.get('transaction_type')} | Qty: {o.get('quantity')} | Status: {o.get('status')} | Price: {o.get('average_price')} | StatusMsg: {o.get('status_message')}")

if __name__ == '__main__':
    main()
