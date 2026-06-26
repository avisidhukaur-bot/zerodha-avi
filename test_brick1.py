"""
test_brick1.py — Brick 1 Verification Script
Run: python test_brick1.py
"""
import os
import sys
sys.path.insert(0, ".")

# Clean up test DB first
for db_name in ("zerodha_trader.db",):
    if os.path.exists(db_name):
        try:
            os.remove(db_name)
            print(f"[TEST] Cleaned up old DB: {db_name}")
        except Exception as e:
            print(f"[TEST] Warn: could not remove {db_name}: {e}")

print("=" * 50)
print("  BRICK 1 VERIFICATION — db.py")
print("=" * 50)

import db

print()
print("--- Testing create_block ---")
bid1 = db.create_block("26-Jun-2025", "MONTHLY", "Test Monthly Block")
bid2 = db.create_block("19-Jun-2025", "WEEKLY",  "Test Weekly Block")
print(f"Block IDs created: {bid1}, {bid2}")
assert bid1 > 0, "Block 1 creation failed"
assert bid2 > 0, "Block 2 creation failed"

print()
print("--- Testing get_all_blocks ---")
blocks = db.get_all_blocks()
for b in blocks:
    print(f"  Block {b['block_number']}: {b['expiry_date']} ({b['expiry_type']}) Status={b['status']}")
assert len(blocks) == 2, f"Expected 2 blocks, got {len(blocks)}"

print()
print("--- Testing add_strike (SELL legs) ---")
s1 = db.add_strike(bid1, 24000, "CE", "SELL",     120.00, 2)
s2 = db.add_strike(bid1, 24000, "PE", "SELL",     115.00, 2)
s3 = db.add_strike(bid1, 24500, "CE", "HEDGE_BUY", 40.00, 2)
print(f"Strike IDs: s1={s1}, s2={s2}, s3={s3}")
assert all(x > 0 for x in [s1, s2, s3]), "Strike creation failed"

print()
print("--- HARD RULE: anchor=0 must FAIL ---")
bad = db.add_strike(bid1, 25000, "CE", "SELL", 0.0, 1)
assert bad == -1, "RULE VIOLATION: anchor=0 should return -1"
print("  ✅ anchor=0 correctly rejected")

print()
print("--- HARD RULE: invalid option_type must FAIL ---")
bad2 = db.add_strike(bid1, 25000, "XX", "SELL", 50.0, 1)
assert bad2 == -1, "RULE VIOLATION: invalid option_type should return -1"
print("  ✅ invalid option_type correctly rejected")

print()
print("--- Testing link_hedge ---")
ok = db.link_hedge(s1, s3)
assert ok, "Hedge linking failed"
s1_data = db.get_strike(s1)
assert s1_data["hedge_strike_id"] == s3, "Hedge link not saved"
print("  ✅ Hedge linked and verified in DB")

print()
print("--- Testing create_leg (order fill) ---")
leg1 = db.create_leg(s1, 119.50, "KITE_ORD_001")
assert leg1 > 0, "Leg creation failed"
s1_updated = db.get_strike(s1)
assert s1_updated["status"] == "OPEN", "Strike should be OPEN after leg created"
print(f"  ✅ Leg {leg1} created — Strike {s1} now OPEN")

print()
print("--- Testing log_trade ---")
t1 = db.log_trade(bid1, s1, "ENTRY", 119.50, 2, "SUCCESS")
assert t1 > 0, "Trade log failed"
trades = db.get_trades(block_id=bid1)
assert len(trades) == 1, f"Expected 1 trade, got {len(trades)}"
print(f"  ✅ Trade {t1} logged and retrieved")

print()
print("--- Testing P&L calculation ---")
ltp_map = {s1: 95.00, s2: 88.00, s3: 52.00}

# Only s1 is OPEN, so only s1 P&L is calculated
# s1 = SELL: (120 - 95) * 2 * 65 = 3250
bpnl = db.calc_block_pnl(bid1, ltp_map)
print(f"  Block {bid1} P&L: Rs{bpnl['total_pnl']}")
for sp in bpnl["strike_pnls"]:
    print(f"    {sp['strike_price']} {sp['option_type']} {sp['leg_type']}: Rs{sp['pnl']}")
assert bpnl["total_pnl"] == 3250.0, f"Expected 3250.0, got {bpnl['total_pnl']}"
print("  ✅ P&L formula verified: (120-95)*2*65 = Rs3250")

print()
print("--- Testing settings get/set ---")
db.set("test_key", "hello_world")
val = db.get("test_key")
assert val == "hello_world", f"Settings failed: {val}"
print(f"  ✅ Settings: set/get working")

print()
print("--- HARD RULE: Max 5 strikes per block ---")
# Already have 3 (s1, s2, s3). Add 2 more to reach max
db.add_strike(bid1, 24100, "CE", "SELL", 50.0, 1)
db.add_strike(bid1, 24200, "PE", "SELL", 45.0, 1)
# This 6th one should be blocked
result_6th = db.add_strike(bid1, 24300, "CE", "SELL", 40.0, 1)
total_strikes = len(db.get_strikes_by_block(bid1))
assert total_strikes == 5, f"RULE VIOLATION: {total_strikes} strikes in block (max=5)"
assert result_6th == -1, "RULE VIOLATION: 6th strike should be blocked"
print(f"  ✅ Max 5 strikes enforced — 6th correctly blocked")

print()
print("--- HARD RULE: Cannot delete OPEN block ---")
ok_delete = db.delete_block(bid1)
assert not ok_delete, "RULE VIOLATION: Block with OPEN strike should not be deletable"
print("  ✅ Delete blocked correctly (OPEN strike exists)")

print()
print("--- Testing close_leg ---")
closed = db.close_leg(leg1, 80.00, 3250.00)
assert closed, "Leg close failed"
strike_after = db.get_strike(s1)
assert strike_after["status"] == "CLOSED", f"Strike should be CLOSED: {strike_after['status']}"
print("  ✅ Leg closed — Strike status CLOSED")

print()
print("--- Testing portfolio P&L ---")
port = db.calc_portfolio_pnl({})
print(f"  Portfolio P&L: Rs{port['total_pnl']}")
print(f"  Active blocks: {len(port['block_pnls'])}")
print("  ✅ Portfolio P&L function working")

print()
print("=" * 50)
print("  ✅ ALL BRICK 1 TESTS PASSED!")
print("  db.py is VERIFIED and READY")
print("=" * 50)
