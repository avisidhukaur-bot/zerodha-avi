# 🚀 PRODUCT DEVELOPMENT SPECIFICATION: V8.2 ARCHITECTURE
### Modules: W1 Weekly SuperTrend Hunter & Directional M-Units JIT Engine
**System:** Bharat Zerodha OS (Cheenna Zerodha) | **Reference:** V8.2 Production Standard

---

## ⚡ 1. EXECUTIVE SUMMARY
This document outlines the operational and architectural mechanics of the newly integrated **V8.2 Engine Suite**, introducing:
1. **Weekly ST-2H Autonomous Spread Engine (`W1`)**:
   - Native 2-Hour Resampled Nifty Spot Candles.
   - SuperTrend Indicator with Parameters `(Period=8, Multiplier=3.0)`.
   - Asymmetric Dual-Expiry Hunter (`Current Week` $\rightarrow$ `Next Week` $\rightarrow$ `Monthly Cascade`).
   - Fixed 3-Pulse Daily Cadence: `11:15 AM`, `01:15 PM`, `03:10 PM IST`.
2. **Directional M-Units (`M1`–`M4`) JIT Auto-Hunter**:
   - High-Frequency Kite LTP continuous streaming via `terminal_backend.py`.
   - Strike Hunter target ~₹200 on **EVEN 100-Multiples** (`strike % 100 == 0`).
   - Dynamic real-time Stop-Loss synchronization computed directly from execution fill price.

---

## 🎯 2. WEEKLY ST-2H ENGINE (`W1`) SPECIFICATION

### A. Mathematical Formulation & Signal Logic
$$\text{SuperTrend}(8, 3.0) \quad \text{on 2-Hour Spot Candles}$$

* **Bullish Regime ($\text{Spot} \ge \text{ST}$):**
  $$\text{Action: Deploy Bull Put Spread}$$
  - **Sell Leg:** OTM Put Strike yielding target premium $₹80 \le P \le ₹115$.
  - **Hedge Leg (Armor):** Buy Put Strike at $\text{Sell Strike} - 500\text{ pts}$.
  
* **Bearish Regime ($\text{Spot} < \text{ST}$):**
  $$\text{Action: Deploy Bear Call Spread}$$
  - **Sell Leg:** OTM Call Strike yielding target premium $₹80 \le P \le ₹115$.
  - **Hedge Leg (Armor):** Buy Call Strike at $\text{Sell Strike} + 500\text{ pts}$.

### B. The Asymmetric Dual-Expiry Volatility Cascade
```
[2H SuperTrend Evaluated]
           │
           ▼
[Step 1: Current Week Expiry Scan]
├── Enforce ST Moat Buffer (ST ± 50 pts)
├── Enforce Spot Clearance (Spot ± 150 pts)
└── Target Premium: ₹80 (Tolerance ₹65 - ₹115)
           │
     (LTP < ₹65?)
           │
           ├── YES ──► [Step 2: Next Week Asymmetric Hunter]
           │             ├── Bypass Current ST Moat
           │             ├── Enforce Spot OTM Clearance (Spot ± 150 pts)
           │             └── Capture Rich ₹80 Theta Decay
           │
           └── (Still < ₹65?) ──► [Step 2b: Monthly Expiry Deep Cascade]
```

### C. Execution Pulse Schedule
1. **Pulse 1 (`11:15 AM IST`):**
   - 09:15 to 11:15 2H candle boundary close.
   - On Mondays: Acts as First-Signal Rollover pulse (rolls Tuesday expiries cleanly to next week).
2. **Pulse 2 (`01:15 PM IST`):**
   - 11:15 to 13:15 2H candle boundary close. Mid-day trend audit.
3. **Pulse 3 (`03:10 PM IST`):**
   - 13:15 to 15:10 afternoon session wrap.

### D. Margin-Safe Broker Invariant
- **Entry Sequence:** $\text{BUY HEDGE FIRST} \longrightarrow \text{SELL SHORT SECOND}$.
  * Guarantees broker margin relief and zero margin-shortfall rejections.
- **Exit Sequence:** $\text{BUY-TO-COVER SHORT FIRST} \longrightarrow \text{SELL HEDGE SECOND}$.
  * Guarantees naked short position never exists on broker terminal.

---

## 🏛️ 3. ZERO-COLLISION MODULO ARCHITECTURE

To eliminate cross-system interference, all strategies run on disjoint strike grids:

| System | Modulo Condition | Strike Grid Example | Target Premium |
|---|---|---|---|
| **M-Units (`M1`–`M4`)** | `strike % 100 == 0` | `22500, 22600, 22700, 22800` | ~₹200 |
| **OS-Units (`OS1`–`OS5`)** | `strike % 100 == 50` | `22550, 22650, 22750, 22850` | ~₹150 |
| **Weekly ST (`W1`)** | Isolated Execution Table | `weekly_st_positions` table | ~₹80 |

$$\text{Mathematical Strike Overlap between M-Units and OS-Units} = \mathbf{0.00\%}$$
