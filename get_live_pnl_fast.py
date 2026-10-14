import json
from kiteconnect import KiteConnect

def main():
    with open('/root/BHARAT-SYSTEMS/ZERODHA-OS/access_token.json') as f:
        auth = json.load(f)

    k = KiteConnect(api_key=auth['api_key'])
    k.set_access_token(auth['access_token'])

    quotes = k.quote(['NFO:NIFTY26OCT23500CE', 'NFO:NIFTY26OCT23000CE', 'NSE:NIFTY 50'])
    nifty_ltp = quotes.get('NSE:NIFTY 50', {}).get('last_price', 0)
    buy_ltp = quotes.get('NFO:NIFTY26OCT23500CE', {}).get('last_price', 0)
    sell_ltp = quotes.get('NFO:NIFTY26OCT23000CE', {}).get('last_price', 0)

    buy_pnl = (buy_ltp - 42.40) * 325
    sell_pnl = (147.10 - sell_ltp) * 325
    total_pnl = buy_pnl + sell_pnl

    print(f"SPOT:{nifty_ltp}|BUY_LTP:{buy_ltp}|BUY_PNL:{buy_pnl:.2f}|SELL_LTP:{sell_ltp}|SELL_PNL:{sell_pnl:.2f}|TOTAL_PNL:{total_pnl:.2f}")

if __name__ == '__main__':
    main()
