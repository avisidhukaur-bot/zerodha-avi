"""
test_strict_regime_execution_guard.py -- Test Suite for Strict Regime Execution Guardrails
========================================================================================
Verifies:
  1. execute_block() in BULLISH regime executes ONLY PE strikes; CE strikes remain PENDING (Armed).
  2. execute_block() in BEARISH regime executes ONLY CE strikes; PE strikes remain PENDING (Armed).
  3. execute_strike() directly on a MUTED strike is rejected before placing broker orders.
"""

import unittest
from unittest.mock import patch, MagicMock
import os
import sys

import db
import config as cfg
import regime_engine as re_eng
import block_manager as bm


class TestStrictRegimeExecutionGuard(unittest.TestCase):

    def setUp(self):
        self.created_bids = []
        active = db.get_all_blocks(status_filter="ACTIVE")
        for b in active:
            if "TEST" in (b.get("notes") or "") or b.get("expiry_date") in ("28-Sep-2028", "26-Oct-2028", "30-Nov-2028"):
                db.update_block_status(b["block_id"], "CLOSED")
        self.orig_anchor = db.get("master_nifty_anchor", "0.0")
        self.orig_buffer = db.get("regime_buffer", "15.0")
        self.orig_mode   = db.get("regime_mode", "AUTO")
        self.orig_regime = db.get("active_regime", "NEUTRAL")

        db.set("algo_running", "ON")
        db.set("regime_mode", "AUTO")

    def tearDown(self):
        for bid in self.created_bids:
            try:
                bm.kill_block(bid)
            except Exception:
                pass
        active = db.get_all_blocks(status_filter="ACTIVE")
        for b in active:
            if "TEST" in (b.get("notes") or "") or b.get("expiry_date") in ("28-Sep-2028", "26-Oct-2028", "30-Nov-2028"):
                db.update_block_status(b["block_id"], "CLOSED")
        db.set("master_nifty_anchor", self.orig_anchor)
        db.set("regime_buffer", self.orig_buffer)
        db.set("regime_mode", self.orig_mode)
        db.set("active_regime", self.orig_regime)

    @patch("kite_executor.kite_executor.ensure_logged_in", return_value=True)
    @patch("kite_executor.kite_executor.search_option_symbol")
    @patch("kite_executor.kite_executor.execute_buy_and_confirm", return_value=("ORD_BUY_MOCK", True))
    @patch("kite_executor.kite_executor.execute_sell_and_confirm", return_value=("ORD_SELL_MOCK", True))
    @patch("kite_executor.kite_executor.get_ltp", return_value=50.0)
    @patch("kite_executor.kite_executor.get_nifty_spot", return_value=24200.0)
    @patch("telegram_bot.send")
    def test_execute_block_bullish_executes_pe_only(self, mock_tg, mock_spot, mock_ltp, mock_sell, mock_buy, mock_sym, mock_login):
        """In BULLISH regime (Spot 24200 > Anchor 24000), execute_block executes PE and keeps CE in PENDING."""
        mock_sym.side_effect = lambda expiry_date, strike_price, option_type: {
            "token": f"TOK_{strike_price}_{option_type}",
            "trading_symbol": f"NIFTY_{strike_price}_{option_type}"
        }

        # Create Block for Unit M1 with Anchor 24000
        res = bm.create_block(expiry_date="28-Sep-2028", expiry_type="MONTHLY", side_type="BOTH", master_anchor_price=24000.0, anchor_unit_name="M1", notes="TEST_GUARD")
        self.assertTrue(res["ok"])
        bid = res["block_id"]
        self.created_bids.append(bid)

        # Evaluate regime -> BULLISH (PE Allowed, CE Muted)
        b = db.get_block(bid)
        re_res = re_eng.evaluate_block_regime(b, current_spot=24200.0, force_eval=True)
        self.assertEqual(re_res["regime"], "BULLISH")
        b = db.get_block(bid)
        self.assertEqual(b["current_regime"], "BULLISH")

        # Add CE Sell + Hedge (MUTED)
        r_ce_sell = bm.add_strike_to_block(bid, strike_price=24500, option_type="CE", leg_type="SELL", anchor_price=100.0, lots=1)
        r_ce_hdg  = bm.add_strike_to_block(bid, strike_price=24800, option_type="CE", leg_type="HEDGE_BUY", anchor_price=20.0, lots=1)
        bm.link_hedge_to_sell(r_ce_sell["strike_id"], r_ce_hdg["strike_id"])

        # Add PE Sell + Hedge (ACTIVE)
        r_pe_sell = bm.add_strike_to_block(bid, strike_price=23500, option_type="PE", leg_type="SELL", anchor_price=80.0, lots=1)
        r_pe_hdg  = bm.add_strike_to_block(bid, strike_price=23200, option_type="PE", leg_type="HEDGE_BUY", anchor_price=15.0, lots=1)
        bm.link_hedge_to_sell(r_pe_sell["strike_id"], r_pe_hdg["strike_id"])

        # Execute Block
        exec_res = bm.execute_block(bid)
        self.assertTrue(exec_res["ok"])

        # PE strike should be executed
        self.assertIn(r_pe_sell["strike_id"], exec_res["executed"])
        pe_s = db.get_strike(r_pe_sell["strike_id"])
        self.assertEqual(pe_s["status"], "OPEN")

        # CE strike MUST NOT be executed -- MUST remain PENDING!
        self.assertIn(r_ce_sell["strike_id"], exec_res["muted_pending"])
        ce_s = db.get_strike(r_ce_sell["strike_id"])
        self.assertEqual(ce_s["status"], "PENDING")

    @patch("kite_executor.kite_executor.ensure_logged_in", return_value=True)
    @patch("kite_executor.kite_executor.search_option_symbol")
    @patch("kite_executor.kite_executor.execute_buy_and_confirm", return_value=("ORD_BUY_MOCK", True))
    @patch("kite_executor.kite_executor.execute_sell_and_confirm", return_value=("ORD_SELL_MOCK", True))
    @patch("kite_executor.kite_executor.get_ltp", return_value=50.0)
    @patch("kite_executor.kite_executor.get_nifty_spot", return_value=24200.0)
    @patch("telegram_bot.send")
    def test_execute_block_bearish_executes_ce_only(self, mock_tg, mock_spot, mock_ltp, mock_sell, mock_buy, mock_sym, mock_login):
        """In BEARISH regime (Spot 24200 < Anchor 24500), execute_block executes CE and keeps PE in PENDING."""
        mock_sym.side_effect = lambda expiry_date, strike_price, option_type: {
            "token": f"TOK_{strike_price}_{option_type}",
            "trading_symbol": f"NIFTY_{strike_price}_{option_type}"
        }

        # Create Block for Unit M2 with Anchor 24500
        res = bm.create_block(expiry_date="26-Oct-2028", expiry_type="MONTHLY", side_type="BOTH", master_anchor_price=24500.0, anchor_unit_name="M2", notes="TEST_GUARD")
        self.assertTrue(res["ok"])
        bid = res["block_id"]
        self.created_bids.append(bid)

        # Evaluate regime -> BEARISH (CE Allowed, PE Muted)
        b = db.get_block(bid)
        re_res = re_eng.evaluate_block_regime(b, current_spot=24200.0, force_eval=True)
        self.assertEqual(re_res["regime"], "BEARISH")
        b = db.get_block(bid)
        self.assertEqual(b["current_regime"], "BEARISH")

        # Add CE Sell + Hedge (ACTIVE)
        r_ce_sell = bm.add_strike_to_block(bid, strike_price=24800, option_type="CE", leg_type="SELL", anchor_price=90.0, lots=1)
        r_ce_hdg  = bm.add_strike_to_block(bid, strike_price=25100, option_type="CE", leg_type="HEDGE_BUY", anchor_price=18.0, lots=1)
        bm.link_hedge_to_sell(r_ce_sell["strike_id"], r_ce_hdg["strike_id"])

        # Add PE Sell + Hedge (MUTED)
        r_pe_sell = bm.add_strike_to_block(bid, strike_price=23800, option_type="PE", leg_type="SELL", anchor_price=75.0, lots=1)
        r_pe_hdg  = bm.add_strike_to_block(bid, strike_price=23500, option_type="PE", leg_type="HEDGE_BUY", anchor_price=12.0, lots=1)
        bm.link_hedge_to_sell(r_pe_sell["strike_id"], r_pe_hdg["strike_id"])

        # Execute Block
        exec_res = bm.execute_block(bid)
        self.assertTrue(exec_res["ok"])

        # CE strike should be executed
        self.assertIn(r_ce_sell["strike_id"], exec_res["executed"])
        ce_s = db.get_strike(r_ce_sell["strike_id"])
        self.assertEqual(ce_s["status"], "OPEN")

        # PE strike MUST NOT be executed -- MUST remain PENDING!
        self.assertIn(r_pe_sell["strike_id"], exec_res["muted_pending"])
        pe_s = db.get_strike(r_pe_sell["strike_id"])
        self.assertEqual(pe_s["status"], "PENDING")

    @patch("kite_executor.kite_executor.ensure_logged_in", return_value=True)
    @patch("kite_executor.kite_executor.search_option_symbol")
    @patch("kite_executor.kite_executor.execute_buy_and_confirm", return_value=("ORD_BUY_MOCK", True))
    @patch("kite_executor.kite_executor.execute_sell_and_confirm", return_value=("ORD_SELL_MOCK", True))
    @patch("kite_executor.kite_executor.get_ltp", return_value=50.0)
    @patch("kite_executor.kite_executor.get_nifty_spot", return_value=24200.0)
    def test_direct_execute_strike_blocked_on_muted_strike(self, mock_spot, mock_ltp, mock_sell, mock_buy, mock_sym, mock_login):
        """Calling execute_strike directly on a MUTED strike is rejected without placing orders."""
        mock_sym.side_effect = lambda expiry_date, strike_price, option_type: {
            "token": f"TOK_{strike_price}_{option_type}",
            "trading_symbol": f"NIFTY_{strike_price}_{option_type}"
        }

        res = bm.create_block(expiry_date="30-Nov-2028", expiry_type="MONTHLY", side_type="BOTH", master_anchor_price=24000.0, anchor_unit_name="M1", notes="TEST_GUARD")
        self.assertTrue(res["ok"])
        bid = res["block_id"]
        self.created_bids.append(bid)

        b = db.get_block(bid)
        re_eng.evaluate_block_regime(b, current_spot=24200.0, force_eval=True)  # BULLISH

        r_ce_sell = bm.add_strike_to_block(bid, strike_price=24500, option_type="CE", leg_type="SELL", anchor_price=100.0, lots=1)
        r_ce_hdg  = bm.add_strike_to_block(bid, strike_price=24800, option_type="CE", leg_type="HEDGE_BUY", anchor_price=20.0, lots=1)
        bm.link_hedge_to_sell(r_ce_sell["strike_id"], r_ce_hdg["strike_id"])

        # Direct execute_strike on muted CE
        exec_res = bm.execute_strike(r_ce_sell["strike_id"])
        self.assertFalse(exec_res["ok"])
        self.assertTrue(exec_res.get("blocked_by_regime"))
        self.assertEqual(mock_sell.call_count, 0)  # ZERO broker calls!
        self.assertEqual(mock_buy.call_count, 0)

        # Strike remains in PENDING
        ce_s = db.get_strike(r_ce_sell["strike_id"])
        self.assertEqual(ce_s["status"], "PENDING")


if __name__ == "__main__":
    unittest.main()
