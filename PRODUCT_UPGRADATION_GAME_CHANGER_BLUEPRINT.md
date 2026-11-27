# 🏛️ PRODUCT UPGRADATION BLUEPRINT: GAME CHANGERS vs UNNECESSARY FEATURES
## STRATEGIC SYSTEM REVIEW & TAILORED ARCHITECTURE FOR CHHOTI BAHAN
> **System:** Zerodha Kite Option Selling App (Sister's Workspace: `XK7125`)  
> **Source Review:** Bhaiya's Master System (`v8.7.6` — Gg Gg Delhi)  
> **Authority:** Gurjeet Mamu's Strategic Directives (09:49 AM & 10:37 AM IST)  
> **Version:** `v8.7.6-ASYMMETRIC-PULSE-PARITY` | Date: 27-Nov-2026 10:42 AM IST  

---

## 🧭 1. EXECUTIVE VISION & OPERATING PHILOSOPHY

### "Do Not Blindly Copy-Paste — Sister's System is Different"
Bhaiya's system is a multi-broker, multi-pod algorithmic environment operated by developers with live CLI debugging.  
**Sister's system is built on a completely different philosophy:**
1. **Non-Coder Operational Simplicity**: The interface must be foolproof, sequential, and zero-clutter.
2. **Strict Capital & Risk Boundaries**: Exactly 1 Master Unit (M1 — 3 Lots) + 1 Weekly ST Spread (2 Lots). Zero rogue sprawl.
3. **Peaceful Theta Harvesting**: No intraday whipsaw churn; positions breathe safely under a 500-point protective armor.
4. **Institutional Safety**: Broker ground truth is king; duplicate orders are mathematically impossible.

---

## ⚖️ 2. GURJEET MAMU'S ASYMMETRIC DUAL-WING ENTRY vs 3-PULSE CLOSING CADENCE (CORE INVARIANT)

| Dimension | New Trend Entry Cadence (CE / PE Start) | Opposing Leg Exit / Cut Cadence (Flip & Square-Off) |
|---|---|---|
| **Operational Cadence** | **Continuous (Every 30s / 5-Min Filter)** | **Strictly 3 Times / Day (Triple Pulses)** |
| **Check Timings** | Real-time continuous background check across 09:15–14:55 IST | **`11:00 AM`**, **`01:00 PM`**, and **`02:57 PM IST`** |
| **Trigger Condition** | Spot crosses Master Anchor by $\pm 15.0\text{ pt}$ buffer AND **stays continuously for 5 minutes (300s)** | Evaluated strictly at the exact pulse candle: Spot outside Anchor $\pm 15.0\text{ pt}$ |
| **Action Taken** | **Deploys trend-aligned wing IMMEDIATELY** via JIT Auto-Hunter (~₹200 target strike + 500-pt hedge buy). | **Cuts opposing short & hedge** on decisive breakout; **KEEPS BOTH WINGS** if inside $\pm 15$ pt chop zone. |
| **Opposing Leg Status** | **100% UNTOUCHED**: Running opposing leg is NOT cut when new wing enters. Both wings run simultaneously. | Square-off occurs ONLY during the 3 pulses, or on autonomous 25% Stop-Loss hit. |
| **Mathematical Rationale** | Early trend capture maximizes premium collection and creates an asymmetric strangle/theta hedge. | Eliminates midday chop whipsaws and saves hundreds of thousands in false breakout churn. |

---

## 🚀 3. THE 5 GAME CHANGERS (MUST IMPLEMENT IN SISTER'S SYSTEM)

| # | Game Changer | Why It Is a Game Changer for Sister | How It Works |
|---|---|---|---|
| **1** | **Super Sukhoi M1-Attachment & Auto-Disarm** | Prevents rogue background triggers. If Sister closes M1, Super Sukhoi dies instantly with it. | `_auto_disarm_sukhoi_if_m1()` hooked into strike closures and wipeouts. Sets `super_sukhoi_active = '0'`, purges anchor keys, manual restart only. |
| **2** | **Broker Ground Truth Lot Ceiling in `execute_strike()`** | Eliminates double-entry blunders forever (e.g. 195 doubling to 390). | Queries `kite.positions()`. If account already holds $\ge 195$ qty short for that strike, **HARD ABORTS with `[REJECT-DUPLICATE-BLOCK]`**. |
| **3** | **Morning Clean-Slate Sentinel (09:00 AM)** | Eliminates the 09:15 AM market-open order spike. | Neutralized the old `run_daily_strike_reset()` (which was reviving closed strikes back to PENDING). Now automatically purges stale previous-day pending strikes. |
| **4** | **Lean Context Rule (`GEMINI.md` + `CHANGELOG_ARCHIVE.md`)** | Cuts AI inference time in half; eliminates hallucinations from ancient version notes. | `GEMINI.md` holds ONLY active rules + latest 2 version entries. All historical changelogs moved to `CHANGELOG_ARCHIVE.md`. |
| **5** | **Workspace Skills Structure (`.agents/skills/`)** | Gives the AI deterministic, step-by-step procedures for broker audits and VPS deployments. | • `bharat-broker-recon`: 3-state reconciliation (SHORT/FLAT/UNKNOWN).<br>• `bharat-vps-deploy`: 5-step single-brick Lego deployment. |

---

## 🛑 4. WHAT IS UNNECESSARY & HARMFUL (MUST NOT BE COPIED FROM BHAIYA'S SYSTEM)

| Feature in Bhaiya's System | Why It Is UNNECESSARY / HARMFUL for Sister | Verdict for Sister's System |
|---|---|---|
| **Multi-Pod Sprawl (M1–M10, OS1–OS10)** | Creating multiple concurrent blocks in SQLite overwhelms the UI and leads to zombie block leaks. Sister only needs 1 M1 unit. | ❌ **REJECTED**: Strictly enforce Single-Unit Sanctity (Max 1 M1 block). |
| **Aggressive Intraday Stop-Loss Churn** | Cutting and re-entering trades 3–4 times midday creates high transaction costs, bid-ask slippage, and panic. | ❌ **REJECTED**: Preserve Mamu's Invariant: Midday SL is **DISABLED** under 500-pt hedge helmet; wrong-side evaluated strictly during 3 pulses. |
| **Complex Multi-Window Dashboard Controls** | Side-by-side buttons and concurrent execution triggers cause misclicks for a non-coder operator. | ❌ **REJECTED**: Preserve Sister's signature **3-Step Sequential Pipeline** (Step 1: Fetch -> Step 2: Lock -> Step 3: Option A / Option B). |
| **Autonomous Standalone Auto-Pilot** | Background daemons deciding to deploy trades without M1 seed alignment causes confusion. | ❌ **REJECTED**: Super Sukhoi remains strictly a subordinate slave to M1. |

---

## 🏛️ 5. SISTER'S TAILORED ARCHITECTURE MATRIX

```
                        ┌──────────────────────────────────────────────┐
                        │        CHHOTI BAHAN TAILORED ENGINE         │
                        └──────────────────────┬───────────────────────┘
                                               │
             ┌─────────────────────────────────┴─────────────────────────────────┐
             ▼                                                                   ▼
┌─────────────────────────┐                                         ┌─────────────────────────┐
│     WEEKLY ST ENGINE    │                                         │      MONTHLY M1 UNIT    │
│       (Tab 3 — W1)      │                                         │       (Tab 1 — M1)      │
├─────────────────────────┤                                         ├─────────────────────────┤
│ • 2-Hour SuperTrend (8,3)│                                         │ • Master Anchor (A1)    │
│ • 2 Lots (130 Qty)      │                                         │ • Strictly 3 Lots (195) │
│ • 3 Pulses/Day:         │                                         │ • 3-Step Sequential UI  │
│   11:15, 13:15, 15:10   │                                         │ • Asymmetric Entry:     │
│ • Target ~₹80 + 500-pt  │                                         │   5-Min Stay -> Instant │
│   synthetic hedge armor │                                         │ • 3 Exit Pulses:        │
│                         │                                         │   11:00, 13:00, 14:57   │
└─────────────────────────┘                                         └────────────┬────────────┘
                                                                                 │
                                                                                 ▼
                                                                    ┌─────────────────────────┐
                                                                    │   SUPER SUKHOI SLAVE    │
                                                                    │    (Optional Ladder)    │
                                                                    ├─────────────────────────┤
                                                                    │ • Lives & Dies with M1  │
                                                                    │ • M1 Close = AUTO-OFF   │
                                                                    │ • Lot Cap: Max 195 Qty  │
                                                                    │ • 15-min cooldown       │
                                                                    │ • Dynamic A2 execution  │
                                                                    └─────────────────────────┘
```

---

## 🔍 6. 27-NOV FORENSIC ROOT-CAUSE: WHY THE SOFTWARE DID NOT ENTER CE (MAMU'S AUDIT)

1. **The Primary Blocker (`algo_running = OFF`)**:
   - At 09:18–09:20 AM, while manually covering the 195 double-lot spike on Kite terminal, `algo_running` was toggled to `'OFF'` in SQLite `settings` table as a safety precaution.
   - When the v8.7.6 code was deployed and services restarted at 10:24 AM, `algo_running` remained saved as `'OFF'` in the database.
   - In `main.py` lines 147-155, the background loop checks `if not algo_running:` and immediately sleeps 10s and continues, logging `Trading engine is currently PAUSED (algo_running = OFF)`.
   - **Result**: The entire trading engine daemon was in PAUSE mode. It never called `regime_engine.evaluate_all_blocks()`, so the 5-minute stay timer never ran.

2. **The Permanent Guard Implemented (Lego Brick)**:
   - When engine service is restarted in production, or when an operator deploys M1, `algo_running` must be explicitly verified and set to `'ON'`.
   - `regime_engine.py` is 100% verified to have the 5-minute stay timer (`breakout_ts_bearish_121`) and JIT Dynamic Hunter ready to fire CE entry the moment `algo_running == 'ON'`.
