# -*- coding: utf-8 -*-
with open('memory.md', 'r', encoding='utf-8') as f:
    text = f.read()

entry = """

---

## 🛒 04-NOV-2026: BHARAT OPTION BUYING ENGINE (NSL v6.1 — NON-MONTHLY BREAKOUT & CHHOTI BAHAN INVARIANTS)

### 📋 1. Architectural Genesis & Coexistence Mandate
- **Source Artifact:** Brother's Zip package `ZERODHA_OPTION_BUYING_PACKAGE` (`NSL v6.0`).
- **Target Desk:** Chhoti Bahan / Sister's Trading Desk on Zerodha (`XK7125`).
- **Core Dilemma:** Existing Option Selling setups (`M1`, `M2`, `M3`) sell **Monthly Expiry** contracts. Running Monthly Option Buying on the same broker account introduces orderbook clash, margin competition, and operator confusion.
- **Master User Rule (Non-Monthly Invariant):**
  - **STRICTLY AVOID MONTHLY EXPIRY DATES.**
  - Target weekly expiries ~3 to 4 weeks forward (approx 21-28 days).
  - If the 4th week is the Monthly Expiry, **cascade to the 3rd Week** (approx 14-21 days forward) for maximum liquidity.
- **Strike Selection Rule (Modulo 100 Invariant):**
  - Far-dated weekly 50-ending strikes (`23750, 23850`) suffer from nil/thin liquidity and extreme bid-ask slippage.
  - **STRICTLY EVEN 100 STRIKES ONLY** (`strike % 100 == 0`: `23600, 23700, 23800...`).
- **Position Sizing:**
  - Strictly **1 Lot** (`65 Qty`) to start. Capital risk capped at approx ₹10,400-₹13,000.
- **Long-Only Coexistence Shield:**
  - `get_open_buying_position()` filters `quantity > 0` AND matching token. Any short position (`quantity < 0`) is 100% invisible and untouchable.
  - Tag: `NSLBUY`.
  - Database: Private `zerodha_buying.db` (isolated from `zerodha_trader.db`).
- **UI Architecture Decision:**
  - Dedicated standalone page/dashboard rather than cramming into Port 9007 to eliminate cognitive clutter ("bhashan") and prevent cross-app state corruption.
"""

if '## 🛒 04-NOV-2026: BHARAT OPTION BUYING ENGINE' not in text:
    text = text + entry
    with open('memory.md', 'w', encoding='utf-8') as f:
        f.write(text)
    print('memory.md updated successfully.')
else:
    print('memory.md already has Section.')

