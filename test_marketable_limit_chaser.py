# -*- coding: utf-8 -*-
import unittest
from unittest.mock import MagicMock, patch
import os
import sys

os.environ['TESTING'] = '1'

class TestMarketableLimitChaser(unittest.TestCase):
    def setUp(self):
        import kite_executor as ke
        self.ke = ke.kite_executor
        self.ke.kite = MagicMock()
        self.ke.ensure_logged_in = MagicMock(return_value=True)

    def test_01_marketable_limit_calculation_and_instant_fill(self):
        # Mock quotes
        self.ke.get_live_ltp = MagicMock(return_value=180.0)
        self.ke.place_order = MagicMock(return_value="210000000001")
        self.ke.get_all_orders = MagicMock(return_value=[
            {"order_id": "210000000001", "status": "COMPLETE", "average_price": 180.5}
        ])

        oid, filled, price = self.ke.execute_marketable_limit_with_chaser(
            trading_symbol="NIFTY26DEC26400CE",
            transaction_type="BUY",
            qty=195,
            buffer_pct=0.10,
            chase_delay_sec=1.0
        )

        self.assertEqual(oid, "210000000001")
        self.assertTrue(filled)
        self.assertEqual(price, 180.5)
        # Verify limit price was calculated as LTP * 1.10 = 198.0
        self.ke.place_order.assert_called_with(
            transaction_type="BUY",
            trading_symbol="NIFTY26DEC26400CE",
            symbol_token="",
            qty=195,
            order_type="LIMIT",
            price=198.0
        )

    def test_02_dynamic_chaser_on_market_jump(self):
        self.ke.get_live_ltp = MagicMock(return_value=180.0)
        self.ke.place_order = MagicMock(return_value="210000000002")
        
        # In attempt 1: order is OPEN. In attempt 2: after modify, order is COMPLETE @ 202.0
        orders_state = [
            [{"order_id": "210000000002", "status": "OPEN", "price": 198.0}],
            [{"order_id": "210000000002", "status": "COMPLETE", "average_price": 202.0}]
        ]
        self.ke.get_all_orders = MagicMock(side_effect=orders_state * 10)
        self.ke.kite.quote = MagicMock(return_value={"NFO:NIFTY26DEC26400CE": {"last_price": 200.0}})
        self.ke.kite.modify_order = MagicMock()

        oid, filled, price = self.ke.execute_marketable_limit_with_chaser(
            trading_symbol="NIFTY26DEC26400CE",
            transaction_type="BUY",
            qty=195,
            buffer_pct=0.10,
            max_chase_attempts=2,
            chase_delay_sec=0.1
        )

        self.assertTrue(filled)
        self.assertEqual(price, 202.0)
        self.ke.kite.modify_order.assert_called()

if __name__ == '__main__':
    unittest.main()
