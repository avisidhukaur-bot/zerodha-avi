import sqlite3
import os
from datetime import datetime
import pytz

IST = pytz.timezone("Asia/Kolkata")
now_str = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")

local_db = os.path.join(os.path.dirname(__file__), "zerodha_trader.db")
conn = sqlite3.connect(local_db)
cur = conn.cursor()

# 1. Update strikes 154 and 155 to OPEN
cur.execute("UPDATE strikes SET status='OPEN', trade_state='OPEN' WHERE strike_id IN (154, 155)")

# 2. Check and insert open legs for 154 and 155
cur.execute("SELECT leg_id FROM legs WHERE strike_id=154 AND (exit_time IS NULL OR exit_time='')")
if not cur.fetchone():
    cur.execute("INSERT INTO legs (strike_id, entry_price, entry_time, order_id) VALUES (154, 42.40, ?, '2106720737909033984')", (now_str,))
    print("Inserted Local Leg 154 (Hedge)")

cur.execute("SELECT leg_id FROM legs WHERE strike_id=155 AND (exit_time IS NULL OR exit_time='')")
if not cur.fetchone():
    cur.execute("INSERT INTO legs (strike_id, entry_price, entry_time, order_id) VALUES (155, 147.10, ?, '2106720743143525376')", (now_str,))
    print("Inserted Local Leg 155 (Sell)")

conn.commit()

# Verify
cur.execute("SELECT strike_id, strike_price, option_type, leg_type, status, trade_state FROM strikes WHERE block_id=57")
for row in cur.fetchall():
    print("Local Strike:", row)

conn.close()
print("Local database updated to OPEN state successfully!")
