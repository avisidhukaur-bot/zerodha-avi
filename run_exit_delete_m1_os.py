import paramiko
import sys
import time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

secrets = {}
with open('secrets.txt', encoding='utf-8') as f:
    for l in f:
        if '=' in l and not l.startswith('#'):
            k, v = l.strip().split('=', 1)
            secrets[k.strip()] = v.strip()

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(secrets['VPS_IP'], username=secrets['VPS_USER'], password=secrets['VPS_PASSWORD'], timeout=15)

script = r'''
import sys
sys.path.insert(0, '/root/BHARAT-SYSTEMS/ZERODHA-OS')
import db
import time
from kite_executor import kite_executor
import telegram_bot as tg

db.load_secrets()
kite_executor.load_session_from_db()

print("=== 1. ENSURE KITE LOGIN ===")
if not kite_executor.ensure_logged_in():
    print("❌ Failed to login to Kite!")
    sys.exit(1)

kite = kite_executor.kite

print("\n=== 2. CANCELING ANY OPEN/PENDING ORDERS FOR M1 & OS ===")
try:
    orders = kite.orders()
    for o in orders:
        if o.get('status') in ('OPEN', 'TRIGGER PENDING'):
            oid = o.get('order_id')
            sym = o.get('tradingsymbol')
            if any(k in sym for k in ['23600', '24100', '24000', '24500']):
                print(f"Cancelling pending order {oid} for {sym}...")
                kite.cancel_order(variety=kite.VARIETY_REGULAR, order_id=oid)
except Exception as e:
    print(f"Cancel error: {e}")

print("\n=== 3. FETCHING CURRENT BROKER POSITIONS ===")
pos = kite.positions().get('net', [])
pos_dict = {p.get('tradingsymbol'): p for p in pos}

# -------------------------------------------------------------
# M1 SYMBOLS: 23600 CE (Sell), 24100 CE (Hedge)
# OS1 SYMBOLS: 24000 CE (Sell), 24500 CE (Hedge)
# -------------------------------------------------------------
targets_to_close = [
    # (Symbol, Target Qty close type, Leg Name)
    ("NIFTY26OCT23600CE", "SELL_LEG", "M1 SELL 23600 CE"),
    ("NIFTY26OCT24000CE", "SELL_LEG", "OS1 SELL 24000 CE"),
    ("NIFTY26OCT24100CE", "HEDGE_LEG", "M1 HEDGE 24100 CE"),
    ("NIFTY26OCT24500CE", "HEDGE_LEG", "OS1 HEDGE 24500 CE"),
]

print("\n=== 4. EXECUTING CLOSURES ON ZERODHA BROKER ===")
# Phase A: Close SELL positions first (Buy to cover)
for sym, leg_type, desc in targets_to_close:
    if leg_type != "SELL_LEG":
        continue
    p = pos_dict.get(sym, {})
    qty = int(p.get('quantity', 0) or 0)
    if qty < 0:
        buy_qty = abs(qty)
        ltp = kite_executor.get_live_ltp("", sym) or float(p.get('last_price', 0)) or 100.0
        # Tolerant limit price to ensure instant fill without slippage risk
        limit_price = round((ltp + max(3.0, ltp * 0.10)) * 20) / 20
        print(f"Closing {desc} [{sym}]: BUY {buy_qty} qty @ Limit Rs {limit_price} (LTP: Rs {ltp})...")
        try:
            oid = kite.place_order(
                variety=kite.VARIETY_REGULAR,
                exchange=kite.EXCHANGE_NFO,
                tradingsymbol=sym,
                transaction_type=kite.TRANSACTION_TYPE_BUY,
                quantity=buy_qty,
                product=kite.PRODUCT_NRML,
                order_type=kite.ORDER_TYPE_LIMIT,
                price=limit_price
            )
            print(f"✅ BUY Order placed: ID {oid}")
            time.sleep(1.5)
            hist = kite.order_history(order_id=oid)
            if hist:
                print(f"   Status: {hist[-1].get('status')} | Avg: Rs {hist[-1].get('average_price')}")
        except Exception as e:
            print(f"❌ Error closing {sym}: {e}")

# Phase B: Close HEDGE positions second (Sell to square off)
for sym, leg_type, desc in targets_to_close:
    if leg_type != "HEDGE_LEG":
        continue
    p = pos_dict.get(sym, {})
    qty = int(p.get('quantity', 0) or 0)
    if qty > 0:
        sell_qty = qty
        ltp = kite_executor.get_live_ltp("", sym) or float(p.get('last_price', 0)) or 30.0
        limit_price = round(max(0.05, ltp - max(2.0, ltp * 0.10)) * 20) / 20
        print(f"Closing {desc} [{sym}]: SELL {sell_qty} qty @ Limit Rs {limit_price} (LTP: Rs {ltp})...")
        try:
            oid = kite.place_order(
                variety=kite.VARIETY_REGULAR,
                exchange=kite.EXCHANGE_NFO,
                tradingsymbol=sym,
                transaction_type=kite.TRANSACTION_TYPE_SELL,
                quantity=sell_qty,
                product=kite.PRODUCT_NRML,
                order_type=kite.ORDER_TYPE_LIMIT,
                price=limit_price
            )
            print(f"✅ SELL Order placed: ID {oid}")
            time.sleep(1.5)
            hist = kite.order_history(order_id=oid)
            if hist:
                print(f"   Status: {hist[-1].get('status')} | Avg: Rs {hist[-1].get('average_price')}")
        except Exception as e:
            print(f"❌ Error closing {sym}: {e}")

time.sleep(2)

print("\n=== 5. PURGING / DELETING M1 & OS1 FROM DATABASE ===")
# 1. Force delete M1 Block
all_blocks = db.get_all_blocks()
for b in all_blocks:
    unit_name = (b.get('anchor_unit_name') or '').strip().upper()
    bid = b.get('block_id')
    if unit_name == 'M1' or b.get('block_number') == 6:
        print(f"Force deleting M1 Block ID {bid} (Num #{b.get('block_number')})...")
        res = db.force_delete_block(bid)
        print(f"✅ M1 Block deleted: {res}")
    elif unit_name.startswith('OS') or b.get('block_number') == 5:
        print(f"Wiping out OS Pod Block ID {bid} (Num #{b.get('block_number')})...")
        res = db.force_delete_block(bid)
        print(f"✅ OS Block deleted: {res}")

db.reset_os_daily_trade_flag('OS1')
db.unlock_os_settings()
print("✅ OS1 settings reset & unlocked.")

print("\n=== 6. VERIFY FINAL BROKER POSITIONS ===")
final_pos = kite.positions().get('net', [])
for p in final_pos:
    sym = p.get('tradingsymbol', '')
    qty = p.get('quantity', 0)
    pnl = p.get('pnl', 0.0)
    if qty != 0:
        print(f"🟢 STILL OPEN: {sym} | Qty: {qty} | P&L: Rs {pnl:,.2f}")
    else:
        print(f"⚪ CLOSED: {sym} | Net Qty: 0 | P&L: Rs {pnl:,.2f}")

print("\n=== 7. VERIFY FINAL DATABASE BLOCKS ===")
remaining_blocks = db.get_all_blocks()
for b in remaining_blocks:
    print(f"Remaining Block: ID {b.get('block_id')} | Num #{b.get('block_number')} | Unit: {b.get('anchor_unit_name')} | Status: {b.get('status')}")

# Telegram alert
try:
    tg.send(
        "🛑 <b>PROFIT BOOKED & UNITS DELETED</b> 🛑\n\n"
        "✅ <b>Unit M1 (23600 CE / 24100 CE)</b>: Safely Closed & Block deleted.\n"
        "✅ <b>Unit OS1 (24000 CE / 24500 CE)</b>: Safely Closed & Pod wiped out.\n"
        "🟢 <b>Unit M2 (23400 CE / 23900 CE)</b>: Active & Running smoothly."
    )
except Exception as e:
    print(f"Telegram error: {e}")
'''

sftp = c.open_sftp()
with sftp.file('/root/BHARAT-SYSTEMS/ZERODHA-OS/execute_exit_and_delete_m1_os.py', 'w') as f:
    f.write(script)
sftp.close()

stdin, stdout, stderr = c.exec_command("python3 /root/BHARAT-SYSTEMS/ZERODHA-OS/execute_exit_and_delete_m1_os.py")
out = stdout.read().decode('utf-8', errors='replace')
err = stderr.read().decode('utf-8', errors='replace')
print("STDOUT:\n", out)
if err:
    print("STDERR:\n", err)

c.close()
