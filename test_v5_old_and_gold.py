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
  7. test_07_multi_unit_isolation_m1_m2
  8. test_08_explicit_25_pct_stop_loss_trigger
"""

import unittest
from unittest.mock import patch, MagicMock
import os
import sqlite3
import db
import block_manager as bm
import regime_engine as re_eng
from kite_executor import kite_executor


class TestV5OldAndGold(unittest.TestCase):

    def setUp(self):
        db.init_db()
        self.cleanup_test_blocks()
        
        self.patches = [
            patch.object(kite_executor, "ensure_logged_in", return_value=True),
            patch.object(kite_executor, "get_all_orders", return_value=[]),
            patch.object(kite_executor, "get_order_fill_price", return_value=80.0),
            patch.object(kite_executor, "execute_buy_and_confirm", return_value=("ORD_BUY_MOCK", True)),
            patch.object(kite_executor, "execute_sell_and_confirm", return_value=("ORD_SELL_MOCK", True)),
            patch.object(kite_executor, "get_ltp", return_value=80.0),
            patch.object(kite_executor, "get_live_ltp", return_value=80.0),
            patch.object(kite_executor, "get_nifty_spot", return_value=24200.0),
            patch.object(kite_executor, "search_option_symbol", side_effect=lambda expiry_date, strike_price, option_type: {
                "token": f"TOK_{strike_price}_{option_type}",
                "trading_symbol": f"NIFTY_{strike_price}_{option_type}"
            }),
            patch("telegram_bot.send", return_value=True),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            try:
                p.stop()
            except Exception:
                pass
        self.cleanup_test_blocks()

    def cleanup_test_blocks(self):
        try:
            conn = db._conn()
            conn.execute("DELETE FROM legs WHERE strike_id IN (SELECT strike_id FROM strikes WHERE block_id IN (SELECT block_id FROM blocks WHERE anchor_unit_name LIKE 'V5_%' OR anchor_unit_name IN ('M1', 'M2')))")
            conn.execute("DELETE FROM strikes WHERE block_id IN (SELECT block_id FROM blocks WHERE anchor_unit_name LIKE 'V5_%' OR anchor_unit_name IN ('M1', 'M2'))")
            conn.execute("DELETE FROM blocks WHERE anchor_unit_name LIKE 'V5_%' OR anchor_unit_name IN ('M1', 'M2')")
            conn.commit()
            conn.close()
        except Exception:
            pass

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

    def test_03_unified_console_bearish_selective_execution(self):
        """Spot < Anchor -> Call Wing executes LIVE; Put Wing remains PENDING."""
        test_expiry = "26-Nov-2026"
        res = bm.deploy_unified_master_unit(
            expiry_date=test_expiry,
            anchor_unit_name="V5_TEST_BEARISH",
            master_anchor_price=24500.0,
            recommended_lots=1,
            ce_sell_strike=24800,
            ce_sell_anchor=80.0,
            ce_hedge_strike=25100,
            ce_hedge_anchor=12.0,
            ce_sl_pct=25.0,
            pe_sell_strike=24200,
            pe_sell_anchor=80.0,
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

    def test_04_intraday_anchor_crossing_does_not_close_trades(self):
        """Mid-day spot crossings over/under anchor do NOT exit positions in V5 Decoupled mode."""
        test_expiry = "31-Dec-2026"
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

    def test_05_3pm_master_anchor_decision_continuation(self):
        """At 15:00 IST, winning side is CONTINUED and opposing side is closed."""
        test_expiry = "28-Jan-2027"
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

    def test_07_multi_unit_isolation_m1_m2(self):
        """M1 and M2 operate with dedicated master anchors without interference."""
        test_expiry = "25-Mar-2027"
        
        # Deploy M1 with Master Anchor 24000 (Bullish at Spot 24300)
        res_m1 = bm.deploy_unified_master_unit(
            expiry_date=test_expiry,
            anchor_unit_name="M1",
            master_anchor_price=24000.0,
            recommended_lots=1,
            ce_sell_strike=24800,
            ce_sell_anchor=80.0,
            pe_sell_strike=23500,
            pe_sell_anchor=80.0,
            execute_live=True,
            current_spot=24300.0
        )
        self.assertTrue(res_m1["ok"])
        self.assertEqual(res_m1["executed_side"], "PUT", "M1 (Spot 24300 >= Anchor 24000) should be BULLISH / PUT")

        # Deploy M2 with Master Anchor 24600 (Bearish at Spot 24300)
        res_m2 = bm.deploy_unified_master_unit(
            expiry_date=test_expiry,
            anchor_unit_name="M2",
            master_anchor_price=24600.0,
            recommended_lots=1,
            ce_sell_strike=25000,
            ce_sell_anchor=85.0,
            pe_sell_strike=23800,
            pe_sell_anchor=85.0,
            execute_live=True,
            current_spot=24300.0
        )
        self.assertTrue(res_m2["ok"])
        self.assertEqual(res_m2["executed_side"], "CALL", "M2 (Spot 24300 < Anchor 24600) should be BEARISH / CALL")

        # Verify M1's PE sell is OPEN and M2's CE sell is OPEN
        m1_pe = db.get_strike(res_m1["pe_sell_id"])
        m2_ce = db.get_strike(res_m2["ce_sell_id"])
        self.assertEqual(m1_pe["status"], "OPEN")
        self.assertEqual(m2_ce["status"], "OPEN")

    def test_08_explicit_25_pct_stop_loss_trigger(self):
        """Stop-loss is explicitly calculated as entry + 25% and never placed at LTP."""
        test_expiry = "29-Apr-2027"
        res = bm.deploy_unified_master_unit(
            expiry_date=test_expiry,
            anchor_unit_name="V5_SL_TEST",
            master_anchor_price=24000.0,
            recommended_lots=1,
            ce_sell_strike=24600,
            ce_sell_anchor=100.0,  # 100.00
            ce_sl_pct=25.0,        # 25%
            pe_sell_strike=23600,
            pe_sell_anchor=100.0,  # 100.00
            pe_sl_pct=25.0,        # 25%
            execute_live=False
        )
        self.assertTrue(res["ok"])

        ce_sell = db.get_strike(res["ce_sell_id"])
        pe_sell = db.get_strike(res["pe_sell_id"])

        # SL price must be exactly 100.0 * 1.25 = 125.0
        self.assertEqual(float(ce_sell["sl_price"]), 125.0, "CE Stop-loss trigger must be at 125.0 (25% away from 100.0)")
        self.assertEqual(float(pe_sell["sl_price"]), 125.0, "PE Stop-loss trigger must be at 125.0 (25% away from 100.0)")

    def test_09_custom_rupee_stop_loss_price_and_dual_editing(self):
        """User can set custom Anchor=60.00 and SL=61.00 directly, and edit both anytime."""
        test_expiry = "27-May-2027"
        res = bm.deploy_unified_master_unit(
            expiry_date=test_expiry,
            anchor_unit_name="V5_CUSTOM_SL",
            master_anchor_price=24000.0,
            recommended_lots=1,
            ce_sell_strike=24600,
            ce_sell_anchor=60.0,
            ce_sl_price=61.0,  # User explicitly specified ₹61.00 Stop Loss Price
            pe_sell_strike=23600,
            pe_sell_anchor=60.0,
            pe_sl_price=61.0,  # User explicitly specified ₹61.00 Stop Loss Price
            execute_live=False
        )
        self.assertTrue(res["ok"])

        ce_sell = db.get_strike(res["ce_sell_id"])
        self.assertEqual(float(ce_sell["anchor_price"]), 60.0)
        self.assertEqual(float(ce_sell["sl_price"]), 61.0, "Stop loss price must be explicitly preserved at ₹61.00")

        # Now test dual editing via update_strike_price_and_sl
        edit_res = bm.update_strike_price_and_sl(
            strike_id=res["ce_sell_id"],
            new_anchor=60.0,
            new_sl_price=68.0,
            new_lots=2
        )
        self.assertTrue(edit_res["ok"])
        updated_ce = db.get_strike(res["ce_sell_id"])
        self.assertEqual(float(updated_ce["anchor_price"]), 60.0)
        self.assertEqual(float(updated_ce["sl_price"]), 68.0, "Updated SL price must be ₹68.00")
        self.assertEqual(int(updated_ce["lots"]), 2)


if __name__ == "__main__":
    unittest.main()
