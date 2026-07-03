"""
test_brick7.py -- Brick 7 Verification: main.py
Run: python test_brick7.py
"""
import sys
import os
import subprocess

for db_name in ("zerodha_trader.db",):
    if os.path.exists(db_name):
        try:
            os.remove(db_name)
        except Exception:
            pass

import db
import config as cfg

# Initialize database settings for testing
db.set("paper_mode", "YES")
db.set("algo_running", "ON")
db.set("KITE_API_KEY", "95380c0ac16a4482abd5ff1f30628435")
db.set("KITE_API_SECRET", "33cbad5ac8ef4793abc5234bd802c7de")
db.set("KITE_CLIENT_CODE", "4350935")
db.set("KITE_PASSWORD", "123456")
db.set("KITE_TOTP_KEY", "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP")
db.set("TELEGRAM_TOKEN", "123456:ABC-DEF")
db.set("TELEGRAM_CHAT_ID", "586422450")
db.set("ALLOWED_TRADING_IP", "ANY")  # bypass IP guard for local test run

print("--- Starting Brick 7 (main.py) integration test ---")

# Execute main.py via an inline python script that mocks requests
python_code = """
import sys
import time
import requests
import db

# Setup mock database secrets inside the subprocess
db.set("KITE_CLIENT_CODE", "MOCK_CODE")
db.set("KITE_PASSWORD", "MOCK_PASSWORD")
db.set("KITE_TOTP_KEY", "MOCK_TOTP")
db.set("KITE_API_KEY", "MOCK_KEY")
db.set("KITE_API_SECRET", "MOCK_SECRET")

# Mock the executor methods directly
from kite_executor import kite_executor
kite_executor.login = lambda: True
kite_executor.ensure_logged_in = lambda: True
kite_executor.test_connection = lambda: {"status": "OK", "mode": "LIVE", "message": "Zerodha API connected. Open positions: 0", "positions": 0}

# Prevent secrets.txt from overriding our mock secrets
db.load_secrets = lambda: True

class MockResponse:
    def __init__(self, status_code, json_data, text_data=""):
        self.status_code = status_code
        self.json_data = json_data
        self.text = text_data
    def json(self):
        return self.json_data

def mock_post(*args, **kwargs):
    url = args[0] if isinstance(args[0], str) else args[1]
    if "/login" in url:
        return MockResponse(200, {"data": {"request_token": "MOCK_REQUEST_TOKEN"}, "status": "true"})
    elif "/access-token" in url:
        return MockResponse(200, {"data": {"access_token": "MOCK_ACCESS_TOKEN"}, "status": "true"})
    elif "/instruments" in url:
        return MockResponse(200, {"data": []})
    elif "/orders/regular" in url:
        return MockResponse(200, {"status": "true", "data": {"orderid": "PAPER_MOCK_123"}})
    return MockResponse(404, {})

def mock_get(*args, **kwargs):
    url = args[0] if isinstance(args[0], str) else args[1]
    if "/orders/" in url:
        return MockResponse(200, {"status": "true", "data": {"orderstatus": "COMPLETE"}})
    elif "/orders" in url:
        return MockResponse(200, {"data": []})
    elif "/trades" in url:
        return MockResponse(200, {"data": []})
    elif "/portfolio/positions" in url or "/portfolio/overall_positions" in url:
        return MockResponse(200, {"data": []})
    elif "ipify.org" in url:
        return MockResponse(200, {}, "46.224.133.16")
    return MockResponse(404, {})

def mock_delete(*args, **kwargs):
    url = args[0] if isinstance(args[0], str) else args[1]
    return MockResponse(200, {"status": "true"})

requests.Session.post = mock_post
requests.Session.get = mock_get
requests.Session.delete = mock_delete
requests.get = mock_get
requests.post = mock_post
requests.delete = mock_delete

sys.argv = ['main.py', '--once']
import main
main.start_engine_loop()
"""

cmd = [sys.executable, "-c", python_code]
print(f"Running command: Python with inline mock snippet")

result = subprocess.run(cmd, capture_output=True, text=True)

print("\n--- Process Return Code ---")
print(result.returncode)

print("\n--- Process STDOUT ---")
print(result.stdout)

print("\n--- Process STDERR ---")
print(result.stderr)

# Verify results
assert result.returncode == 0, "main.py --once failed to execute cleanly"
assert "Starting Zerodha Option Selling trading engine background loop" in result.stdout, "Engine startup message not found"
assert "Attempting initial login to Zerodha Kite Connect API..." in result.stdout, "Attempting login message not found"
assert "Sending periodic system heartbeat" in result.stdout, "Heartbeat message not found"
assert "Running block expiry checks" in result.stdout, "Expiry checks message not found"
assert "Dry run / --once execution complete" in result.stdout, "Dry run completion message not found"

print("\n✅ BRICK 7 TEST PASSED: main.py executes cleanly in --once mode with correct outputs!")
