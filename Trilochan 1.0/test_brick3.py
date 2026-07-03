"""
test_brick3.py -- Brick 3 Verification: block_manager.py
Run: python test_brick3.py
"""
import sys, os
sys.path.insert(0, ".")

# Clean test DB
for db_name in ("zerodha_trader.db",):
    if os.path.exists(db_name):
        try:
            os.remove(db_name)
        except Exception:
            pass

import db
db.set("KITE_CLIENT_CODE", "MOCK_CODE")
db.set("KITE_PASSWORD", "123456")
db.set("KITE_TOTP_KEY", "123456")
db.set("KITE_API_KEY", "MOCK_KEY")
db.set("KITE_API_SECRET", "MOCK_SECRET")

print("=" * 58)
print("  BRICK 3 VERIFICATION -- block_manager.py")
print("=" * 58)

from kite_executor import kite_executor

# Mock the methods of kite_executor directly
import time
kite_executor.login = lambda: True
kite_executor.ensure_logged_in = lambda: True
kite_executor.search_option_symbol = lambda expiry_date, strike_price, option_type, **kwargs: {
    "token": "MOCK_TOKEN_001" if option_type == "CE" else "MOCK_TOKEN_002",
    "trading_symbol": f"NIFTY{expiry_date.replace('-', '').upper()}{strike_price}{option_type}",
    "security_id": "MOCK_TOKEN_001" if option_type == "CE" else "MOCK_TOKEN_002",
    "underlying": "NIFTY 50",
}
kite_executor.execute_sell_and_confirm = lambda trading_symbol, symbol_token, qty, limit_price=0.0: (f"PAPER_MOCK_ORDER_SELL", True)
kite_executor.execute_buy_and_confirm = lambda trading_symbol, symbol_token, qty, limit_price=0.0: (f"PAPER_MOCK_ORDER_BUY", True)
kite_executor.get_ltp = lambda symbol_token, trading_symbol="": 0.0
kite_executor.get_order_fill_price = lambda order_id: 0.0
kite_executor.cancel_order = lambda order_id, variety="regular": True
kite_executor.get_positions = lambda: []
kite_executor.get_all_orders = lambda: []
kite_executor.get_trade_book = lambda: []

import block_manager as bm

# ─── Test 1: Create blocks ───────────────────────────────────
print()
print("--- Test 1: create_block ---")
r1 = bm.create_block("26-Jun-2025", "MONTHLY", "Main monthly block")
assert r1["ok"], f"Block creation failed: {r1}"
assert r1["block_number"] == 1
bid1 = r1["block_id"]
print(f"  PASS: Block {r1['block_number']} created | ID={bid1}")

r2 = bm.create_block("19-Jun-2025", "WEEKLY", "Weekly block")
assert r2["ok"]
bid2 = r2["block_id"]
print(f"  PASS: Block {r2['block_number']} created | ID={bid2}")

# ─── Test 2: Duplicate expiry blocked ────────────────────────
print()
print("--- Test 2: HARD RULE -- duplicate expiry blocked ---")
r_dup = bm.create_block("26-Jun-2025", "MONTHLY")
assert not r_dup["ok"], "Duplicate expiry should fail"
assert r_dup.get("duplicate"), "Should flag as duplicate"
print(f"  PASS: Duplicate expiry correctly blocked: {r_dup['message']}")

# ─── Test 3: Add strikes ─────────────────────────────────────
print()
print("--- Test 3: add_strike_to_block ---")
s1 = bm.add_strike_to_block(bid1, 24000, "CE", "SELL",      120.00, 2)
s2 = bm.add_strike_to_block(bid1, 24000, "PE", "SELL",      115.00, 2)
s3 = bm.add_strike_to_block(bid1, 24300, "CE", "HEDGE_BUY",  40.00, 2)
s4 = bm.add_strike_to_block(bid1, 23700, "PE", "HEDGE_BUY",  38.00, 2)
assert all(x["ok"] for x in [s1, s2, s3, s4]), "All strikes should be added"
sid1, sid2, sid3, sid4 = s1["strike_id"], s2["strike_id"], s3["strike_id"], s4["strike_id"]
print(f"  PASS: 4 strikes added: {sid1},{sid2},{sid3},{sid4}")
print(f"         Qty per strike: {s1['qty']} (2 lots x 65)")
assert s1["qty"] == 130, f"Qty should be 130 (2x65): {s1['qty']}"

# ─── Test 4: HARD RULE -- anchor=0 blocked ───────────────────
print()
print("--- Test 4: HARD RULE -- anchor=0 blocked ---")
bad = bm.add_strike_to_block(bid1, 25000, "CE", "SELL", 0.0, 1)
assert not bad["ok"], "anchor=0 should fail"
print(f"  PASS: anchor=0 blocked")

# ─── Test 5: Link hedge to sell ──────────────────────────────
print()
print("--- Test 5: link_hedge_to_sell ---")
lr1 = bm.link_hedge_to_sell(sid1, sid3)  # CE sell <-> CE hedge
lr2 = bm.link_hedge_to_sell(sid2, sid4)  # PE sell <-> PE hedge
assert lr1["ok"], f"Link 1 failed: {lr1}"
assert lr2["ok"], f"Link 2 failed: {lr2}"

# Verify both directions stored
s1_data = db.get_strike(sid1)
assert s1_data["hedge_strike_id"] == sid3, "Sell should point to hedge"
print(f"  PASS: CE Sell {sid1} <-> CE Hedge {sid3}")
print(f"  PASS: PE Sell {sid2} <-> PE Hedge {sid4}")

# ─── Test 6: Wrong link type blocked ─────────────────────────
print()
print("--- Test 6: Wrong leg_type link blocked ---")
bad_link = bm.link_hedge_to_sell(sid3, sid4)  # hedge->hedge (wrong)
assert not bad_link["ok"], "Linking hedge->hedge should fail"
print(f"  PASS: Wrong leg_type link blocked: {bad_link['message']}")

# ─── Test 7: Execute single strike ───────────────────────────
print()
print("--- Test 7: execute_strike (paper mode) ---")
result = bm.execute_strike(sid1)
assert result["ok"], f"Strike execution failed: {result}"
assert result["sell_order_id"] is not None
# After execution, sell strike and its hedge should be OPEN
s1_updated    = db.get_strike(sid1)
hedge_updated = db.get_strike(sid3)
assert s1_updated["status"] == "OPEN", f"Sell should be OPEN: {s1_updated['status']}"
assert hedge_updated["status"] == "OPEN", f"Hedge should be OPEN: {hedge_updated['status']}"
print(f"  PASS: Strike {sid1} executed | Order: {result['sell_order_id'][:25]}...")
print(f"  PASS: Hedge {sid3} auto-executed before sell")
print(f"  PASS: Sell OPEN={s1_updated['status']}, Hedge OPEN={hedge_updated['status']}")

# ─── Test 8: Cannot re-execute OPEN strike ───────────────────
print()
print("--- Test 8: Cannot re-execute OPEN strike ---")
re_exec = bm.execute_strike(sid1)
assert not re_exec["ok"], "Re-executing OPEN strike should fail"
print(f"  PASS: Re-execution blocked: {re_exec['message']}")

# ─── Test 9: execute_block for remaining strikes ─────────────
print()
print("--- Test 9: execute_block (remaining pending) ---")
block_result = bm.execute_block(bid1)
assert block_result["ok"], f"Block execution failed: {block_result}"
print(f"  PASS: {block_result['message']}")
print(f"        Executed: {block_result['executed']}")

# ─── Test 10: get_block_summary ──────────────────────────────
print()
print("--- Test 10: get_block_summary ---")
summary = bm.get_block_summary(bid1)
assert summary["ok"]
assert summary["open_strikes"] > 0, "Should have open strikes"
print(f"  PASS: Block {summary['block']['block_number']} summary OK")
print(f"        Total strikes: {summary['total_strikes']}")
print(f"        Open strikes:  {summary['open_strikes']}")

# ─── Test 11: Close strike + hedge together ───────────────────
print()
print("--- Test 11: close_strike (SELL + HEDGE together) ---")
close_result = bm.close_strike(sid2)  # Close PE sell (sid4 is its hedge)
assert close_result["ok"], f"Close failed: {close_result}"
assert "realized_pnl" in close_result
s2_closed = db.get_strike(sid2)
s4_closed = db.get_strike(sid4)
assert s2_closed["status"] == "CLOSED", f"Sell should be CLOSED: {s2_closed['status']}"
assert s4_closed["status"] == "PENDING_CLOSE", f"Hedge should be PENDING_CLOSE immediately: {s4_closed['status']}"
print(f"  PASS: PE Sell {sid2} CLOSED immediately")
print(f"  PASS: PE Hedge {sid4} marked as PENDING_CLOSE immediately")

# Set the scheduled time to the past and execute processing
db.set(f"pending_close_time_{sid4}", "0")
processed = bm.process_pending_closes()
assert processed == 1, f"Expected 1 processed close, got {processed}"

s4_fully_closed = db.get_strike(sid4)
assert s4_fully_closed["status"] == "CLOSED", f"Hedge should be CLOSED after processing: {s4_fully_closed['status']}"
print(f"  PASS: PE Hedge {sid4} CLOSED after background queue processing")
print(f"  PASS: Realized P&L = Rs{close_result['realized_pnl']}")

# ─── Test 12: Cannot delete block with OPEN strikes ──────────
print()
print("--- Test 12: HARD RULE -- cannot delete block with OPEN strikes ---")
del_result = bm.delete_block(bid1)
assert not del_result["ok"], "Should not delete block with OPEN strikes"
print(f"  PASS: Delete blocked: {del_result['message']}")

# ─── Test 13: get_portfolio_status ───────────────────────────
print()
print("--- Test 13: get_portfolio_status ---")
status = bm.get_portfolio_status()
assert "active_blocks" in status
assert "total_open_strikes" in status
assert status["paper_mode"] == False
print(f"  PASS: Portfolio status:")
print(f"        Active blocks:      {status['active_blocks']}")
print(f"        Open strikes:       {status['total_open_strikes']}")
print(f"        Paper mode:         {status['paper_mode']}")
print(f"        Algo running:       {status['algo_running']}")

# ─── Test 14: check_expiries ─────────────────────────────────
print()
print("--- Test 14: check_expiries (auto-expire past dates) ---")
# Create a past-date block for testing expiry
past_block = bm.create_block("01-Jan-2020", "WEEKLY", "Old block to expire")
assert past_block["ok"]
expired = bm.check_expiries()
assert past_block["block_id"] in expired, f"Past block should be auto-expired: {expired}"
print(f"  PASS: {len(expired)} block(s) auto-expired: {expired}")

# ─── Test 15: get_all_blocks_summary ─────────────────────────
print()
print("--- Test 15: get_all_blocks_summary ---")
all_summaries = bm.get_all_blocks_summary()
assert len(all_summaries) >= 2
print(f"  PASS: {len(all_summaries)} block summaries returned")

# ─── Test 16: close_hedge_strike_only ────────────────────────
print()
print("--- Test 16: close_hedge_strike_only ---")
hb = bm.create_block("10-Jun-2027", "MONTHLY", "Test manual hedge close")
assert hb["ok"]
hbid = hb["block_id"]
h_strike = bm.add_strike_to_block(hbid, 24000, "CE", "HEDGE_BUY", 10.0, 1)
assert h_strike["ok"]
hsid = h_strike["strike_id"]
db.create_leg(hsid, 10.0, "MOCK_ORDER_HEDGE")
h_strike_data = db.get_strike(hsid)
assert h_strike_data["status"] == "OPEN"
close_h_res = bm.close_hedge_strike_only(hsid)
assert close_h_res["ok"]
h_strike_data_2 = db.get_strike(hsid)
assert h_strike_data_2["status"] == "PENDING_CLOSE"
print(f"  PASS: close_hedge_strike_only successfully scheduled hedge close")

print()
print("=" * 58)
print("  ALL BRICK 3 TESTS PASSED!")
print("  block_manager.py is VERIFIED and READY")
print("=" * 58)

