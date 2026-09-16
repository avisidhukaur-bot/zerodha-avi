# 📘 Zerodha Option Selling Engine — Re-Entry & Safety Rules Guide
**Document Reference:** `ZERODHA-OS-REENTRY-RULES-v1.0`  
**Date:** 09-Sept-2026  
**Audience:** Internal Team & Trading Desk  

---

## 🎯 Executive Summary (संक्षिप्त विवरण)
Zerodha Option Selling Engine me **Stop-Loss (SL) hit hone ke baad automated re-entry turant kyu nahi aati**, aur **15–20 minute ka delay kyu hota hai**, iska complete logic aur safety mechanisms is document me explain kiye gaye hain.

Yeh delay kisi technical glitch ya bug ki wajah se nahi hai, balki **"Anti-Whipsaw Protection Engine"** ka designed safety feature hai jo trader ko **double stop-loss (chot pe chot)** se bachata hai.

---

## 🛡️ The 3-Step Automated Re-Entry Process (3-स्टेप सुरक्षा चक्र)

Jab bhi kisi strike ka Stop-Loss hit hota hai, engine 3 sequential safety filters run karta hai:

```
[SL Hit @ Market] 
       │
       ▼
[STEP 1: 5-Min Cooldown Timer (300 sec)]  --->  Engine strikes par entry block rakhta hai
       │
       ▼
[STEP 2: Anchor Price Condition Check]    --->  LTP <= (Anchor Price - Buffer) ka intezar
       │
       ▼
[STEP 3: 5-Min Continuous Hold Timer]     --->  Price lagatar 5 min neeche sustain hona zaroori
       │
       ▼
[🎯 NEW RE-ENTRY SELL ORDER PLACED @ MARKET]
```

---

### Step 1: Post-Exit Cooldown (5 Minutes / 300s)
* **Kyu zaroori hai?** Jab Stop-Loss hit hota hai, toh market me temporary spike ya aggressive buying aati hai. Agar system turant usi second dobara sell kar dega, toh badhte hue premium me dobara SL lag sakta hai.
* **Mechanism:** SL hit hone ke baad agle **300 seconds (5 minutes)** tak system us strike par kisi bhi nayi entry ko strictly ignore/block karta hai.

---

### Step 2: Price Threshold Condition (LTP $\le$ Anchor - Buffer)
* **Rule:** Re-entry tabhi valid maani jaati hai jab option premium wapas discount par aa jaye:
  $$\text{Re-entry Trigger Price} \le \text{Anchor Price} - \text{Buffer (₹1.00)}$$
* **Example:** Agar Strike ka Anchor Price **₹39.00** hai, toh re-entry check tabhi active hoga jab LTP **₹38.00 ya usse neeche** aayega.
* Jab tak price ₹38.00 se upar rahega, engine wait karega.

---

### Step 3: 5-Min Continuous Hold Confirmation (300s)
* **Kyu zaroori hai?** Fake dips se bachne ke liye (Anti-Whipsaw). 
* **Mechanism:** Jaise hi LTP ₹38.00 ke neeche aata hai, system turant buy/sell nahi karta. System ek 300-second ka continuous confirmation timer start karta hai.
* **Spike Reset Rule:** Agar in 5 minutes ke dauraan price ek second ke liye bhi ₹38.00 ke upar gaya, toh **timer wapas ZERO (0)** ho jayega aur dobara 5 minute wait karega jab tak price lagatar stable na ho.
* **Execution:** Jab lagatar 5 minutes complete ho jaate hain, system **Market Order** par SELL leg place karta hai.

---

## 📊 Live Case Study: Strike 24300 CE (09-Sept-2026)

| Time (IST) | Event / Stage | Price | Details |
| :--- | :--- | :--- | :--- |
| **10:24:26 AM** | **SL Exit Trigger** | ₹40.65 | Leg 191 close hui. **+₹6,064.50** ka profit safely book ho gaya. |
| **10:24:26 — 10:29:26 AM** | **5-Min Cooldown** | ₹40.00+ | Step 1 active. Engine locked, re-entry scan paused. |
| **10:29:26 — 10:36:26 AM** | **Threshold Wait** | ₹39.50 ➔ ₹38.00 | Step 2 active. Market ₹38.00 threshold ke neeche aane ka intezar. |
| **10:36:26 — 10:41:26 AM** | **5-Min Continuous Hold** | ₹37.80 ➔ ₹36.50 | Step 3 active. Price 300 seconds tak continuous ₹38 ke neeche sustain hua. |
| **10:41:27 AM** | **Re-entry Placed** | **₹36.50** | Leg 194 fresh SELL execute hui. New SL manually set **₹42.00** active. |

---

## 💡 Benefits of this Safety System (Trader Ke Fayde)

1. **Double Loss / Whipsaw Protection:**  
   Spike aate hi aggressive re-entry lene se jo badha loss lag sakta tha, 5-min cooldown aur 5-min hold ne usse bacha liya.
2. **Favorable Sell Price:**  
   Anchor ₹39 tha, aur confirm hone ke baad ₹36.50 par better/safer level par entry mili.
3. **Locking Realized Profits:**  
   Pehle leg ka **+₹6,064.50** profit account me secure raha bina kisi drawdown ke.
4. **Preserved Manual Stop-Loss:**  
   Manual Stop-Loss (₹42.00) ko system ne 25% default se overwrite hone se rok kar strictly enforce kiya.

---

## ⚙️ Configuration Parameters in Code

| Parameter Name | Default Value | Location | Description |
| :--- | :--- | :--- | :--- |
| `reentry_cooldown_sec` | `300` (5 mins) | `pnl_engine.py` | Post SL-exit engine lock duration |
| `entry_delay_seconds` | `300` (5 mins) | `pnl_engine.py` | Continuous price hold confirmation timer |
| `discount_buffer` | `₹1.00` | `pnl_engine.py` | Anchor price re-entry buffer discount |
| `sl_price` | User Manual | `block_manager.py` | Custom manual Rupee Stop-Loss protection |

---
*Created automatically by Zerodha Automated Trading Engine Documentation.*
