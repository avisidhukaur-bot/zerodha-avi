# Zerodha Option Selling App — Permanent Memory (V5.0 "Old & Gold" Architecture)
_Last updated: 08-Sep-2026_

## 🖥️ VPN & IP Settings
- **Whitelisted IP (PERMANENT — NEVER CHANGE)**: `5.75.250.104`
- **VPS Real IP**: `5.75.250.104`
- **IP Guard**: Engine checks public IP before each cycle. If not `5.75.250.104`, trading pauses + Telegram & ntfy alert.

## 🧱 Lego System Convention
- **lego0_diagnose.py**: VPS diagnostics (logs, status, connections, port checks).
- **lego1_deploy.py**: Laptop-to-VPS SSH deployment script.
- **lego2_rollover.py**: Monthly contract rollover helper.

## ⚙️ Ports and Services
- **Dashboard Port**: `9007` (PERMANENT — reserved strictly for Zerodha OS. Do not change!)
- **Dashboard URL**: http://5.75.250.104:9007
- **Systemd Services**: `zerodha_engine.service`, `zerodha_dashboard.service`, `zerodha_commodity.service`
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
- **Hedge-First Rule**: The BUY hedge leg is ALWAYS placed and confirmed BEFORE the SELL leg to ensure margin relief and capital safety.
- **Market Protection**: To prevent slippage, MARKET orders are converted to LIMIT orders in `kite_executor.py` using live LTP quotes with a maximum 10% buffer.

### Local Instruments Cache
- Instruments are cached daily from `https://api.kite.trade/instruments` to `zerodha_instruments.csv` inside the app directory.
- Expiries and options details are matched locally using pandas filtering on `name == 'NIFTY'` and `exchange == 'NFO'` to resolve contracts quickly.

## 📊 Default Trading Parameters
- **Index**: NIFTY ONLY (HARD RULE — never BANKNIFTY or others)
- **Exchange**: NFO (Zerodha uses NFO for derivatives)
- **Product**: NRML (multi-day holding)
- **Lot Size**: 65 (as of Jun 2026)
- **P&L Refresh Interval**: 30 seconds

## 📱 Notifications (Telegram + ntfy)
- Dual alert channel delivery: Telegram alerts duplicate to `https://ntfy.sh/<NTFY_TOPIC>` if configured, serving as a reliable fallback for operators.

---

## 🏛️ V5.0 "OLD & GOLD" ARCHITECTURE & GOLDEN INVARIANTS

### 1. Isolated Unit Master Anchors (M1, M2, M3...):
- **NO Single Global Master Anchor**: There is no universal anchor for the whole application.
- **Each Unit is Independent**: `M1` has its own Master Anchor Price, `M2` has its own Master Anchor Price. Every unit operates as an autonomous pod.
- **Anchor Fixed for the Day**: Once an M-unit is deployed, its Master Anchor price is fixed and not dynamically recalculated during the day.

### 2. Unified Single-Window Deployment ("Ek Hi Jagah Saari Chijen"):
- Trader configures Expiry, Unit Master Anchor, Lots, Call Wing (CE Sell + Hedge + 25% SL), and Put Wing (PE Sell + Hedge + 25% SL) on a single screen.
- **Selective 1-Click Execution**:
  - **Bullish (Live Spot >= Unit Master Anchor)**: Executes **PUT Wing LIVE** on Zerodha (Buy Hedge -> Sell PE leg). The **CALL Wing** is placed into `PENDING` (armed on sidelines).
  - **Bearish (Live Spot < Unit Master Anchor)**: Executes **CALL Wing LIVE** on Zerodha (Buy Hedge -> Sell CE leg). The **PUT Wing** is placed into `PENDING` (armed on sidelines).

### 3. Decoupled Stop-Loss Engine (Configurable in ₹ Price and %):
- Each sold option has its own independent risk trigger:
  $$\text{SL Trigger Price} = P_{\text{entry}} \times \left(1 + \frac{\text{SL}_{\%}}{100}\right)$$
- **Dual Direct Inputs**: Operator can directly input either the exact **Stop Loss Price (₹)** (e.g. ₹61.00 when Anchor is ₹60.00) OR select a **Stop Loss %** (10%, 20%, 25%, 30%, Custom). Both variables are available and can be edited anytime.
- **Default SL**: **25%** away from entry ($P_{\text{entry}} \times 1.25$), providing buffer against market noise.
- When SL is hit, **only the short leg is covered**.

### 4. The Orphan Hedge Invariant (Capital Shield):
- When a short leg hits Stop-Loss, the linked long hedge is **NEVER auto-liquidated**.
- It remains active as an **Orphan Hedge** (`trade_state = "ORPHAN"`) to protect against runaway market moves.
- Operator can lock in profits at any time using the 1-click **Manual Profit Lock** button on the dashboard.

### 5. Intraday Decoupling (No Kill & Flip Whipsaws):
- Intraday Spot crossings over/under the Master Anchor do **NOT** exit positions.
- Short positions are held peacefully from 09:15 to 14:59 IST to harvest theta decay.

### 6. The 3:00 PM Continuation Decision (15:00 IST):
- Evaluated once daily at 15:00 IST:
  - Compares Live Spot vs each Unit's Master Anchor:
    - **Bullish (Spot >= Anchor)**: **PUT Sell is marked `CONTINUED` and carried forward overnight (Positional Trade)**. Opposing Call Sell + paired hedge are squared off.
    - **Bearish (Spot < Anchor)**: **CALL Sell is marked `CONTINUED` and carried forward overnight (Positional Trade)**. Opposing Put Sell + paired hedge are squared off.
  - **Positional trades are NEVER closed at EOD** — they carry forward overnight as designed.
  - Stranded orphan hedges are cleaned up at EOD or preserved as per policy.

### 7. 5-Minute Auto Re-Entry Guard:
- When an SL-hit strike cools down below its Anchor price (LTP < Anchor), a 5-minute countdown starts.
- If it stays continuously below anchor for 5 minutes, auto re-entry executes using the retained hedge.
