# 📘 Zerodha Option Engine — Re-Entry & Stop-Loss System Guide

## 🎯 Main Point (सरल शब्दों में)
Jab kisi strike ka Stop-Loss hit hota hai, toh algorithm **turant jump nahi karta**. System **15–17 minute** wait karta hai taaki market me spike aane par trader ko **"Double Stop-Loss"** na lage. Jaise hi price wapas stable discount par settle hota hai, system automatically best price par fresh SELL order place kar deta hai.

---

## 🛡️ Re-Entry Ke 3 Sequential Safety Filters

1. **Step 1: Post-Exit Cooldown (5 Minutes / 300 Sec)**
   - SL hit hote hi market me buying spike hoti hai. Engine agle **5 minute** tak entry ko freeze rakhta hai taaki spike me dobara loss na ho.

2. **Step 2: Price Threshold Check (Anchor - ₹1 Buffer)**
   - Re-entry tabhi scan hoti hai jab `LTP <= Anchor (₹39.00) - ₹1.00 = ₹38.00` ya uske neeche aaye. Jab tak price ₹38 se upar hai, system wait karta hai.

3. **Step 3: 5-Min Continuous Hold Confirmation (300 Sec)**
   - LTP ₹38 ke neeche aane par price ko **lagatar 5 minute (300 seconds)** tak wahi sustain karna zaroori hai. Agar beech me spike aaya toh timer 0 ho jayega. Full 5 min stable rehne par hi SELL re-entry execute hoti hai.

---

## 📊 Live Case Study: Strike 24300 CE (09-Sep-2026)

| Time (IST) | Event | Price | Result / Action |
| :--- | :--- | :--- | :--- |
| **10:24:26 AM** | **SL Exit Triggered** | ₹40.65 | **+₹6,064.50 Profit Booked** (Leg 191 Closed) |
| **10:24 — 10:29 AM** | **5-Min Cooldown** | ₹40.00+ | Engine freeze raha. Spike se bachaav kiya. |
| **10:29 — 10:36 AM** | **Threshold Check** | ₹39.50 ➔ ₹38.00 | Market ₹38.00 ke neeche aane ka wait kiya. |
| **10:36 — 10:41 AM** | **5-Min Confirmation Hold** | ₹37.80 ➔ ₹36.50 | Price 300 seconds tak continuous ₹38 ke neeche raha. |
| **10:41:27 AM** | **Fresh SELL Re-entry** | **₹36.50** | **Leg 194 Executed** \| SL ₹42.00 active |

---

## 🎯 Stop-Loss Rules & Calculation

- **Manual Rupee Stop-Loss:** Agar aapne manual SL enter kiya hai (jaise Anchor ₹39 par **SL = ₹42**), toh system manual SL ko 100% preserve karega.
- **Default Rule (+25%):** Agar manual SL blank choda jata hai, tabhi default **+25%** rule lagta hai (e.g. ₹39 Anchor ➔ SL = ₹48.75).

---

## 💡 Is System Ke 4 Bade Fayde

1. **🛡️ Double Stop-Loss Se Bachat:** Sudden spike me fast re-entry se hone wale losses se 100% protection.
2. **💰 Behtar Entry Price:** Anchor ₹39 tha, confirm hone ke baad ₹36.50 par fresh sell mila.
3. **🔒 Realized Profit Lock:** Pehli leg ka +₹6,064.50 profit safe lock ho chuka hai.
4. **⚡ 100% Automated & Disciplined:** Emotion-free mechanical execution.
