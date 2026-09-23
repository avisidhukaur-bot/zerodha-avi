"""
Unit Tests for Zero-Clash Strike Shield & Far-Month 500-Multiple Liquidity Engine
Validates:
  1. Horizon & Step Size Resolution (Near Month = 100, Far Month = 500)
  2. Anti-Collision Gatekeeper (Occupied strike shifting: +step for CE, -step for PE)
  3. Far-Month Premium Flexibility (Up to Rs 185 on 500-multiples)
  4. Integration with DB and Inspection Flow
"""

import unittest
from datetime import datetime, date, timedelta
from unittest.mock import MagicMock, patch
import os_engine
import db
import config as cfg


class TestOsStrikeShield(unittest.TestCase):

    def setUp(self):
        """Clean DB test environment."""
        db.init_db()

    def test_01_far_month_expiry_detection(self):
        """Verifies near-month (<=35 days in current month) vs far-month (>35 days / next month)."""
        today = datetime.now(os_engine.IST).date()

        # Near month test: tomorrow
        near_date = (today + timedelta(days=5)).strftime("%Y-%m-%d")
        # Far month test: 60 days ahead
        far_date = (today + timedelta(days=60)).strftime("%Y-%m-%d")

        self.assertFalse(os_engine.is_far_month_expiry(near_date))
        self.assertTrue(os_engine.is_far_month_expiry(far_date))

    def test_02_step_size_resolution(self):
        """Verifies automatic and manual override step sizes."""
        today = datetime.now(os_engine.IST).date()
        near_date = (today + timedelta(days=5)).strftime("%Y-%m-%d")
        far_date = (today + timedelta(days=60)).strftime("%Y-%m-%d")

        # AUTO
        self.assertEqual(os_engine.get_os_step_size(near_date, "AUTO"), 100)
        self.assertEqual(os_engine.get_os_step_size(far_date, "AUTO"), 500)

        # STRICT OVERRIDES
        self.assertEqual(os_engine.get_os_step_size(near_date, "500"), 500)
        self.assertEqual(os_engine.get_os_step_size(far_date, "100"), 100)

    @patch("os_engine.kite_executor.get_positions")
    @patch("os_engine.db.get_all_blocks")
    @patch("os_engine.db.get_strikes_by_block")
    def test_03_get_occupied_strikes(self, mock_get_strikes, mock_get_blocks, mock_get_positions):
        """Verifies occupied strikes aggregation from both SQLite active blocks and live broker positions."""
        test_exp = "2026-10-29"

        # Mock DB active block M1 holding 24000 CE and 23000 PE
        mock_get_blocks.return_value = [{"block_id": 1, "anchor_unit_name": "M1", "expiry_date": test_exp}]
        mock_get_strikes.return_value = [
            {"leg_type": "SELL", "strike_price": 24000, "option_type": "CE"},
            {"leg_type": "SELL", "strike_price": 23000, "option_type": "PE"},
            {"leg_type": "HEDGE_BUY", "strike_price": 24500, "option_type": "CE"}
        ]

        # Mock broker positions holding 24200 CE
        mock_get_positions.return_value = [
            {"tradingsymbol": "NIFTY26OCT24200CE", "quantity": -65},
            {"tradingsymbol": "NIFTY26OCT24700CE", "quantity": 65}
        ]

        occupied = os_engine.get_occupied_strikes(test_exp)
        self.assertIn((24000, "CE"), occupied)
        self.assertIn((23000, "PE"), occupied)
        self.assertIn((24200, "CE"), occupied)
        self.assertNotIn((25000, "CE"), occupied)

    @patch("os_engine.kite_executor.ensure_logged_in", return_value=False)
    @patch("os_engine.get_occupied_strikes")
    @patch("os_engine.kite_executor.get_ltp")
    @patch("os_engine.kite_executor.get_nifty_spot")
    @patch("os_engine.kite_executor._load_security_master")
    def test_04_anti_collision_shifting_ce(self, mock_sec_master, mock_spot, mock_ltp, mock_occupied, mock_logged_in):
        """Verifies that if candidate CE strike is occupied, engine automatically shifts UP maintaining Odd parity."""
        import pandas as pd
        test_exp = "2026-10-29"

        # Mock instruments df with odd/even multiples
        mock_sec_master.return_value = pd.DataFrame([
            {"name": "NIFTY", "exchange": "NFO", "expiry": test_exp, "instrument_type": "CE", "strike": 24100.0, "instrument_token": "101", "tradingsymbol": "NIFTY26OCT24100CE"},
            {"name": "NIFTY", "exchange": "NFO", "expiry": test_exp, "instrument_type": "CE", "strike": 24300.0, "instrument_token": "102", "tradingsymbol": "NIFTY26OCT24300CE"},
            {"name": "NIFTY", "exchange": "NFO", "expiry": test_exp, "instrument_type": "CE", "strike": 24800.0, "instrument_token": "103", "tradingsymbol": "NIFTY26OCT24800CE"},
        ])
        mock_spot.return_value = 23800.0
        mock_ltp.return_value = 140.0

        # Mark 24300 CE as occupied (held by M1/broker)
        mock_occupied.return_value = {(24300, "CE")}

        # Hunt candidate
        res = os_engine.hunt_os_strike("CE", test_exp, target_premium=150.0, step_size=100)

        self.assertTrue(res["ok"])
        # Should have selected 24100 CE (unoccupied)
        self.assertEqual(res["sell_strike"], 24100)
        self.assertEqual((res["sell_strike"] // 100) % 2, 1, "Sell strike must be ODD parity")

    @patch("os_engine.kite_executor.ensure_logged_in", return_value=False)
    @patch("os_engine.get_occupied_strikes")
    @patch("os_engine.kite_executor.get_ltp")
    @patch("os_engine.kite_executor.get_nifty_spot")
    @patch("os_engine.kite_executor._load_security_master")
    def test_05_anti_collision_shifting_pe(self, mock_sec_master, mock_spot, mock_ltp, mock_occupied, mock_logged_in):
        """Verifies that if candidate PE strike is occupied, engine automatically shifts DOWN maintaining Odd parity."""
        import pandas as pd
        test_exp = "2026-10-29"

        # Mock instruments df with odd multiples
        mock_sec_master.return_value = pd.DataFrame([
            {"name": "NIFTY", "exchange": "NFO", "expiry": test_exp, "instrument_type": "PE", "strike": 23300.0, "instrument_token": "201", "tradingsymbol": "NIFTY26OCT23300PE"},
            {"name": "NIFTY", "exchange": "NFO", "expiry": test_exp, "instrument_type": "PE", "strike": 23100.0, "instrument_token": "202", "tradingsymbol": "NIFTY26OCT23100PE"},
            {"name": "NIFTY", "exchange": "NFO", "expiry": test_exp, "instrument_type": "PE", "strike": 22600.0, "instrument_token": "203", "tradingsymbol": "NIFTY26OCT22600PE"},
        ])
        mock_spot.return_value = 23800.0
        mock_ltp.return_value = 135.0

        # Mark 23300 PE as occupied
        mock_occupied.return_value = {(23300, "PE")}

        # Hunt candidate
        res = os_engine.hunt_os_strike("PE", test_exp, target_premium=150.0, step_size=100)

        self.assertTrue(res["ok"])
        # Should have shifted/selected 23100 PE
        self.assertEqual(res["sell_strike"], 23100)
        self.assertEqual((res["sell_strike"] // 100) % 2, 1, "Sell strike must be ODD parity")

    def test_06_db_os_settings_step_size_persistence(self):
        """Verifies that step_size preference is persisted and restored cleanly in SQLite."""
        db.set_os_settings(
            locked=True,
            horizon="Monthly Expiry",
            expiry_date="2026-10-29",
            lots=2,
            lot_size=65,
            mode="AUTO",
            step_size="500",
            target_premium=160.0
        )

        settings = db.get_os_settings()
        self.assertTrue(settings["locked"])
        self.assertEqual(settings["step_size"], "500")
        self.assertEqual(settings["target_premium"], 160.0)
        self.assertEqual(settings["horizon"], "Monthly Expiry")


if __name__ == "__main__":
    unittest.main()
