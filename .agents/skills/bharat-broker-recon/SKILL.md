---
name: bharat-broker-recon
description: White Glass broker ground-truth reconciliation across Zerodha Kite, Kotak Neo, and HDFC Sky. Enforces 3-state (SHORT / FLAT / UNKNOWN) fail-safe.
---

# 🛡️ BHARAT BROKER GROUND-TRUTH RECONCILIATION SKILL

## 1. Core Operating Invariant
- **Broker is the Single Source of Truth**: The SQLite database (`zerodha_trader.db`) is merely a local cache.
- Before executing ANY action (entry, exit, square-off, or overnight continuation), ALWAYS query broker API:
  - **Zerodha Kite**: `kite_executor.get_positions()` / `kite.positions()['net']`
  - **Kotak Neo**: `client.positions()`
  - **HDFC Sky**: `hdfc_executor.get_positions()` (Never `get_holdings()` for F&O)

## 2. Three-State Reconciliation Engine
| State | Broker Net Quantity | Engine Action |
|---|---|---|
| **SHORT** | Net Qty < 0 (Confirmed Short) | Normal monitoring / SL / 15:00 continuation permitted. |
| **FLAT** | Net Qty == 0 (Confirmed Closed) | Mark DB closed immediately. ZERO market orders placed. |
| **UNKNOWN** | Timeout / Connection Lost / Parse Error | **FAIL-SAFE ACTIVATED: ZERO ACTION.** No ghost closes, no entries, no flips. |

## 3. Strict Execution Ordering
- **Entry**: Buy 500-pt Protective Hedge **FIRST** $\rightarrow$ Confirm Fill $\rightarrow$ Sell Short Leg **SECOND**.
- **Exit**: Buy-to-Cover Short Leg **FIRST** $\rightarrow$ Confirm Fill $\rightarrow$ Sell Protective Hedge **SECOND**.
- **Lot Ceiling Guard**: Before routing sell orders, check if broker net short $\ge$ unit locked limit (e.g. 195 qty / 3 lots). If already present, **HARD ABORT with `[REJECT-DUPLICATE-BLOCK]`**.
