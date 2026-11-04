# 🛠️ PRODUCT DEVELOPMENT SPECIFICATION: ZERODHA OPTION BUYING ENGINE (v6.1)
## Non-Monthly Weekly Reference Breakout System (Chhoti Bahan Edition)

> **Document Type:** Technical Architecture, Data Contracts & Algorithmic Specification  
> **Target Asset:** **NIFTY 50** (`NIFTY`, 65 Qty/Lot)  
> **Broker API:** Zerodha Kite Connect v3 (REST API)  
> **Database:** SQLite (`zerodha_buying.db` — WAL Mode Enabled)  
> **Date:** November 2026  

---

## 1. COMPONENT DIRECTORY & FILE REGISTRY

```
ZERODHA_OPTION_BUYING_PACKAGE/
├── BLUEPRINT_OPTION_BUYING_V6_1_NON_MONTHLY.md ← Master Strategic Blueprint
├── PRODUCT_DEVELOPMENT_SPEC_OPTION_BUYING_V6_1.md ← Technical Specification (THIS FILE)
├── README_CHHOTI_BAHAN.md                     ← Plain-Hindi Operator Guide
├── config.py                                  ← Lego 1: Constants, Timing Gates & Expiry Rules
├── db.py                                      ← Lego 2: Isolated SQLite Storage (`zerodha_buying.db`)
├── kite_auth.py                               ← Lego 3: Autonomous Headless TOTP Authenticator
├── market_data.py                             ← Lego 4: Non-Monthly Expiry Resolver & Modulo 100 Scanner
├── executor.py                                ← Lego 5: Long-Only Execution Shield & "NSLBUY" Tag
├── engine.py                                  ← Lego 6: 10:45 AM / 15:00 Timing State Machine
├── telegram_alerts.py                         ← Lego 7: Real-time Dispatcher for Trade Signals
├── dashboard.py                               ← Lego 8: Dedicated Standalone Streamlit Cockpit
├── START_OPTION_BUYING.bat                    ← Windows 1-Click Launcher
├── STOP_OPTION_BUYING.bat                     ← Windows 1-Click Stopper
└── test_system.py                             ← Pre-flight connection & data verification suite
```

---

## 2. REVISED MODULE CONTRACTS & USER-DEFINED ALGORITHMS

### 2.1 `config.py` — Revised System Constants
```python
UNDERLYING = "NIFTY"
LOT_SIZE = 65
DEFAULT_LOTS = 1                    # User Rule: Fixed 1 Lot to start
TARGET_PREMIUM_MIN = 160.0
TARGET_PREMIUM_MAX = 200.0
PROFIT_TARGET_PCT = 50.0            # +50% Rollover Target

# Timing Gates (IST)
GATE_ENTRY_H, GATE_ENTRY_M = 10, 45 # 10:45 AM IST (Gate 1)
GATE_REVIEW_H, GATE_REVIEW_M = 15, 0 # 03:00 PM IST (Gate 2)
MARKET_OPEN_H, MARKET_OPEN_M = 9, 16
MARKET_CLOSE_H, MARKET_CLOSE_M = 15, 30

ORDER_TAG = "NSLBUY"                # Strict Broker Order Tag
ORDER_PRODUCT = "NRML"
DATABASE_PATH = "zerodha_buying.db" # Strictly Isolated DB
```

---

### 2.2 `market_data.py` — Non-Monthly Expiry Resolver & Modulo 100 Strike Filter

#### Algorithm 1: Non-Monthly Expiry Resolver (`get_target_non_monthly_weekly_expiry`)
```python
def get_target_non_monthly_weekly_expiry(kite) -> date:
    """
    User Invariant:
      - STRICTLY AVOID MONTHLY EXPIRY DATES (Last Thursday of each month).
      - Target ~4 weeks forward (approx 21-28 days away).
      - If 4th week is the Monthly Expiry, cascade to 3RD WEEK (approx 14-21 days)
        for superior liquidity.
    """
    df = get_nfo_instruments(kite)
    df["expiry"] = pd.to_datetime(df["expiry"]).dt.date
    all_expiries = sorted(df["expiry"].unique())
    today = datetime.now(TZ_IST).date()

    # Identify monthly dates (last Thursday of each month)
    month_groups = {}
    for exp in all_expiries:
        if exp >= today:
            key = (exp.year, exp.month)
            month_groups.setdefault(key, []).append(exp)
    monthly_expiries = set(max(dates) for dates in month_groups.values())

    # Filter out all monthly expiries
    weekly_non_monthly = [e for e in all_expiries if e >= today and e not in monthly_expiries]

    if not weekly_non_monthly:
        raise ValueError("No non-monthly weekly expiries available!")

    # Target 3rd to 4th weekly non-monthly expiry
    # Index 2 = 3rd week forward (~14-21 days)
    # Index 3 = 4th week forward (~21-28 days)
    if len(weekly_non_monthly) >= 3:
        target = weekly_non_monthly[2] # 3rd week has optimal liquidity
    else:
        target = weekly_non_monthly[-1]

    assert target not in monthly_expiries, "CRITICAL: Target expiry must NEVER be a monthly expiry!"
    return target
```

#### Algorithm 2: Modulo 100 Strike Filter (`find_best_100_modulo_strike`)
```python
def find_best_100_modulo_strike(kite, leg_type: str, target_expiry: date) -> Optional[dict]:
    """
    User Invariant:
      - Strikes MUST be multiple of 100 only (strike % 100 == 0).
      - Eliminates illiquid 50-ending strikes in far-dated contracts.
      - Finds strike with LTP in [160.0, 200.0] closest to 160.0.
    """
    df = get_nfo_instruments(kite)
    df["expiry"] = pd.to_datetime(df["expiry"]).dt.date

    # Filter for target expiry, leg type, AND modulo 100
    subset = df[
        (df["expiry"] == target_expiry) &
        (df["instrument_type"] == leg_type) &
        (df["strike"] % 100 == 0)
    ].copy()

    if subset.empty:
        return None

    # Fetch live quotes
    symbols = [f"NFO:{s}" for s in subset["tradingsymbol"].tolist()]
    quotes = {}
    for i in range(0, len(symbols), 50):
        batch = symbols[i:i+50]
        q = kite.quote(batch)
        quotes.update(q)

    candidates = []
    for _, row in subset.iterrows():
        sym_key = f"NFO:{row['tradingsymbol']}"
        ltp = float(quotes.get(sym_key, {}).get("last_price", 0.0))
        if TARGET_PREMIUM_MIN <= ltp <= TARGET_PREMIUM_MAX:
            candidates.append({
                "tradingsymbol": row["tradingsymbol"],
                "instrument_token": int(row["instrument_token"]),
                "strike": float(row["strike"]),
                "ltp": ltp,
                "expiry": str(target_expiry),
                "leg": leg_type
            })

    if not candidates:
        # Fallback: Closest to 160 on modulo 100
        pool = []
        for _, row in subset.iterrows():
            sym_key = f"NFO:{row['tradingsymbol']}"
            ltp = float(quotes.get(sym_key, {}).get("last_price", 0.0))
            if ltp > 100:
                pool.append({
                    "tradingsymbol": row["tradingsymbol"],
                    "instrument_token": int(row["instrument_token"]),
                    "strike": float(row["strike"]),
                    "ltp": ltp,
                    "expiry": str(target_expiry),
                    "leg": leg_type
                })
        if pool:
            pool.sort(key=lambda x: abs(x["ltp"] - 160.0))
            return pool[0]
        return None

    # Preferred: Closest to 160.0
    candidates.sort(key=lambda x: (x["ltp"] - 160.0))
    return candidates[0]
```

---

### 2.3 `executor.py` — Sister Coexistence Long-Only Safety Shield
```python
def get_open_buying_position(kite, leg_name: str) -> Optional[dict]:
    """
    CRITICAL COEXISTENCE INVARIANT:
      - Reads broker positions via kite.positions()['net'].
      - STRICTLY filters for POSITIVE QUANTITY (qty > 0).
      - Checks matching instrument token stored in zerodha_buying.db.
      - ANY SHORT POSITION (qty < 0) FROM OPTION SELLING IS 100% INVISIBLE
        AND CAN NEVER BE TOUCHED OR SQUARED OFF BY THIS ENGINE.
    """
    token_str = db.get(f"{leg_name.lower()}_active_token", "0")
    if not token_str or token_str == "0":
        return None
    target_token = int(token_str)

    positions = kite.positions().get("net", [])
    for p in positions:
        # Safety Gate: Qty must be POSITIVE (Long Buy)
        if p.get("instrument_token") == target_token and p.get("quantity", 0) > 0:
            return p
    return None
```

---

## 3. TIMING STATE MACHINE SPECIFICATION (`engine.py`)

| Time (IST) | Trigger Event | Engine Action | Safety Invariant |
|---|---|---|---|
| **09:16 AM** | Startup Sync | Loads cached instruments; verifies broker session; syncs active long positions. | Zero orders placed. |
| **09:30 AM** | Discovery Phase | Price discovery equilibrium establishing; engine is completely idle. | No premature entries. |
| **10:45 AM** | **Decision Gate 1** | Scans 3rd-week non-monthly chain for ~₹160 strikes (modulo 100). Checks $LTP_{1045} > Ref_{930}$. If true $\rightarrow$ **BUY 1 Lot**. | If false, stays dormant. |
| **10:45–15:00**| **5-Min Watchdog** | Runs at :00, :05, :10... Evaluates unrealized P&L. If $P\&L \ge +50\% \implies$ **SELL Active $\rightarrow$ Sleep 30s $\rightarrow$ ROLLOVER to fresh ~₹160 strike**. | Compounding asymmetry. |
| **03:00 PM** | **Decision Gate 2** | Reviews held positions against $Ref_{930}$. If $LTP > Ref_{930} \implies$ **HOLD overnight**. If $LTP \le Ref_{930} \implies$ **EXIT immediately**. | Cuts failing trends before overnight gap risk. |

---

## 4. UI ARCHITECTURE: DEDICATED INDEPENDENT DASHBOARD

- **Dedicated Port / Process:** Runs on its own standalone port (e.g. `Port 9012` on VPS or standalone desktop launcher) with its own SQLite database `zerodha_buying.db`.
- **Zero Cross-Contamination:** Option Selling (`Port 9007`) and Option Buying are completely physically separated.
- **HUD Components:**
  - Active Call Leg card with live LTP, Entry, PnL %, and +50% Rollover Progress Bar.
  - Active Put Leg card with live LTP, Entry, PnL %, and +50% Rollover Progress Bar.
  - Emergency 1-Click Square-Off buttons (strictly targeting the buying token).
  - Daily audit trade table.

