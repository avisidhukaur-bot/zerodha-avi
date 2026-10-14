import json
from kiteconnect import KiteConnect

def main():
    with open('/root/BHARAT-SYSTEMS/ZERODHA-OS/access_token.json') as f:
        auth = json.load(f)

    k = KiteConnect(api_key=auth['api_key'])
    k.set_access_token(auth['access_token'])

    prof = k.profile()
    print("=== PROFILE ===")
    print(prof)

    print("\n=== ORDERS ===")
    orders = k.orders()
    print(f"Total Orders: {len(orders)}")
    for o in orders:
        print(f"Order ID: {o.get('order_id')} | Sym: {o.get('tradingsymbol')} | Type: {o.get('transaction_type')} | Qty: {o.get('quantity')} | Status: {o.get('status')} | Price: {o.get('average_price')} | ExchOrder: {o.get('exchange_order_id')}")

    print("\n=== POSITIONS ===")
    pos = k.positions()
    print("Net Positions:", pos.get('net'))
    print("Day Positions:", pos.get('day'))

if __name__ == '__main__':
    main()
