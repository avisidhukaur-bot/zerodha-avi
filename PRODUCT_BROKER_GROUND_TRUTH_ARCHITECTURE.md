# 🛡️ Product Architecture: Broker-First Ground-Truth Engine ("Zero-Assumption Trading")

**Document Reference:** `PRODUCT-BROKER-GROUND-TRUTH-v1.0`  
**Date:** 17-Sept-2026  
**Status:** IMPLEMENTED & DEPLOYED  
**System:** Zerodha Option Selling Engine (Port 9007)

---

## 🎯 1. Executive Summary & Root Cause Analysis

### The Problem (The "Assumption" Vulnerability)
In automated option selling, relying solely on local SQLite database state to decide order execution creates a catastrophic vulnerability:
1. If a position was already open on the broker terminal (e.g. carried forward from previous day or held on Kite), but the local DB marked the leg as `CLOSED` (due to test scripts, manual DB edits, or desync), the engine assumed `Open Quantity = 0`.
2. As a consequence, when the market fell below Anchor, the engine triggered a "fresh" 1-lot order.
3. This 1-lot order got **super-imposed on top of the existing broker position**, creating an unintended **2 Lots (130 Qty)** exposure!

### The Solution (Broker-as-Ground-Truth Rule)
**The broker terminal (`kite.positions()`) is the SINGLE SOURCE OF TRUTH (SSOT).**
The engine must NEVER place an order based on DB assumptions. Every execution path (Manual, Auto-Entry, Auto-Re-Entry, Scaling) must first query the live broker net position.

---

## 🏛️ 2. Core Architectural Invariants

### Invariant 1: Pre-Execution Broker Position Gatekeeper
Before ANY BUY or SELL order is submitted to the Kite Connect SDK:
$$\text{Live Broker Net Qty} = \text{kite.positions()['net'] for } \text{Symbol}$$
* **For Short Leg (SELL):**  
  If $\text{Broker Net Qty} \le -\text{Target Qty}$, **ABORT ORDER IMMEDIATELY**.  
  *Action:* Re-link existing broker position, sync DB state to `OPEN / ACTIVE`, and log `[BROKER-GROUND-TRUTH] Strike already held short. Duplicate order blocked.`
* **For Long Hedge (BUY):**  
  If $\text{Broker Net Qty} \ge \text{Target Qty}$, **DO NOT BUY NEW HEDGE**.  
  *Action:* Re-use existing open hedge on the broker.

```
                  [Order Execution Request]
                             │
                             ▼
              [Query Broker Net Position API]
              kite.positions()['net'][Symbol]
                             │
            ┌────────────────┴────────────────┐
            ▼                                 ▼
   [Broker Qty >= Target]            [Broker Qty == 0]
            │                                 │
     🛑 ABORT ORDER                   ✅ ALLOW ORDER
  (Re-use existing leg)            (Hedge-First -> Short Leg)
  (Sync DB to ACTIVE)              (Record fill in DB)
```

---

## ⚙️ 3. Implementation Across Code Modules

### 1. `kite_executor.py`
* Added `get_net_position_qty(trading_symbol: str) -> int`:
  Queries live net positions from `kite.positions()['net']` and returns integer net quantity (`-65`, `+130`, `0`).

### 2. `block_manager.py`
* In `_execute_sell_leg()`: Intercepts before API call; if `broker_net_qty <= -qty`, blocks duplicate sell order and records existing leg.
* In `_execute_buy_leg()`: Intercepts before API call; if `broker_net_qty >= qty`, prevents duplicate hedge buy and reuses active hedge.

### 3. `pnl_engine.py`
* In `run_pnl_cycle()` Auto-Entry & Auto-Re-Entry loops:
  * Prior to starting 5-minute continuous hold countdown timers, verifies live broker quantity.
  * If broker already holds the contract, cancels timer, synchronizes DB to `OPEN / ACTIVE`, and avoids firing duplicate orders.

---

## 📊 4. Operational Safety Checklist

| Scenario | Broker State | DB State | Engine Action |
| :--- | :--- | :--- | :--- |
| **Normal Fresh Entry** | 0 Qty | PENDING | Executes Buy Hedge (65) -> Sell (65). |
| **Desync (Broker held, DB closed)** | -65 Qty | PENDING/CLOSED | **BLOCKED.** Reuses broker 65 Qty. No new order placed. |
| **Desync (Broker 0, DB open)** | 0 Qty | OPEN | Reconciles DB or alerts operator. |
| **Re-Entry after SL** | 0 Qty (SL closed) | CLOSED | Verifies broker 0 Qty -> Waits 5m cooldown & hold -> Re-enters 1 lot. |

---

## 🚀 5. Verification & Test Proof
* **Live Test on 17-Sep-2026:**
  * Live trade of 130 Qty was cleanly squared off (Short leg covered first @ ₹54.20, Hedge exited @ ₹8.35).
  * Net Realized Profit: **+₹299.00** locked into Zerodha account.
  * Broker positions verified to be strictly **0 (Zero)**.
  * Engine paused (`algo_running = OFF`) to ensure zero unapproved activity.
