# ⚡ BHARAT OPTION BUYING ENGINE (NSL v6.1 — ZERODHA EDITION)
## Master Strategic Blueprint: Non-Monthly Weekly Reference Breakout System

> **System Name:** BHARAT OPTION BUYING ENGINE (NSL v6.1 — Non-Monthly Weekly Edition)  
> **Target Broker:** Zerodha Kite Connect API v3  
> **Underlying Asset:** **NIFTY 50 ONLY** (`NIFTY`, Standard Lot Size: `65`)  
> **Target Desk:** Chhoti Bahan / Sister's Trading Desk  
> **Architectural Guard:** 100% Autonomous, Isolated Database, Long-Only Protected, Zero Clash with Option Selling  
> **Date Formulated:** 04-Nov-2026  

---

## 🎯 1. STRATEGIC PURPOSE & USER INVARIANTS

Traditional option buying fails primarily due to:
1. **Theta Decay Trap:** Buying 1–3 day weekly expiries where time decay accelerates exponentially ($-\frac{\partial V}{\partial t} \propto \frac{1}{\sqrt{T}}$).
2. **Intraday Indicator Churn:** Flipping on 1-min or 5-min supertrends/EMAs, generating massive slippage and transaction taxes.
3. **Collision with Option Selling:** In accounts running short option strangles/spreads, concurrent buying creates orderbook confusion, margin cross-deduction, and position desync.

### The User's Non-Monthly Solution (NSL v6.1):
To protect the existing Option Selling setup (**M1, M2, M3** and **OS Systems**) while harvesting explosive directional momentum, the system enforces **5 Non-Negotiable Invariants**:

```
┌────────────────────────────────────────────────────────────────────────┐
│                   THE 5 GOLDEN INVARIANTS (v6.1)                       │
├────────────────────────────────────────────────────────────────────────┤
│ 1. STRICTLY NON-MONTHLY DATES : Never trade monthly expiry (Last Thu) │
│ 2. 3RD/4TH WEEK DISTANCE      : Target ~4 weeks; shift to 3rd if 4th  │
│                                 is monthly (optimal liquidity)         │
│ 3. MODULO 100 STRIKE FILTER   : strike % 100 == 0 (no 50-strikes)     │
│ 4. 1 LOT FIXED SIZING         : Strictly 1 Lot (65 Qty) to start       │
│ 5. ISOLATED DEDICATED PAGE    : Standalone UI & DB; zero clutter       │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 📅 2. EXPIRY SELECTION CALCULUS (THE NON-MONTHLY RULE)

Existing Option Selling systems in the account trade **Monthly Expiries** (e.g. `26-NOV-2026`). If Option Buying also enters Monthly expiries, margin confusion, broker position net-off, and cognitive chaos ("bhashan") occur.

### Mathematical Expiry Selection Algorithm:
1. **Fetch All Nifty Expiries:** Retrieve all active NFO Nifty option expiry dates sorted ascending: $[E_0, E_1, E_2, \dots, E_n]$.
2. **Identify Monthly Dates:** For each year-month group, the maximum expiry date is the monthly contract ($E_{\text{monthly}}$).
3. **Filter Out Monthly Dates:**
   $$\text{Candidate Expiries} = \{E_i \mid E_i \notin E_{\text{monthly}} \land E_i \ge \text{Today}\}$$
4. **Distance Calculus (Target ~4 Weeks Away):**
   - Calculate forward week offset: $\text{Target Index} \approx 4\text{th available week}$ ($\approx 21–28$ days).
   - **Collision Check:** If the 4th week coincides with a Monthly expiry (or is illiquid), the engine **cascades to the 3rd Week** ($\approx 14–21$ days forward).
   - **Why 3rd Week?**
     - Nifty weekly options 3 weeks out have substantially higher open interest and tighter bid-ask spreads than 5-week options.
     - Theta decay is still flat and linear (negligible intraday burn).
     - **0.00% Date Overlap** with Option Selling M-Units.

---

## 🎯 3. STRIKE SELECTION & MODULO 100 FILTER

### Why 50-Ending Strikes Are Banned:
In far-dated weekly option chains (3–4 weeks away), 50-ending strikes (`23750`, `23850`, `23950`) suffer from **Nil/Extremely Thin Liquidity**:
- Bid-Ask spreads can be ₹15–₹30 wide.
- Market buy orders face horrific execution slippage.
- Historical candle data at 09:30 AM can be missing or zero-volume.

### The Modulo 100 Filter Invariant:
$$\text{strike} \pmod{100} == 0 \quad (\text{e.g. } 23600, 23700, 23800, 23900, 24000)$$
Any strike with $\text{strike} \pmod{100} \neq 0$ is strictly discarded from the candidate pool.

### Target Premium Window:
- **Price Range:** **₹160.00 to ₹200.00**
- **Preference:** Strike closest to ₹160.00 (lower premium preferred within the window to maximize leverage while preserving delta $\Delta \approx 0.35–0.42$).

---

## ⏰ 4. THE TWO-GATE TIMING STATE MACHINE

All execution decisions occur strictly at two daily gates. The system does **zero intraday churning**:

```
[ 09:16 AM ] Startup Sync & Instruments Cache
     │
[ 09:30 AM ] Reference Price Discovery Phase (0 Trades)
     │
[ 10:45 AM ] DECISION GATE 1: Morning Breakout Scan
     │       ├── If LTP_1045 > Ref_930 ──▶ BUY 1 Lot Market (Tag: NSLBUY)
     │       └── Else ──────────────────▶ DORMANT (No Trade)
     │
[ 10:45 - 15:00 ] 5-Min Watchdog Loop (:00, :05, :10...)
     │       ├── If P&L >= +50% ────────▶ SELL Active (Lock +50%) ──▶ ROLLOVER to fresh ~₹160 strike
     │       └── If P&L < +50% ─────────▶ HOLD CALMLY
     │
[ 03:00 PM ] DECISION GATE 2: Afternoon Trend Review
     │       ├── If Holding & LTP > Ref_930 ──▶ HOLD OVERNIGHT (Strong Trend)
     │       ├── If Holding & LTP <= Ref_930 ─▶ EXIT / SQUARE OFF (Trend Failed)
     │       └── If Flat & Breakout Detected ─▶ BUY for Overnight Carry
```

---

## 🛡️ 5. ZERODHA COEXISTENCE & TRIPLE LONG-ONLY SHIELD

To guarantee that Option Buying **NEVER** touches or closes any Option Selling trades on Zerodha account `XK7125`:

1. **Long Position Filter:**
   ```python
   def get_buying_position(kite, token):
       for p in kite.positions().get("net", []):
           # MUST BE POSITIVE QUANTITY (BUY) AND MATCH TOKEN
           if p["quantity"] > 0 and p["instrument_token"] == int(token):
               return p
       return None
   ```
   Any short position (`quantity < 0`, such as M1, M2, M3, OS) is completely invisible to this engine.
2. **Broker Tag Invariant:**
   Every order placed routes with:
   ```python
   tag="NSLBUY"
   ```
3. **Database Isolation:**
   All settings, state variables, and audit trails reside in `zerodha_buying.db` (completely isolated from `zerodha_trader.db`).
4. **Sequential Flip Rule:**
   If flipping from Call to Put at Gate 1 or Gate 2:
   $$\text{Exit Active Position} \implies \text{Sleep 30 Seconds (RMS Margin Release)} \implies \text{Enter New Position}$$

---

## 🖥️ 6. PAGE ARCHITECTURE: DEDICATED STANDALONE PAGE VS TAB

The user specifically requested advice on UI design:
> *"Dekho mere ko lagta hai ki ek Naya page Banakar banana jyada Bator rahega... otherwise bahut jyada bhashan [chaos] mach jayegi"*

### Technical Recommendation:
**A Dedicated Independent Standalone Page / Port is 1000% Superior.**

| Dimension | Jammed into Existing Dashboard (`Port 9007`) | Dedicated Standalone Page (`Port 9002` / Standalone) | Recommendation |
|---|---|---|---|
| **Process Isolation** | Shared Streamlit thread with Option Selling | Independent Python process & systemd service | **Dedicated Page** ✅ |
| **Crash Blast Radius**| An error in Buying UI can crash Port 9007 selling controls | Zero impact. Option Selling remains 100% active | **Dedicated Page** ✅ |
| **Visual Clutter** | 4-5 tabs crammed together; high cognitive load | Clean, uncluttered cockpit showing ONLY Option Buying | **Dedicated Page** ✅ |
| **Database Locks** | Potential SQLite write contention on `zerodha_trader.db`| Completely isolated database (`zerodha_buying.db`) | **Dedicated Page** ✅ |
| **Operator Safety** | High risk of sister clicking wrong button on wrong tab | Distinct URL / screen: zero chance of mix-up | **Dedicated Page** ✅ |

**Conclusion:** Implement as a dedicated, standalone dashboard with its own independent service and isolated database. Zero clutter, zero interference, 100% peace of mind.

---

## 💰 7. CAPITAL ALLOCATION & 1-LOT FIXED SIZING

- **Starting Lots:** Strictly **`1 Lot` (`65 Qty`)**.
- **Margin Required per Trade:** $\approx ₹10,400$ to $₹13,000$ ($65 \times ₹160–₹200$).
- **Recommended Capital Allocation:** **`₹30,000`**.
  - Trade Margin: $\approx ₹11,500$
  - Drawdown Reserve: $\approx ₹18,500$ (Absorbs up to 4 consecutive choppy sideways days without stress).
- **Scaling Rule:** No lot increase until accumulated realized profit exceeds $+₹30,000$.

