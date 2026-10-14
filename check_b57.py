import db
from kite_executor import kite_executor
import sqlite3

db.load_secrets()
kite_executor.load_session_from_db()
kite = kite_executor.kite

conn = db._conn()
cur = conn.cursor()
cur.execute("SELECT * FROM blocks WHERE status='ACTIVE'")
blocks = cur.fetchall()
print(f"=== ACTIVE BLOCK IN DB ===")
for b in blocks:
    b_dict = dict(b)
    print("Block ID:", b_dict['block_id'], "| Expiry:", b_dict['expiry_date'], "| Anchor:", b_dict['master_anchor_price'], "| Regime:", b_dict['current_regime'])
    cur.execute("SELECT * FROM strikes WHERE block_id=?", (b_dict['block_id'],))
    for s in cur.fetchall():
        s_dict = dict(s)
        sym = kite_executor.search_option_symbol(s_dict['strike_price'], s_dict['option_type'], b_dict['expiry_date'])
        ltp = kite_executor.get_ltp(f"NFO:{sym}") if sym else 0.0
        print(f"   Strike ID {s_dict['strike_id']}: {sym} ({s_dict['leg_type']}) | Lots: {s_dict['lots']} | Anchor: {s_dict['anchor_price']} | Live LTP: {ltp} | Status: {s_dict['status']} | State: {s_dict.get('trade_state')}")
conn.close()
