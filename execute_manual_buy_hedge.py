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
c.connect(secrets['VPS_IP'], username=secrets['VPS_USER'], password=secrets['VPS_PASSWORD'], timeout=15)

script = '''
import sys
import time
sys.path.insert(0, '/root/BHARAT-SYSTEMS/ZERODHA-OS')
import kite_executor as ke
import db

print("=== INITIATING HEDGE BUY FOR NIFTY26OCT23300CE (195 QTY / 3 LOTS) ===")
ke.kite_executor.ensure_logged_in()
kite = ke.kite_executor.kite

if not kite:
    print("❌ Error: Kite client not available.")
    sys.exit(1)

# Step 1: Fetch LTP for NIFTY26OCT23300CE
token = 13149186
tradingsymbol = "NIFTY26OCT23300CE"
ltp = ke.kite_executor.get_ltp(token, tradingsymbol)
if ltp <= 0:
    ltp = ke.kite_executor.get_live_ltp(token, tradingsymbol)
if ltp <= 0:
    # Direct quote via kite
    q = kite.quote(f"NFO:{tradingsymbol}")
    ltp = float(q.get(f"NFO:{tradingsymbol}", {}).get("last_price", 60.0))

print(f"Current LTP for {tradingsymbol}: ₹{ltp:.2f}")

# Calculate Limit Price (LTP + buffer for guaranteed fill)
limit_price = round((ltp + max(3.0, ltp * 0.08)) * 20) / 20
print(f"Placing LIMIT BUY order @ ₹{limit_price:.2f} (Qty: 195)")

# Step 2: Place LIMIT BUY order on Zerodha Kite
try:
    order_id = kite.place_order(
        variety=kite.VARIETY_REGULAR,
        exchange=kite.EXCHANGE_NFO,
        tradingsymbol=tradingsymbol,
        transaction_type=kite.TRANSACTION_TYPE_BUY,
        quantity=195,
        product=kite.PRODUCT_NRML,
        order_type=kite.ORDER_TYPE_LIMIT,
        price=limit_price
    )
    print(f"✅ Kite Order Placed: Order ID = {order_id}")
except Exception as e:
    print(f"❌ Failed to place limit buy order on Kite: {e}")
    sys.exit(1)

# Step 3: Poll order status and get fill price
fill_price = 0.0
for i in range(8):
    time.sleep(1)
    try:
        history = kite.order_history(order_id=order_id)
        if history:
            last = history[-1]
            status = last.get("status")
            print(f"Check {i+1}: Order status = {status}")
            if status == "COMPLETE":
                fill_price = float(last.get("average_price") or 0.0)
                print(f"🎉 Order COMPLETE! Fill Price: ₹{fill_price:.2f}")
                break
            elif status in ("REJECTED", "CANCELLED"):
                print(f"❌ Order {status}: {last.get('status_message')}")
                sys.exit(1)
    except Exception as e:
        print(f"Error checking order history: {e}")

if fill_price <= 0.0:
    fill_price = ltp
    print(f"Fallback Fill Price: ₹{fill_price:.2f}")

# Step 4: Update DB Strike 192 (or Block 73 Hedge)
conn = db._conn()
cur = conn.cursor()

cur.execute("""
    UPDATE strikes 
    SET status = 'OPEN', 
        trade_state = 'OPEN', 
        anchor_price = ?, 
        hedge_strike_id = 193 
    WHERE strike_id = 192
""", (fill_price,))

cur.execute("""
    UPDATE strikes 
    SET hedge_strike_id = 192 
    WHERE strike_id = 193
""")

conn.commit()

# Create active leg in DB
db.create_leg(192, fill_price, "MANUAL_HEDGE_BUY")

print("✅ DB Successfully updated: Strike 192 set to OPEN with linked Sell Strike 193")

# Step 5: Verify Live Positions
print("\\n=== LIVE BROKER POSITIONS VERIFICATION ===")
time.sleep(1)
pos = ke.kite_executor.get_positions()
for p in pos:
    if p.get('quantity') != 0:
        print(f"Symbol: {p['tradingsymbol']} | Qty: {p['quantity']} | Avg: ₹{p.get('average_price') or p.get('buy_price') or p.get('sell_price')} | PnL: ₹{p.get('pnl'):,.2f} | LTP: ₹{p.get('last_price'):.2f}")

'''

sftp = c.open_sftp()
f = sftp.file('/tmp/exec_hedge_buy.py', 'w')
f.write(script)
f.close()
sftp.close()

stdin, stdout, stderr = c.exec_command('python3 /tmp/exec_hedge_buy.py')
print(stdout.read().decode('utf-8', errors='replace'))
print(stderr.read().decode('utf-8', errors='replace'))
c.close()
