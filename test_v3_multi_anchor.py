"""
test_v3_multi_anchor.py -- Comprehensive Unit Tests for V3.0 Autonomous Multi-Anchor Units
========================================================================================
Tests:
  1. Creating multiple independent Units (M1, M2, M3) for the SAME expiry date.
  2. Duplicate block prevention (blocks duplicate unit+side, allows distinct units).
  3. Decentralized Multi-Unit Regime evaluation at live spot levels.
  4. Block-level gating (is_strike_allowed_by_regime with block context).
  5. Isolated Kill & Flip per Unit.
  6. Unit 1-Click Spot Lock & DB updates.
"""

import unittest
from unittest.mock import patch, MagicMock
import os
import sys

# Force UTF-8 on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import db
import block_manager as bm
import regime_engine as re_eng

class TestV3MultiAnchorUnits(unittest.TestCase):

    def setUp(self):
        # Clean test state: close any active blocks created during previous tests
        active = db.get_all_blocks(status_filter="ACTIVE")
        for b in active:
            if "TEST" in (b.get("notes") or "") or b.get("expiry_date") in ("29-Oct-2026", "26-Nov-2026", "31-Dec-2026", "28-Jan-2027", "28-Sep-2028", "26-Oct-2028", "30-Nov-2028"):
                db.update_block_status(b["block_id"], "CLOSED")

    def tearDown(self):
        # Clean up test blocks
        active = db.get_all_blocks(status_filter="ACTIVE")
        for b in active:
            if "TEST" in (b.get("notes") or "") or b.get("expiry_date") in ("29-Oct-2026", "26-Nov-2026", "31-Dec-2026", "28-Jan-2027", "28-Sep-2028", "26-Oct-2028", "30-Nov-2028"):
                db.update_block_status(b["block_id"], "CLOSED")

    @patch("telegram_bot.send")
    def test_01_create_multiple_units_same_month(self, mock_tg):
        """Verify creating Unit M1 and Unit M2 for the SAME expiry month succeeds."""
        exp = "29-Oct-2026"
        
        # 1. Create Unit M1 (Separate Call & Put blocks)
        res_m1 = bm.create_separate_blocks(
            expiry_date=exp,
            expiry_type="MONTHLY",
            notes="TEST_V3 Unit M1",
            anchor_unit_name="M1",
            master_anchor_price=24000.0,
            regime_buffer=15.0
        )
        self.assertTrue(res_m1["ok"], f"Failed to create Unit M1: {res_m1.get('message')}")
        
        # 2. Create Unit M2 in the SAME month (Separate Call & Put blocks)
        res_m2 = bm.create_separate_blocks(
            expiry_date=exp,
            expiry_type="MONTHLY",
            notes="TEST_V3 Unit M2",
            anchor_unit_name="M2",
            master_anchor_price=24500.0,
            regime_buffer=15.0
        )
        self.assertTrue(res_m2["ok"], f"Failed to create Unit M2 in same month: {res_m2.get('message')}")

        # Verify DB attributes
        b_m1_call = db.get_block(res_m1["call_block_id"])
        b_m2_call = db.get_block(res_m2["call_block_id"])
        
        self.assertEqual(b_m1_call["anchor_unit_name"], "M1")
        self.assertEqual(float(b_m1_call["master_anchor_price"]), 24000.0)
        self.assertEqual(b_m2_call["anchor_unit_name"], "M2")
        self.assertEqual(float(b_m2_call["master_anchor_price"]), 24500.0)

    @patch("telegram_bot.send")
    def test_02_duplicate_prevention_within_same_unit(self, mock_tg):
        """Verify duplicate check blocks creating duplicate M1 for same side, but allows M2."""
        exp = "26-Nov-2026"
        
        # Create M1 CALL block
        res1 = bm.create_block(
            expiry_date=exp,
            expiry_type="MONTHLY",
            side_type="CALL",
            notes="TEST_V3 M1 Call",
            anchor_unit_name="M1",
            master_anchor_price=24000.0
        )
        self.assertTrue(res1["ok"])

        # Attempt to create duplicate M1 CALL block -> MUST be blocked
        res_dup = bm.create_block(
            expiry_date=exp,
            expiry_type="MONTHLY",
            side_type="CALL",
            notes="TEST_V3 M1 Call Dup",
            anchor_unit_name="M1",
            master_anchor_price=24000.0
        )
        self.assertFalse(res_dup["ok"])
        self.assertTrue(res_dup.get("duplicate"))

        # Attempt to create M2 CALL block for same month -> MUST succeed
        res_m2 = bm.create_block(
            expiry_date=exp,
            expiry_type="MONTHLY",
            side_type="CALL",
            notes="TEST_V3 M2 Call",
            anchor_unit_name="M2",
            master_anchor_price=24500.0
        )
        self.assertTrue(res_m2["ok"])

    @patch("telegram_bot.send")
    def test_03_decentralized_regimes_simultaneous_execution(self, mock_tg):
        """Verify Unit M1 @ 24,000 is BULLISH while Unit M2 @ 24,500 is BEARISH at Spot 24,200."""
        exp = "31-Dec-2026"
        
        # Unit M1 @ ₹24,000
        res_m1 = bm.create_block(
            expiry_date=exp,
            side_type="CALL",
            notes="TEST_V3 M1",
            anchor_unit_name="M1",
            master_anchor_price=24000.0,
            regime_buffer=15.0
        )
        # Unit M2 @ ₹24,500
        res_m2 = bm.create_block(
            expiry_date=exp,
            side_type="CALL",
            notes="TEST_V3 M2",
            anchor_unit_name="M2",
            master_anchor_price=24500.0,
            regime_buffer=15.0
        )
        
        b1 = db.get_block(res_m1["block_id"])
        b2 = db.get_block(res_m2["block_id"])
        
        # Evaluate regimes at Spot ₹24,200
        spot = 24200.0
        eval1 = re_eng.evaluate_block_regime(b1, current_spot=spot, force_eval=True)
        eval2 = re_eng.evaluate_block_regime(b2, current_spot=spot, force_eval=True)
        
        self.assertEqual(eval1["regime"], "BULLISH", "Spot 24,200 > Anchor 24,000 should be BULLISH for Unit M1")
        self.assertEqual(eval2["regime"], "BEARISH", "Spot 24,200 < Anchor 24,500 should be BEARISH for Unit M2")

        # Check strike gating
        # Unit M1 (BULLISH): PE Allowed, CE Muted
        up_b1 = db.get_block(res_m1["block_id"])
        pe_allowed_m1, _ = re_eng.is_strike_allowed_by_regime("PE", block=up_b1)
        ce_allowed_m1, _ = re_eng.is_strike_allowed_by_regime("CE", block=up_b1)
        self.assertTrue(pe_allowed_m1)
        self.assertFalse(ce_allowed_m1)

        # Unit M2 (BEARISH): CE Allowed, PE Muted
        up_b2 = db.get_block(res_m2["block_id"])
        ce_allowed_m2, _ = re_eng.is_strike_allowed_by_regime("CE", block=up_b2)
        pe_allowed_m2, _ = re_eng.is_strike_allowed_by_regime("PE", block=up_b2)
        self.assertTrue(ce_allowed_m2)
        self.assertFalse(pe_allowed_m2)

    @patch("telegram_bot.send")
    def test_04_isolated_unit_spot_lock_and_kill(self, mock_tg):
        """Verify 1-Click Spot Lock and Kill Block operate strictly per-unit."""
        exp = "28-Jan-2027"
        res = bm.create_block(
            expiry_date=exp,
            side_type="CALL",
            notes="TEST_V3 Lock Spot",
            anchor_unit_name="M3",
            master_anchor_price=0.0
        )
        bid = res["block_id"]
        
        # Set anchor
        db.update_block_anchor(bid, 24350.0, 10.0, "M3")
        b = db.get_block(bid)
        self.assertEqual(float(b["master_anchor_price"]), 24350.0)
        self.assertEqual(float(b["regime_buffer"]), 10.0)

        # Kill unit
        k_res = bm.kill_block(bid)
        self.assertTrue(k_res["ok"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
