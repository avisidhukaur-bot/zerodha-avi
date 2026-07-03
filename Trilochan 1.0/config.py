"""
config.py — Configuration parameters for Zerodha Option Selling App
"""
import os

# System Name
SYSTEM_NAME = "Zerodha Option Selling App"

# Port Configuration  — PORT 9007
DASHBOARD_PORT = 9007

# File Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "zerodha_trader.db")
LOG_PATH = os.path.join(BASE_DIR, "zerodha_engine.log")
SECRETS_PATH = os.path.join(BASE_DIR, "secrets.txt")

# Trading Parameters
UNDERLYING_INDEX = "NIFTY 50"
NIFTY_LOT_SIZE = 65  # Default Nifty 50 lot size

# Expiry Settings
DEFAULT_HEDGE_DISTANCE = 300  # 300 points OTM
DEFAULT_BUFFER_TOLERANCE = 2.0  # ₹2 buffer above anchor price for SL exit
DEFAULT_CHECK_INTERVAL = 30  # 30 seconds in seconds

# Time Windows (IST)
MARKET_START_TIME = "09:15"
MARKET_END_TIME = "15:30"
ROLLOVER_TIME = "14:00"  # Monday hedge rollover check time
FORCE_CLOSE_TIME = "15:15"  # Square off time if necessary

# Fallback Settings
YAHOO_TICKER = "^NSEI"  # Nifty 50 Spot ticker
NSE_INDEX_NAME = "NIFTY 50"
