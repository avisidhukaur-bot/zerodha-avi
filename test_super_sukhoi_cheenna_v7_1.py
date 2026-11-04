"""
test_super_sukhoi_cheenna_v7_1.py — Automated Verification Suite for Super Sukhoi V7.1
=======================================================================================
Target System : Cheenna Zerodha Option Selling App (Chhoti Bahan Edition)
Protocol      : Gurjas's Lego System Protocol (Brick 6: Sanity Verification)
Features      :
  1. Mom's Dynamic Execution-Anchored Invariant (A2 = fill spot rounded to 50)
  2. Sequential Chaining (M3 trigger derives strictly from A2, never double-triggers)
  3. Dynamic Lot Inheritance (M2/M3 inherits M1 lot count, never defaults to 1)
  4. Regime Engine JIT Auto-Hunter mute guard on Super Sukhoi blocks
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import db
import super_sukhoi_engine as sukhoi

class TestSuperSukhoiV71(unittest.TestCase):

    def setUp(self):
        self.orig_active = db.get("super_sukhoi_active", "0")
        self.orig_anchor = db.get("super_sukhoi_m1_anchor", "")
        self.orig_lots = db.get("super_sukhoi_m1_lots", "3")
        self.orig_m2_dep = db.get("super_sukhoi_m2_deployed", "0")
        self.orig_m2_anchor = db.get("super_sukhoi_m2_anchor", "0.0")
        self.orig_m3_dep = db.get("super_sukhoi_m3_deployed", "0")
        self.orig_m3_anchor = db.get("super_sukhoi_m3_anchor", "0.0")

    def tearDown(self):
        db.set("super_sukhoi_active", self.orig_active)
        db.set("super_sukhoi_m1_anchor", self.orig_anchor)
        db.set("super_sukhoi_m1_lots", self.orig_lots)
        db.set("super_sukhoi_m2_deployed", self.orig_m2_dep)
        db.set("super_sukhoi_m2_anchor", self.orig_m2_anchor)
        db.set("super_sukhoi_m3_deployed", self.orig_m3_dep)
        db.set("super_sukhoi_m3_anchor", self.orig_m3_anchor)

    def test_01_chained_trigger_calculus(self):
        """Verify M2 triggers from A1, and M3 triggers sequentially from A2."""
        a1 = 23000.00
        # When M2 is not deployed (m2_anchor = 0.0)
        t_standby = sukhoi.compute_triggers(a1, m2_anchor=0.0)
        self.assertEqual(t_standby["m2_up"], 23460.00)
        self.assertEqual(t_standby["m2_down"], 22540.00)
        self.assertEqual(t_standby["m3_up"], 23920.00)  # Theoretical 4% standby

        # When M2 is deployed at actual gap-up spot 23,600!
        a2 = 23600.00
        t_chained = sukhoi.compute_triggers(a1, m2_anchor=a2)
        # M3 trigger must be derived from 23,600, NOT 23,000!
        expected_m3_up = round(23600.00 * 1.020, 2)    # 24,072.00
        expected_m3_down = round(23600.00 * 0.980, 2)  # 23,128.00
        self.assertEqual(t_chained["m3_up"], expected_m3_up, "M3 UP must be A2 + 2% (24,072.00)")
        self.assertEqual(t_chained["m3_down"], expected_m3_down, "M3 DOWN must be A2 - 2% (23,128.00)")
        print("\n✅ Test 01 Passed: Sequential Chaining calculus verified (M3 derives from A2).")

    def test_02_dynamic_lot_and_anchor_persistence(self):
        """Verify dynamic lot inheritance and anchor persistence in DB state."""
        # Activate with 3 lots
        sukhoi.activate_super_sukhoi(m1_anchor=23000.00, expiry_date="2026-11-26", lots=3)
        state = db.get_super_sukhoi_state()
        self.assertEqual(state["m1_lots"], 3, "Lots must be strictly 3 (inherited)")
        self.assertEqual(state["m1_anchor"], 23000.00)

        # Simulate M2 deployment at actual spot 23,600
        db.set("super_sukhoi_m2_deployed", "1")
        db.set("super_sukhoi_m2_direction", "UP")
        db.set("super_sukhoi_m2_anchor", "23600.00")

        state2 = db.get_super_sukhoi_state()
        self.assertTrue(state2["m2_deployed"])
        self.assertEqual(state2["m2_anchor"], 23600.00)

        # Telemetry radar must reflect chained M3 trigger from 23,600
        telemetry = sukhoi.get_super_sukhoi_status()
        self.assertEqual(telemetry["m1_lots"], 3)
        self.assertEqual(telemetry["m2_anchor"], 23600.00)
        self.assertEqual(telemetry["triggers"]["m3_up"], 24072.00)
        print("✅ Test 02 Passed: Dynamic Lot & Anchor persistence verified.")

    def test_03_reset_locks_clears_anchors(self):
        """Verify reset_super_sukhoi_deployments clears M2/M3 anchors cleanly."""
        db.set("super_sukhoi_m2_deployed", "1")
        db.set("super_sukhoi_m2_anchor", "23600.00")
        db.set("super_sukhoi_m3_deployed", "1")
        db.set("super_sukhoi_m3_anchor", "24100.00")

        res = sukhoi.reset_super_sukhoi_deployments()
        self.assertTrue(res["ok"])

        state = db.get_super_sukhoi_state()
        self.assertFalse(state["m2_deployed"])
        self.assertEqual(state["m2_anchor"], 0.0)
        self.assertFalse(state["m3_deployed"])
        self.assertEqual(state["m3_anchor"], 0.0)
        print("✅ Test 03 Passed: Deployment reset clears benchmark anchors.")


if __name__ == "__main__":
    unittest.main()
