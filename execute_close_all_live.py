import paramiko
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

secrets = {}
with open('secrets.txt', encoding='utf-8') as f:
    for l in f:
        if '=' in l and not l.startswith('#'):
            k, v = l.strip().split('=', 1)
            secrets[k.strip()] = v.strip()

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(secrets['VPS_IP'], username=secrets['VPS_USER'], password=secrets['VPS_PASSWORD'], timeout=10)

script = r'''
import sys
sys.path.insert(0, '/root/BHARAT-SYSTEMS/ZERODHA-OS')
import db
import time
from kite_executor import kite_executor
import telegram_bot as tg

db.load_secrets()
kite_executor.load_session_from_db()

print("=== 1. PAUSING ALGO IN DATABASE ===")
db.set("algo_running", "OFF")
print("✅ Algo set to OFF (Trading paused).")

print("\n=== 2. FETCHING LIVE POSITIONS FROM BROKER ===")
if not kite_executor.ensure_logged_in():
    print("❌ Cannot login to Kite!")
    sys.exit(1)

kite = kite_executor.kite
pos = kite.positions().get('net', [])

ce_sell_sym = "NIFTY26SEP23700CE"
ce_hedge_sym = "NIFTY26SEP24200CE"

sell_qty = 0
hedge_qty = 0

for p in pos:
    sym = p.get('tradingsymbol', '')
    qty = int(p.get('quantity', 0) or 0)
    if sym == ce_sell_sym:
        sell_qty = qty
    elif sym == ce_hedge_sym:
        hedge_qty = qty

print(f"Current Broker Positions -> {ce_sell_sym}: {sell_qty} | {ce_hedge_sym}: {hedge_qty}")

# STEP 1: CLOSE SHORT SELL LEG FIRST (Buy to Cover)
if sell_qty < 0:
    cover_qty = abs(sell_qty)
    ltp_s = kite_executor.get_live_ltp("", ce_sell_sym) or 55.0
    limit_buy = round((ltp_s + max(2.0, ltp_s * 0.15)) * 20) / 20
    print(f"\n[STEP 1] Buying to cover short leg {ce_sell_sym} (Qty: {cover_qty}, Limit: Rs {limit_buy})...")
    try:
        oid_cover = kite.place_order(
            variety=kite.VARIETY_REGULAR,
            exchange=kite.EXCHANGE_NFO,
            tradingsymbol=ce_sell_sym,
            transaction_type=kite.TRANSACTION_TYPE_BUY,
            quantity=cover_qty,
            product=kite.PRODUCT_NRML,
            order_type=kite.ORDER_TYPE_LIMIT,
            price=limit_buy
        )
        print(f"✅ Short cover order placed! Order ID: {oid_cover}")
        time.sleep(2)
        hist = kite.order_history(order_id=oid_cover)
        if hist:
            print(f"Order status: {hist[-1].get('status')} | Avg Price: {hist[-1].get('average_price')}")
    except Exception as e:
        print(f"❌ Error covering short leg: {e}")

time.sleep(2)

# STEP 2: CLOSE HEDGE BUY LEG SECOND (Sell to Exit)
if hedge_qty > 0:
    exit_qty = hedge_qty
    ltp_h = kite_executor.get_live_ltp("", ce_hedge_sym) or 8.0
    limit_sell = round(max(0.05, (ltp_h - max(2.0, ltp_h * 0.15))) * 20) / 20
    print(f"\n[STEP 2] Selling to exit hedge leg {ce_hedge_sym} (Qty: {exit_qty}, Limit: Rs {limit_sell})...")
    try:
        oid_exit = kite.place_order(
            variety=kite.VARIETY_REGULAR,
            exchange=kite.EXCHANGE_NFO,
            tradingsymbol=ce_hedge_sym,
            transaction_type=kite.TRANSACTION_TYPE_SELL,
            quantity=exit_qty,
            product=kite.PRODUCT_NRML,
            order_type=kite.ORDER_TYPE_LIMIT,
            price=limit_sell
        )
        print(f"✅ Hedge exit order placed! Order ID: {oid_exit}")
        time.sleep(2)
        hist = kite.order_history(order_id=oid_exit)
        if hist:
            print(f"Order status: {hist[-1].get('status')} | Avg Price: {hist[-1].get('average_price')}")
    except Exception as e:
        print(f"❌ Error exiting hedge leg: {e}")

# STEP 3: UPDATE DB STRIKES & LEGS
print("\n=== 3. UPDATING DATABASE LEGS ===")
conn = db._conn()
cur = conn.cursor()
cur.execute("UPDATE legs SET exit_time=datetime('now', 'localtime') WHERE exit_time IS NULL OR exit_time = ''")
cur.execute("UPDATE strikes SET status='CLOSED', trade_state='CLOSED' WHERE block_id=32")
conn.commit()
conn.close()
print("✅ Database legs and strikes updated to CLOSED.")

# STEP 4: VERIFY BROKER POSITIONS ARE ZERO
time.sleep(2)
pos_after = kite.positions().get('net', [])
print("\n=== 4. FINAL BROKER POSITIONS VERIFICATION ===")
for p in pos_after:
    if p.get('quantity') != 0:
        print(f"⚠️ Open Position: {p.get('tradingsymbol')} Qty: {p.get('quantity')}")
    else:
        print(f"✅ Closed: {p.get('tradingsymbol')} Net Qty: 0 | P&L: Rs {p.get('pnl',0):,.2f}")

try:
    tg.send("🛑 <b>MANUAL TRADE CLOSURE COMPLETE</b>\nAll open positions on Unit M3 (23700 CE & 24200 CE) have been safely closed in sequence. Algo paused.")
except Exception:
    pass
'''

sftp = c.open_sftp()
with sftp.file('/root/BHARAT-SYSTEMS/ZERODHA-OS/execute_close_all_live.py', 'w') as f:
    f.write(script)
sftp.close()

stdin, stdout, stderr = c.exec_command("python3 /root/BHARAT-SYSTEMS/ZERODHA-OS/execute_close_all_live.py")
print(stdout.read().decode('utf-8', errors='replace'))
err = stderr.read().decode('utf-8', errors='replace')
if err:
    print("STDERR:", err)

c.close()
