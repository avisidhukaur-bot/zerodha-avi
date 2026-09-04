# Zerodha Option Selling App — Permanent Memory
_Last updated: 17-Jun-2026_

## 🖥️ VPN & IP Settings
- **Whitelisted IP (PERMANENT — NEVER CHANGE)**: `5.75.250.104`
- **VPS Real IP**: `5.75.250.104`
- **IP Guard**: Engine checks public IP before each cycle. If not `5.75.250.104`, trading pauses + Telegram & ntfy alert.

## 🧱 Lego System Convention
- **lego0_diagnose.py**: VPS diagnostics (logs, status, connections, port checks).
- **lego1_deploy.py**: Laptop-to-VPS SSH deployment script.

## ⚙️ Ports and Services
- **Dashboard Port**: `9007` (PERMANENT — reserved strictly for Zerodha OS. Do not change!)
- **Dashboard URL**: http://5.75.250.104:9007
- **Systemd Services**: `zerodha_engine.service`, `zerodha_dashboard.service`
- **VPS Remote Path**: `/root/BHARAT-SYSTEMS/ZERODHA-OS`
- **⚠️ CRITICAL PORT RULE (DO NOT TOUCH PORT 9004):** Port `9004` is strictly reserved for the operator's stable HDFC option selling system (`hdfc_dashboard.service` and `hdfc_engine.service` located in `/root/BHARAT-SYSTEMS/HDFC-OPTIONSELLING`). Never stop, disable, modify, or host anything on port 9004, and never touch the HDFC system running outside the current Zerodha OS directory!


## 🔑 Broker — ZERODHA KITE CONNECT ONLY
- **Developer Portal**: https://developer.kite.trade/
- **Docs**: https://kite.trade/docs/connect/v3/
- **API Base URL**: `https://api.kite.trade`
- **Active Executor File**: `kite_executor.py` (imported and used directly in core modules)
- **Credentials**: `KITE_API_KEY`, `KITE_API_SECRET`, `KITE_CLIENT_CODE`, `KITE_PASSWORD`, `KITE_TOTP_KEY`, and `NTFY_TOPIC`.

### Auth Flow
1. **Automated Headless Login (Morning)**: A requests-based scraper submits Client Code + Password to `kite.zerodha.com/api/login`, retrieves `request_id`, generates TOTP code using `pyotp` and submits it to `/api/twofa` to obtain a session. It then hits `kite.trade/connect/login` to get the redirect `request_token`, which it exchanges for an `access_token`.
2. **Dashboard Redirect Login**: Fallback login button redirects to `kite.login_url()`. Once logged in, the user is redirected back to the Streamlit app which reads the `request_token` from URL parameters and exchanges it.

### Place Order — Request Parameters (Kite Connect SDK)
```python
kite.place_order(
    variety=kite.VARIETY_REGULAR,
    exchange=kite.EXCHANGE_NFO,
    tradingsymbol=trading_symbol,
    transaction_type=transaction_type,  # kite.TRANSACTION_TYPE_BUY / TRANSACTION_TYPE_SELL
    quantity=qty,
    product=kite.PRODUCT_NRML,  # PRODUCT_NRML for multi-day option selling
    order_type=order_type,
    price=price
)
```
**CRITICAL NOTES:**
- **Product type**: F&O overnight positions must be placed using `PRODUCT_NRML` in Zerodha.
- **Market Protection**: To prevent slippage, MARKET orders are converted to LIMIT orders in `kite_executor.py` using live LTP quotes with a maximum 10% buffer.

### Local Instruments Cache
- Instruments are cached daily from `https://api.kite.trade/instruments` to `zerodha_instruments.csv` inside the app directory.
- Expiries and options details are matched locally using pandas filtering on `name == 'NIFTY'` and `exchange == 'NFO'` to resolve contracts quickly.

## 📊 Default Trading Parameters
- **Index**: NIFTY ONLY (HARD RULE — never BANKNIFTY or others)
- **Exchange**: NFO (Zerodha uses NFO for derivatives)
- **Product**: NRML (multi-day holding)
- **Lot Size**: 65 (as of Jun 2026)
- **P&L Refresh Interval**: 30 seconds (1800 seconds fallback)

## 📱 Notifications (Telegram + ntfy)
- Dual alert channel delivery: Telegram alerts duplicate to `https://ntfy.sh/<NTFY_TOPIC>` if configured, serving as a reliable fallback for operators.

## 🔄 Daily Auto-Reset and Re-entry Logic (5-Minute Rule)
- **Auto-Entry Rule (5-Minute Delay Below Anchor)**: During market hours (09:15 to 15:15 IST), the engine monitors `PENDING` strikes. When an option price drops below its `anchor_price` (LTP < anchor_price), the engine starts a **5-minute countdown (300 seconds)**. It executes entry only after the price remains continuously below anchor for 5 minutes (morning entries trigger at 09:20 AM after market opening at 09:15 AM).
- **Auto Re-entry Rule (5-Minute Delay Below Anchor)**: When a closed strike price drops below its anchor price (LTP < anchor_price), the engine starts a **5-minute countdown (300 seconds)**. It automatically re-enters the sell leg using the retained hedge after 5 continuous minutes below anchor.
- **Stop Loss Rule**: Exit triggers immediately on tick cycle (every 30 seconds) if `LTP >= Anchor Price + Buffer Tolerance (Default ₹2.00)`.
- **Max Same-Day Re-entries Rule**: Maximum **5 re-entries per strike per trading day**.
- **Hedge Retention Rule (PERMANENT)**: Hedges are **NEVER automatically exited** when a SELL leg hits Stop-Loss (`auto_close_eod_hedge: OFF`). The hedge stays permanently active to retain margin benefit and support safe re-entry.
- **Resolved Symbol Lookup**: The engine uses the exact trading symbol resolved from the cache master instead of hand-constructed symbols for live LTP lookup, guaranteeing correct pricing queries.

## 🛡️ Strict Macro Regime Execution Guard (M1 / M2 / M3 Governor)
- **Hard Single-Directional Rule on ALL Execution (Manual & Automated)**:
  - **BEARISH Regime (Live Spot < Master Anchor)**:
    - **CALL (CE) Selling**: Aligned with Bearish trend $\rightarrow$ **Executes on the spot**.
    - **PUT (PE) Selling**: Against trend $\rightarrow$ **STRICTLY MUTED & HELD IN PENDING (Armed)**. Even if the operator presses the manual execute button, PE trades will NOT place orders on the broker. They remain paused/pending until a valid Bullish regime signal occurs.
  - **BULLISH Regime (Live Spot >= Master Anchor)**:
    - **PUT (PE) Selling**: Aligned with Bullish trend $\rightarrow$ **Executes on the spot**.
    - **CALL (CE) Selling**: Against trend $\rightarrow$ **STRICTLY MUTED & HELD IN PENDING (Armed)**. CE trades will NOT place orders on the broker. They remain paused/pending until a valid Bearish regime signal occurs.
  - **Kill & Flip Transition**: When Spot crosses the Master Anchor level (with $\pm 15$ pt buffer), the opposing side is immediately market-covered and the newly permitted side in PENDING is deployed.
  - **Anti-Whipsaw**: 5-minute cooldown after SL exit + 5-minute continuous hold below anchor before any auto entry/re-entry.




