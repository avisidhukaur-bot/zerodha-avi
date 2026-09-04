"""
equity_200dma_engine.py -- Zerodha OS | Equity 200 DMA Monitor Engine
=============================================================================
Monitors long-term Equity stocks held in Zerodha (including 100% Pledged / Collateral holdings).
Calculates 100% exact 200 Days Moving Average (200 DMA) from Zerodha Kite historical daily candles.
Excludes Gold assets & Liquid cash ETFs from 200 DMA alerts.
Runs automatically twice daily (10:00 AM & 2:00 PM IST) and sends Telegram Emergency Alerts when LTP < 200 DMA.
"""

import os
import sys
import time
import json
import sqlite3
import pandas as pd
import numpy as np
import streamlit as st
from datetime import datetime, timedelta
import pytz

import config as cfg
import db

IST = pytz.timezone("Asia/Kolkata")


def _ist_now() -> str:
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")


def init_equity_db():
    """Ensures equity_holdings table exists in zerodha_trader.db."""
    conn = sqlite3.connect(cfg.DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS equity_holdings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tradingsymbol TEXT UNIQUE NOT NULL,
                name TEXT DEFAULT '',
                asset_category TEXT DEFAULT 'EQUITY',
                quantity INTEGER DEFAULT 0,
                average_price REAL DEFAULT 0.0,
                last_price REAL DEFAULT 0.0,
                dma_200 REAL DEFAULT 0.0,
                last_updated TEXT DEFAULT ''
            )
        """)
    conn.close()


def clear_all_holdings():
    """Wipes all holdings from SQLite database."""
    init_equity_db()
    conn = sqlite3.connect(cfg.DB_PATH, check_same_thread=False)
    with conn:
        conn.execute("DELETE FROM equity_holdings")
    conn.close()


def save_holding(tradingsymbol: str, name: str, category: str, qty: int, avg_price: float, ltp: float = 0.0, dma: float = 0.0):
    """Inserts or updates a holding in SQLite database."""
    init_equity_db()
    conn = sqlite3.connect(cfg.DB_PATH, check_same_thread=False)
    ts_upper = tradingsymbol.strip().upper()
    now_str = _ist_now()
    with conn:
        conn.execute("""
            INSERT INTO equity_holdings (tradingsymbol, name, asset_category, quantity, average_price, last_price, dma_200, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(tradingsymbol) DO UPDATE SET
                name = EXCLUDED.name,
                asset_category = EXCLUDED.asset_category,
                quantity = EXCLUDED.quantity,
                average_price = EXCLUDED.average_price,
                last_price = CASE WHEN EXCLUDED.last_price > 0 THEN EXCLUDED.last_price ELSE last_price END,
                dma_200 = CASE WHEN EXCLUDED.dma_200 > 0 THEN EXCLUDED.dma_200 ELSE dma_200 END,
                last_updated = EXCLUDED.last_updated
        """, (ts_upper, name, category, qty, avg_price, ltp, dma, now_str))
    conn.close()


def delete_holding(tradingsymbol: str):
    """Deletes a single holding from SQLite database."""
    init_equity_db()
    conn = sqlite3.connect(cfg.DB_PATH, check_same_thread=False)
    with conn:
        conn.execute("DELETE FROM equity_holdings WHERE tradingsymbol = ?", (tradingsymbol.strip().upper(),))
    conn.close()


def get_stored_holdings() -> list:
    """Returns list of stored holdings dicts from SQLite database."""
    init_equity_db()
    conn = sqlite3.connect(cfg.DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM equity_holdings ORDER BY asset_category DESC, tradingsymbol ASC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def categorize_holding(symbol: str, name: str = "") -> str:
    """Detects whether asset is GOLD, LIQUID, or EQUITY stock."""
    s_up = symbol.upper()
    n_up = name.upper()
    
    liquid_keywords = ["LIQUID", "LIQUIDBEES", "LIQUIDCASE", "LIQUIDETF", "SETFLIQUID", "CASH"]
    for kw in liquid_keywords:
        if kw in s_up or kw in n_up:
            return "LIQUID"

    gold_keywords = ["GOLD", "GOLDBEES", "GOLDETF", "SGB", "SOVEREIGN", "SGBAUG", "SGBSEP", "SGBNOV", "SGBDEC", "SGBJAN", "SGBFEB", "SGBMAR", "SGBMAY", "SGBJUN", "SGBJUL", "SETFGOLD", "AXISGOLD", "HDFCGOLD"]
    for kw in gold_keywords:
        if kw in s_up or kw in n_up:
            return "GOLD"
            
    return "EQUITY"


def fetch_200dma_from_kite(kite_client, instrument_token: int) -> tuple[float, float]:
    """
    Fetches daily candles for past 400 calendar days via Zerodha Kite Connect API.
    Calculates exact 200-day Simple Moving Average (200 DMA) from the last 200 completed daily close prices.
    Returns (latest_ltp, dma_200). Returns (0.0, 0.0) if failed.
    """
    try:
        to_date = datetime.now()
        from_date = to_date - timedelta(days=400)
        candles = kite_client.historical_data(
            instrument_token=instrument_token,
            from_date=from_date.strftime("%Y-%m-%d"),
            to_date=to_date.strftime("%Y-%m-%d"),
            interval="day"
        )
        if not candles or len(candles) < 50:
            return 0.0, 0.0
        
        df = pd.DataFrame(candles)
        if "close" not in df.columns or df["close"].empty:
            return 0.0, 0.0
            
        latest_ltp = float(df["close"].iloc[-1])
        window = min(len(df), 200)
        dma_200 = float(df["close"].iloc[-window:].mean())
        return round(latest_ltp, 2), round(dma_200, 2)
    except Exception as e:
        print(f"[EQUITY_200DMA] Kite historical fetch failed for token {instrument_token}: {e}")
        return 0.0, 0.0


def fetch_200dma_from_yfinance(symbol: str) -> tuple[float, float]:
    """
    Fallback 200 DMA fetch via yfinance when Kite API is unavailable.
    Uses auto_adjust=False to prevent dividend distortions on historical candles.
    """
    try:
        import yfinance as yf
        ticker_sym = symbol if "." in symbol else f"{symbol}.NS"
        ticker = yf.Ticker(ticker_sym)
        df = ticker.history(period="2y", auto_adjust=False)
        if df.empty or len(df) < 50:
            return 0.0, 0.0
        
        close_prices = df["Close"].dropna()
        latest_ltp = float(close_prices.iloc[-1])
        window = min(len(close_prices), 200)
        dma_200 = float(close_prices.iloc[-window:].mean())
        
        return round(latest_ltp, 2), round(dma_200, 2)
    except Exception as e:
        print(f"[EQUITY_200DMA] yfinance fallback fetch failed for {symbol}: {e}")
        return 0.0, 0.0


def sync_holdings_from_zerodha():
    """
    Queries live Zerodha Kite Connect API for holdings (kite.holdings()).
    Properly includes ALL free quantity, T1 quantity, and PLEDGED/COLLATERAL quantity!
    Updates SQLite database with fresh real holdings, quantities, avg prices, LTP, and exact 200 DMAs.
    """
    try:
        from kite_executor import kite_executor
        if not kite_executor.ensure_logged_in():
            print("[EQUITY_200DMA] Kite not logged in. Cannot auto-sync holdings.")
            return False, "Zerodha Kite login expired or credentials not active. Please click 'Zerodha Kite Login' in sidebar first."
        
        holdings = kite_executor.kite.holdings()
        if not holdings:
            return True, "Zerodha API connected, but 0 holdings were returned."
        
        # Clear old data before saving fresh real holdings
        clear_all_holdings()
        
        synced_count = 0
        for h in holdings:
            symbol = h.get("tradingsymbol", "")
            if not symbol:
                continue
            name = h.get("company_name", symbol)
            
            # FULL QUANTITY: Free quantity + T1 delivery + Collateral (Pledged for margin) + Pledged in CDSL
            free_qty = int(h.get("quantity", 0) or 0)
            t1_qty = int(h.get("t1_quantity", 0) or 0)
            collateral_qty = int(h.get("collateral_quantity", 0) or 0)
            pledged_qty = int(h.get("pledged_quantity", 0) or 0)
            total_qty = free_qty + t1_qty + collateral_qty + pledged_qty
            
            if total_qty <= 0:
                continue
                
            avg_price = float(h.get("average_price", 0.0) or 0.0)
            ltp = float(h.get("last_price", 0.0) or 0.0)
            inst_token = h.get("instrument_token")
            category = categorize_holding(symbol, name)
            
            dma = 0.0
            # Only calculate 200 DMA for EQUITY assets (Gold and Liquid ETFs excluded as requested)
            if category == "EQUITY":
                if inst_token:
                    _, dma = fetch_200dma_from_kite(kite_executor.kite, inst_token)
                if dma == 0.0:
                    _, dma = fetch_200dma_from_yfinance(symbol)
                
            save_holding(symbol, name, category, total_qty, avg_price, ltp, dma)
            synced_count += 1
            
        db.set("equity_last_sync", _ist_now())
        return True, f"Successfully synced {synced_count} holdings (including pledged/collateral) from Zerodha Kite!"
    except Exception as e:
        print(f"[EQUITY_200DMA] Holdings sync error: {e}")
        return False, f"Sync failed: {e}"


def refresh_all_200dma():
    """Recalculates 200 DMA for all stored holdings directly using Kite API where possible."""
    holdings = get_stored_holdings()
    if not holdings:
        return
    
    from kite_executor import kite_executor
    has_kite = kite_executor.ensure_logged_in()
    
    for h in holdings:
        symbol = h["tradingsymbol"]
        category = h["asset_category"]
        
        # Skip 200 DMA calculation for GOLD and LIQUID assets
        if category in ("GOLD", "LIQUID"):
            continue
            
        ltp, dma = 0.0, 0.0
        if has_kite:
            try:
                # Try quote/LTP from Kite
                q = kite_executor.kite.quote([f"NSE:{symbol}"])
                if f"NSE:{symbol}" in q:
                    inst_token = q[f"NSE:{symbol}"].get("instrument_token")
                    ltp = float(q[f"NSE:{symbol}"].get("last_price", 0.0))
                    if inst_token:
                        _, dma = fetch_200dma_from_kite(kite_executor.kite, inst_token)
            except Exception:
                pass
                
        if dma == 0.0:
            ltp_yf, dma_yf = fetch_200dma_from_yfinance(symbol)
            if ltp == 0.0:
                ltp = ltp_yf
            dma = dma_yf
            
        cur_ltp = ltp if ltp > 0 else h["last_price"]
        cur_dma = dma if dma > 0 else h["dma_200"]
        
        save_holding(
            tradingsymbol=symbol,
            name=h["name"],
            category=category,
            qty=h["quantity"],
            avg_price=h["average_price"],
            ltp=cur_ltp,
            dma=cur_dma
        )


def run_scheduled_equity_scan(scan_label: str = "Scheduled 200 DMA Scan") -> dict:
    """
    Runs full automated equity holdings sync, calculates Kite 200 DMA for all equity stocks,
    and sends Telegram emergency alerts if any equity holding is trading below 200 DMA.
    Called automatically at 10:00 AM IST and 2:00 PM IST by main.py.
    """
    print(f"[EQUITY_200DMA] Starting {scan_label} at {_ist_now()}...")
    ok, msg = sync_holdings_from_zerodha()
    if not ok:
        print(f"[EQUITY_200DMA] Sync warning during {scan_label}: {msg}")
        
    analysis = get_equity_analysis()
    red_alerts = analysis.get("red_alerts", [])
    equity_items = [it for it in analysis.get("items", []) if it.get("category") == "EQUITY"]
    total_equity_count = len(equity_items)
    
    if red_alerts:
        print(f"[EQUITY_200DMA] ALERT: {len(red_alerts)} equity holding(s) below 200 DMA. Sending emergency Telegram alert...")
        try:
            import telegram_bot as tg
            tg.alert_equity_200dma_breach(
                red_alerts=red_alerts,
                total_count=total_equity_count,
                scan_time_label=scan_label
            )
        except Exception as e:
            print(f"[EQUITY_200DMA] Error sending Telegram alert: {e}")
    else:
        print(f"[EQUITY_200DMA] All {total_equity_count} equity holdings are trading SAFELY above 200 DMA.")
        
    db.set("equity_last_auto_scan", _ist_now())
    db.set("equity_last_auto_scan_label", scan_label)
    return analysis


def load_demo_samples():
    """Populates sample demo holdings if user wants to see demo data."""
    default_samples = [
        {"tradingsymbol": "RELIANCE", "name": "Reliance Industries Ltd", "asset_category": "EQUITY", "quantity": 50, "average_price": 2400.0, "last_price": 2350.0, "dma_200": 2480.0},
        {"tradingsymbol": "GOLDBEES", "name": "Nippon India ETF Gold BeES", "asset_category": "GOLD", "quantity": 1000, "average_price": 55.0, "last_price": 62.5, "dma_200": 0.0},
        {"tradingsymbol": "TATAMOTORS", "name": "Tata Motors Ltd", "asset_category": "EQUITY", "quantity": 100, "average_price": 650.0, "last_price": 710.0, "dma_200": 680.0},
        {"tradingsymbol": "INFY", "name": "Infosys Ltd", "asset_category": "EQUITY", "quantity": 75, "average_price": 1450.0, "last_price": 1390.0, "dma_200": 1420.0},
    ]
    for s in default_samples:
        save_holding(s["tradingsymbol"], s["name"], s["asset_category"], s["quantity"], s["average_price"], s["last_price"], s["dma_200"])


def get_equity_analysis() -> dict:
    """
    Analyzes stored holdings (including pledged holdings):
    - Calculates current LTP vs 200 DMA for EQUITY stocks.
    - Excludes GOLD and LIQUID assets from 200 DMA triggers.
    - Generates 🟢 GREEN (LTP >= 200 DMA) or 🔴 RED (LTP < 200 DMA) signals.
    - Computes summary metrics & returns red alert list.
    """
    holdings = get_stored_holdings()
    
    results = []
    red_alerts = []
    green_count = 0
    red_count = 0
    total_invested = 0.0
    total_current = 0.0

    for h in holdings:
        symbol = h["tradingsymbol"]
        qty = h["quantity"]
        avg_price = h["average_price"]
        ltp = h["last_price"]
        dma = h["dma_200"]
        category = h["asset_category"]

        invested_val = qty * avg_price
        current_val = qty * ltp if ltp > 0 else invested_val
        pnl = current_val - invested_val
        pnl_pct = (pnl / invested_val * 100) if invested_val > 0 else 0.0

        total_invested += invested_val
        total_current += current_val

        # Non-equity exclusion logic
        if category == "GOLD":
            signal = "GOLD"
            status_text = "🟡 Gold Asset (200 DMA Excluded)"
            recommendation = "Long-Term Hedge / Hold"
            dma_diff = 0.0
            dma_diff_pct = 0.0
        elif category == "LIQUID":
            signal = "LIQUID"
            status_text = "💧 Liquid / Cash Asset (200 DMA Excluded)"
            recommendation = "Margin Collateral / Cash"
            dma_diff = 0.0
            dma_diff_pct = 0.0
        else:
            dma_diff = ltp - dma if (ltp > 0 and dma > 0) else 0.0
            dma_diff_pct = (dma_diff / dma * 100) if dma > 0 else 0.0

            # Signal logic for EQUITY: RED if LTP < 200 DMA
            if dma > 0 and ltp > 0 and ltp < dma:
                signal = "RED"
                status_text = "🔴 Below 200 DMA Benchmark"
                recommendation = "Trend Warning / Review"
                red_count += 1
                red_alerts.append({
                    "symbol": symbol,
                    "name": h["name"],
                    "category": category,
                    "ltp": ltp,
                    "dma_200": dma,
                    "diff": dma_diff,
                    "diff_pct": dma_diff_pct
                })
            elif dma > 0 and ltp > 0 and ltp >= dma:
                signal = "GREEN"
                status_text = "🟢 Above 200 DMA Benchmark"
                recommendation = "Healthy Bullish Trend"
                green_count += 1
            else:
                signal = "NEUTRAL"
                status_text = "⚪ PENDING 200 DMA"
                recommendation = "FETCHING DATA"

        results.append({
            "symbol": symbol,
            "name": h["name"],
            "category": category,
            "qty": qty,
            "avg_price": avg_price,
            "ltp": ltp,
            "dma_200": dma,
            "dma_diff": dma_diff,
            "dma_diff_pct": dma_diff_pct,
            "invested_val": invested_val,
            "current_val": current_val,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "signal": signal,
            "status_text": status_text,
            "recommendation": recommendation,
            "last_updated": h["last_updated"]
        })

    total_pnl = total_current - total_invested
    total_pnl_pct = (total_pnl / total_invested * 100) if total_invested > 0 else 0.0

    return {
        "items": results,
        "red_alerts": red_alerts,
        "total_count": len(results),
        "green_count": green_count,
        "red_count": red_count,
        "total_invested": total_invested,
        "total_current": total_current,
        "total_pnl": total_pnl,
        "total_pnl_pct": total_pnl_pct
    }


def render_global_red_alert_banner():
    """
    Renders a clean native Streamlit advisory banner when equity holdings are below 200 DMA.
    """
    data = get_equity_analysis()
    red_alerts = data.get("red_alerts", [])
    
    if not red_alerts:
        return

    st.error(
        f"⚠️ **PORTFOLIO TREND ADVISORY: {len(red_alerts)} Equity Holding(s) Below 200 DMA Benchmark**\n\n"
        "The following equity holding(s) are currently trading below their 200-day moving average. "
        "Please review their trend metrics below:"
    )

    for r in red_alerts:
        c1, c2, c3, c4 = st.columns([2, 1.5, 2, 2])
        with c1:
            st.markdown(f"🔴 **{r['symbol']}**")
        with c2:
            st.markdown(f"**LTP:** ₹{r['ltp']:,.2f}")
        with c3:
            st.markdown(f"**200 DMA:** ₹{r['dma_200']:,.2f}")
        with c4:
            st.markdown(f"**Variance:** ₹{r['diff']:,.2f} ({r['diff_pct']:.2f}%)")

    st.markdown("---")


def render_equity_tab():
    """Renders Page 3: Equity Portfolio 200 DMA Monitor Tab UI."""
    last_auto_scan = db.get("equity_last_auto_scan", "Never")
    
    st.markdown(f"""
    <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;'>
        <div>
            <h2 style='margin:0;color:#1e293b;font-size:1.5rem;font-weight:800;'>📊 Equity Portfolio — 200 DMA Monitor</h2>
            <p style='margin:0;color:#64748b;font-size:0.85rem;'>Includes Free & Pledged/Collateral holdings. Automated twice-daily scan (10:00 AM & 2:00 PM IST).</p>
        </div>
        <div style='text-align:right;'>
            <span style='background:#f0fdf4;border:1px solid #16a34a;color:#15803d;padding:4px 10px;border-radius:6px;font-size:0.8rem;font-weight:700;'>
                ⚡ Auto Scan: 10:00 AM & 2:00 PM IST
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Action bar (Sync, Refresh, Clear buttons)
    col_act1, col_act2, col_act3, col_act4 = st.columns([2.5, 2.5, 2, 2])
    with col_act1:
        if st.button("🔄 Sync Zerodha Holdings (Live Kite)", key="btn_sync_zerodha", use_container_width=True, type="primary"):
            with st.spinner("Connecting to Zerodha Kite to fetch all live & pledged holdings..."):
                ok, msg = sync_holdings_from_zerodha()
                if ok:
                    st.success(msg)
                else:
                    st.warning(msg)
                st.rerun()

    with col_act2:
        if st.button("📈 Recalculate 200 DMAs", key="btn_recalc_dma", use_container_width=True):
            with st.spinner("Fetching 200-day Kite price history for all equity stocks..."):
                refresh_all_200dma()
                st.success("200 DMA prices updated successfully!")
                st.rerun()

    with col_act3:
        if st.button("🗑️ Clear Stored Data", key="btn_clear_holdings", use_container_width=True):
            clear_all_holdings()
            st.info("Stored holdings cleared. Click 'Sync Zerodha Holdings' to fetch live account holdings.")
            st.rerun()

    with col_act4:
        last_sync = db.get("equity_last_sync", "Never")
        st.markdown(f"<p style='font-size:0.78rem;color:#64748b;margin-top:2px;text-align:right;'><b>Last Sync</b>: {last_sync}<br/><b>Last Auto</b>: {last_auto_scan}</p>", unsafe_allow_html=True)

    st.markdown("<br/>", unsafe_allow_html=True)

    # Fetch fresh analysis data
    analysis = get_equity_analysis()
    items = analysis["items"]

    if not items:
        st.info("💡 **No holdings stored yet.**\n\n- Click **'🔄 Sync Zerodha Holdings (Live Kite)'** to fetch your real portfolio holdings from Zerodha.\n- Or add stocks manually using the form below.")
        
        if st.button("📥 Load Sample Demo Data (for testing)", key="btn_load_demo_data"):
            load_demo_samples()
            st.success("Sample demo data loaded!")
            st.rerun()
            
        st.markdown("<br/>", unsafe_allow_html=True)

    # Metrics Summary Row
    mcol1, mcol2, mcol3, mcol4, mcol5 = st.columns(5)
    with mcol1:
        st.markdown(f"""
        <div style='background:#ffffff;border:1px solid #cbd5e1;border-radius:10px;padding:12px;text-align:center;'>
            <div style='font-size:0.72rem;color:#64748b;font-weight:700;text-transform:uppercase;'>Total Holdings</div>
            <div style='font-size:1.5rem;font-weight:800;color:#0f172a;'>{analysis['total_count']}</div>
        </div>
        """, unsafe_allow_html=True)

    with mcol2:
        st.markdown(f"""
        <div style='background:#ffffff;border:1px solid #cbd5e1;border-radius:10px;padding:12px;text-align:center;'>
            <div style='font-size:0.72rem;color:#64748b;font-weight:700;text-transform:uppercase;'>Invested Value</div>
            <div style='font-size:1.3rem;font-weight:800;color:#1e293b;font-family:monospace;'>₹{analysis['total_invested']:,.2f}</div>
        </div>
        """, unsafe_allow_html=True)

    with mcol3:
        st.markdown(f"""
        <div style='background:#ffffff;border:1px solid #cbd5e1;border-radius:10px;padding:12px;text-align:center;'>
            <div style='font-size:0.72rem;color:#64748b;font-weight:700;text-transform:uppercase;'>Current Value</div>
            <div style='font-size:1.3rem;font-weight:800;color:#1e293b;font-family:monospace;'>₹{analysis['total_current']:,.2f}</div>
        </div>
        """, unsafe_allow_html=True)

    with mcol4:
        pnl_color = "#166534" if analysis['total_pnl'] >= 0 else "#991b1b"
        pnl_bg = "#f0fdf4" if analysis['total_pnl'] >= 0 else "#fef2f2"
        st.markdown(f"""
        <div style='background:{pnl_bg};border:1px solid {pnl_color};border-radius:10px;padding:12px;text-align:center;'>
            <div style='font-size:0.72rem;color:{pnl_color};font-weight:700;text-transform:uppercase;'>Total Return P&L</div>
            <div style='font-size:1.3rem;font-weight:800;color:{pnl_color};font-family:monospace;'>
                {"+" if analysis['total_pnl'] >= 0 else ""}₹{analysis['total_pnl']:,.2f} ({analysis['total_pnl_pct']:.2f}%)
            </div>
        </div>
        """, unsafe_allow_html=True)

    with mcol5:
        st.markdown(f"""
        <div style='background:#ffffff;border:1px solid #cbd5e1;border-radius:10px;padding:12px;text-align:center;'>
            <div style='font-size:0.72rem;color:#64748b;font-weight:700;text-transform:uppercase;'>Equity 200 DMA Status</div>
            <div style='font-size:1.2rem;font-weight:800;margin-top:2px;'>
                <span style='color:#166534;'>🟢 {analysis['green_count']} OK</span> &nbsp;|&nbsp; 
                <span style='color:#991b1b;'>🔴 {analysis['red_count']} ALERT</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br/>", unsafe_allow_html=True)

    # Detailed Table of Holdings
    if items:
        st.markdown("### 📋 Holdings & 200 DMA Breakdown")

        table_rows = []
        for it in items:
            if it["category"] == "GOLD":
                sig_badge = "🟡 GOLD (Tracked for P&L)"
                dma_str = "N/A (Excluded)"
                dma_diff_str = "--"
            elif it["category"] == "LIQUID":
                sig_badge = "💧 LIQUID / CASH"
                dma_str = "N/A (Excluded)"
                dma_diff_str = "--"
            else:
                sig_badge = f"🟢 ABOVE 200 DMA" if it["signal"] == "GREEN" else f"🔴 BELOW 200 DMA" if it["signal"] == "RED" else "⚪ PENDING"
                dma_str = f"₹{it['dma_200']:,.2f}" if it['dma_200'] > 0 else "--"
                dma_diff_str = f"{'+' if it['dma_diff'] >= 0 else ''}₹{it['dma_diff']:,.2f} ({it['dma_diff_pct']:.2f}%)" if it['dma_200'] > 0 else "--"
                
            pnl_str = f"{'+' if it['pnl'] >= 0 else ''}₹{it['pnl']:,.2f} ({it['pnl_pct']:.2f}%)"
            
            table_rows.append({
                "Symbol": it["symbol"],
                "Category": it["category"],
                "Total Qty": it["qty"],
                "Avg Price": f"₹{it['avg_price']:,.2f}",
                "Current LTP": f"₹{it['ltp']:,.2f}",
                "200 DMA": dma_str,
                "LTP vs 200 DMA": dma_diff_str,
                "Invested Value": f"₹{it['invested_val']:,.2f}",
                "Current Value": f"₹{it['current_val']:,.2f}",
                "Total P&L": pnl_str,
                "Signal Status": sig_badge,
                "Action Recommendation": it["recommendation"]
            })

        df_table = pd.DataFrame(table_rows)
        st.dataframe(df_table, use_container_width=True, hide_index=True)

    st.markdown("<br/>", unsafe_allow_html=True)

    # Manual Add / Edit Holding Form
    with st.expander("➕ Add / Modify Equity Holding (Manual Entry)", expanded=False):
        col_f1, col_f2, col_f3, col_f4 = st.columns(4)
        with col_f1:
            in_symbol = st.text_input("Trading Symbol (e.g. RELIANCE, TCS, INFY)", key="in_eq_symbol").strip().upper()
        with col_f2:
            in_cat = st.selectbox("Category", options=["EQUITY", "GOLD", "LIQUID"], key="in_eq_cat")
        with col_f3:
            in_qty = st.number_input("Quantity", min_value=1, value=10, key="in_eq_qty")
        with col_f4:
            in_avg = st.number_input("Average Price (Rs)", min_value=0.1, value=100.0, step=1.0, key="in_eq_avg")

        col_fb1, col_fb2 = st.columns([3, 3])
        with col_fb1:
            if st.button("💾 Save Holding", key="btn_save_manual_eq", type="primary", use_container_width=True):
                if not in_symbol:
                    st.error("Please enter a valid trading symbol.")
                else:
                    ltp, dma = 0.0, 0.0
                    if in_cat == "EQUITY":
                        from kite_executor import kite_executor
                        if kite_executor.ensure_logged_in():
                            try:
                                q = kite_executor.kite.quote([f"NSE:{in_symbol}"])
                                if f"NSE:{in_symbol}" in q:
                                    inst_token = q[f"NSE:{in_symbol}"].get("instrument_token")
                                    ltp = float(q[f"NSE:{in_symbol}"].get("last_price", 0.0))
                                    if inst_token:
                                        _, dma = fetch_200dma_from_kite(kite_executor.kite, inst_token)
                            except Exception:
                                pass
                        if dma == 0.0:
                            ltp, dma = fetch_200dma_from_yfinance(in_symbol)
                    else:
                        ltp, _ = fetch_200dma_from_yfinance(in_symbol)
                        
                    save_holding(in_symbol, in_symbol, in_cat, in_qty, in_avg, ltp, dma)
                    st.success(f"Saved {in_symbol} to monitor list!")
                    st.rerun()

        with col_fb2:
            if st.button("🗑️ Delete Holding", key="btn_del_manual_eq", use_container_width=True):
                if not in_symbol:
                    st.error("Please enter a valid trading symbol to delete.")
                else:
                    delete_holding(in_symbol)
                    st.success(f"Removed {in_symbol} from monitor list!")
                    st.rerun()
