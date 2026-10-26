"""
test_super_sukhoi_cheenna_v7.py — Automated Verification Suite for Super Sukhoi V7.0
=====================================================================================
Target System : Cheenna Zerodha Option Selling App
Protocol      : Gurjas's Lego System Protocol (Brick 6: Sanity Verification)
"""

import sys
import os
import unittest
from datetime import datetime
import pytz

# Add workspace to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import db
import utils
import super_sukhoi_engine as sukhoi

IST = pytz.timezone("Asia/Kolkata")


class TestSuperSukhoiV7(unittest.TestCase):

    def setUp(self):
        # Save original state for restore
        self.orig_active = db.get("super_sukhoi_active", "0")
        self.orig_anchor = db.get("super_sukhoi_m1_anchor", "")
        self.orig_m2_dep = db.get("super_sukhoi_m2_deployed", "0")
        self.orig_m2_dir = db.get("super_sukhoi_m2_direction", "")
        self.orig_m3_dep = db.get("super_sukhoi_m3_deployed", "0")
        self.orig_m3_dir = db.get("super_sukhoi_m3_direction", "")
        self.orig_sl_mode = db.get("m_stoploss_mode", "DISABLED")

    def tearDown(self):
        # Restore original state
        db.set("super_sukhoi_active", self.orig_active)
        db.set("super_sukhoi_m1_anchor", self.orig_anchor)
        db.set("super_sukhoi_m2_deployed", self.orig_m2_dep)
        db.set("super_sukhoi_m2_direction", self.orig_m2_dir)
        db.set("super_sukhoi_m3_deployed", self.orig_m3_dep)
        db.set("super_sukhoi_m3_direction", self.orig_m3_dir)
        db.set("m_stoploss_mode", self.orig_sl_mode)

    def test_01_trigger_calculus(self):
        """Verify mathematical trigger bounds derived from M1 Seed Anchor."""
        anchor = 22650.00
        triggers = sukhoi.compute_triggers(anchor)

        self.assertEqual(triggers["m2_up"], 23103.00, "M2 UP should be exactly +2.00% (₹23,103.00)")
        self.assertEqual(triggers["m2_down"], 22197.00, "M2 DOWN should be exactly -2.00% (₹22,197.00)")
        self.assertEqual(triggers["m3_up"], 23556.00, "M3 UP should be exactly +4.00% (₹23,556.00)")
        self.assertEqual(triggers["m3_down"], 21744.00, "M3 DOWN should be exactly -4.00% (₹21,744.00)")
        print("\n✅ Test 01 Passed: Mathematical trigger calculus is 100% deterministic.")

    def test_02_db_state_transitions(self):
        """Verify Super Sukhoi DB schema, getters, setters, and state persistence."""
        # Test activation
        res = sukhoi.activate_super_sukhoi(m1_anchor=22650.00, expiry_date="2026-11-26", lots=2)
        self.assertTrue(res["ok"])

        state = db.get_super_sukhoi_state()
        self.assertTrue(state["active"], "Super Sukhoi should be ACTIVE")
        self.assertEqual(state["m1_anchor"], 22650.00)
        self.assertEqual(state["m1_expiry"], "2026-11-26")
        self.assertEqual(state["m1_lots"], 2)
        self.assertFalse(state["m2_deployed"])
        self.assertFalse(state["m3_deployed"])

        # Test deactivation
        deact_res = sukhoi.deactivate_super_sukhoi()
        self.assertTrue(deact_res["ok"])
        self.assertFalse(db.get_super_sukhoi_state()["active"])
        print("✅ Test 02 Passed: Super Sukhoi DB state transitions persist cleanly.")

    def test_03_decoupled_stoploss_mode(self):
        """Verify m_stoploss_mode default is DISABLED and correctly read."""
        sl_mode = db.get("m_stoploss_mode", "DISABLED")
        self.assertEqual(sl_mode.strip().upper(), "DISABLED", "Default Stop-Loss mode must be DISABLED")

        # Test toggle
        db.set("m_stoploss_mode", "ENABLED")
        self.assertEqual(db.get("m_stoploss_mode"), "ENABLED")
        db.set("m_stoploss_mode", "DISABLED")
        self.assertEqual(db.get("m_stoploss_mode"), "DISABLED")
        print("✅ Test 03 Passed: Decoupled Stop-Loss policy verified (DISABLED default).")

    def test_04_session_and_holiday_guard(self):
        """Verify market session guard silences engine during weekends and NSE holidays."""
        # Test a weekend date (e.g. Saturday 2026-10-31)
        sat_dt = datetime(2026, 10, 31, 11, 30, tzinfo=IST)
        self.assertFalse(utils.is_market_session_active(sat_dt), "Weekend must be inactive")

        # Test an official NSE holiday (e.g. Diwali Laxmi Pujan 2026-11-09)
        holiday_dt = datetime(2026, 11, 9, 11, 30, tzinfo=IST)
        self.assertFalse(utils.is_market_session_active(holiday_dt), "NSE holiday must be inactive")

        # Test an off-hours time on weekday (08:30 AM)
        off_hours_dt = datetime(2026, 10, 27, 8, 30, tzinfo=IST)
        self.assertFalse(utils.is_market_session_active(off_hours_dt), "Pre-market must be inactive")

        # Test valid trading hours on a regular Tuesday (11:30 AM)
        trading_dt = datetime(2026, 10, 27, 11, 30, tzinfo=IST)
        self.assertTrue(utils.is_market_session_active(trading_dt), "Tuesday 11:30 AM must be active")
        print("✅ Test 04 Passed: Market session guard accurately protects off-hours & holidays.")

    def test_05_radar_status_payload(self):
        """Verify get_super_sukhoi_status returns all telemetry fields for Cockpit HUD."""
        sukhoi.activate_super_sukhoi(m1_anchor=22650.00, expiry_date="2026-11-26", lots=1)
        status = sukhoi.get_super_sukhoi_status()

        self.assertIn("active", status)
        self.assertIn("live_spot", status)
        self.assertIn("m1_anchor", status)
        self.assertIn("triggers", status)
        self.assertIn("m2_deployed", status)
        self.assertIn("m3_deployed", status)
        self.assertIn("stoploss_mode", status)
        self.assertEqual(status["m1_anchor"], 22650.00)
        print("✅ Test 05 Passed: Telemetry Radar payload is complete and valid.")


if __name__ == "__main__":
    unittest.main()
