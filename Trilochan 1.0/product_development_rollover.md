# 🔄 Product Development Spec — Weekly Hedge Rollover System
### Setup & Design Specifications for Operator | Hindi + English (Hinglish)

Weekly hedges ko easily aur safely rollover karne ke liye yeh development spec hai. Is spec ke anusaar hum system ke core engine (`block_manager.py`) aur Streamlit dashboard (`app.py`) dono mein change karenge.

---

## 🎯 Goal (Karna Kya Hai?)
Weekly hedges (jo har Thursday expire hoti hain) ko bina kisi margin error aur bina kisi complex SSH commands ke direct Streamlit web dashboard se **1-Click** mein rollover karna.
- Purani hedge leg ko execute/close karna.
- Nayi weekly hedge leg ko purchase karna.
- Dono ke strike difference aur lots ko set karna.
- Dono ko DB mein correctly link aur unlink karna.

---

## ⚠️ Critical Bug Found (⚠️ BADI SAMASYA!)
Research ke dauran humein `block_manager.py` ke active `rollover_hedge()` function (Line 1213) mein ek bada bug mila hai:
* **Current Order Sequence:**
  1. Purani hedge ko close (SELL) karta hai.
  2. Nayi hedge ko buy (BUY) karta hai.
* **Problem:** Agar hum purani hedge pehle sell kar denge, toh hamara live option **SELL** position bina kisi hedge ke **NAKED SHORT** ban jayega (chahe 1 second ke liye hi sahi). 
  * Zerodha immediately margin requirement ko normal ₹30k per lot se badhakar ₹1.5 Lakhs+ kar dega.
  * Agar account mein extra balance nahi hoga, toh **New Hedge BUY order reject ho jayega!** Sell position naked hi reh jayegi aur naked loss risk rahega.
* **Correct Sequence (SAFE):**
  1. Nayi weekly hedge ko pehle buy (BUY) karein.
  2. Buy order execute hone ke baad immediately purani hedge ko sell (close) karein.
  * Isse account hamesha double hedged rahega aur margin spike ka issue nahi aayega!

---

## 🛠️ Proposed Solution (Naya Setup Kaise Kaam Karega?)

Hum rollover functionality ko do main parts mein divide karenge:

### 1. Backend Refactor (`block_manager.py`):
* `rollover_hedge()` function ka flow safe sequence mein change karenge:
  1. Database mein naya strike entry `HEDGE_BUY` type ka create karenge with new expiry.
  2. Nayi hedge ko broker par BUY order bhejkar execute karenge.
  3. Agar BUY successful ho jaye, tabhi purani hedge ko SELL bhejkar close karenge.
  4. Database mein updates karenge (old unlink, new link).
  5. Telegram alerts aur logger update karenge.
  * **Fallback Handling:** Agar nayi hedge buy fail ho jaye, toh rollover abort ho jayega (purani hedge open hi rahegi). Agar purani close fail ho, toh database nayi link kar lega lekin mobile par alert bhejega manually close karne ke liye.

### 2. Frontend Redesign (`app.py`):
Dashboard par user ko scroll karke expanders dhundhne ke bajaye ek top-level card denge:
* **"🔄 WEEKLY HEDGE ROLLOVER CENTER"** (Dashboard ke top par, New Block form ke right ya niche, highly visible).
* Yeh table automatically search karega: **Dono conditions meet karne wale elements:**
  * Active Blocks ke andar jitne bhi `OPEN` aur `SELL` legs hain jinse linked `HEDGE_BUY` strike exist karti hai.
* Tabular representation hoga:
  * **Block #** | **SELL Option Details** | **Current Linked Hedge (Strike, Expiry, Lots)** | **LTP**
* Aur side mein ek quick interactive card hoga jahan operator selected strike ko select karke ye values change kar sake:
  * **New Expiry Date** (Dropdown of sorted master expiries, default automatically selected as next week).
  * **New Strike Price** (Prefilled, easily editable e.g., 27000 se 26000).
  * **New Lots** (Prefilled from current lots, editable).
  * **Button:** `🔄 Confirm & Execute Rollover in 1-Click` (Orange Gradient Premium button).

---

## 📈 Implementation Plan (Step-by-Step)

### Step 1: Backend Fix (`block_manager.py`)
- Python function `rollover_hedge` ki order execution sequence ko change karenge:
  - Create new strike DB entry first.
  - Buy new hedge via `_execute_buy_leg(new_strike, new_qty)`.
  - Close old hedge via `close_hedge_strike_only(old_hedge_id)` (or inline executor).
  - Unlink old hedge, Link new hedge to sell.
  - Alerts send.

### Step 2: UI Implementation (`app.py`)
- Naya helper function `render_rollover_center()` banayenge.
- Dashboard ke main body rendering flow mein ise add karenge:
  - Sidebar -> Header -> Metrics -> **Weekly Hedge Rollover Center** -> New Block Setup -> Active Blocks.
- Expiry list logic ko dynamically connect karenge.

### Step 3: Local Dry Run and Verification
- Local code verify karenge. Run linter checks to prevent syntax errors.

### Step 4: Live deployment on VPS
- Run `python lego1_deploy.py` laptop se VPS sync karne ke liye.
- Run `python lego0_diagnose.py` live logs check karne ke liye.

---
*Documented by Antigravity on 02-Jul-2026.*
