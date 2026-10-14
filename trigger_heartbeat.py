import sys
import os
sys.path.append('/root/BHARAT-SYSTEMS/ZERODHA-OS')
from main import TradingEngine

if __name__ == '__main__':
    engine = TradingEngine()
    engine.open_strikes = engine.get_open_strikes()
    engine.update_pnl()
    engine.send_heartbeat()
    print("Telegram Heartbeat Sent with open strikes:", len(engine.open_strikes))
