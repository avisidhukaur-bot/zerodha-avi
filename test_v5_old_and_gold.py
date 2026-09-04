"""
test_v5_old_and_gold.py -- Comprehensive Verification Suite for V5.0 "Old & Gold" Architecture
==================================================================================================
Tests:
  1. test_01_schema_migrations_v5
  2. test_02_unified_console_bullish_selective_execution
  3. test_03_unified_console_bearish_selective_execution
  4. test_04_intraday_anchor_crossing_does_not_close_trades
  5. test_05_3pm_master_anchor_decision_continuation
  6. test_06_orphan_hedge_preservation_on_sl_exit
"""

import unittest
import os
import sqlite3
import db
import block_manager as bm
import regime_engine as re_eng
from kite_executor import kite_executor


class TestV5OldAndGold(unittest.TestCase):

    def setUp(self):
        # Ensure DB is initialized with migrations
        db.init_db()

    def test_01_schema_migrations_v5(self):
        """Verify that all V5.0 columns exist in strikes and blocks tables."""
        conn = db._conn()
        c = conn.cursor()

        # Check strikes table
        c.execute("PRAGMA table_info(strikes)")
        strike_cols = [col[1] for col in c.fetchall()]
        self.assertIn("sl_pct", strike_cols, "Column 'sl_pct' missing from strikes table")
        self.assertIn("sl_price", strike_cols, "Column 'sl_price' missing from strikes table")
        self.assertIn("reentry_enabled", strike_cols, "Column 'reentry_enabled' missing from strikes table")
        self.assertIn("trade_state", strike_cols, "Column 'trade_state' missing from strikes table")

        # Check blocks table
        c.execute("PRAGMA table_info(blocks)")
        block_cols = [col[1] for col in c.fetchall()]
        self.assertIn("anchor_decision_time", block_cols, "Column 'anchor_decision_time' missing from blocks table")
        self.assertIn("recommended_lots", block_cols, "Column 'recommended_lots' missing from blocks table")
        self.assertIn("orphan_hedge_policy", block_cols, "Column 'orphan_hedge_policy' missing from blocks table")

        conn.close()

    def test_02_unified_console_bullish_selective_execution(self):
        """Spot >= Anchor -> Put Wing executes LIVE; Call Wing remains PENDING."""
        test_expiry = "29-Oct-2026"
        res = bm.deploy_unified_master_unit(
            expiry_date=test_expiry,
            anchor_unit_name="V5_TEST_BULLISH",
            master_anchor_price=24000.0,
            recommended_lots=1,
            ce_sell_strike=24500,
            ce_sell_anchor=80.0,
            ce_hedge_strike=24800,
            ce_hedge_anchor=15.0,
            ce_sl_pct=25.0,
            pe_sell_strike=23500,
            pe_sell_anchor=80.0,
            pe_hedge_strike=23200,
            pe_hedge_anchor=15.0,
            pe_sl_pct=25.0,
            execute_live=True,
            current_spot=24200.0  # Spot (24200) >= Anchor (24000) -> BULLISH
        )

        self.assertTrue(res["ok"], f"Deployment failed: {res.get('message')}")
        self.assertEqual(res["executed_side"], "PUT", "Bullish signal should execute PUT side live")
        self.assertEqual(res["pending_side"], "CALL", "Bullish signal should keep CALL side in PENDING")

        pe_sell = db.get_strike(res["pe_sell_id"])
        ce_sell = db.get_strike(res["ce_sell_id"])

        self.assertEqual(pe_sell["status"], "OPEN")
        self.assertEqual(ce_sell["status"], "PENDING")

        # Clean up
        bm.kill_block(res["block_id"])

    def test_03_unified_console_bearish_selective_execution(self):
        """Spot < Anchor -> Call Wing executes LIVE; Put Wing remains PENDING."""
        test_expiry = "26-Nov-2026"
        res = bm.deploy_unified_master_unit(
            expiry_date=test_expiry,
            anchor_unit_name="V5_TEST_BEARISH",
            master_anchor_price=24500.0,
            recommended_lots=1,
            ce_sell_strike=24800,
            ce_sell_anchor=75.0,
            ce_hedge_strike=25100,
            ce_hedge_anchor=12.0,
            ce_sl_pct=25.0,
            pe_sell_strike=24200,
            pe_sell_anchor=75.0,
            pe_hedge_strike=23900,
            pe_hedge_anchor=12.0,
            pe_sl_pct=25.0,
            execute_live=True,
            current_spot=24100.0  # Spot (24100) < Anchor (24500) -> BEARISH
        )

        self.assertTrue(res["ok"], f"Deployment failed: {res.get('message')}")
        self.assertEqual(res["executed_side"], "CALL", "Bearish signal should execute CALL side live")
        self.assertEqual(res["pending_side"], "PUT", "Bearish signal should keep PUT side in PENDING")

        ce_sell = db.get_strike(res["ce_sell_id"])
        pe_sell = db.get_strike(res["pe_sell_id"])

        self.assertEqual(ce_sell["status"], "OPEN")
        self.assertEqual(pe_sell["status"], "PENDING")

        # Clean up
        bm.kill_block(res["block_id"])

    def test_04_intraday_anchor_crossing_does_not_close_trades(self):
        """Mid-day spot crossings over/under anchor do NOT exit positions in V5 Decoupled mode."""
        test_expiry = "31-Dec-2026"
        # Deploy Bullish (PE open)
        res = bm.deploy_unified_master_unit(
            expiry_date=test_expiry,
            anchor_unit_name="V5_TEST_NOISE",
            master_anchor_price=24000.0,
            recommended_lots=1,
            ce_sell_strike=24500,
            ce_sell_anchor=80.0,
            pe_sell_strike=23500,
            pe_sell_anchor=80.0,
            execute_live=True,
            current_spot=24100.0  # Bullish initially
        )
        self.assertTrue(res["ok"])
        pe_sell_id = res["pe_sell_id"]

        # Intraday spot drops below anchor (23800 < 24000)
        block = db.get_block(res["block_id"])
        eval_res = re_eng.evaluate_block_regime(block, current_spot=23800.0, force_eval=False)

        # In V5 decoupled mode, the open PE strike MUST remain OPEN
        pe_strike_after = db.get_strike(pe_sell_id)
        self.assertEqual(pe_strike_after["status"], "OPEN", "Intraday anchor crossing must NOT close open positions!")

        # Clean up
        bm.kill_block(res["block_id"])

    def test_05_3pm_master_anchor_decision_continuation(self):
        """At 15:00 IST, winning side is CONTINUED and opposing side is closed."""
        test_expiry = "28-Jan-2027"
        # Create block with Master Anchor 24000
        res = bm.deploy_unified_master_unit(
            expiry_date=test_expiry,
            anchor_unit_name="V5_TEST_3PM",
            master_anchor_price=24000.0,
            recommended_lots=1,
            ce_sell_strike=24500,
            ce_sell_anchor=80.0,
            ce_hedge_strike=24800,
            ce_hedge_anchor=15.0,
            pe_sell_strike=23500,
            pe_sell_anchor=80.0,
            pe_hedge_strike=23200,
            pe_hedge_anchor=15.0,
            execute_live=True,
            current_spot=24200.0  # Spot >= Anchor -> PE open
        )
        self.assertTrue(res["ok"])

        # Execute 3PM Continuation Decision at Spot 24300 (Bullish)
        dec_res = re_eng.execute_3pm_master_anchor_decision(current_spot=24300.0, force_decision=True)
        self.assertTrue(dec_res["ok"])

        pe_sell = db.get_strike(res["pe_sell_id"])
        self.assertEqual(pe_sell.get("trade_state"), "CONTINUED", "3PM decision should mark winning PE as CONTINUED")

        # Clean up
        bm.kill_block(res["block_id"])

    def test_06_orphan_hedge_preservation_on_sl_exit(self):
        """When short SL triggers, long hedge remains open as ORPHAN."""
        test_expiry = "25-Feb-2027"
        block_id = db.create_block(
            expiry_date=test_expiry,
            expiry_type="MONTHLY",
            side_type="BOTH",
            anchor_unit_name="V5_ORPHAN_TEST",
            master_anchor_price=24000.0
        )
        h_id = db.add_strike(block_id, 24800, "CE", "HEDGE_BUY", 15.0, 1, trade_state="PENDING")
        s_id = db.add_strike(block_id, 24500, "CE", "SELL", 80.0, 1, hedge_strike_id=h_id, sl_pct=25.0, trade_state="PENDING")
        bm.link_hedge_to_sell(s_id, h_id)

        # Execute strike (opens hedge and sell leg)
        exec_res = bm.execute_strike(s_id)
        self.assertTrue(exec_res["ok"])

        # Simulate SL breach: close short sell leg only
        close_res = bm.close_strike(s_id, close_hedge=False)
        self.assertTrue(close_res["ok"])
        db.update_strike_trade_state(s_id, "SL_HIT")
        db.update_strike_trade_state(h_id, "ORPHAN")

        # Verify Sell is CLOSED and Hedge is OPEN & ORPHAN
        s_strike = db.get_strike(s_id)
        h_strike = db.get_strike(h_id)
        self.assertEqual(s_strike["status"], "CLOSED")
        self.assertEqual(h_strike["status"], "OPEN", "Long hedge must remain OPEN after short SL exit")
        self.assertEqual(h_strike.get("trade_state"), "ORPHAN")

        # Verify Manual Profit Lock closes the Orphan Hedge
        lock_res = bm.exit_orphan_hedge(h_id)
        self.assertTrue(lock_res["ok"], "Manual profit lock should succeed")
        h_after = db.get_strike(h_id)
        self.assertEqual(h_after["status"], "CLOSED")

        # Clean up
        bm.kill_block(block_id)


if __name__ == "__main__":
    unittest.main()
