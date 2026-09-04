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
DEFAULT_MAX_REENTRIES_PER_DAY = 0  # 0 = Unlimited re-entries per day
DEFAULT_REENTRY_COOLDOWN_SEC = 300  # 5 minutes cooldown after exit
DEFAULT_REENTRY_DISCOUNT_BUFFER = 1.0  # ₹1.00 below anchor price for re-entry

# Time Windows (IST)
MARKET_START_TIME = "09:15"
MARKET_END_TIME = "15:45"
TRADING_CUTOFF_TIME = "15:36"  # Continue trading & re-entries till 15:36 IST
ROLLOVER_TIME = "14:00"  # Monday hedge rollover check time
FORCE_CLOSE_TIME = "15:36"  # Square off / EOD cutoff time

# Fallback Settings
YAHOO_TICKER = "^NSEI"  # Nifty 50 Spot ticker
NSE_INDEX_NAME = "NIFTY 50"

# Strike Configuration
MAX_STRIKES_PER_BLOCK = 50  # Default maximum strikes allowed in a block


# Commodity Configuration
COMMODITY_LOCK_PORT = 9991  # Port to prevent duplicate engine processes
COMMODITY_MARKET_OPEN_H = 9  # MCX opens at 09:00
COMMODITY_MARKET_OPEN_M = 0
COMMODITY_SQUAREOFF_H = 23  # Intraday square-off at 23:00 IST
COMMODITY_SQUAREOFF_M = 0

# Master Nifty Anchor & Single-Directional Regime Configuration (V2.0)
DEFAULT_MASTER_NIFTY_ANCHOR = 0.0          # 0.0 = Not set (Unrestricted / Dual-sided)
DEFAULT_REGIME_BUFFER = 15.0               # Points buffer for hysteresis whipsaw guard (±15 pts)
DEFAULT_REGIME_MODE = "AUTO"               # AUTO = Governed by Master Anchor, MANUAL = Fixed, OFF = Dual-sided
DEFAULT_REGIME_AUTO_SNAPSHOT_915 = "ON"    # Auto-capture 9:15 AM spot as Anchor if not set



