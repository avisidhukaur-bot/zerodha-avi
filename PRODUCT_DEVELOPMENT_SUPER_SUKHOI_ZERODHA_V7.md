# 🏛️ PRODUCT DEVELOPMENT FILE — SUPER SUKHOI ENGINE (V7.0) — ZERODHA SISTER EDITION
> **Target System**: Zerodha Kite Option Selling App (*Bharat Systems — Chhoti Bahan Edition*)  
> **Target Version**: V7.0 Super Sukhoi Autonomous Laddering Edition  
> **Broker Integration**: Zerodha KiteConnect REST API (`kite_executor.py`)  
> **Protocol**: Gurjas's Lego System Protocol (Single-Brick Implementation)  
> **Date**: 26-Oct-2026

---

## 📌 1. EXECUTIVE SUMMARY & OBJECTIVES

### 1.1 What is Super Sukhoi V7.0 for Zerodha?
Super Sukhoi transforms the Directional M-Unit Engine (`M1`, `M2`, `M3`) into a fully autonomous, fire-and-forget directional laddering machine on Zerodha Kite:
1. **Seed Unit Configuration (`M1`)**: Sister configures and locks `M1` with Master Anchor Price ($A_1$), Expiry Date, and Lots (e.g. $A_1 = ₹22,650.00$, Monthly Expiry, 2 Lots).
2. **Autonomous Tier 1 (`M2 UP` / `M2 DOWN`)**: Monitored continuously via Zerodha live Spot feed. When Spot moves $\pm 2.00\%$ from $A_1$:
   - Engine automatically spawns `M2`.
   - Sets its anchor to the trigger level ($A_1 \times 1.02$ or $A_1 \times 0.98$).
   - Inherits M1's expiry horizon and lot sizing.
   - Scans EVEN-100 strikes paying ~₹200 target premium.
   - Pre-buys the 500-pt hedge helmet FIRST for full Zerodha margin relief.
   - Executes the short trend-aligned leg SECOND.
3. **Autonomous Tier 2 (`M3 UP` / `M3 DOWN`)**: If market extends an additional $\pm 2.00\%$ ($\pm 4.00\%$ from $A_1$) while M1 is active, engine autonomously spawns `M3` with identical inherited rules.
4. **Decoupled Midday 25% Stop-Loss**: The aggressive 25% Stop Loss on SELL legs is disabled by default to eliminate premature whipsaw exits. Positions are protected by the pre-bought 500-pt hedge helmet and evaluated at the 14:57 IST EOD Master Anchor audit.
5. **Zerodha TOTP Silent Guard**: Leverages PyOTP with Zerodha's 32-char Base32 key for silent morning authentication without nag spam.
6. **1-Click High-Visibility UI**: Prominent button `[ 🚀 ACTIVATE SUPER SUKHOI AUTO-MODE ]` with a 2-step confirmation modal and real-time telemetry radar in the Zerodha Cockpit (Port `9007`).

---

## 🛡️ 2. ZERODHA HARD INVARIANTS & RISK ARMOR

| Invariant | Specification | Zerodha Implementation Rule |
|---|---|---|
| **Compulsory Hedge Armor** | ZERO NAKED TRADES | Pre-bought 500-pt OTM hedge helmet strictly required on every single directional leg. |
| **Zerodha Margin Execution Order** | **Buy Hedge FIRST ➔ Sell Leg SECOND** | Firing the Buy Hedge first gives Zerodha Kite immediate margin benefit, dropping required margin from ~₹1.3L to ~₹35K per lot. |
| **Fail-Safe Abort** | Instant Rollback | If the hedge buy order is rejected by Zerodha (e.g. margin, freeze limit), the sell order is **ABORTED IMMEDIATELY**. |
| **Even-100 Strike Series** | Modulo `strike % 100 == 0` | M-Units operate strictly on liquid 00-ending strikes (`22600, 22700, 22800...`), ensuring `0.00%` overlap with OS 50-series (`22650, 22750...`). |
| **Decoupled SL Policy** | Theta Harvest Default | Optional 25% Stop-Loss default is **`DISABLED`**; positions remain 100% hedged and safe. |
| **Trading IP Support** | `ALLOWED_TRADING_IP=ANY` | Pre-configured for sister's home Wi-Fi laptop; works seamlessly without static IP lockouts. |

---

## 🧱 3. SINGLE-BRICK IMPLEMENTATION ROADMAP (ZERODHA OS)

| Brick ID | Component | File(s) | Function / Purpose |
|---|---|---|---|
| **Brick 1** | **Quiet Hours & Holiday Guard** | `utils.py`, `main.py` | Add `is_trading_day()`, `is_market_session_active()`, and `NSE_HOLIDAYS_2026`. Silence alerts during off-hours/holidays. |
| **Brick 2** | **Stop Loss Decoupling Switch** | `pnl_engine.py`, `db.py` | Add `m_stoploss_mode` (`"DISABLED"` default). Skip aggressive intraday 25% SELL exit when disabled. |
| **Brick 3** | **Super Sukhoi Core Engine** | `super_sukhoi_engine.py` | Autonomous trigger math ($\pm 2\%$, $\pm 4\%$), parameter inheritance, strike hunter integration, and deployment lifecycle. |
| **Brick 4** | **Background Engine Hook** | `main.py` | Hook `super_sukhoi_engine.evaluate_super_sukhoi_cycle()` into the 30-second loop during trading hours. |
| **Brick 5** | **Cockpit Dashboard UI** | `app.py`, `ui_m_units.py` | Prominent Auto-Mode button, confirmation modal, and real-time radar HUD in Tab 1 (Port `9007`). |
| **Brick 6** | **Automated Test Suite** | `test_super_sukhoi_zerodha_v7.py` | 100% test coverage for trigger calculus, state transitions, SL disabling, and holiday guards. |

---

## 🗄️ 4. DATABASE SCHEMA & CONFIGURATION ATTRIBUTES

New key-value entries stored in SQLite `settings` table of `zerodha_trader.db`:

| Key | Type | Default | Description |
|---|---|---|---|
| `super_sukhoi_active` | `TEXT` | `"0"` | `"1"` if Super Sukhoi Auto-Mode is ON, `"0"` if OFF/Manual. |
| `super_sukhoi_m1_anchor` | `TEXT` | `""` | Cached M1 anchor price at time of activation. |
| `super_sukhoi_m1_expiry` | `TEXT` | `""` | Cached M1 expiry date (e.g. `2026-11-23`). |
| `super_sukhoi_m1_lots` | `TEXT` | `"1"` | Cached M1 lot size (e.g. `2`). |
| `super_sukhoi_m2_deployed` | `TEXT` | `"0"` | `"1"` once M2 has been spawned by Super Sukhoi. |
| `super_sukhoi_m2_direction` | `TEXT` | `""` | `"UP"` or `"DOWN"` indicating which side M2 was deployed on. |
| `super_sukhoi_m3_deployed` | `TEXT` | `"0"` | `"1"` once M3 has been spawned by Super Sukhoi. |
| `super_sukhoi_m3_direction` | `TEXT` | `""` | `"UP"` or `"DOWN"` indicating which side M3 was deployed on. |
| `super_sukhoi_activated_at` | `TEXT` | `""` | Timestamp when sister activated Super Sukhoi. |
| `m_stoploss_mode` | `TEXT` | `"DISABLED"` | `"DISABLED"` (default, 500-pt hedge only) or `"ENABLED"` (25% SL). |

---

## 📐 5. MATHEMATICAL FORMULATION & SCALING MATRIX

Given sister's configured seed unit `M1` with Anchor Price $A_1$ (e.g. $A_1 = ₹22,650.00$):

| Tier & Leg | Formula | Trigger Level ($A_1 = 22,650$) | Action on Nifty Spot Breach |
|---|---|---|---|
| **M2 UP (+2.00%)** | $\text{round}(A_1 \times 1.020, 2)$ | **₹23,103.00** | Auto-deploy `M2` Bull Put Spread (Sell PE + Buy PE Hedge at $-500\text{ pts}$). |
| **M2 DOWN (-2.00%)** | $\text{round}(A_1 \times 0.980, 2)$ | **₹22,197.00** | Auto-deploy `M2` Bear Call Spread (Sell CE + Buy CE Hedge at $+500\text{ pts}$). |
| **M3 UP (+4.00%)** | $\text{round}(A_1 \times 1.040, 2)$ | **₹23,556.00** | Auto-deploy `M3` Bull Put Spread (Active only if M1 still active). |
| **M3 DOWN (-4.00%)** | $\text{round}(A_1 \times 0.960, 2)$ | **₹21,744.00** | Auto-deploy `M3` Bear Call Spread (Active only if M1 still active). |

---

## 🚀 6. SISTER 1-CLICK AUTO-UPDATE SCRIPT (`START_CHHOTI_BAHAN_AUTO_UPDATE.bat`)

When sister receives the update zip, she runs the 1-click update script:
1. Automatically backs up existing `secrets.txt` and `zerodha_trader.db`.
2. Copies `super_sukhoi_engine.py`, updated `app.py`, `main.py`, and `block_manager.py`.
3. Runs database schema migration to add `super_sukhoi` settings.
4. Executes `test_super_sukhoi_zerodha_v7.py` to ensure 100% green pass before launching.
5. Launches Dashboard at `http://localhost:9007`.
