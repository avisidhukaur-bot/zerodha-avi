# Zerodha Option Selling App — Permanent Memory
_Last updated: 17-Jun-2026_

## 🖥️ VPN & IP Settings
- **Whitelisted IP (PERMANENT — NEVER CHANGE)**: `46.224.133.16` (VPN IP)
- **VPS Real IP**: `157.49.182.222` (do NOT use as trading IP)
- **IP Guard**: Engine checks public IP before each cycle. If not `46.224.133.16`, trading pauses + Telegram & ntfy alert.

## 🧱 Lego System Convention
- **lego0_diagnose.py**: VPS diagnostics (logs, status, connections, port checks).
- **lego1_deploy.py**: Laptop-to-VPS SSH deployment script.

## ⚙️ Ports and Services
- **Dashboard Port**: `9007` (PERMANENT — reserved strictly for Zerodha OS. Do not change!)
- **Dashboard URL**: http://46.224.133.16:9007
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

## 🔄 Daily Auto-Reset and Re-entry Logic (Option A)
- **Daily Reset Check**: At 09:00 AM IST, the background engine scans all ACTIVE blocks. Any strike that was closed on a previous day (SELL leg is CLOSED) is automatically reset to `PENDING` status along with its linked HEDGE_BUY strike.
- **Auto-Entry Check**: During market hours (09:15 to 15:15 IST), the engine monitors `PENDING` SELL strikes. If the Nifty option price drops below its manual `anchor_price` (LTP < anchor_price), the engine automatically executes it (buys the hedge first, then sells the option).
- **Same-Day Re-entry**: If a strike is closed TODAY (e.g. stopped out during the day), the engine allows it to re-enter today if the Nifty option price drops below `anchor_price`, provided the hedge strike is still OPEN.
- **Resolved Symbol Lookup**: The engine uses the exact trading symbol resolved from the cache master instead of hand-constructed symbols for live LTP lookup, guaranteeing correct pricing queries.


