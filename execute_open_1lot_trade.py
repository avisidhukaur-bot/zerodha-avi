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

if not kite_executor.ensure_logged_in():
    print("❌ Kite login failed!")
    sys.exit(1)

kite = kite_executor.kite

ce_sell_sym = "NIFTY26SEP23700CE"
ce_hedge_sym = "NIFTY26SEP24200CE"
qty = 65  # Strictly 1 Lot

print("=== 1. VERIFYING CURRENT BROKER POSITIONS ===")
pos = kite.positions().get('net', [])
cur_sell_qty = 0
cur_hedge_qty = 0
for p in pos:
    if p.get('tradingsymbol') == ce_sell_sym:
        cur_sell_qty = int(p.get('quantity', 0) or 0)
    elif p.get('tradingsymbol') == ce_hedge_sym:
        cur_hedge_qty = int(p.get('quantity', 0) or 0)

print(f"Broker Live Qty -> {ce_sell_sym}: {cur_sell_qty} | {ce_hedge_sym}: {cur_hedge_qty}")

# STEP 1: PLACE 1 LOT HEDGE BUY (24200 CE) FIRST
hedge_oid = None
hedge_fill_price = 0.0
if cur_hedge_qty < qty:
    needed_h = qty - cur_hedge_qty
    ltp_h = kite_executor.get_live_ltp("", ce_hedge_sym) or 8.5
    limit_h = round((ltp_h + max(2.0, ltp_h * 0.15)) * 20) / 20
    print(f"\n[STEP 1] Buying 1 Lot Hedge {ce_hedge_sym} (Qty: {needed_h}, Limit: Rs {limit_h})...")
    hedge_oid = kite.place_order(
        variety=kite.VARIETY_REGULAR,
        exchange=kite.EXCHANGE_NFO,
        tradingsymbol=ce_hedge_sym,
        transaction_type=kite.TRANSACTION_TYPE_BUY,
        quantity=needed_h,
        product=kite.PRODUCT_NRML,
        order_type=kite.ORDER_TYPE_LIMIT,
        price=limit_h
    )
    print(f"✅ Hedge Buy Placed: Order ID {hedge_oid}")
    time.sleep(2)
    hist = kite.order_history(order_id=hedge_oid)
    if hist:
        hedge_fill_price = float(hist[-1].get('average_price', 0.0) or ltp_h)
        print(f"Hedge Fill Status: {hist[-1].get('status')} | Price: Rs {hedge_fill_price}")

time.sleep(2)

# STEP 2: PLACE 1 LOT SHORT SELL (23700 CE) SECOND
sell_oid = None
sell_fill_price = 0.0
if cur_sell_qty > -qty:
    needed_s = abs(-qty - cur_sell_qty)
    ltp_s = kite_executor.get_live_ltp("", ce_sell_sym) or 54.0
    limit_s = round(max(0.05, (ltp_s - max(2.0, ltp_s * 0.15))) * 20) / 20
    print(f"\n[STEP 2] Selling 1 Lot {ce_sell_sym} (Qty: {needed_s}, Limit: Rs {limit_s})...")
    sell_oid = kite.place_order(
        variety=kite.VARIETY_REGULAR,
        exchange=kite.EXCHANGE_NFO,
        tradingsymbol=ce_sell_sym,
        transaction_type=kite.TRANSACTION_TYPE_SELL,
        quantity=needed_s,
        product=kite.PRODUCT_NRML,
        order_type=kite.ORDER_TYPE_LIMIT,
        price=limit_s
    )
    print(f"✅ Sell Order Placed: Order ID {sell_oid}")
    time.sleep(2)
    hist = kite.order_history(order_id=sell_oid)
    if hist:
        sell_fill_price = float(hist[-1].get('average_price', 0.0) or ltp_s)
        print(f"Sell Fill Status: {hist[-1].get('status')} | Price: Rs {sell_fill_price}")

# STEP 3: UPDATE DATABASE WITH EXACT 1 LOT LEGS & STRIKES
print("\n=== 3. UPDATING DATABASE TO ACTIVE 1 LOT ===")
conn = db._conn()
cur = conn.cursor()

# Update strikes status to OPEN and trade_state to ACTIVE
cur.execute("UPDATE strikes SET status='OPEN', trade_state='ACTIVE', lots=1 WHERE strike_id=90")
cur.execute("UPDATE strikes SET status='OPEN', trade_state='ACTIVE', lots=1, sl_price=80.0 WHERE strike_id=91")

# Insert open legs
cur.execute("INSERT INTO legs (strike_id, entry_price, entry_time, order_id) VALUES (?, ?, datetime('now', 'localtime'), ?)",
            (90, hedge_fill_price, hedge_oid or 'MANUAL_1LOT'))
cur.execute("INSERT INTO legs (strike_id, entry_price, entry_time, order_id) VALUES (?, ?, datetime('now', 'localtime'), ?)",
            (91, sell_fill_price, sell_oid or 'MANUAL_1LOT'))

# Turn Algo ON
cur.execute("UPDATE settings SET value='ON' WHERE key='algo_running'")
conn.commit()
conn.close()
print("✅ Database updated & Algo set to ON.")

# STEP 4: VERIFY FINAL POSITIONS
time.sleep(2)
pos_after = kite.positions().get('net', [])
print("\n=== 4. LIVE BROKER POSITIONS VERIFICATION ===")
for p in pos_after:
    if p.get('quantity') != 0:
        print(f"📊 Active: {p.get('tradingsymbol')} | Net Qty: {p.get('quantity')} | Buy Avg: {p.get('buy_price')} | Sell Avg: {p.get('sell_price')} | LTP: {p.get('last_price')}")

try:
    tg.send(f"🚀 <b>UNIT M3 RE-DEPLOYED (EXACTLY 1 LOT)</b>\n• Sell: 23700 CE (-65 Qty) @ ₹{sell_fill_price:.2f}\n• Hedge: 24200 CE (+65 Qty) @ ₹{hedge_fill_price:.2f}\n• SL Trigger: ₹80.00\n• Algo Running: ON")
except Exception:
    pass
'''

sftp = c.open_sftp()
with sftp.file('/root/BHARAT-SYSTEMS/ZERODHA-OS/execute_open_1lot_trade.py', 'w') as f:
    f.write(script)
sftp.close()

stdin, stdout, stderr = c.exec_command("python3 /root/BHARAT-SYSTEMS/ZERODHA-OS/execute_open_1lot_trade.py")
print(stdout.read().decode('utf-8', errors='replace'))
err = stderr.read().decode('utf-8', errors='replace')
if err:
    print("STDERR:", err)

c.close()
