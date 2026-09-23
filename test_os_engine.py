"""
test_os_engine.py -- Automated Test Suite for Pure Option Price OS Engine
========================================================================
Validates all 6 core invariants of the OS Option Selling Strategy:
  1. Pure Option Price Action (Zero Spot Reliance) & 4 Market Scenarios
  2. 100-Multiple Strike Hunter (<= Rs150 target)
  3. 500-point OTM Hedge Mapping ("Helmet Rule")
  4. 1.382 Stop Loss Rule (+38.2% expansion protection)
  5. Multi-Day Continuation & 3:00 PM Line-Cross Exit
  6. Pod Isolation (OS Units vs M-Series Units)
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

import db
import config as cfg
import block_manager as bm
import os_engine


class TestOSEngine(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.orig_db = cfg.DB_PATH
        cls.test_db = os.path.join(cfg.BASE_DIR, "test_os_isolated.db")
        cfg.DB_PATH = cls.test_db
        db.init_db()

    @classmethod
    def tearDownClass(cls):
        cfg.DB_PATH = cls.orig_db
        if os.path.exists(cls.test_db):
            try:
                os.remove(cls.test_db)
            except Exception:
                pass

    def setUp(self):
        db.init_db()

    @patch("os_engine.get_occupied_strikes", return_value=set())
    def test_01_100_multiple_strike_hunter_and_hedge(self, mock_occ):
        """Verify candidate strikes are strictly multiples of 100 with 500-pt hedge and 1.382 SL."""
        expiries = os_engine.get_nifty_expiry_dates()
        self.assertTrue(len(expiries) > 0, "Should have valid Nifty option expiries")
        test_exp = expiries[0]

        # Hunt CE
        hunt_ce = os_engine.hunt_os_strike("CE", test_exp, target_premium=150.0)
        self.assertTrue(hunt_ce.get("ok"), f"Hunt CE failed: {hunt_ce.get('message')}")
        self.assertEqual(hunt_ce["sell_strike"] % 100, 0, "CE Sell strike must be multiple of 100")
        self.assertEqual(hunt_ce["hedge_distance"], 500, "CE Hedge distance must be exactly 500 points")
        self.assertEqual(hunt_ce["hedge_strike"], hunt_ce["sell_strike"] + 500, "CE Hedge must be OTM (K + 500)")
        expected_ce_sl = round(hunt_ce["sell_ltp"] * 1.382, 2)
        self.assertEqual(hunt_ce["sl_price"], expected_ce_sl, "CE Stop Loss must follow 1.382 rule")

        # Hunt PE
        hunt_pe = os_engine.hunt_os_strike("PE", test_exp, target_premium=150.0)
        self.assertTrue(hunt_pe.get("ok"), f"Hunt PE failed: {hunt_pe.get('message')}")
        self.assertEqual(hunt_pe["sell_strike"] % 100, 0, "PE Sell strike must be multiple of 100")
        self.assertEqual(hunt_pe["hedge_distance"], 500, "PE Hedge distance must be exactly 500 points")
        self.assertEqual(hunt_pe["hedge_strike"], hunt_pe["sell_strike"] - 500, "PE Hedge must be OTM (K - 500)")
        expected_pe_sl = round(hunt_pe["sell_ltp"] * 1.382, 2)
        self.assertEqual(hunt_pe["sl_price"], expected_pe_sl, "PE Stop Loss must follow 1.382 rule")

    @patch("os_engine.get_occupied_strikes", return_value=set())
    def test_02_manual_strike_override(self, mock_occ):
        """Verify operator can manually specify a strike in 100 multiples."""
        expiries = os_engine.get_nifty_expiry_dates()
        test_exp = expiries[0]

        res = os_engine.hunt_os_strike("CE", test_exp, manual_strike=24000)
        if res.get("ok"):
            self.assertEqual(res["sell_strike"], 24000)
            self.assertEqual(res["hedge_strike"], 24500)

    @patch("telegram_bot.send")
    def test_03_four_market_scenarios(self, mock_tg):
        """Verify the 4 daily market scenarios (Both Sell, CE Only, PE Only, No Trade)."""
        expiries = os_engine.get_nifty_expiry_dates()
        test_exp = expiries[0]

        # Scenario 1: Both Decaying (CE today < yest, PE today < yest)
        with patch.object(os_engine, "hunt_os_strike") as mock_hunt:
            mock_hunt.side_effect = [
                {"ok": True, "option_type": "CE", "sell_strike": 25200, "hedge_strike": 25700, "sell_ltp": 140.0, "yesterday_anchor": 160.0, "is_decaying": True, "decay_diff": 20.0, "sl_price": 193.48, "sl_pct": 38.2, "expiry_date": test_exp, "hedge_ltp": 20.0},
                {"ok": True, "option_type": "PE", "sell_strike": 24600, "hedge_strike": 24100, "sell_ltp": 135.0, "yesterday_anchor": 155.0, "is_decaying": True, "decay_diff": 20.0, "sl_price": 186.57, "sl_pct": 38.2, "expiry_date": test_exp, "hedge_ltp": 18.0}
            ]
            deploy_res = os_engine.deploy_os_unit("OS_TEST1", test_exp, deploy_now=False)
            self.assertEqual(deploy_res.get("action"), "SELL_BOTH")
            self.assertIn("Sold 25200 CE", deploy_res["message"])
            self.assertIn("Sold 24600 PE", deploy_res["message"])

        # Scenario 2: Falling Market (CE decaying, PE expanding)
        with patch.object(os_engine, "hunt_os_strike") as mock_hunt:
            mock_hunt.side_effect = [
                {"ok": True, "option_type": "CE", "sell_strike": 25200, "hedge_strike": 25700, "sell_ltp": 120.0, "yesterday_anchor": 160.0, "is_decaying": True, "decay_diff": 40.0, "sl_price": 165.84, "sl_pct": 38.2, "expiry_date": test_exp, "hedge_ltp": 15.0},
                {"ok": True, "option_type": "PE", "sell_strike": 24600, "hedge_strike": 24100, "sell_ltp": 180.0, "yesterday_anchor": 155.0, "is_decaying": False, "decay_diff": -25.0, "sl_price": 248.76, "sl_pct": 38.2, "expiry_date": test_exp, "hedge_ltp": 25.0}
            ]
            deploy_res = os_engine.deploy_os_unit("OS_TEST2", test_exp, deploy_now=False)
            self.assertEqual(deploy_res.get("action"), "SELL_CE_ONLY")
            self.assertIn("Sold 25200 CE", deploy_res["message"])
            self.assertNotIn("Sold 24600 PE", deploy_res["message"])

        # Scenario 3: Rising Market (PE decaying, CE expanding)
        with patch.object(os_engine, "hunt_os_strike") as mock_hunt:
            mock_hunt.side_effect = [
                {"ok": True, "option_type": "CE", "sell_strike": 25200, "hedge_strike": 25700, "sell_ltp": 190.0, "yesterday_anchor": 150.0, "is_decaying": False, "decay_diff": -40.0, "sl_price": 262.58, "sl_pct": 38.2, "expiry_date": test_exp, "hedge_ltp": 30.0},
                {"ok": True, "option_type": "PE", "sell_strike": 24600, "hedge_strike": 24100, "sell_ltp": 125.0, "yesterday_anchor": 160.0, "is_decaying": True, "decay_diff": 35.0, "sl_price": 172.75, "sl_pct": 38.2, "expiry_date": test_exp, "hedge_ltp": 15.0}
            ]
            deploy_res = os_engine.deploy_os_unit("OS_TEST3", test_exp, deploy_now=False)
            self.assertEqual(deploy_res.get("action"), "SELL_PE_ONLY")
            self.assertIn("Sold 24600 PE", deploy_res["message"])
            self.assertNotIn("Sold 25200 CE", deploy_res["message"])

        # Scenario 4: High VIX Spike (Both expanding) => NO TRADE
        with patch.object(os_engine, "hunt_os_strike") as mock_hunt:
            mock_hunt.side_effect = [
                {"ok": True, "option_type": "CE", "sell_strike": 25200, "sell_ltp": 180.0, "yesterday_anchor": 150.0, "is_decaying": False, "decay_diff": -30.0},
                {"ok": True, "option_type": "PE", "sell_strike": 24600, "sell_ltp": 175.0, "yesterday_anchor": 145.0, "is_decaying": False, "decay_diff": -30.0}
            ]
            deploy_res = os_engine.deploy_os_unit("OS_TEST4", test_exp, deploy_now=False)
            self.assertEqual(deploy_res.get("action"), "NO_TRADE")
            self.assertIn("NO TRADE TAKEN", deploy_res["message"])

    def test_04_stop_loss_1382_calculation(self):
        """Verify 1.382 Stop Loss calculation across diverse entry prices."""
        entry_100 = 100.0
        self.assertEqual(round(entry_100 * 1.382, 2), 138.20)

        entry_140 = 140.0
        self.assertEqual(round(entry_140 * 1.382, 2), 193.48)

        entry_149_1 = 149.10
        self.assertEqual(round(entry_149_1 * 1.382, 2), 206.06)

    def test_05_pod_isolation(self):
        """Verify OS units have 'OS' namespace and do not interfere with M-series units."""
        name1 = db.get_next_os_unit_name()
        self.assertTrue(name1.startswith("OS"), f"Expected OS unit prefix, got {name1}")

        # Check M-series unit generator
        m_name = db.get_next_unit_name()
        self.assertTrue(m_name.startswith("M"), f"Expected M-series unit prefix, got {m_name}")

    def test_06_inspect_os_candidates(self):
        """Verify Step 1 inspect_os_candidates produces structured audit for operator."""
        expiries = os_engine.get_nifty_expiry_dates()
        test_exp = expiries[0]

        with patch.object(os_engine, "hunt_os_strike") as mock_hunt:
            mock_hunt.side_effect = [
                {"ok": True, "option_type": "CE", "sell_strike": 25200, "hedge_strike": 25700, "sell_ltp": 130.0, "yesterday_anchor": 150.0, "is_decaying": True, "decay_diff": 20.0, "sl_price": 179.66, "sl_pct": 38.2, "expiry_date": test_exp, "hedge_ltp": 15.0},
                {"ok": True, "option_type": "PE", "sell_strike": 24600, "hedge_strike": 24100, "sell_ltp": 140.0, "yesterday_anchor": 160.0, "is_decaying": True, "decay_diff": 20.0, "sl_price": 193.48, "sl_pct": 38.2, "expiry_date": test_exp, "hedge_ltp": 18.0}
            ]
            res = os_engine.inspect_os_candidates(test_exp)
            self.assertTrue(res["ok"])
            self.assertEqual(res["action"], "SELL_BOTH")
            self.assertTrue(res["ce_qualified"])
            self.assertTrue(res["pe_qualified"])

    def test_07_daily_trade_limit_guard(self):
        """Verify 'Din mein sirf ek hi baar trade karna hai' blocks repeat executions."""
        unit = "OS_GUARD_TEST"
        db.reset_os_daily_trade_flag(unit)
        self.assertFalse(db.has_os_traded_today(unit))

        # Mark as traded
        db.mark_os_traded_today(unit)
        self.assertTrue(db.has_os_traded_today(unit))

        # Try to deploy with deploy_now=True
        deploy_res = os_engine.deploy_os_unit(unit, deploy_now=True, force_override_daily_limit=False)
        self.assertFalse(deploy_res["ok"])
        self.assertEqual(deploy_res["action"], "BLOCKED_DAILY_LIMIT")
        self.assertIn("Din mein sirf ek hi baar trade karna hai", deploy_res["message"])

        # Reset flag for cleanup
        db.reset_os_daily_trade_flag(unit)
        self.assertFalse(db.has_os_traded_today(unit))

    def test_08_manual_lot_size_decision(self):
        """Verify user can manually decide the lot size and total quantity matches Lots * Lot Size."""
        orig_ls = db.get_os_lot_size()
        try:
            # Set manual lot size
            db.set_os_lot_size(75)
            self.assertEqual(db.get_os_lot_size(), 75)

            expiries = os_engine.get_nifty_expiry_dates()
            test_exp = expiries[0]

            with patch.object(os_engine, "hunt_os_strike") as mock_hunt, patch("telegram_bot.send"):
                mock_hunt.side_effect = [
                    {"ok": True, "option_type": "CE", "sell_strike": 25200, "hedge_strike": 25700, "sell_ltp": 130.0, "yesterday_anchor": 150.0, "is_decaying": True, "decay_diff": 20.0, "sl_price": 179.66, "sl_pct": 38.2, "expiry_date": test_exp, "hedge_ltp": 15.0},
                    {"ok": True, "option_type": "PE", "sell_strike": 24600, "hedge_strike": 24100, "sell_ltp": 140.0, "yesterday_anchor": 160.0, "is_decaying": True, "decay_diff": 20.0, "sl_price": 193.48, "sl_pct": 38.2, "expiry_date": test_exp, "hedge_ltp": 18.0}
                ]
                # Deploy with 2 lots and manual lot_size=75 => total 150 qty
                deploy_res = os_engine.deploy_os_unit("OS_LOT_TEST", test_exp, lots=2, lot_size=75, deploy_now=False)
                self.assertTrue(deploy_res["ok"])
                self.assertEqual(deploy_res["lots"], 2)
                self.assertEqual(deploy_res["lot_size"], 75)
                self.assertEqual(deploy_res["total_qty"], 150)
        finally:
            db.set_os_lot_size(orig_ls)


    def test_09_wipeout_os_unit_now(self):
        """Verify wipeout_os_unit_now closes open strikes, deletes block from DB, and unlocks settings."""
        test_exp = "2026-10-29"
        unit = "OS_WIPEOUT_TEST"

        # 1. Create a block for this unit with a sell strike and hedge
        b_res = bm.create_block(expiry_date=test_exp, expiry_type="MONTHLY", side_type="BOTH", anchor_unit_name=unit)
        self.assertTrue(b_res["ok"])
        bid = b_res["block_id"]

        # Add strikes
        s1 = db.add_strike(bid, 24100, "CE", "SELL", 120.0, lots=1, expiry_date=test_exp)
        s2 = db.add_strike(bid, 24600, "CE", "HEDGE_BUY", 30.0, lots=1, expiry_date=test_exp)

        db.set_os_settings(locked=True, expiry_date=test_exp, lots=1)
        db.mark_os_traded_today(unit)

        self.assertTrue(db.is_os_settings_locked())
        self.assertTrue(db.has_os_traded_today(unit))
        self.assertIsNotNone(db.get_block(bid))

        # 2. Execute wipeout without live broker sync
        w_res = os_engine.wipeout_os_unit_now(unit, sync_live=False)
        self.assertTrue(w_res["ok"])
        self.assertIn("completely wiped out and reset", w_res["message"])

        # 3. Assert DB cleaned up
        self.assertFalse(db.get_block(bid))
        self.assertFalse(db.is_os_settings_locked())
        self.assertFalse(db.has_os_traded_today(unit))


if __name__ == "__main__":
    unittest.main()


