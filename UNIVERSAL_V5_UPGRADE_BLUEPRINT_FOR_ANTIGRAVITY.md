# UNIVERSAL V5.0 "OLD & GOLD" UPGRADE BLUEPRINT FOR ANTIGRAVITY IDE
**Target Workspace:** Any Bharat Options Engine (Zerodha Kite, Kotak Neo, HDFC Sky, Angel One, Finvasia)  
**Upgrade Vector:** Direct jump from **V3.0 / V3.1 / V4.0** $\longrightarrow$ **V5.0 "Old & Gold"**  
**Author:** Bharat Systems Quantitative Trading Architecture  
**Release Date:** September 2026  

---

## ⚡ HOW TO USE THIS FILE IN ANTIGRAVITY IDE (30-SECOND GUIDE)

If you are upgrading your sister's laptop or your own Zerodha / Kotak setup:
1. Open **Antigravity IDE** on the target laptop.
2. Open your trading system workspace (e.g. `ZERODHA-OPTIONSELLING` or `KOTAK-OPTIONSELLING`).
3. Copy the text in the prompt box below and send it to Antigravity:

```text
Please read UNIVERSAL_V5_UPGRADE_BLUEPRINT_FOR_ANTIGRAVITY.md in detail. 
You are our lead quantitative architect. Upgrade our current codebase directly 
from its current version to the V5.0 "Old & Gold" Architecture with 100% precision:
1. Create/migrate DB columns (reentry_enabled, trade_state, sl_pct, sl_price, anchor_decision_time, recommended_lots, orphan_hedge_policy).
2. Build the Unified Single-Window Console ("Ek Hi Jagah Saari Chijen") for side-by-side CE & PE configuration with 1-click selective deployment.
3. Decouple M1 Master Anchor from intraday trade exits (intraday anchor crossings do NOT close trades; trades breathe for theta decay).
4. Implement the 3:00 PM Continuation Decision (15:00 IST) to continue the favorable side and close opposing positions.
5. Implement the individual trade Stop-Loss engine (10%, 20%, 25%, Custom) separate from M1.
6. Enforce the Orphan Hedge Invariant (never auto-liquidate long hedges on short SL exits; retain manual profit lock).
7. Preserve 5-min cooldown re-entry logic.
Verify all changes with comprehensive unit tests before finishing.
```

---

## 🏛️ PART 1: THE CORE PHILOSOPHY ("OLD & GOLD")

> **"M1 is the master of the day's direction. Stop-Loss is the master of individual trade risk. Re-entry is controlled by market condition. Orphan hedges remain untouched."**

### 1. The Core Golden Invariants
1. **M1 Master Anchor is Fixed for the Day:**
   - When M1 is deployed in the morning, its Master Anchor Price is recorded once.
   - It is **never recalculated repeatedly** during the day.
2. **Intraday Noise Does Not Close Trades:**
   - Mid-day spot crossings over/under the anchor do **NOT** exit positions.
   - Short positions are held peacefully from 09:15 to 14:59 IST to harvest theta decay.
3. **The 3:00 PM Continuation Decision (15:00 IST):**
   - At 15:00 IST, the engine evaluates Spot vs M1 Master Anchor:
     - $\text{Spot} \ge \text{Anchor}$ $\implies$ **Continue Put Sell** (`trade_state = "CONTINUED"`), close Call Sell + active hedges.
     - $\text{Spot} < \text{Anchor}$ $\implies$ **Continue Call Sell** (`trade_state = "CONTINUED"`), close Put Sell + active hedges.
   - Opposing positions are liquidated; favored positions are held overnight.
4. **Individual Trade Stop-Loss Engine (Decoupled from M1):**
   - Each sold option has its own independent risk trigger:
     $$\text{SL Trigger Price} = P_{\text{entry}} \times \left(1 + \frac{\text{SL}_{\%}}{100}\right)$$
   - Configurable: `10%`, `20%`, `25%`, or `Custom %`.
   - Checks every 5-minute decision loop. When breached, **only that leg is covered**. It does **not** close M1 or other legs.
5. **The Orphan Hedge Invariant (Capital Shield):**
   - When a short leg is stopped out, the associated long hedge is **NEVER auto-liquidated**.
   - It stays active as an **Orphan Hedge** to protect against black-swan runaway moves.
   - The dashboard provides a 1-click **Manual Profit Lock** button to bank hedge gains when desired.
6. **Re-entry After Stop-Loss:**
   - A Stop-Loss exit does **not** permanently disable the side.
   - After a 5-minute cooldown guard, if the market remains favorable and premium cools down, the engine can re-enter.
7. **Unified Single-Window Console ("Ek Hi Jagah Saari Chijen"):**
   - Eliminates operator fatigue. Both Call Wing and Put Wing are configured on **one single screen**.
   - 1-Click Deploy evaluates Spot vs Anchor at the instant of execution:
     - Bullish ($\text{Spot} \ge \text{Anchor}$): Executes Put Sell LIVE, stores Call Sell in `PENDING`.
     - Bearish ($\text{Spot} < \text{Anchor}$): Executes Call Sell LIVE, stores Put Sell in `PENDING`.

---

## 💾 PART 2: DATABASE MIGRATIONS (SQLITE DDL)

In your `db.py` (or equivalent database module), add automated column migrations inside `init_db()`:

```python
def init_db():
    conn = _conn()
    c = conn.cursor()

    # 1. Ensure core tables exist (blocks, strikes, legs, trades, config)
    # ...

    # 2. V5.0 Migration for 'strikes' table
    c.execute("PRAGMA table_info(strikes)")
    existing_strike_cols = [col[1] for col in c.fetchall()]

    if "sl_pct" not in existing_strike_cols:
        c.execute("ALTER TABLE strikes ADD COLUMN sl_pct REAL DEFAULT 25.0")
    if "sl_price" not in existing_strike_cols:
        c.execute("ALTER TABLE strikes ADD COLUMN sl_price REAL DEFAULT 0.0")
    if "reentry_enabled" not in existing_strike_cols:
        c.execute("ALTER TABLE strikes ADD COLUMN reentry_enabled INTEGER DEFAULT 1")
    if "trade_state" not in existing_strike_cols:
        c.execute("ALTER TABLE strikes ADD COLUMN trade_state TEXT DEFAULT 'OPEN'")

    # 3. V5.0 Migration for 'blocks' table
    c.execute("PRAGMA table_info(blocks)")
    existing_block_cols = [col[1] for col in c.fetchall()]

    if "anchor_decision_time" not in existing_block_cols:
        c.execute("ALTER TABLE blocks ADD COLUMN anchor_decision_time TEXT DEFAULT '15:00'")
    if "recommended_lots" not in existing_block_cols:
        c.execute("ALTER TABLE blocks ADD COLUMN recommended_lots INTEGER DEFAULT 1")
    if "orphan_hedge_policy" not in existing_block_cols:
        c.execute("ALTER TABLE blocks ADD COLUMN orphan_hedge_policy TEXT DEFAULT 'PRESERVE'")

    conn.commit()
    conn.close()
```

### Granular Trade States:
* `OPEN`: Active live position.
* `PENDING`: Armored on broker sidelines; ready to execute on signal.
* `SL_HIT`: Stopped out on premium breach; entering cooldown.
* `REENTRY_ELIGIBLE`: Cooldown elapsed; eligible to re-enter.
* `CONTINUED`: Selected by 3:00 PM Master Anchor decision to hold overnight.
* `CLOSED`: Gracefully closed / squared off.
* `ORPHAN`: Long hedge whose short leg has exited.

---

## 🔌 PART 3: UNIVERSAL BROKER EXECUTOR ADAPTER

Whether your system uses **Zerodha KiteConnect**, **Kotak Neo**, **HDFC Sky**, or **Paper/Simulated Trading**, standardise the executor interface as follows:

```python
class UniversalBrokerExecutor:
    """
    Standard interface across Zerodha, Kotak Neo, and HDFC.
    """
    def get_spot_price(self, symbol="NIFTY 50") -> float:
        """Returns live Nifty 50 Index LTP."""
        pass

    def get_option_ltp(self, trading_symbol: str) -> float:
        """Returns live option premium LTP."""
        pass

    def place_buy_hedge(self, trading_symbol: str, qty: int) -> dict:
        """
        Places Market / Limit BUY order for hedge.
        MUST execute BEFORE Sell leg (Hedge-First rule).
        """
        pass

    def place_sell_short(self, trading_symbol: str, qty: int) -> dict:
        """Places Market / Limit SELL order for short leg."""
        pass

    def cover_short(self, trading_symbol: str, qty: int) -> dict:
        """Buys back short leg upon SL hit or square-off."""
        pass

    def exit_hedge(self, trading_symbol: str, qty: int) -> dict:
        """Sells hedge leg upon explicit closure or manual profit lock."""
        pass
```

### Broker-Specific SDK Mappings:
* **Zerodha Kite (`kiteconnect`):**
  - Place Order: `kite.place_order(variety=kite.VARIETY_REGULAR, exchange=kite.EXCHANGE_NFO, tradingsymbol=sym, transaction_type=kite.TRANSACTION_TYPE_BUY/SELL, quantity=qty, order_type=kite.ORDER_TYPE_MARKET, product=kite.PRODUCT_NRML)`
  - Quotes: `kite.ltp(["NFO:" + sym])`
* **Kotak Neo (`neo_api_client`):**
  - Place Order: `client.order_report(exchange_segment="nse_fo", product="NRML", order_type="MKT", ...)`
* **HDFC Sky / Securities:**
  - Place Order: Standard REST `/order/regular` endpoint with MPIN/TOTP token session.

---

## ⚙️ PART 4: BUSINESS LOGIC SPECIFICATION

### Module A: Unified Console Deployment (`block_manager.py`)
```python
def deploy_unified_master_unit(
    expiry_date: str,
    anchor_unit_name: str = "M1",
    master_anchor_price: float = 0.0,
    regime_buffer: float = 15.0,
    recommended_lots: int = 1,
    # Call wing
    ce_sell_strike: int = 0,
    ce_sell_anchor: float = 0.0,
    ce_hedge_strike: int = 0,
    ce_hedge_anchor: float = 0.0,
    ce_sl_pct: float = 25.0,
    ce_reentry_enabled: int = 1,
    # Put wing
    pe_sell_strike: int = 0,
    pe_sell_anchor: float = 0.0,
    pe_hedge_strike: int = 0,
    pe_hedge_anchor: float = 0.0,
    pe_sl_pct: float = 25.0,
    pe_reentry_enabled: int = 1,
) -> dict:
    # 1. Create Block with Master Anchor
    # 2. Attach Call Wing strikes (trade_state = "PENDING")
    # 3. Attach Put Wing strikes (trade_state = "PENDING")
    # 4. Check Live Spot vs master_anchor_price:
    #    If Spot >= Anchor: Execute Put Wing LIVE (Buy Hedge -> Sell PE). Leave CE in PENDING.
    #    If Spot < Anchor:  Execute Call Wing LIVE (Buy Hedge -> Sell CE). Leave PE in PENDING.
```

### Module B: The 3:00 PM Continuation Engine
```python
def execute_3pm_master_anchor_decision() -> dict:
    """
    Triggered once daily at 15:00 IST:
    1. Fetches live NIFTY Spot.
    2. For each active unit:
       - Compares Spot vs Unit Master Anchor.
       - If Bullish (Spot >= Anchor):
           * Put Sell marked CONTINUED (held overnight).
           * Call Sell closed on broker + marked CLOSED.
           * Active Call Hedge closed on broker + marked CLOSED.
           * Orphan Hedges preserved untouched.
       - If Bearish (Spot < Anchor):
           * Call Sell marked CONTINUED (held overnight).
           * Put Sell closed on broker + marked CLOSED.
           * Active Put Hedge closed on broker + marked CLOSED.
           * Orphan Hedges preserved untouched.
       - Dispatches Telegram alert with decision and PnL.
    """
```

### Module C: Decoupled Stop-Loss & Orphan Hedge Protection (`pnl_engine.py`)
```python
# In P&L cycle check:
if ltp >= exit_threshold:
    # 1. Close Short leg only
    broker.cover_short(s['trading_symbol'], qty)
    db.update_strike_trade_state(strike_id, "SL_HIT")
    
    # 2. INVARIANT: DO NOT auto-liquidate hedge!
    # Long hedge remains open as orphan hedge.
    should_close_hedge = False
    
    # 3. Alert Telegram
    tg.send(f"🚨 AUTO-EXIT STOP LOSS TRIGGERED: Strike {s['strike_price']} {s['option_type']} covered. Hedge preserved.")
```

---

## 🎨 PART 5: FRONTEND CONSOLE (`app.py` / Streamlit)

1. **Top Banner:** Display `MASTER NIFTY CONTROLLER (V5.0 "OLD & GOLD" ARCHITECTURE)` with live Spot and Anchor levels.
2. **Landing Tab (Tab 0):** Make `🚀 Unified V5 Console` the very first tab.
3. **Inputs on Unified Tab:**
   - Top: Expiry Date, Master Anchor Price, Buffer, Lots.
   - Left Column: Call Sell Wing (CE Strike, Hedge Strike, SL % Dropdown [10%, 20%, 25%, Custom], Re-entry checkbox).
   - Right Column: Put Sell Wing (PE Strike, Hedge Strike, SL % Dropdown [10%, 20%, 25%, Custom], Re-entry checkbox).
   - Dynamic banner showing which side will fire based on live Spot vs Anchor.
   - Action: Single `🚀 DEPLOY UNIFIED MASTER UNIT` button.
4. **Active Positions Table:** Add a **State** column displaying `OPEN`, `PENDING`, `SL_HIT`, `CONTINUED`, or `ORPHAN`.
5. **Retain Orphan Profit Lock Button:** 1-Click button on open hedge rows allowing the trader to manually bank profits at will.

---

## 🧪 PART 6: VERIFICATION SUITE CHECKLIST

Before deploying live on your sister's or your own laptop, verify that the following 6 tests pass:
1. `test_01_schema_migrations_v5`: Confirms DB columns exist.
2. `test_02_unified_console_bullish_selective_execution`: Spot $\ge$ Anchor $\rightarrow$ PE opens live, CE remains PENDING.
3. `test_03_unified_console_bearish_selective_execution`: Spot $<$ Anchor $\rightarrow$ CE opens live, PE remains PENDING.
4. `test_04_intraday_anchor_crossing_does_not_close_trades`: Mid-day anchor cross does not exit short legs.
5. `test_05_3pm_master_anchor_decision_continuation`: 15:00 IST decision continues favorable side and squares counter side.
6. `test_06_orphan_hedge_preservation_on_sl_exit`: Short SL hit preserves long hedge untouched.

**All Bharat Systems engines conforming to this blueprint achieve 100% interoperability and institutional risk discipline.**
