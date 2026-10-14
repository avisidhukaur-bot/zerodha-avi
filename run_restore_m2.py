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

script = r'''
import sys
sys.path.insert(0, '/root/BHARAT-SYSTEMS/ZERODHA-OS')
import db
import time
from kite_executor import kite_executor
import regime_engine as re_eng

db.load_secrets()
kite_executor.load_session_from_db()

print("=== 1. FETCHING BROKER POSITIONS ===")
kite = kite_executor.kite
pos = kite.positions().get('net', [])

sell_sym = "NIFTY26OCT23400CE"
hedge_sym = "NIFTY26OCT23900CE"

sell_pos = next((p for p in pos if p.get('tradingsymbol') == sell_sym), None)
hedge_pos = next((p for p in pos if p.get('tradingsymbol') == hedge_sym), None)

sell_buy_price = float(sell_pos.get('sell_price') or sell_pos.get('average_price') or 146.85) if sell_pos else 146.85
hedge_buy_price = float(hedge_pos.get('buy_price') or hedge_pos.get('average_price') or 48.90) if hedge_pos else 48.90
sell_qty = abs(int(sell_pos.get('quantity', -260))) if sell_pos else 260
lots = max(1, sell_qty // 65)

print(f"Sell: {sell_sym} (Price: {sell_buy_price}, Qty: {sell_qty}, Lots: {lots})")
print(f"Hedge: {hedge_sym} (Price: {hedge_buy_price})")

# Check if any blocks exist
existing_blocks = db.get_all_blocks()
for b in existing_blocks:
    print(f"Cleaning block {b['block_id']}...")
    db.force_delete_block(b['block_id'])

# Step 1: Create Block
spot = re_eng.get_current_nifty_spot() or 22839.25
block_id = db.create_block(
    expiry_date="27-Oct-2026",
    expiry_type="MONTHLY",
    side_type="BOTH",
    master_anchor_price=spot,
    regime_buffer=15.0,
    anchor_unit_name="M2"
)
print(f"✅ Created Block ID: {block_id} for Unit M2")

# Set regime to BEARISH
db.update_block_regime(block_id, "BEARISH")

# Step 2: Add Strikes
# CE Hedge
s_h_id = db.add_strike(
    block_id=block_id,
    strike_price=23900,
    option_type="CE",
    leg_type="HEDGE_BUY",
    anchor_price=hedge_buy_price,
    lots=lots,
    expiry_date="27-Oct-2026",
    sl_pct=25.0,
    sl_price=0.0,
    reentry_enabled=1,
    trade_state="OPEN"
)
db.update_strike_status(s_h_id, "OPEN")

# CE Sell
sl_p = round(sell_buy_price * 1.25 * 20) / 20
s_s_id = db.add_strike(
    block_id=block_id,
    strike_price=23400,
    option_type="CE",
    leg_type="SELL",
    anchor_price=sell_buy_price,
    lots=lots,
    expiry_date="27-Oct-2026",
    sl_pct=25.0,
    sl_price=sl_p,
    reentry_enabled=1,
    trade_state="OPEN"
)
db.update_strike_status(s_s_id, "OPEN")

# Link CE hedge and sell in DB
conn = db._conn()
conn.execute("UPDATE strikes SET hedge_strike_id=? WHERE strike_id=?", (s_s_id, s_h_id))
conn.execute("UPDATE strikes SET hedge_strike_id=? WHERE strike_id=?", (s_h_id, s_s_id))
conn.commit()
conn.close()

# Create Legs in DB
db.create_leg(s_h_id, hedge_buy_price, "BROKER_SYNC")
db.create_leg(s_s_id, sell_buy_price, "BROKER_SYNC")

# Add Pending PE Wings (Armed)
p_h_id = db.add_strike(
    block_id=block_id,
    strike_price=22100,
    option_type="PE",
    leg_type="HEDGE_BUY",
    anchor_price=0.0,
    lots=lots,
    expiry_date="27-Oct-2026",
    sl_pct=25.0,
    sl_price=0.0,
    reentry_enabled=1,
    trade_state="PENDING"
)
db.update_strike_status(p_h_id, "PENDING")

p_s_id = db.add_strike(
    block_id=block_id,
    strike_price=22600,
    option_type="PE",
    leg_type="SELL",
    anchor_price=0.0,
    lots=lots,
    expiry_date="27-Oct-2026",
    sl_pct=25.0,
    sl_price=0.0,
    reentry_enabled=1,
    trade_state="PENDING"
)
db.update_strike_status(p_s_id, "PENDING")

conn = db._conn()
conn.execute("UPDATE strikes SET hedge_strike_id=? WHERE strike_id=?", (p_s_id, p_h_id))
conn.execute("UPDATE strikes SET hedge_strike_id=? WHERE strike_id=?", (p_h_id, p_s_id))
conn.commit()
conn.close()

print("✅ All M2 strikes & legs synchronized to DB!")

# Verify
all_b = db.get_all_blocks()
print(f"Total Blocks in DB: {len(all_b)}")
for b in all_b:
    print(f"Block ID: {b['block_id']} | Num: {b['block_number']} | Unit: {b['anchor_unit_name']} | Status: {b['status']}")
    for s in db.get_strikes_by_block(b['block_id']):
        print(f"   Strike {s['strike_id']} | {s['strike_price']} {s['option_type']} ({s['leg_type']}) | Status: {s['status']} | Lots: {s['lots']}")
'''

sftp = c.open_sftp()
with sftp.file('/root/BHARAT-SYSTEMS/ZERODHA-OS/restore_and_sync_m2.py', 'w') as f:
    f.write(script)
sftp.close()

stdin, stdout, stderr = c.exec_command("python3 /root/BHARAT-SYSTEMS/ZERODHA-OS/restore_and_sync_m2.py && systemctl restart zerodha_dashboard")
out = stdout.read().decode('utf-8', errors='replace')
err = stderr.read().decode('utf-8', errors='replace')
print("STDOUT:\n", out)
if err:
    print("STDERR:\n", err)

c.close()
