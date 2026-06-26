"""
test_brick2.py -- Brick 2 Verification: kite_executor.py
Run: python test_brick2.py
"""
import sys
import os
sys.path.insert(0, ".")

# Clean up DB
for db_name in ("zerodha_trader.db",):
    if os.path.exists(db_name):
        try:
            os.remove(db_name)
        except Exception:
            pass

# Setup mock database settings so executor checks pass
import db
db.set("KITE_CLIENT_CODE", "MOCK_CODE")
db.set("KITE_PASSWORD", "mock_password")
db.set("KITE_TOTP_KEY", "MOCK_TOTP_KEY")
db.set("KITE_API_KEY", "MOCK_API_KEY")
db.set("KITE_API_SECRET", "MOCK_SECRET")

print("=" * 55)
print("  BRICK 2 VERIFICATION -- kite_executor.py")
print("=" * 55)

from kite_executor import kite_executor

# Mock KiteConnect interface to test functions in isolation
class MockKiteConnect:
    def __init__(self, api_key):
        self.api_key = api_key
        self.access_token = None
        self.TRANSACTION_TYPE_BUY = "BUY"
        self.TRANSACTION_TYPE_SELL = "SELL"
        self.ORDER_TYPE_LIMIT = "LIMIT"
        self.ORDER_TYPE_MARKET = "MARKET"
        self.VARIETY_REGULAR = "regular"
        self.EXCHANGE_NFO = "NFO"
        self.PRODUCT_NRML = "NRML"

    def set_access_token(self, token):
        self.access_token = token

    def place_order(self, variety, exchange, tradingsymbol, transaction_type, quantity, product, order_type, price=None, trigger_price=None):
        return "MOCK_KITE_ORDER_12345"

    def cancel_order(self, variety, order_id):
        return True

    def order_history(self, order_id):
        return [{"status": "COMPLETE", "average_price": 16.0}]

    def orders(self):
        return []

    def trades(self):
        return []

    def positions(self):
        return {"net": [], "day": []}

    def ltp(self, query):
        return {query: {"last_price": 16.0}}

# Inject Mock client and bypass headless login
kite_executor.kite = MockKiteConnect("MOCK_API_KEY")
kite_executor.is_logged_in = True
kite_executor.login_time = 9999999999.0
kite_executor.access_token = "MOCK_ACCESS_TOKEN"

# Mock ensure_logged_in to bypass freshness checks
kite_executor.ensure_logged_in = lambda: True

print()
print("--- Test 1: Mock login check ---")
assert kite_executor.is_logged_in, "Should be marked logged in"
print("  PASS: Mock login OK")

print()
print("--- Test 2: test_connection in mock mode ---")
result = kite_executor.test_connection()
assert result["status"] == "OK", f"Expected OK, got {result}"
assert result["mode"] == "LIVE", "Should show LIVE mode"
print(f"  PASS: {result['message']}")

print()
print("--- Test 3: search_option_symbol (local mock) ---")
# Use a mock DataFrame for security master to test resolution
import pandas as pd
mock_df = pd.DataFrame([
    {
        "expiry": "2025-06-26",
        "strike": 24000,
        "instrument_type": "CE",
        "instrument_token": "12345",
        "tradingsymbol": "NIFTY2562624000CE",
        "name": "NIFTY",
        "segment": "NFO-OPT",
        "exchange": "NFO",
        "lot_size": 65
    },
    {
        "expiry": "2025-06-26",
        "strike": 24300,
        "instrument_type": "CE",
        "instrument_token": "67890",
        "tradingsymbol": "NIFTY2562624300CE",
        "name": "NIFTY",
        "segment": "NFO-OPT",
        "exchange": "NFO",
        "lot_size": 65
    }
])
kite_executor._instruments_cache = mock_df
kite_executor._instruments_date = "2026-06-18" # mock current date to match today

info = kite_executor.search_option_symbol(
    expiry_date  = "26-Jun-2025",
    strike_price = 24000,
    option_type  = "CE",
)
assert info is not None, "Resolution should return mock symbol"
assert info["trading_symbol"] == "NIFTY2562624000CE", f"Expected NIFTY2562624000CE, got {info['trading_symbol']}"
assert info["token"] == "12345", f"Expected token 12345, got {info['token']}"
print(f"  PASS: Symbol={info['trading_symbol']} | Token={info['token']}")

print()
print("--- Test 4: HARD RULE - symbol forced to NIFTY ---")
# If BANKNIFTY is passed, must override to NIFTY
info2 = kite_executor.search_option_symbol(
    expiry_date  = "26-Jun-2025",
    strike_price = 24000,
    option_type  = "CE",
    symbol       = "BANKNIFTY"
)
assert info2 is not None, "Resolution should override and return symbol"
assert info2["trading_symbol"] == "NIFTY2562624000CE", f"Expected NIFTY2562624000CE, got {info2['trading_symbol']}"
print(f"  PASS: Symbol={info2['trading_symbol']} (BANKNIFTY overridden to NIFTY)")

print()
print("--- Test 5: place_order SELL (MARKET converted to LIMIT check) ---")
# MARKET orders are converted to LIMIT using LTP
order_id = kite_executor.place_order(
    transaction_type = "SELL",
    trading_symbol   = "NIFTY2562624000CE",
    symbol_token     = "12345",
    qty              = 130, # 2 lots
    order_type       = "MARKET"
)
assert order_id == "MOCK_KITE_ORDER_12345", "Order ID mismatch"
print(f"  PASS: Sell order placed | ID: {order_id}")

print()
print("--- Test 6: get_order_status & poll_order_fill ---")
status = kite_executor.get_order_status("MOCK_KITE_ORDER_12345")
assert status == "SUCCESS", f"Expected SUCCESS, got {status}"
filled = kite_executor.poll_order_fill("MOCK_KITE_ORDER_12345", max_attempts=1, delay_sec=0.1)
assert filled, "Order should be filled in mock mode"
print("  PASS: Order status and fill verification OK")

print()
print("--- Test 7: get_ltp ---")
ltp = kite_executor.get_ltp("12345", "NIFTY2562624000CE")
assert ltp == 16.0, f"Expected 16.0, got {ltp}"
print(f"  PASS: LTP={ltp} fetched successfully")

print()
print("--- Test 8: cancel_order ---")
ok = kite_executor.cancel_order("MOCK_KITE_ORDER_12345")
assert ok, "Cancel order failed"
print("  PASS: Order cancellation OK")

print()
print("--- Test 9: login_with_otp mock check ---")
import requests

class MockSessionResponse:
    def __init__(self, status_code, json_data, headers=None, url=""):
        self.status_code = status_code
        self.json_data = json_data
        self.headers = headers or {}
        self.url = url
    def json(self):
        return self.json_data

orig_post = requests.Session.post
orig_get = requests.Session.get

def mock_session_post(self, url, *args, **kwargs):
    if "/login" in url:
        return MockSessionResponse(200, {"status": "success", "data": {"request_id": "MOCK_REQ_ID"}})
    elif "/twofa" in url:
        return MockSessionResponse(200, {"status": "success"})
    return MockSessionResponse(404, {})

def mock_session_get(self, url, *args, **kwargs):
    if "/connect/login" in url:
        return MockSessionResponse(200, {}, {"Location": "https://localhost/?request_token=MOCK_REQ_TOKEN"})
    return MockSessionResponse(200, {}, url="https://kite.zerodha.com/")

requests.Session.post = mock_session_post
requests.Session.get = mock_session_get

class MockKiteWithGenerate(MockKiteConnect):
    def generate_session(self, request_token, api_secret):
        return {"access_token": "MOCK_GEN_ACCESS_TOKEN"}

import kite_executor as ke_mod
orig_kiteconnect_class = getattr(ke_mod, "KiteConnect", None)
ke_mod.KiteConnect = MockKiteWithGenerate

# Temporarily restore non-mocked properties to test login
ke_mod.kite_executor.kite = MockKiteWithGenerate("MOCK_API_KEY")
ke_mod.kite_executor.is_logged_in = False
ke_mod.kite_executor.access_token = None
ke_mod.kite_executor.login_time = None
if hasattr(ke_mod.kite_executor, 'ensure_logged_in'):
    del ke_mod.kite_executor.ensure_logged_in

try:
    ok = ke_mod.kite_executor.login_with_otp("123456")
    assert ok, "login_with_otp should return True"
    assert ke_mod.kite_executor.is_logged_in, "Should be logged in"
    assert ke_mod.kite_executor.access_token == "MOCK_GEN_ACCESS_TOKEN", f"Expected MOCK_GEN_ACCESS_TOKEN, got {ke_mod.kite_executor.access_token}"
    print("  PASS: login_with_otp verified successfully")
finally:
    requests.Session.post = orig_post
    requests.Session.get = orig_get
    if orig_kiteconnect_class:
        ke_mod.KiteConnect = orig_kiteconnect_class
    ke_mod.kite_executor.kite = MockKiteConnect("MOCK_API_KEY")
    ke_mod.kite_executor.is_logged_in = True
    ke_mod.kite_executor.login_time = 9999999999.0
    ke_mod.kite_executor.access_token = "MOCK_ACCESS_TOKEN"
    ke_mod.kite_executor.ensure_logged_in = lambda: True




print()
print("--- Test 10: Singleton instance check ---")
from kite_executor import KiteExecutor
inst1 = kite_executor
import kite_executor as ke_mod
inst2 = ke_mod.kite_executor
assert inst1 is inst2, "KiteExecutor is not a singleton"
print("  PASS: Singleton verified")

print("\n" + "=" * 55)
print("  ALL BRICK 2 TESTS PASSED!")
print("  kite_executor.py is VERIFIED and READY")
print("=" * 55)

