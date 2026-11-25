"""
test_3pulse_cadence_v8_3.py — Comprehensive Test Suite for Gurjeet Mamu's 3-Pulse Cadence (V8.3)
Verifies:
1. BULLISH Pulse (Spot >= Anchor + 15.0): PUT continues, CALL closed.
2. BEARISH Pulse (Spot <= Anchor - 15.0): CALL continues, PUT closed.
3. NEUTRAL Buffer Zone (Anchor - 15.0 < Spot < Anchor + 15.0): BOTH held, 0 trades closed!
4. Evening 14:57 Pulse: Marks trade_state as CONTINUED.
5. Backward-compatibility of execute_3pm_master_anchor_decision().
"""
import unittest
from unittest.mock import patch
import os
import db
import block_manager as bm
import config as cfg

def fake_close_strike(strike_id, close_hedge=False):
    db.update_strike_status(strike_id, "CLOSED")
    db.update_strike_trade_state(strike_id, "CLOSED")
    return {"ok": True, "message": "Mock closed successfully"}

class Test3PulseCadence(unittest.TestCase):
    def setUp(self):
        db.init_db()
        self.orig_paper_mode = db.get("paper_mode", "NO")
        self.cleanup_test_blocks()

    def tearDown(self):
        self.cleanup_test_blocks()
        db.set("paper_mode", self.orig_paper_mode)

    def cleanup_test_blocks(self):
        blocks = db.get_all_blocks()
        for b in blocks:
            if "TEST_PULSE" in (b.get("anchor_unit_name") or ""):
                db.force_delete_block(b["block_id"])

    @patch("block_manager.close_strike", side_effect=fake_close_strike)
    def test_01_bullish_pulse_above_buffer(self, mock_close):
        """Spot >= Anchor + 15.0: PUT continues, CALL closed."""
        anchor = 24000.0
        buffer_pts = 15.0
        bullish_spot = 24025.0  # Above 24015.0

        block_id = db.create_block(
            expiry_date="29-Dec-2026",
            expiry_type="MONTHLY",
            side_type="BOTH",
            anchor_unit_name="TEST_PULSE_BULL",
            master_anchor_price=anchor,
            regime_buffer=buffer_pts
        )
        ce_h_id = db.add_strike(block_id, 24500, "CE", "HEDGE_BUY", 20.0, 1, trade_state="OPEN")
        ce_s_id = db.add_strike(block_id, 24200, "CE", "SELL", 80.0, 1, hedge_strike_id=ce_h_id, trade_state="OPEN")
        pe_h_id = db.add_strike(block_id, 23500, "PE", "HEDGE_BUY", 20.0, 1, trade_state="OPEN")
        pe_s_id = db.add_strike(block_id, 23800, "PE", "SELL", 80.0, 1, hedge_strike_id=pe_h_id, trade_state="OPEN")

        for sid in [ce_h_id, ce_s_id, pe_h_id, pe_s_id]:
            db.update_strike_status(sid, "OPEN")

        db.set("paper_mode", "YES")

        res = bm.execute_m_pulse_decision(pulse_id="PULSE_11_00", pulse_label="11:00 AM Pulse", nifty_spot=bullish_spot)
        self.assertTrue(res["ok"])

        # Check unit results
        u_res = [r for r in res["results"] if r["block_id"] == block_id][0]
        self.assertEqual(u_res["regime"], "BULLISH")
        self.assertEqual(u_res["continued_side"], "PUT")
        self.assertEqual(u_res["opposing_side"], "CALL")
        self.assertEqual(u_res["closed_count"], 1)

        # CE sell and its hedge should be CLOSED
        ce_sell = db.get_strike(ce_s_id)
        self.assertEqual(ce_sell["status"], "CLOSED")
        ce_hedge = db.get_strike(ce_h_id)
        self.assertEqual(ce_hedge["status"], "CLOSED")

        # PE sell and its hedge should remain OPEN
        pe_sell = db.get_strike(pe_s_id)
        self.assertEqual(pe_sell["status"], "OPEN")
        pe_hedge = db.get_strike(pe_h_id)
        self.assertEqual(pe_hedge["status"], "OPEN")

    @patch("block_manager.close_strike", side_effect=fake_close_strike)
    def test_02_bearish_pulse_below_buffer(self, mock_close):
        """Spot <= Anchor - 15.0: CALL continues, PUT closed."""
        anchor = 24000.0
        buffer_pts = 15.0
        bearish_spot = 23975.0  # Below 23985.0

        block_id = db.create_block(
            expiry_date="29-Dec-2026",
            expiry_type="MONTHLY",
            side_type="BOTH",
            anchor_unit_name="TEST_PULSE_BEAR",
            master_anchor_price=anchor,
            regime_buffer=buffer_pts
        )
        ce_h_id = db.add_strike(block_id, 24500, "CE", "HEDGE_BUY", 20.0, 1, trade_state="OPEN")
        ce_s_id = db.add_strike(block_id, 24200, "CE", "SELL", 80.0, 1, hedge_strike_id=ce_h_id, trade_state="OPEN")
        pe_h_id = db.add_strike(block_id, 23500, "PE", "HEDGE_BUY", 20.0, 1, trade_state="OPEN")
        pe_s_id = db.add_strike(block_id, 23800, "PE", "SELL", 80.0, 1, hedge_strike_id=pe_h_id, trade_state="OPEN")

        for sid in [ce_h_id, ce_s_id, pe_h_id, pe_s_id]:
            db.update_strike_status(sid, "OPEN")

        db.set("paper_mode", "YES")

        res = bm.execute_m_pulse_decision(pulse_id="PULSE_13_00", pulse_label="1:00 PM Pulse", nifty_spot=bearish_spot)
        self.assertTrue(res["ok"])

        u_res = [r for r in res["results"] if r["block_id"] == block_id][0]
        self.assertEqual(u_res["regime"], "BEARISH")
        self.assertEqual(u_res["continued_side"], "CALL")
        self.assertEqual(u_res["opposing_side"], "PUT")
        self.assertEqual(u_res["closed_count"], 1)

        # PE sell and hedge should be CLOSED
        pe_sell = db.get_strike(pe_s_id)
        self.assertEqual(pe_sell["status"], "CLOSED")
        pe_hedge = db.get_strike(pe_h_id)
        self.assertEqual(pe_hedge["status"], "CLOSED")

        # CE sell and hedge should remain OPEN
        ce_sell = db.get_strike(ce_s_id)
        self.assertEqual(ce_sell["status"], "OPEN")
        ce_hedge = db.get_strike(ce_h_id)
        self.assertEqual(ce_hedge["status"], "OPEN")

    def test_03_neutral_pulse_inside_buffer(self):
        """Anchor - 15.0 < Spot < Anchor + 15.0: NEUTRAL! BOTH wings preserved untouched (0 closed)."""
        anchor = 24000.0
        buffer_pts = 15.0
        neutral_spot = 24005.0  # Inside 23985.0 to 24015.0

        block_id = db.create_block(
            expiry_date="29-Dec-2026",
            expiry_type="MONTHLY",
            side_type="BOTH",
            anchor_unit_name="TEST_PULSE_NEUT",
            master_anchor_price=anchor,
            regime_buffer=buffer_pts
        )
        ce_h_id = db.add_strike(block_id, 24500, "CE", "HEDGE_BUY", 20.0, 1, trade_state="OPEN")
        ce_s_id = db.add_strike(block_id, 24200, "CE", "SELL", 80.0, 1, hedge_strike_id=ce_h_id, trade_state="OPEN")
        pe_h_id = db.add_strike(block_id, 23500, "PE", "HEDGE_BUY", 20.0, 1, trade_state="OPEN")
        pe_s_id = db.add_strike(block_id, 23800, "PE", "SELL", 80.0, 1, hedge_strike_id=pe_h_id, trade_state="OPEN")

        for sid in [ce_h_id, ce_s_id, pe_h_id, pe_s_id]:
            db.update_strike_status(sid, "OPEN")

        db.set("paper_mode", "YES")

        res = bm.execute_m_pulse_decision(pulse_id="PULSE_11_00", pulse_label="11:00 AM Pulse", nifty_spot=neutral_spot)
        self.assertTrue(res["ok"])

        u_res = [r for r in res["results"] if r["block_id"] == block_id][0]
        self.assertEqual(u_res["regime"], "NEUTRAL")
        self.assertEqual(u_res["continued_side"], "BOTH")
        self.assertEqual(u_res["opposing_side"], "NONE")
        self.assertEqual(u_res["closed_count"], 0)

        # Both CE and PE sells and hedges MUST remain OPEN
        ce_sell = db.get_strike(ce_s_id)
        self.assertEqual(ce_sell["status"], "OPEN")
        pe_sell = db.get_strike(pe_s_id)
        self.assertEqual(pe_sell["status"], "OPEN")

    def test_04_evening_decision_wrapper_compatibility(self):
        """execute_3pm_master_anchor_decision calls PULSE_14_57 and marks CONTINUED."""
        anchor = 24000.0
        buffer_pts = 15.0
        bullish_spot = 24030.0

        block_id = db.create_block(
            expiry_date="29-Dec-2026",
            expiry_type="MONTHLY",
            side_type="BOTH",
            anchor_unit_name="TEST_PULSE_WRAP",
            master_anchor_price=anchor,
            regime_buffer=buffer_pts
        )
        pe_h_id = db.add_strike(block_id, 23500, "PE", "HEDGE_BUY", 20.0, 1, trade_state="OPEN")
        pe_s_id = db.add_strike(block_id, 23800, "PE", "SELL", 80.0, 1, hedge_strike_id=pe_h_id, trade_state="OPEN")

        for sid in [pe_h_id, pe_s_id]:
            db.update_strike_status(sid, "OPEN")

        # Set paper_mode = YES so broker check passes in test environment
        db.set("paper_mode", "YES")

        res = bm.execute_3pm_master_anchor_decision(nifty_spot=bullish_spot)
        self.assertTrue(res["ok"])
        self.assertEqual(res["pulse_id"], "PULSE_14_57")

        pe_sell = db.get_strike(pe_s_id)
        self.assertEqual(pe_sell["trade_state"], "CONTINUED")

if __name__ == "__main__":
    unittest.main()
