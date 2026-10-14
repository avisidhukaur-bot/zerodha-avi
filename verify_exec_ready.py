import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import db
from kite_executor import kite_executor
import block_manager as bm

db.load_secrets()
kite_executor.load_session_from_db()

print("=== READY TO EXECUTE BLOCK 57 ===")
block = db.get_block(57)
print("Block:", block)

strikes = db.get_strikes_by_block(57)
for s in strikes:
    print("Strike:", s['strike_id'], s['strike_price'], s['option_type'], s['leg_type'], s['status'], "Lots:", s['lots'])

# Check kite connection
profile = kite_executor.kite.profile()
print(f"Kite Profile: {profile.get('user_name')} ({profile.get('user_id')})")
