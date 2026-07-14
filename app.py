"""
app.py -- Zerodha OptionSelling Engine | Brick 6
==============================================
Reference: memory.md
Version  : 2.0 BASE MODEL (Brick 6)
Date     : June 2026

Streamlit Dashboard — VPS Port 9007
Run: streamlit run app.py --server.port 9007

SECTIONS:
  Header      -- System status bar (mode, algo, lot size, portfolio P&L)
  Sidebar     -- Settings + Controls + Test buttons
  Main Area   -- Block cards with strike tables + P&L
  New Block   -- Form to create a new expiry block
  New Strike  -- Form to add strikes + link hedges
  Execute     -- Execute block / individual strike buttons
  Close       -- Close strike + hedge together
  Trade History -- Full log of entries / exits
"""

import sys
import time
import streamlit as st
from streamlit_autorefresh import st_autorefresh
import pandas as pd
from datetime import date, datetime
import pytz

# Force UTF-8 on Windows terminals
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import db
import commodity_executor as comm_exec  # MCX Commodity Engine

import config as cfg
import block_manager as bm
import pnl_engine as pe
import telegram_bot as tg
import threading
import main

# Start background trading engine thread once
@st.cache_resource
def start_trading_engine():
    engine_thread = threading.Thread(target=main.start_engine_loop, daemon=True)
    engine_thread.start()
    return "Engine Started"

start_trading_engine()

IST = pytz.timezone("Asia/Kolkata")

# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title       = "Zerodha OptionSelling Engine",
    page_icon        = "📈",
    layout           = "wide",
    initial_sidebar_state = "expanded",
    menu_items       = {
        "Get Help"    : None,
        "Report a bug": None,
        "About"       : "Zerodha OptionSelling Engine v1.01 | Port 9007 | NIFTY Only",
    }
)

# ─────────────────────────────────────────────────────────────────────────────
# CUSTOM CSS — Premium Zerodha Orange Gradient Style
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

/* ── Root / Background: Premium Light Orange Gradient ── */
html, body, [data-testid="stAppViewContainer"] {
    background: linear-gradient(135deg, #fff5f0 0%, #fafafa 100%) !important;
    color: #0f172a !important;
    font-family: 'Inter', sans-serif;
}
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1f1f2e 0%, #111119 100%) !important;
    border-right: 1px solid #2d2d3d;
}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {
    color: #f8fafc !important;
}
[data-testid="stSidebar"] p {
    color: #cbd5e1 !important;
}

/* ── Header bar ── */
.zerodha-header {
    background: linear-gradient(135deg, #ff5722 0%, #f4511e 50%, #d84315 100%);
    border: 1px solid #ff5722;
    border-radius: 12px;
    padding: 16px 24px;
    margin-bottom: 16px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    box-shadow: 0 4px 6px -1px rgba(255, 87, 34, 0.2);
}
.zerodha-title {
    font-size: 1.5rem;
    font-weight: 700;
    color: #ffffff;
    letter-spacing: 0.5px;
}
.zerodha-subtitle {
    font-size: 0.75rem;
    color: #ffe0b2;
    margin-top: 2px;
}

/* ── Status pills ── */
.status-pill {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.3px;
}
.pill-live    { background:#dcfce7; color:#166534; border:1px solid #bbf7d0; }
.pill-on      { background:#dcfce7; color:#166534; border:1px solid #bbf7d0; }
.pill-off     { background:#fee2e2; color:#991b1b; border:1px solid #fecaca; }
.pill-active  { background:#fff3e0; color:#e65100; border:1px solid #ffe0b2; }
.pill-expired { background:#fef3c7; color:#92400e; border:1px solid #fde68a; }
.pill-closed  { background:#f1f5f9; color:#475569; border:1px solid #e2e8f0; }

/* ── Metric cards ── */
.metric-card {
    background: rgba(255, 255, 255, 0.85);
    border: 1px solid rgba(255, 87, 34, 0.2);
    border-radius: 10px;
    padding: 14px 18px;
    margin: 4px 0;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
}
.metric-label {
    font-size: 0.72rem;
    color: #475569;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    font-weight: 600;
}
.metric-value {
    font-size: 1.4rem;
    font-weight: 700;
    font-family: 'JetBrains Mono', monospace;
    margin-top: 4px;
}
.metric-profit { color: #166534; }
.metric-loss   { color: #991b1b; }
.metric-neutral{ color: #0f172a; }

/* ── Block cards ── */
.block-card {
    background: rgba(255, 255, 255, 0.85);
    border: 1px solid rgba(255, 87, 34, 0.2);
    border-radius: 12px;
    padding: 0;
    margin-bottom: 20px;
    overflow: hidden;
    box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.05);
}
.block-header {
    background: linear-gradient(90deg, #fff3e0 0%, #f1f5f9 100%);
    padding: 12px 18px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid rgba(255, 87, 34, 0.15);
}
.block-title {
    font-size: 1.0rem;
    font-weight: 700;
    color: #e65100;
}
.block-expiry {
    font-size: 0.80rem;
    color: #f4511e;
}
.block-pnl-positive {
    font-size: 1.1rem;
    font-weight: 700;
    font-family: 'JetBrains Mono', monospace;
    color: #166534;
}
.block-pnl-negative {
    font-size: 1.1rem;
    font-weight: 700;
    font-family: 'JetBrains Mono', monospace;
    color: #991b1b;
}

/* ── Strike tables ── */
.dataframe { font-family: 'JetBrains Mono', monospace !important; font-size: 0.82rem; }

/* ── Buttons ── */
.stButton > button {
    background: linear-gradient(135deg, #ff5722 0%, #f4511e 100%) !important;
    color: #ffffff !important;
    border: 1px solid #ff5722 !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    transition: all 0.2s ease;
    box-shadow: 0 2px 4px rgba(255, 87, 34, 0.2) !important;
}
.stButton > button:hover {
    background: linear-gradient(135deg, #f4511e 0%, #d84315 100%) !important;
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(255, 87, 34, 0.4) !important;
}
.btn-danger > button {
    background: linear-gradient(135deg, #b91c1c 0%, #991b1b 100%) !important;
    border-color: #b91c1c !important;
    color: #ffffff !important;
}
.btn-danger > button:hover {
    background: #7f1d1d !important;
}
.btn-success > button {
    background: linear-gradient(135deg, #15803d 0%, #166534 100%) !important;
    border-color: #15803d !important;
    color: #ffffff !important;
}
.btn-success > button:hover {
    background: #14532d !important;
}

/* ── Forms ── */
.stTextInput > div > div > input,
.stNumberInput > div > div > input,
.stSelectbox > div > div > div {
    background: #ffffff !important;
    border: 1px solid #cbd5e1 !important;
    color: #0f172a !important;
    border-radius: 8px !important;
}

/* ── Expander ── */
.streamlit-expanderHeader {
    background: rgba(255, 255, 255, 0.8) !important;
    border: 1px solid rgba(255, 87, 34, 0.2) !important;
    border-radius: 8px !important;
    color: #0f172a !important;
    font-weight: 600 !important;
}

/* ── Section headers ── */
.section-title {
    font-size: 0.85rem;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    color: #475569;
    font-weight: 700;
    margin: 12px 0 8px 0;
    border-bottom: 2px solid rgba(255, 87, 34, 0.2);
    padding-bottom: 6px;
}

/* ── Trade log ── */
.trade-entry  { color: #166534; font-weight: 600; }
.trade-exit   { color: #d97706; font-weight: 600; }
.trade-hedge  { color: #f4511e; font-weight: 600; }
.trade-failed { color: #991b1b; font-weight: 600; }

/* ── Divider ── */
hr { border-color: rgba(255, 87, 34, 0.2) !important; }

/* ── Alert boxes ── */
.stAlert { border-radius: 8px !important; }

/* ── Sidebar styling ── */
[data-testid="stSidebar"] .stMarkdown h3 {
    color: #ffcc80;
    font-size: 0.85rem;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-top: 16px;
}

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #f1f5f9; }
::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #94a3b8; }
.trade-hedge  { color: #0284c7; font-weight: 600; }
.trade-failed { color: #991b1b; font-weight: 600; }

/* ── Divider ── */
hr { border-color: rgba(14, 165, 233, 0.2) !important; }

/* ── Alert boxes ── */
.stAlert { border-radius: 8px !important; }

/* ── Sidebar styling ── */
[data-testid="stSidebar"] .stMarkdown h3 {
    color: #bae6fd;
    font-size: 0.85rem;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-top: 16px;
}

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #f1f5f9; }
::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #94a3b8; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────────────────────────────────────
def _init_state():
    defaults = {
        "last_refresh"    : 0,
        "portfolio_pnl"   : None,
        "selected_block"  : None,
        "add_strike_block": None,
        "show_trade_log"  : False,
        "action_msg"      : None,
        "action_type"     : "info",  # info | success | error | warning
        "sim_pnl"         : False,   # Show simulated P&L in paper mode
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def _ist_now() -> str:
    return datetime.now(IST).strftime("%H:%M:%S")


def _flash(msg: str, msg_type: str = "info") -> None:
    st.session_state["action_msg"]  = msg
    st.session_state["action_type"] = msg_type


def _show_flash() -> None:
    msg  = st.session_state.get("action_msg")
    mtype = st.session_state.get("action_type", "info")
    if msg:
        if mtype == "success": st.success(msg, icon="✅")
        elif mtype == "error": st.error(msg, icon="❌")
        elif mtype == "warning": st.warning(msg, icon="⚠️")
        else: st.info(msg, icon="ℹ️")
        st.session_state["action_msg"] = None


# ─────────────────────────────────────────────────────────────────────────────
# ACTION CALLBACKS (Prevents Streamlit double-click issues)
# ─────────────────────────────────────────────────────────────────────────────

def cb_quick_relogin():
    from kite_executor import kite_executor as _kexec
    _kexec.access_token  = None
    _kexec.is_logged_in  = False
    _kexec.login_time    = None
    db.set("kite_access_token", "")
    db.set("kite_is_logged_in", "False")
    ok = _kexec.login()
    if ok:
        db.set("kite_login_status", "OK")
        tg.alert_login_success()
        _flash("✅ Re-login successful!", "success")
    else:
        db.set("kite_login_status", "FAILED")
        _flash("❌ Re-login failed. Use manual credentials below.", "error")

def cb_send_otp_sms():
    from kite_executor import kite_executor as _kexec
    res = _kexec.request_login_otp()
    if res:
        st.session_state["manual_login_session"] = res
        _flash("✅ OTP sent to your registered mobile/email!", "success")
    else:
        _flash("❌ Failed to request OTP. Check credentials in secrets.txt.", "error")

def cb_connect_with_totp():
    manual_otp = st.session_state.get("input_manual_totp")
    if not manual_otp or len(manual_otp) != 6 or not manual_otp.isdigit():
        _flash("Please enter a valid 6-digit code.", "error")
    else:
        from kite_executor import kite_executor as _kexec
        _kexec.access_token  = None
        _kexec.is_logged_in  = False
        _kexec.login_time    = None
        db.set("kite_access_token", "")
        db.set("kite_is_logged_in", "False")
        ok, msg = _kexec.login_with_otp(manual_otp)
        if ok:
            db.set("kite_login_status", "OK")
            tg.alert_login_success()
            _flash("✅ Login successful! Session active.", "success")
        else:
            db.set("kite_login_status", "FAILED")
            _flash(f"❌ Login failed: {msg}", "error")

def cb_verify_otp():
    manual_otp = st.session_state.get("input_manual_sms_otp")
    sent_session = st.session_state.get("manual_login_session")
    if not sent_session:
        _flash("No active login session found.", "error")
        return
    if not manual_otp or len(manual_otp) != 6 or not manual_otp.isdigit():
        _flash("Please enter a valid 6-digit OTP code.", "error")
    else:
        from kite_executor import kite_executor as _kexec
        _kexec.access_token  = None
        _kexec.is_logged_in  = False
        _kexec.login_time    = None
        db.set("kite_access_token", "")
        db.set("kite_is_logged_in", "False")
        ok, msg = _kexec.complete_login_with_otp(
            sent_session["request_id"],
            sent_session["session"],
            manual_otp,
            sent_session["twofa_type"]
        )
        if ok:
            db.set("kite_login_status", "OK")
            st.session_state.pop("manual_login_session", None)
            tg.alert_login_success()
            _flash("✅ OTP login successful! Session active.", "success")
        else:
            db.set("kite_login_status", "FAILED")
            _flash(f"❌ Verification failed: {msg}", "error")

def cb_cancel_otp():
    st.session_state.pop("manual_login_session", None)
    _flash("Session reset. You can request a new OTP now.", "info")

def cb_save_credentials(input_api_key, input_api_secret, input_client_code, input_password, input_totp, input_ntfy):
    if not input_api_key or not input_api_secret or not input_client_code or not input_password:
        _flash("Please fill all required fields (API Key, API Secret, Client Code, Password).", "error")
    else:
        save_totp = input_totp.strip() if input_totp else "YOUR_TOTP_SECRET_KEY"
        db.save_secrets_to_file({
            "KITE_API_KEY": input_api_key,
            "KITE_API_SECRET": input_api_secret,
            "KITE_CLIENT_CODE": input_client_code.strip(),
            "KITE_PASSWORD": input_password.strip(),
            "KITE_TOTP_KEY": save_totp,
            "NTFY_TOPIC": input_ntfy.strip()
        })
        _flash("✅ Credentials saved successfully! You can now use Manual OTP.", "success")
    st.session_state["login_expanded"] = True

def cb_headless_login(has_totp):
    if not has_totp:
        _flash("TOTP key is required for headless login.", "error")
        return
    from kite_executor import kite_executor as _kexec
    _kexec.access_token = None
    _kexec.is_logged_in = False
    _kexec.login_time = None
    success = _kexec.login()
    if success:
        db.set("kite_login_status", "OK")
        tg.alert_login_success()
        _flash("✅ Headless login successful! Session active.", "success")
    else:
        db.set("kite_login_status", "FAILED")
        tg.alert_login_failed("Headless credentials login failed.")
        _flash("❌ Login failed. Check your credentials and TOTP Secret.", "error")
    st.session_state["login_expanded"] = True

def cb_reconcile():
    import block_manager as bm
    reconciled = bm.reconcile_active_blocks()
    if reconciled > 0:
        _flash(f"Reconciled: {reconciled} trade(s) synced!", "success")
    else:
        _flash("DB is already fully synchronized with broker.", "info")

def cb_refresh_pnl():
    st.session_state["portfolio_pnl"] = _get_portfolio(sim=st.session_state.get("sim_pnl", False))
    st.session_state["last_refresh"]  = time.time()

def cb_send_test_tg():
    r = tg.test_telegram_connection()
    _flash(r["message"], "success" if r["ok"] else "error")

def cb_send_portfolio_summary():
    pnl  = _get_portfolio(sim=st.session_state.get("sim_pnl", False))
    sent = tg.alert_portfolio_summary(pnl)
    _flash("Portfolio summary sent to Telegram/ntfy!" if sent else "Alert channels not configured.", "success" if sent else "warning")

def cb_toggle_trade_history():
    st.session_state["show_trade_log"] = not st.session_state.get("show_trade_log", False)

def cb_close_stranded_hedge(h_strike_id):
    res = bm.close_hedge_strike_only(h_strike_id)
    if res["ok"]:
        _flash(res["message"], "success")
    else:
        _flash(res["message"], "error")

def cb_set_add_strike_block(block_id):
    st.session_state["add_strike_block"] = block_id

def cb_execute_block(block_id):
    r = bm.execute_block(block_id)
    if r["ok"]:
        _flash(r["message"], "success")
        tg.alert_engine_started()
    else:
        _flash(r["message"], "error")

def cb_close_strike(block_id):
    sel_label = st.session_state.get(f"close_sel_{block_id}")
    if not sel_label:
        _flash("No strike selected to close.", "error")
        return
    try:
        sid_str = sel_label.split("(#")[-1].replace(")", "")
        sid = int(sid_str)
    except Exception as e:
        _flash(f"Failed to parse strike ID: {e}", "error")
        return
        
    block = db.get_block(block_id)
    block_num = block["block_number"] if block else "?"
    strike_data = db.get_strike(sid)
    
    result = bm.close_strike(sid)
    if result["ok"]:
        tg.alert_strike_closed(
            block_number     = block_num,
            strike_price     = strike_data["strike_price"] if strike_data else 0,
            option_type      = strike_data["option_type"] if strike_data else "",
            sell_anchor      = result.get("sell_close_price", 0),
            sell_exit_price  = result.get("sell_close_price", 0),
            hedge_anchor     = result.get("hedge_close_price", 0),
            hedge_exit_price = result.get("hedge_close_price", 0),
            realized_pnl     = result.get("realized_pnl", 0),
        )
        _flash(result["message"], "success")
    else:
        _flash(result["message"], "error")

def cb_send_daily_summary(block_id, block_num):
    pnl_data = pe.calc_block_pnl(block_id)
    tg.alert_block_daily_summary(pnl_data)
    _flash(f"Block {block_num} summary sent to Telegram!", "success")

def cb_execute_inline_rollover(sell_sid):
    rv_strike = st.session_state.get(f"rv_strike_{sell_sid}")
    rv_expiry = st.session_state.get(f"rv_expiry_{sell_sid}")
    rv_lots = st.session_state.get(f"rv_lots_{sell_sid}")
    
    sell_s = db.get_strike(sell_sid)
    if not sell_s:
        _flash("Failed to retrieve Sell strike information.", "error")
        return
        
    rv_res = bm.rollover_hedge(
        sell_strike_id         = sell_sid,
        new_hedge_strike_price = int(rv_strike),
        new_hedge_expiry       = rv_expiry,
        new_hedge_lots         = int(rv_lots),
        new_hedge_option_type  = sell_s["option_type"],
    )
    if rv_res["ok"]:
        _flash(rv_res["message"], "success")
    else:
        _flash(rv_res["message"], "error")
        st.session_state[f"rollover_exp_{sell_sid}"] = True

def cb_execute_rollover_center(sell_sid):
    rv_strike = st.session_state.get(f"rv_center_strike_{sell_sid}")
    rv_expiry = st.session_state.get(f"rv_center_expiry_{sell_sid}")
    rv_lots = st.session_state.get(f"rv_center_lots_{sell_sid}")
    
    sell_s = db.get_strike(sell_sid)
    if not sell_s:
        _flash("Failed to retrieve Sell strike information for rollover.", "error")
        return
        
    rv_res = bm.rollover_hedge(
        sell_strike_id=sell_sid,
        new_hedge_strike_price=int(rv_strike),
        new_hedge_expiry=rv_expiry,
        new_hedge_lots=int(rv_lots),
        new_hedge_option_type=sell_s["option_type"],
    )
    if rv_res["ok"]:
        _flash(rv_res["message"], "success")
    else:
        _flash(rv_res["message"], "error")
        st.session_state["rollover_expanded"] = True

def cb_create_block():
    expiry_str = st.session_state.get("new_block_expiry")
    expiry_type = st.session_state.get("new_block_type")
    notes = st.session_state.get("new_block_notes", "")
    result     = bm.create_block(expiry_str, expiry_type, notes)
    if result["ok"]:
        _flash(f"Block {result['block_number']} created for {expiry_str} ({expiry_type})", "success")
    else:
        if result.get("duplicate"):
            _flash(result["message"], "warning")
        else:
            _flash(result["message"], "error")
        st.session_state["new_block_expanded"] = True

def cb_execute_live_trade(block_id):
    strike_price = st.session_state.get(f"sell_sp_{block_id}", 24000)
    option_type = st.session_state.get(f"sell_ot_{block_id}", "CE")
    lots = st.session_state.get(f"sell_ls_{block_id}", 1)
    use_live_anchor = st.session_state.get(f"use_live_ap_{block_id}", True)
    
    from kite_executor import kite_executor
    sell_sym_info = kite_executor.search_option_symbol(db.get_block(block_id)["expiry_date"], strike_price, option_type)
    sell_ltp = 0.0
    if sell_sym_info:
        sell_ltp = kite_executor.get_ltp(sell_sym_info["token"], sell_sym_info["trading_symbol"])
        
    if use_live_anchor:
        anchor_price = sell_ltp if sell_ltp > 0 else 10.0
    else:
        anchor_price = st.session_state.get(f"manual_ap_{block_id}", 100.0)
        
    if anchor_price <= 0:
        _flash("Sell anchor price must be greater than 0.", "error")
        return

    sell_res = bm.add_strike_to_block(
        block_id     = block_id,
        strike_price = int(strike_price),
        option_type  = option_type,
        leg_type     = "SELL",
        anchor_price = float(anchor_price),
        lots         = int(lots)
    )
    
    if not sell_res["ok"]:
        _flash(sell_res["message"], "error")
        return
        
    sell_strike_id = sell_res["strike_id"]

    all_block_strikes = db.get_strikes_by_block(block_id)
    existing_open_hedges = [
        h for h in all_block_strikes
        if h["leg_type"] == "HEDGE_BUY"
        and h["status"] == "OPEN"
    ]
    
    use_existing_hedge = False
    selected_existing_hedge = None
    
    if existing_open_hedges:
        eg_choice = st.session_state.get(f"eg_radio_{block_id}", "")
        use_existing_hedge = eg_choice.startswith("Use existing")
        if use_existing_hedge:
            if len(existing_open_hedges) == 1:
                selected_existing_hedge = existing_open_hedges[0]
            else:
                sel_eg_label = st.session_state.get(f"eg_sel_{block_id}")
                for h in existing_open_hedges:
                    h_sym = kite_executor.search_option_symbol(h.get("expiry_date", ""), h["strike_price"], h["option_type"])
                    h_ltp = kite_executor.get_ltp(h_sym["token"], h_sym["trading_symbol"]) if h_sym else 0.0
                    label = f"{h['strike_price']} {h['option_type']} (exp: {h.get('expiry_date', '?')}) | LTP ₹{h_ltp:.2f} | #{h['strike_id']}"
                    if label == sel_eg_label:
                        selected_existing_hedge = h
                        break

    if use_existing_hedge and selected_existing_hedge:
        bm.link_hedge_to_sell(sell_strike_id, selected_existing_hedge["strike_id"])
        _flash_msg_suffix = f" (Using existing hedge {selected_existing_hedge['strike_price']} {selected_existing_hedge['option_type']})"
    elif st.session_state.get(f"add_hedge_chk_{block_id}", False):
        h_sp = st.session_state.get(f"hedge_sp_{block_id}", 0)
        h_exp = st.session_state.get(f"hedge_exp_{block_id}", None)
        
        hedge_res = bm.add_strike_to_block(
            block_id     = block_id,
            strike_price = int(h_sp),
            option_type  = option_type,
            leg_type     = "HEDGE_BUY",
            anchor_price = 0.0,
            lots         = int(lots),
            expiry_date  = h_exp
        )
        
        if hedge_res["ok"]:
            bm.link_hedge_to_sell(sell_strike_id, hedge_res["strike_id"])
        else:
            _flash(f"Hedge creation failed: {hedge_res['message']}. Aborting trade.", "error")
            bm.remove_strike(sell_strike_id)
            return
        _flash_msg_suffix = ""
    else:
        _flash_msg_suffix = " (No hedge — unhedged sell!)"
        
    r = bm.execute_strike(sell_strike_id)
    if r["ok"]:
        _flash(f"Live trade executed successfully! {r['message']}{_flash_msg_suffix}", "success")
        st.session_state["add_strike_block"] = None
        tg.alert_engine_started()
    else:
        _flash(f"Execution failed: {r['message']}", "error")

def cb_save_pending_trade(block_id):
    strike_price = st.session_state.get(f"sell_sp_{block_id}", 24000)
    option_type = st.session_state.get(f"sell_ot_{block_id}", "CE")
    lots = st.session_state.get(f"sell_ls_{block_id}", 1)
    use_live_anchor = st.session_state.get(f"use_live_ap_{block_id}", True)
    
    from kite_executor import kite_executor
    sell_sym_info = kite_executor.search_option_symbol(db.get_block(block_id)["expiry_date"], strike_price, option_type)
    sell_ltp = 0.0
    if sell_sym_info:
        sell_ltp = kite_executor.get_ltp(sell_sym_info["token"], sell_sym_info["trading_symbol"])
        
    if use_live_anchor:
        anchor_price = sell_ltp if sell_ltp > 0 else 10.0
    else:
        anchor_price = st.session_state.get(f"manual_ap_{block_id}", 100.0)
        
    if anchor_price <= 0:
        _flash("Sell anchor price must be greater than 0.", "error")
        return

    sell_res = bm.add_strike_to_block(
        block_id     = block_id,
        strike_price = int(strike_price),
        option_type  = option_type,
        leg_type     = "SELL",
        anchor_price = float(anchor_price),
        lots         = int(lots)
    )
    
    if not sell_res["ok"]:
        _flash(sell_res["message"], "error")
        return
        
    sell_strike_id = sell_res["strike_id"]

    all_block_strikes = db.get_strikes_by_block(block_id)
    existing_open_hedges = [
        h for h in all_block_strikes
        if h["leg_type"] == "HEDGE_BUY"
        and h["status"] == "OPEN"
    ]
    
    use_existing_hedge = False
    selected_existing_hedge = None
    
    if existing_open_hedges:
        eg_choice = st.session_state.get(f"eg_radio_{block_id}", "")
        use_existing_hedge = eg_choice.startswith("Use existing")
        if use_existing_hedge:
            if len(existing_open_hedges) == 1:
                selected_existing_hedge = existing_open_hedges[0]
            else:
                sel_eg_label = st.session_state.get(f"eg_sel_{block_id}")
                for h in existing_open_hedges:
                    h_sym = kite_executor.search_option_symbol(h.get("expiry_date", ""), h["strike_price"], h["option_type"])
                    h_ltp = kite_executor.get_ltp(h_sym["token"], h_sym["trading_symbol"]) if h_sym else 0.0
                    label = f"{h['strike_price']} {h['option_type']} (exp: {h.get('expiry_date', '?')}) | LTP ₹{h_ltp:.2f} | #{h['strike_id']}"
                    if label == sel_eg_label:
                        selected_existing_hedge = h
                        break

    if use_existing_hedge and selected_existing_hedge:
        bm.link_hedge_to_sell(sell_strike_id, selected_existing_hedge["strike_id"])
        _flash(
            f"Sell strike saved as PENDING. Linked to existing hedge "
            f"{selected_existing_hedge['strike_price']} {selected_existing_hedge['option_type']}.",
            "success"
        )
    elif st.session_state.get(f"add_hedge_chk_{block_id}", False):
        h_sp = st.session_state.get(f"hedge_sp_{block_id}", 0)
        h_exp = st.session_state.get(f"hedge_exp_{block_id}", None)
        
        hedge_res = bm.add_strike_to_block(
            block_id     = block_id,
            strike_price = int(h_sp),
            option_type  = option_type,
            leg_type     = "HEDGE_BUY",
            anchor_price = 0.0,
            lots         = int(lots),
            expiry_date  = h_exp
        )
        
        if hedge_res["ok"]:
            bm.link_hedge_to_sell(sell_strike_id, hedge_res["strike_id"])
            _flash("Sell & Hedge strikes saved as PENDING.", "success")
        else:
            _flash(f"Hedge creation failed: {hedge_res['message']}. Aborting trade.", "error")
            bm.remove_strike(sell_strike_id)
            return
    else:
        _flash("Sell strike saved as PENDING.", "success")
        
    st.session_state["add_strike_block"] = None

def cb_cancel_add_strike(block_id):
    st.session_state["add_strike_block"] = None

def cb_update_anchor_price(strike_id):
    new_anchor = st.session_state.get("anchor_edit_new_val", 0.0)
    r = bm.update_strike_anchor_price(strike_id, new_anchor)
    if r["ok"]:
        _flash(r["message"], "success")
    else:
        _flash(r["message"], "error")
    st.session_state["anchor_edit_expanded"] = True

def cb_edit_block(block_id):
    st.session_state["edit_block_id"] = block_id
    st.session_state["block_mgmt_expanded"] = True

def cb_archive_block(block_id):
    r = bm.archive_block(block_id)
    _flash(r["message"], "success" if r["ok"] else "error")
    st.session_state["block_mgmt_expanded"] = True

def cb_delete_block(block_id):
    r = bm.delete_block(block_id)
    _flash(r["message"], "success" if r["ok"] else "error")
    st.session_state["block_mgmt_expanded"] = True

def cb_save_edit_block(block_id):
    new_expiry = st.session_state.get(f"new_exp_{block_id}", "").strip()
    new_exp_type = st.session_state.get(f"new_etype_{block_id}", "MONTHLY")
    if new_expiry:
        db.update_block_expiry(block_id, new_expiry, new_exp_type)
        _flash(f"Block expiry updated to {new_expiry}", "success")
        st.session_state["edit_block_id"] = None
    else:
        _flash("Expiry date cannot be empty.", "error")
    st.session_state["block_mgmt_expanded"] = True

def cb_cancel_edit_block():
    st.session_state["edit_block_id"] = None
    st.session_state["block_mgmt_expanded"] = True


def _pnl_color_class(pnl: float) -> str:
    return "metric-profit" if pnl >= 0 else "metric-loss"


def _pnl_html(pnl: float, ltp_avail: bool = True) -> str:
    if not ltp_avail:
        return '<span style="color:#6b7280;">--</span>'
    sign  = "+" if pnl >= 0 else ""
    color = "#22c55e" if pnl >= 0 else "#ef4444"
    return f'<span style="color:{color};font-family:\'JetBrains Mono\',monospace;font-weight:700;">{sign}Rs{abs(pnl):,.2f}</span>'


def _get_portfolio(sim: bool = False) -> dict:
    """Fetches portfolio P&L."""
    ltp_map = pe.fetch_all_ltps()
    return pe.calc_portfolio_pnl(ltp_map)


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
def render_sidebar():
    with st.sidebar:
        # Logo
        st.markdown("""
        <div style="text-align:center;padding:12px 0;">
            <div style="font-size:2rem;">📈</div>
            <div style="font-size:1.0rem;font-weight:700;color:#ffffff;">Zerodha Options</div>
            <div style="font-size:0.70rem;color:#cbd5e1;">Option Selling Engine</div>
        </div>
        <hr/>
        """, unsafe_allow_html=True)

        # --- Mode settings ---
        st.markdown("### MODE")

        algo_on = db.get("algo_running", "ON") == "ON"
        algo_toggle = st.toggle(
            "Algo Running",
            value   = algo_on,
            key     = "toggle_algo",
            help    = "Pause/resume background P&L cycle.",
        )
        if algo_toggle != algo_on:
            db.set("algo_running", "ON" if algo_toggle else "OFF")
            st.rerun()

        alerts_on = db.get("NOTIFICATIONS_ENABLED", "YES") == "YES"
        alerts_toggle = st.toggle(
            "Master Alerts Enabled",
            value   = alerts_on,
            key     = "toggle_alerts",
            help    = "Enable or disable all Telegram and Ntfy alerts.",
        )
        if alerts_toggle != alerts_on:
            db.set("NOTIFICATIONS_ENABLED", "YES" if alerts_toggle else "NO")
            _flash("Master Alerts " + ("enabled" if alerts_toggle else "disabled"), "success")
            st.rerun()

        # Premium individual toggles for Telegram and Ntfy
        col_tg, col_ntfy = st.columns(2)
        with col_tg:
            tg_on = db.get("TELEGRAM_ALERTS_ENABLED", "YES") == "YES"
            tg_toggle = st.toggle(
                "Telegram",
                value=tg_on,
                key="toggle_tg_alerts",
                disabled=not alerts_toggle,
                help="Enable or disable Telegram alerts."
            )
            if tg_toggle != tg_on:
                db.set("TELEGRAM_ALERTS_ENABLED", "YES" if tg_toggle else "NO")
                _flash("Telegram Alerts " + ("enabled" if tg_toggle else "disabled"), "success")
                st.rerun()
        with col_ntfy:
            ntfy_on = db.get("NTFY_ALERTS_ENABLED", "YES") == "YES"
            ntfy_toggle = st.toggle(
                "Ntfy",
                value=ntfy_on,
                key="toggle_ntfy_alerts",
                disabled=not alerts_toggle,
                help="Enable or disable Ntfy alerts."
            )
            if ntfy_toggle != ntfy_on:
                db.set("NTFY_ALERTS_ENABLED", "YES" if ntfy_toggle else "NO")
                _flash("Ntfy Alerts " + ("enabled" if ntfy_toggle else "disabled"), "success")
                st.rerun()

        st.divider()

        # --- Zerodha API Login ---
        st.markdown("### ZERODHA KITE API")

        from kite_executor import kite_executor as _kex
        login_status  = db.get("kite_login_status", "PENDING")
        token_fresh   = _kex._is_token_fresh()

        if login_status == "OK" and token_fresh:
            st.success("🟢 Zerodha API: CONNECTED")
            st.button("🔧 Reconcile / Sync DB", key="btn_reconcile", use_container_width=True, help="Scan today's orders to link any filled/pending trades that are not recorded in the DB.", on_click=cb_reconcile)
        elif login_status == "OK" and not token_fresh:
            st.warning("⚠️ Session expired (24hr) — please re-login below")
            login_status = "EXPIRED"
        else:
            st.warning("🔴 Zerodha API: NOT CONNECTED")

        # Quick Re-Login: when TOTP key is set as a 32-char key, offer 1-click re-login
        totp_key_stored = db.get("KITE_TOTP_KEY", "")
        totp_is_real    = (
            totp_key_stored
            and totp_key_stored.upper() not in ("YOUR_TOTP_SECRET_KEY", "TOTP", "")
            and len(totp_key_stored) >= 16
        )
        if login_status in ("EXPIRED", "PENDING", "FAILED") and totp_is_real:
            st.button("🔄 Quick Re-Login (TOTP)", use_container_width=True, key="btn_quick_relogin", on_click=cb_quick_relogin)

        if login_status in ("EXPIRED", "PENDING", "FAILED"):
            st.markdown("### 🔌 MANUAL OTP LOGIN")
            
            # Check if there is an active sent OTP session
            sent_session = st.session_state.get("manual_login_session")
            
            if not sent_session:
                # Option A: Send SMS OTP
                st.button("📲 Send OTP to Mobile", use_container_width=True, key="btn_send_otp_sms", on_click=cb_send_otp_sms)
                
                st.markdown("<div style='text-align: center; margin: 8px 0; color: #64748b; font-size: 0.8rem;'>— OR —</div>", unsafe_allow_html=True)
                
                # Option B: Direct TOTP Entry
                manual_otp = st.text_input(
                    "Google Authenticator / TOTP",
                    max_chars=6,
                    placeholder="e.g. 123456",
                    help="Enter 6-digit code if you use Google Authenticator.",
                    key="input_manual_totp"
                )
                st.button("🔌 Connect with TOTP", use_container_width=True, key="btn_manual_totp_login", on_click=cb_connect_with_totp)
            else:
                # OTP is sent: Show OTP input and Verify/Resend buttons
                st.info("📩 OTP has been sent to your registered mobile/email.")
                manual_otp = st.text_input(
                    "6-Digit Mobile OTP",
                    max_chars=6,
                    placeholder="Enter received OTP",
                    help="Enter the 6-digit OTP code sent to your mobile phone.",
                    key="input_manual_sms_otp"
                )
                
                col1, col2 = st.columns(2)
                with col1:
                    st.button("🔌 Verify & Connect", use_container_width=True, key="btn_verify_otp", on_click=cb_verify_otp)
                with col2:
                    st.button("🔄 Cancel", use_container_width=True, key="btn_cancel_otp", on_click=cb_cancel_otp)

        login_expanded = st.session_state.pop("login_expanded", False)
        with st.expander("🔐 Zerodha Credentials & Login", expanded=login_expanded or login_status not in ("OK",)):
            st.caption("Enter your Zerodha Kite Connect credentials.")
            
            curr_api_key = db.get("KITE_API_KEY", "")
            if curr_api_key.upper() in ("YOUR_API_KEY_HERE", "MOCK_KEY", ""):
                curr_api_key = ""
                
            curr_api_secret = db.get("KITE_API_SECRET", "")
            if curr_api_secret.upper() in ("YOUR_API_SECRET_HERE", "MOCK_SECRET", ""):
                curr_api_secret = ""
                
            curr_client_code = db.get("KITE_CLIENT_CODE", "")
            if curr_client_code.upper() in ("MOCK_CODE", ""):
                curr_client_code = ""
                
            curr_password = db.get("KITE_PASSWORD", "")
            if curr_password.upper() in ("YOUR_PASSWORD", ""):
                curr_password = ""
                
            curr_totp = db.get("KITE_TOTP_KEY", "")
            if curr_totp.upper() in ("YOUR_TOTP_SECRET_KEY", "TOTP", ""):
                curr_totp = ""

            curr_ntfy = db.get("NTFY_TOPIC", "")
            if curr_ntfy.upper() in ("YOUR_NTFY_TOPIC_HERE", "TOPIC", ""):
                curr_ntfy = ""
                
            input_api_key = st.text_input(
                "Kite API Key",
                value=curr_api_key,
                type="password",
                key="login_api_key"
            )
            
            input_api_secret = st.text_input(
                "Kite API Secret",
                value=curr_api_secret,
                type="password",
                key="login_api_secret"
            )
            
            input_client_code = st.text_input(
                "Kite Client Code",
                value=curr_client_code,
                key="login_client_code"
            )
            
            input_password = st.text_input(
                "Kite Password",
                value=curr_password,
                type="password",
                key="login_password"
            )
            
            input_totp = st.text_input(
                "TOTP Secret Key (Base32)",
                value=curr_totp,
                type="password",
                key="login_totp"
            )

            input_ntfy = st.text_input(
                "Ntfy Topic Name",
                value=curr_ntfy,
                key="login_ntfy"
            )
            
            col_s1, col_s2 = st.columns(2)
            with col_s1:
                st.button("💾 Save Credentials", use_container_width=True, key="btn_save_credentials", on_click=cb_save_credentials, args=(input_api_key, input_api_secret, input_client_code, input_password, input_totp, input_ntfy))
            with col_s2:
                has_totp = input_totp and input_totp.upper() not in ("YOUR_TOTP_SECRET_KEY", "")
                st.button("🔑 Run Headless Login", use_container_width=True, key="btn_headless_login", disabled=not has_totp, on_click=cb_headless_login, args=(has_totp,))

            st.markdown("---")
            if input_api_key:
                from kiteconnect import KiteConnect
                kite_temp = KiteConnect(api_key=input_api_key)
                try:
                    login_url = kite_temp.login_url()
                    st.markdown(f'<a href="{login_url}" target="_blank"><button style="width:100%;padding:10px;background-color:#0284c7;color:white;border:none;border-radius:8px;font-weight:bold;cursor:pointer;">🔗 Get Request Token (Official)</button></a>', unsafe_allow_html=True)
                    st.caption("Clicking above opens Zerodha login. Once authenticated, copy the request_token from the URL.")
                except Exception as e:
                    st.caption(f"Error generating login URL: {e}")

        st.divider()

        # --- Config ---
        st.markdown("### CONFIG")
        lot_size = st.number_input(
            "Lot Size",
            min_value = 1,
            max_value = 1000,
            value     = int(db.get("lot_size", "65")),
            key       = "cfg_lot_size",
            help      = "NIFTY lot size (65 as of Jun 2026)",
        )
        if lot_size != int(db.get("lot_size", "65")):
            db.set("lot_size", str(lot_size))
            _flash(f"Lot size updated to {lot_size}", "success")

        check_interval = st.number_input(
            "P&L Refresh (sec)",
            min_value = 30,
            max_value = 3600,
            value     = int(db.get("check_interval", str(cfg.DEFAULT_CHECK_INTERVAL))),
            step      = 30,
            key       = "cfg_interval",
        )
        if check_interval != int(db.get("check_interval", str(cfg.DEFAULT_CHECK_INTERVAL))):
            db.set("check_interval", str(check_interval))

        st.divider()

        # --- Test buttons ---
        st.markdown("### TOOLS")

        st.button("📊 Refresh P&L", use_container_width=True, key="btn_refresh", on_click=cb_refresh_pnl)

        st.button("📱 Send Test Alert", use_container_width=True, key="btn_test_tg", on_click=cb_send_test_tg)

        st.button("📮 Portfolio Summary", use_container_width=True, key="btn_port_sum", on_click=cb_send_portfolio_summary)

        st.button("📋 Trade History", use_container_width=True, key="btn_history", on_click=cb_toggle_trade_history)

        st.divider()

        # --- Status info ---
        st.markdown("### STATUS")
        last_cycle = db.get("last_cycle_time", "Never")
        st.markdown(f"""
        <div style="font-size:0.72rem;color:#6b7280;">
            Last cycle: <span style="color:#93c5fd;">{last_cycle}</span><br/>
            Time (IST): <span style="color:#93c5fd;">{_ist_now()}</span><br/>
            Port: <span style="color:#93c5fd;">9007</span>
        </div>
        """, unsafe_allow_html=True)

        st.divider()
        st.markdown(
            '<div style="text-align:center;font-size:0.65rem;color:#374151;">'
            'v1.01 BASE MODEL | NIFTY Only<br/>VPS 5.75.250.104:9007'
            '</div>',
            unsafe_allow_html=True,
        )


# ─────────────────────────────────────────────────────────────────────────────
# HEADER BAR
# ─────────────────────────────────────────────────────────────────────────────
def render_header(portfolio: dict):
    algo    = db.get("algo_running", "ON") == "ON"
    total   = portfolio.get("total_pnl", 0.0)
    n_blocks = portfolio.get("active_blocks", 0)
    n_open   = portfolio.get("total_open_strikes", 0)

    mode_pill = '<span class="status-pill pill-live">LIVE</span>'
    algo_pill = '<span class="status-pill pill-on">ALGO ON</span>' if algo else '<span class="status-pill pill-off">ALGO OFF</span>'

    pnl_color = "#22c55e" if total >= 0 else "#ef4444"
    pnl_sign  = "+" if total >= 0 else "-"

    st.markdown(f"""
    <div class="zerodha-header">
        <div>
            <div class="zerodha-title">📈 Zerodha OptionSelling Engine</div>
            <div class="zerodha-subtitle">
                NIFTY Options SELL | Port 9007 | VPS 5.75.250.104 &nbsp;
                {mode_pill} &nbsp; {algo_pill}
            </div>
        </div>
        <div style="text-align:right;">
            <div style="font-size:0.72rem;color:#ffe0b2;">PORTFOLIO P&L</div>
            <div style="font-size:1.8rem;font-weight:800;font-family:'JetBrains Mono',monospace;color:{pnl_color};">
                {pnl_sign}Rs{abs(total):,.2f}
            </div>
            <div style="font-size:0.72rem;color:#ffe0b2;">
                {n_blocks} active block{'s' if n_blocks!=1 else ''} &nbsp;|&nbsp; {n_open} open strike{'s' if n_open!=1 else ''}
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# METRICS ROW
# ─────────────────────────────────────────────────────────────────────────────
def render_metrics(portfolio: dict):
    total     = portfolio.get("total_pnl", 0.0)
    n_blocks  = portfolio.get("active_blocks", 0)
    n_open    = portfolio.get("total_open_strikes", 0)
    paper     = False
    updated   = portfolio.get("last_updated", "--")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        color = "#22c55e" if total >= 0 else "#ef4444"
        sign  = "+" if total >= 0 else ""
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Portfolio P&L</div>
            <div class="metric-value" style="color:{color};">{sign}Rs{abs(total):,.2f}</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Active Blocks</div>
            <div class="metric-value metric-neutral">{n_blocks}</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Open Strikes</div>
            <div class="metric-value metric-neutral">{n_open}</div>
        </div>
        """, unsafe_allow_html=True)
    with c4:
        mode_color = "#166534"
        mode_text  = "LIVE"
        lot_size   = db.get("lot_size", "65")
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Mode | Lot Size</div>
            <div class="metric-value" style="color:{mode_color};font-size:1.1rem;">{mode_text} | {lot_size}</div>
        </div>
        """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# BLOCK CARD
# ─────────────────────────────────────────────────────────────────────────────
def render_block_card(block_pnl: dict):
    b          = block_pnl["block"]
    block_id   = b["block_id"]
    block_num  = b["block_number"]
    expiry     = b["expiry_date"]
    exp_type   = b["expiry_type"]
    status     = b["status"]
    total_pnl  = block_pnl.get("total_pnl", 0.0)
    strikes    = block_pnl.get("strike_pnls", [])
    n_open     = block_pnl.get("open_strikes", 0)

    # Status pill
    pill_class = {"ACTIVE": "pill-active", "EXPIRED": "pill-expired", "CLOSED": "pill-closed"}.get(status, "pill-active")

    # P&L text
    ltp_avail = any(s.get("ltp_available") for s in strikes)
    if not ltp_avail:
        pnl_display = '<span style="color:#6b7280;font-size:1.1rem;font-weight:700;">--</span>'
    elif total_pnl >= 0:
        pnl_display = f'<span class="block-pnl-positive">+Rs{total_pnl:,.2f}</span>'
    else:
        pnl_display = f'<span class="block-pnl-negative">-Rs{abs(total_pnl):,.2f}</span>'

    # Card header
    st.markdown(f"""
    <div class="block-header">
        <div>
            <span class="block-title">BLOCK {block_num}</span>
            &nbsp;&nbsp;
            <span class="status-pill {pill_class}">{status}</span>
        </div>
        <div style="text-align:right;">
            <div class="block-expiry">Expiry: {expiry} ({exp_type.title()})</div>
            <div>{pnl_display}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Strike table
    if strikes:
        rows = []
        for s in strikes:
            ltp = s.get("ltp", 0.0)
            pnl = s.get("pnl", 0.0)
            la  = s.get("ltp_available", False)

            anchor_str = f"Rs{s['anchor_price']:.2f}"
            # OPEN  → show live LTP
            # CLOSED → show actual exit price with "Exit @" label
            if s.get("is_exit_price"):
                ltp_str = f"Exit @ Rs{ltp:.2f}" if ltp > 0 else "Exited"
            elif la:
                ltp_str = f"Rs{ltp:.2f}"
            else:
                ltp_str = "--"

            if not la:
                pnl_str = "--"
            elif pnl >= 0:
                pnl_str = f"+Rs{pnl:,.2f}"
            else:
                pnl_str = f"-Rs{abs(pnl):,.2f}"

            pct   = s.get("pnl_pct", 0.0)
            pct_str = f"{'+' if pct>=0 else ''}{pct:.1f}%" if la else "--"

            # Decay % for sell legs
            if s["leg_type"] == "SELL" and la and s["anchor_price"] > 0:
                decay = ((s["anchor_price"] - ltp) / s["anchor_price"]) * 100
                decay_str = f"{decay:.1f}%"
            else:
                decay_str = "--"

            rows.append({
                "Strike" : s["strike_price"],
                "Type"   : s["option_type"],
                "Leg"    : s["leg_type"],
                "Anchor" : anchor_str,
                "LTP"    : ltp_str,
                "Lots"   : s["lots"],
                "Qty"    : s.get("qty", s["lots"] * int(db.get("lot_size","65"))),
                "P&L"    : pnl_str,
                "P&L%"   : pct_str,
                "Decay%" : decay_str,
                "Status" : s["status"],
            })

        df = pd.DataFrame(rows)
        st.dataframe(
            df,
            use_container_width = True,
            hide_index          = True,
            column_config       = {
                "Strike": st.column_config.NumberColumn("Strike", format="%d"),
                "P&L"  : st.column_config.TextColumn("P&L (Rs)"),
                "P&L%" : st.column_config.TextColumn("P&L %"),
            },
        )

        # Scan for orphaned hedges in this block
        orphaned_hedges = []
        for s in strikes:
            if s["status"] == "OPEN" and s["leg_type"] == "HEDGE_BUY":
                sell_id = s.get("hedge_strike_id")
                if sell_id:
                    sell_strike = db.get_strike(sell_id)
                    if sell_strike and sell_strike["status"] == "CLOSED":
                        orphaned_hedges.append(s)

        if orphaned_hedges:
            st.warning("⚠️ **Orphaned Hedges Detected!** (Partner Sell Strike is CLOSED)")
            for h in orphaned_hedges:
                h_label = f"Hedge {h['strike_price']} {h['option_type']} (Strike #{h['strike_id']})"
                st.button(f"✖ Close Stranded {h_label}", key=f"close_orphaned_{h['strike_id']}", use_container_width=True, on_click=cb_close_stranded_hedge, args=(h["strike_id"],))

    else:
        st.markdown(
            '<p style="color:#374151;font-size:0.85rem;padding:12px 18px;">No open strikes.</p>',
            unsafe_allow_html=True,
        )

    # ── Feature A: Rollover Hedge Section ─────────────────────────────────
    # Show a rollover form for each OPEN SELL strike in this block
    open_sell_strikes = [s for s in strikes if s["status"] == "OPEN" and s["leg_type"] == "SELL"]
    for sell_s in open_sell_strikes:
        sell_sid     = sell_s["strike_id"]
        linked_h_id  = sell_s.get("hedge_strike_id")
        linked_hedge = db.get_strike(linked_h_id) if linked_h_id else None

        if linked_hedge and linked_hedge["status"] == "OPEN":
            old_hedge_label = (
                f"{linked_hedge['strike_price']} {linked_hedge['option_type']} "
                f"(exp: {linked_hedge.get('expiry_date', '?')}) — OPEN"
            )
        elif linked_hedge:
            old_hedge_label = (
                f"{linked_hedge['strike_price']} {linked_hedge['option_type']} "
                f"[{linked_hedge['status']}] — no longer active"
            )
        else:
            old_hedge_label = "None linked"

        inline_rv_expanded = st.session_state.pop(f"rollover_exp_{sell_sid}", False)
        with st.expander(
            f"🔄 Rollover Hedge — {sell_s['strike_price']} {sell_s['option_type']} SELL (#{sell_sid})",
            expanded=inline_rv_expanded
        ):
            st.markdown(
                f"""
                <div style='background:#fff8f0;border:1px solid #ff5722;border-radius:8px;padding:10px 14px;margin-bottom:10px;'>
                    <span style='font-size:0.8rem;color:#e65100;font-weight:700;'>CURRENT HEDGE</span><br/>
                    <span style='font-family:JetBrains Mono,monospace;font-size:0.85rem;'>{old_hedge_label}</span>
                </div>
                """,
                unsafe_allow_html=True
            )

            st.markdown("##### New Hedge Details")
            from kite_executor import kite_executor as _kex_rv
            rv_col1, rv_col2, rv_col3 = st.columns([2, 2, 1])

            with rv_col1:
                default_rv_strike = (
                    linked_hedge["strike_price"] if linked_hedge else
                    (sell_s["strike_price"] + 300 if sell_s["option_type"] == "CE" else sell_s["strike_price"] - 300)
                )
                rv_strike = st.number_input(
                    "New Hedge Strike",
                    min_value = 10000,
                    max_value = 50000,
                    value     = int(default_rv_strike),
                    step      = 50,
                    key       = f"rv_strike_{sell_sid}",
                )

            with rv_col2:
                rv_expiries = get_sorted_nifty_expiries()
                # Default to next weekly (first expiry that's not the current hedge's expiry)
                current_exp = linked_hedge.get("expiry_date", "") if linked_hedge else ""
                default_rv_exp_idx = 0
                for i, e in enumerate(rv_expiries):
                    if e != current_exp:
                        default_rv_exp_idx = i
                        break
                rv_expiry = st.selectbox(
                    "New Expiry Date",
                    options = rv_expiries,
                    index   = default_rv_exp_idx,
                    key     = f"rv_expiry_{sell_sid}",
                )

            with rv_col3:
                rv_lots = st.number_input(
                    "Lots",
                    min_value = 1,
                    max_value = 100,
                    value     = sell_s.get("lots", 1),
                    key       = f"rv_lots_{sell_sid}",
                )

            # Show live LTP for the new hedge symbol
            rv_sym_info = _kex_rv.search_option_symbol(rv_expiry, rv_strike, sell_s["option_type"])
            if rv_sym_info:
                rv_ltp = _kex_rv.get_ltp(rv_sym_info["token"], rv_sym_info["trading_symbol"])
                st.info(
                    f"🛡️ **New Hedge Live LTP**: ₹{rv_ltp:.2f} — `{rv_sym_info['trading_symbol']}`"
                )
            else:
                st.warning("⚠️ New hedge symbol not found in Security Master.")

            st.markdown(
                "<div style='background:#fff3e0;border-left:3px solid #ff5722;padding:8px 12px;border-radius:4px;font-size:0.8rem;margin:8px 0;'>"
                "⚠️ <b>Order sequence:</b> New hedge bought first → Old hedge closed immediately to prevent margin spikes."
                "</div>",
                unsafe_allow_html=True
            )

            st.button(
                f"🔄 Execute Rollover",
                key=f"btn_rollover_{sell_sid}",
                use_container_width=True,
                type="primary",
                on_click=cb_execute_inline_rollover,
                args=(sell_sid,)
            )

    # Action buttons row
    if status == "ACTIVE":
        col_a, col_b, col_c, col_d = st.columns([2, 2, 2, 2])

        with col_a:
            st.button(f"+ Add Strike", key=f"add_strike_{block_id}", use_container_width=True, on_click=cb_set_add_strike_block, args=(block_id,))

        with col_b:
            all_pending = [s for s in bm.get_block_summary(block_id)["strikes"] if s["status"] == "PENDING"]
            if all_pending:
                st.button(f"▶ Execute Block", key=f"exec_block_{block_id}", use_container_width=True, on_click=cb_execute_block, args=(block_id,))

        with col_c:
            open_sells = [s for s in bm.get_block_summary(block_id)["strikes"]
                         if s["status"] == "OPEN" and s["leg_type"] == "SELL"]
            if open_sells:
                strike_options = {
                    f"{s['strike_price']} {s['option_type']} SELL (#{s['strike_id']})": s["strike_id"]
                    for s in open_sells
                }
                sel_label = st.selectbox(
                    "Close Strike",
                    options = list(strike_options.keys()),
                    key     = f"close_sel_{block_id}",
                    label_visibility="collapsed",
                )
                st.button(f"✖ Close + Hedge", key=f"close_btn_{block_id}", use_container_width=True, on_click=cb_close_strike, args=(block_id,))

        with col_d:
            st.button(f"📊 Daily Summary", key=f"daily_sum_{block_id}", use_container_width=True, on_click=cb_send_daily_summary, args=(block_id, block_num))


# ─────────────────────────────────────────────────────────────────────────────
# WEEKLY HEDGE ROLLOVER CENTER
# ─────────────────────────────────────────────────────────────────────────────
def render_rollover_center():
    rollover_expanded = st.session_state.pop("rollover_expanded", False)
    with st.expander("🔄 WEEKLY HEDGE ROLLOVER CENTER", expanded=rollover_expanded):
        st.markdown(
            '<p class="section-title">Centralized Weekly Hedge Rollover Control</p>',
            unsafe_allow_html=True
        )

        active_blocks = db.get_all_blocks(status_filter="ACTIVE")
        rollover_candidates = []
        for b in active_blocks:
            strikes = db.get_strikes_by_block(b["block_id"], status_filter="OPEN")
            for s in strikes:
                if s["leg_type"] == "SELL" and s.get("hedge_strike_id"):
                    h = db.get_strike(s["hedge_strike_id"])
                    if h and h["status"] == "OPEN":
                        rollover_candidates.append({
                            "block_id": b["block_id"],
                            "block_num": b["block_number"],
                            "sell_strike": s,
                            "hedge_strike": h,
                        })

        if not rollover_candidates:
            st.info("ℹ️ **No active weekly hedges found to roll over.**\n\nRollover is only available when you have active SELL positions with linked open HEDGE positions.")
            return

        # Prepare option label mapping
        candidate_options = {}
        for rc in rollover_candidates:
            sell_s = rc["sell_strike"]
            hedge_s = rc["hedge_strike"]
            label = (
                f"Block {rc['block_num']} | "
                f"SELL: {sell_s['strike_price']} {sell_s['option_type']} "
                f"(Lots: {sell_s['lots']}) ↔ "
                f"Hedge: {hedge_s['strike_price']} {hedge_s['option_type']} "
                f"(exp: {hedge_s.get('expiry_date') or 'N/A'})"
            )
            candidate_options[label] = rc

        st.markdown("##### 1. Select Active Position to Roll Over")
        selected_label = st.selectbox(
            "Select Position",
            options=list(candidate_options.keys()),
            key="rv_center_select_candidate",
            label_visibility="collapsed"
        )
        selected_rc = candidate_options[selected_label]
        sell_s = selected_rc["sell_strike"]
        hedge_s = selected_rc["hedge_strike"]
        sell_sid = sell_s["strike_id"]

        st.markdown("<br/>", unsafe_allow_html=True)
        st.markdown("##### 2. Customize New Hedge Parameters")

        rv_col1, rv_col2, rv_col3 = st.columns([2, 2, 1])

        with rv_col1:
            rv_strike = st.number_input(
                "New Hedge Strike Price",
                min_value=10000,
                max_value=50000,
                value=int(hedge_s["strike_price"]),
                step=50,
                key=f"rv_center_strike_{sell_sid}",
                help="Target strike price for the new weekly hedge."
            )

        with rv_col2:
            rv_expiries = get_sorted_nifty_expiries()
            current_exp = hedge_s.get("expiry_date", "")
            # Find index of the next weekly expiry (first expiry that is not the current one)
            default_rv_exp_idx = 0
            for i, e in enumerate(rv_expiries):
                if e != current_exp:
                    default_rv_exp_idx = i
                    break
            rv_expiry = st.selectbox(
                "New Expiry Date",
                options=rv_expiries,
                index=default_rv_exp_idx,
                key=f"rv_center_expiry_{sell_sid}",
                help="Select the new weekly expiry date for the rolled hedge."
            )

        with rv_col3:
            rv_lots = st.number_input(
                "Lots",
                min_value=1,
                max_value=100,
                value=int(sell_s["lots"]),
                key=f"rv_center_lots_{sell_sid}",
                help="Number of lots for the new hedge (defaults to Sell lots)."
            )

        # Show live LTP for the selected new hedge symbol
        from kite_executor import kite_executor as _kex_rv
        rv_sym_info = _kex_rv.search_option_symbol(rv_expiry, rv_strike, sell_s["option_type"])
        if rv_sym_info:
            rv_ltp = _kex_rv.get_ltp(rv_sym_info["token"], rv_sym_info["trading_symbol"])
            st.info(
                f"🛡️ **New Hedge Live LTP**: ₹{rv_ltp:.2f} — `{rv_sym_info['trading_symbol']}`"
            )
        else:
            st.warning("⚠️ New hedge symbol not found in Security Master.")

        st.markdown(
            "<div style='background:#fff3e0;border-left:3px solid #ff5722;padding:8px 12px;border-radius:4px;font-size:0.8rem;margin:8px 0;'>"
            "⚠️ <b>Order sequence:</b> New hedge bought first → Old hedge closed immediately to prevent margin spikes."
            "</div>",
            unsafe_allow_html=True
        )

        st.button(
            "🔄 Confirm & Execute Rollover",
            key=f"rv_center_btn_execute_{sell_sid}",
            use_container_width=True,
            type="primary",
            on_click=cb_execute_rollover_center,
            args=(sell_sid,)
        )


# ─────────────────────────────────────────────────────────────────────────────
# NEW BLOCK FORM
# ─────────────────────────────────────────────────────────────────────────────
def render_new_block_form():
    new_block_expanded = st.session_state.pop("new_block_expanded", False)
    with st.expander("➕ CREATE NEW BLOCK", expanded=new_block_expanded):
        st.markdown('<p class="section-title">New Block Setup</p>', unsafe_allow_html=True)
        col1, col2, col3 = st.columns([2, 2, 3])

        with col1:
            expiries_list = get_sorted_nifty_expiries()
            expiry_str = st.selectbox(
                "Expiry Date",
                options = expiries_list,
                key     = "new_block_expiry",
                help    = "Select the option contract expiry date",
            )

        with col2:
            expiry_type = st.selectbox(
                "Expiry Type",
                options = ["MONTHLY", "WEEKLY"],
                index   = 0,
                key     = "new_block_type",
            )

        with col3:
            notes = st.text_input(
                "Notes (optional)",
                placeholder = "e.g. June Monthly Straddle",
                key         = "new_block_notes",
            )

        st.button("🆕 Create Block", key="btn_create_block", type="primary", on_click=cb_create_block)


# ─────────────────────────────────────────────────────────────────────────────
# ADD STRIKE FORM
# ─────────────────────────────────────────────────────────────────────────────
def get_sorted_nifty_expiries():
    from kite_executor import kite_executor
    df = kite_executor._load_security_master()
    expiries = set()
    if not df.empty:
        # Zerodha option master contains name == "NIFTY" and exchange == "NFO"
        filtered = df[(df["name"].str.upper() == "NIFTY") & (df["exchange"].str.upper() == "NFO")]
        for e in filtered["expiry"].dropna().unique():
            expiries.add(e)
    sorted_dates = []
    for e in expiries:
        try:
            # Zerodha date format is YYYY-MM-DD
            dt = datetime.strptime(str(e).strip(), "%Y-%m-%d").date()
            sorted_dates.append(dt)
        except ValueError:
            pass
    sorted_dates.sort()
    res = [d.strftime("%d-%b-%Y") for d in sorted_dates if d >= date.today()]
    if not res:
        res = [date.today().strftime("%d-%b-%Y")]
    return res


def render_add_strike_form(block_id: int):
    block    = db.get_block(block_id)
    block_num = block["block_number"] if block else "?"

    st.markdown(f'<p class="section-title">Add Strike to Block {block_num}</p>', unsafe_allow_html=True)

    # ── Sell Leg Inputs ──
    st.markdown("##### 🔴 Option Selling Leg (SELL)")
    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        strike_price = st.number_input(
            "Strike Price",
            min_value = 10000,
            max_value = 50000,
            value     = 24000,
            step      = 50,
            key       = f"sell_sp_{block_id}",
        )

    with col2:
        option_type = st.selectbox(
            "Option Type (CE/PE)",
            options = ["CE", "PE"],
            key     = f"sell_ot_{block_id}",
        )

    with col3:
        lots = st.number_input(
            "Lots",
            min_value = 1,
            max_value = 100,
            value     = 1,
            key       = f"sell_ls_{block_id}",
        )

    # Fetch and show live LTP of the Sell strike
    from kite_executor import kite_executor
    sell_sym_info = kite_executor.search_option_symbol(block["expiry_date"], strike_price, option_type)
    sell_ltp = 0.0
    if sell_sym_info:
        sell_ltp = kite_executor.get_ltp(sell_sym_info["token"], sell_sym_info["trading_symbol"])
        st.info(f"📈 **Sell Leg Live LTP**: ₹{sell_ltp:.2f} ({sell_sym_info['trading_symbol']})")
    else:
        st.warning("⚠️ Option symbol not found in Security Master.")

    col_ap = st.columns([1])[0]
    with col_ap:
        use_live_anchor = st.checkbox("Use Live LTP as Anchor Price", value=True, key=f"use_live_ap_{block_id}")
        if use_live_anchor:
            anchor_price = sell_ltp if sell_ltp > 0 else 10.0  # safe default if LTP is 0 (closed market)
            st.markdown(f"**Anchor Price**: ₹{anchor_price:.2f}")
        else:
            anchor_price = st.number_input(
                "Manual Anchor Price (Rs)",
                min_value = 0.05,
                max_value = 5000.00,
                value     = sell_ltp if sell_ltp > 0 else 100.00,
                step      = 0.05,
                format    = "%.2f",
                key       = f"manual_ap_{block_id}"
            )

    st.markdown("---")

    # ── Feature B: Entry Guard — scan block for existing open hedges ───────────
    all_block_strikes   = db.get_strikes_by_block(block_id)
    existing_open_hedges = [
        h for h in all_block_strikes
        if h["leg_type"] == "HEDGE_BUY"
        and h["status"] == "OPEN"
    ]

    use_existing_hedge = False
    selected_existing_hedge = None

    if existing_open_hedges:
        from kite_executor import kite_executor as _kex_eg
        hedge_display = []
        for h in existing_open_hedges:
            h_sym = _kex_eg.search_option_symbol(h.get("expiry_date", ""), h["strike_price"], h["option_type"])
            h_ltp = 0.0
            if h_sym:
                h_ltp = _kex_eg.get_ltp(h_sym["token"], h_sym["trading_symbol"])
            hedge_display.append({
                "strike": h,
                "ltp":    h_ltp,
                "label":  f"{h['strike_price']} {h['option_type']} (exp: {h.get('expiry_date', '?')}) | LTP ₹{h_ltp:.2f} | #{h['strike_id']}"
            })

        st.markdown(
            """
            <div style='background:#fefce8;border:1px solid #eab308;border-radius:8px;padding:12px 16px;margin-bottom:10px;'>
                <span style='font-weight:700;color:#854d0e;'>🛡️ EXISTING OPEN HEDGE DETECTED IN THIS BLOCK</span><br/>
                <span style='font-size:0.82rem;color:#713f12;'>
                    This block already has an open hedge position. Using it avoids buying a duplicate hedge.
                </span>
            </div>
            """,
            unsafe_allow_html=True
        )

        eg_choice = st.radio(
            "Hedge Strategy:",
            options = [
                "Use existing open hedge (recommended — no new buy)",
                "Buy a fresh hedge (adds new position)"
            ],
            index = 0,
            key   = f"eg_radio_{block_id}",
        )
        use_existing_hedge = (eg_choice.startswith("Use existing"))

        if use_existing_hedge and len(hedge_display) == 1:
            selected_existing_hedge = hedge_display[0]["strike"]
            st.success(
                f"✅ Will use: **{hedge_display[0]['label']}** for this sell."
            )
        elif use_existing_hedge and len(hedge_display) > 1:
            eg_labels = {h["label"]: h["strike"] for h in hedge_display}
            sel_eg_label = st.selectbox(
                "Select existing hedge to use:",
                options = list(eg_labels.keys()),
                key     = f"eg_sel_{block_id}",
            )
            selected_existing_hedge = eg_labels[sel_eg_label]
            st.success(f"✅ Will use: **{sel_eg_label}**")

    # ── Hedge Inputs (only shown if NOT using existing) ──────────────────────
    if not use_existing_hedge:
        # Checkbox to let the user decide whether to buy/add a fresh hedge leg.
        st.checkbox("Add Hedge Leg (BUY)", value=True, key=f"add_hedge_chk_{block_id}")
        if st.session_state.get(f"add_hedge_chk_{block_id}"):
            st.markdown("##### 🟢 Hedge Leg (BUY)")
            hcol1, hcol2 = st.columns([2, 2])
            
            default_hedge_strike = strike_price + 300 if option_type == "CE" else strike_price - 300
            with hcol1:
                st.number_input(
                    "Hedge Strike Price",
                    min_value = 10000,
                    max_value = 50000,
                    value     = default_hedge_strike,
                    step      = 50,
                    key       = f"hedge_sp_{block_id}",
                )
                
            with hcol2:
                expiries_list = get_sorted_nifty_expiries()
                block_exp = block["expiry_date"]
                default_idx = 0
                if block_exp in expiries_list:
                    default_idx = expiries_list.index(block_exp)
                elif expiries_list:
                    expiries_list.append(block_exp)
                    expiries_list = sorted(list(set(expiries_list)), key=lambda x: datetime.strptime(x, "%d-%b-%Y"))
                    default_idx = expiries_list.index(block_exp)
                    
                st.selectbox(
                    "Hedge Expiry Date",
                    options = expiries_list,
                    index   = default_idx,
                    key     = f"hedge_exp_{block_id}",
                )

            # Fetch and show live LTP of the Hedge strike
            h_sp = st.session_state.get(f"hedge_sp_{block_id}", default_hedge_strike)
            h_exp = st.session_state.get(f"hedge_exp_{block_id}")
            hedge_sym_info = kite_executor.search_option_symbol(h_exp, h_sp, option_type)
            if hedge_sym_info:
                hedge_ltp = kite_executor.get_ltp(hedge_sym_info["token"], hedge_sym_info["trading_symbol"])
                st.info(f"🛡️ **Hedge Leg Live LTP**: ₹{hedge_ltp:.2f} ({hedge_sym_info['trading_symbol']})")
            else:
                st.warning("⚠️ Hedge option symbol not found in Security Master.")

    st.markdown("---")

    # ── Action Buttons ──
    col_btn1, col_btn2, col_btn3 = st.columns([2, 2, 1])

    with col_btn1:
        st.button("▶ Execute Live Trade", key=f"btn_exec_trade_{block_id}", type="primary", use_container_width=True, on_click=cb_execute_live_trade, args=(block_id,))

    with col_btn2:
        st.button("💾 Save as Pending", key=f"btn_save_pending_{block_id}", use_container_width=True, on_click=cb_save_pending_trade, args=(block_id,))

    with col_btn3:
        st.button("✖ Cancel", key=f"cancel_add_{block_id}", use_container_width=True, on_click=cb_cancel_add_strike, args=(block_id,))


# ─────────────────────────────────────────────────────────────────────────────
# TRADE HISTORY LOG
# ─────────────────────────────────────────────────────────────────────────────
def render_trade_log():
    st.markdown("---")
    st.markdown("### 📋 TRADE HISTORY")

    trades = db.get_trades()
    if not trades:
        st.info("No trades recorded yet.", icon="ℹ️")
        return

    rows = []
    for t in trades:
        rows.append({
            "Trade #"  : t["trade_id"],
            "Block"    : t["block_id"],
            "Strike"   : t["strike_id"],
            "Action"   : t["action"],
            "Price"    : f"Rs{t['price']:.2f}",
            "Lots"     : t["lots"],
            "Status"   : t["order_status"],
            "Time"     : t["timestamp"],
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    if st.button("Close History", key="btn_close_history"):
        st.session_state["show_trade_log"] = False
        st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# ARCHIVE / DELETE / EDIT SECTION
# ─────────────────────────────────────────────────────────────────────────────
def render_edit_anchor_form():
    anchor_edit_expanded = st.session_state.pop("anchor_edit_expanded", False)
    with st.expander("✏️ Edit Strike Anchor Price (Mid-Trade)", expanded=anchor_edit_expanded):
        st.markdown('<p class="section-title">Edit Anchor Price</p>', unsafe_allow_html=True)
        blocks = db.get_all_blocks()
        if not blocks:
            st.caption("No blocks available.")
            return

        block_options = {
            f"Block {b['block_number']} ({b['expiry_date']}) - {b['status']}": b["block_id"]
            for b in blocks
        }
        selected_block_label = st.selectbox("Select Block", list(block_options.keys()), key="anchor_edit_block")
        block_id = block_options[selected_block_label]

        strikes = db.get_strikes_by_block(block_id)
        if not strikes:
            st.caption("No strikes in this block.")
            return

        strike_options = {
            f"{s['strike_price']} {s['option_type']} {s['leg_type']} (#{s['strike_id']}) [Current Anchor: ₹{s['anchor_price']:.2f}]": s["strike_id"]
            for s in strikes
        }
        selected_strike_label = st.selectbox("Select Strike", list(strike_options.keys()), key="anchor_edit_strike")
        strike_id = strike_options[selected_strike_label]

        strike = db.get_strike(strike_id)
        if strike:
            curr_anchor = float(strike["anchor_price"])
            new_anchor = st.number_input(
                "New Anchor Price (Rs)",
                min_value=0.05,
                value=curr_anchor,
                step=0.05,
                format="%.2f",
                key="anchor_edit_new_val"
            )
            
            st.button("Update Anchor Price", key="btn_update_anchor", type="primary", on_click=cb_update_anchor_price, args=(strike_id,))


def render_block_management():
    all_blocks = db.get_all_blocks()
    if not all_blocks:
        return

    st.markdown("---")
    st.markdown("### BLOCK MANAGEMENT")

    for b in all_blocks:
        status_class = {"ACTIVE":"pill-active","EXPIRED":"pill-expired","CLOSED":"pill-closed"}.get(b["status"],"pill-active")
        col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
        with col1:
            st.markdown(
                f'Block {b["block_number"]} — {b["expiry_date"]} ({b["expiry_type"]}) '
                f'<span class="status-pill {status_class}">{b["status"]}</span>',
                unsafe_allow_html=True,
            )
        with col2:
            st.button("✏️ Edit", key=f"edit_{b['block_id']}", use_container_width=True, on_click=cb_edit_block, args=(b['block_id'],))
        with col3:
            if b["status"] == "ACTIVE":
                st.button("Archive", key=f"arch_{b['block_id']}", use_container_width=True, on_click=cb_archive_block, args=(b['block_id'],))
        with col4:
            st.button("🗑 Delete", key=f"del_{b['block_id']}", use_container_width=True, on_click=cb_delete_block, args=(b['block_id'],))

        # Edit block inline panel
        if st.session_state.get("edit_block_id") == b["block_id"]:
            with st.form(key=f"edit_block_form_{b['block_id']}"):
                st.markdown(f"**Edit Block {b['block_number']} Expiry**")
                ec1, ec2, ec3 = st.columns([2, 1, 1])
                with ec1:
                    new_expiry = st.text_input(
                        "New Expiry Date",
                        value = b["expiry_date"],
                        placeholder = "e.g. 26-Jun-2026",
                        help = "Format: DD-Mon-YYYY e.g. 26-Jun-2026",
                        key = f"new_exp_{b['block_id']}",
                    )
                with ec2:
                    new_exp_type = st.selectbox(
                        "Type",
                        ["MONTHLY", "WEEKLY"],
                        index = 0 if b["expiry_type"] == "MONTHLY" else 1,
                        key = f"new_etype_{b['block_id']}",
                    )
                with ec3:
                    st.markdown("<br/>", unsafe_allow_html=True)
                st.form_submit_button("💾 Save Changes", use_container_width=True, on_click=cb_save_edit_block, args=(b['block_id'],))

            st.button("Cancel Edit", key=f"cancel_edit_{b['block_id']}", on_click=cb_cancel_edit_block)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN APP
# ─────────────────────────────────────────────────────────────────────────────
def main():
    # Auto-refresh dashboard every 30 seconds
    st_autorefresh(interval=30000, key="pnl_auto_refresh")

    # ── Check for Redirect request_token from Zerodha Kite Login ──
    if "request_token" in st.query_params:
        req_token = st.query_params["request_token"]
        if req_token:
            from kite_executor import kite_executor as _kexec
            with st.spinner("Authenticating with Zerodha Kite..."):
                success = _kexec.validate_token_and_login(req_token)
                if success:
                    tg.alert_login_success()
                    st.query_params.clear()
                    _flash("Zerodha Official Login Successful!", "success")
                    st.rerun()
                else:
                    st.query_params.clear()
                    _flash("Zerodha Redirect Login Failed. Invalid request token.", "error")
                    st.rerun()

    # Auto-expire old blocks
    bm.check_expiries()

    # Render sidebar
    render_sidebar()

    # Fetch portfolio P&L
    portfolio = _get_portfolio()
    st.session_state["portfolio_pnl"] = portfolio

    # Header
    render_header(portfolio)

    # Flash messages
    _show_flash()

    # Create Tabs for Option Selling and Commodities
    tab_options, tab_commodity = st.tabs(["💰 Nifty Option Selling", "🛢️ MCX Commodities FUT"])

    with tab_options:


        # Metrics row
        render_metrics(portfolio)

        st.markdown("<br/>", unsafe_allow_html=True)

        # Weekly hedge rollover center (always visible at top)
        render_rollover_center()

        st.markdown("<br/>", unsafe_allow_html=True)

        # New block form (always visible at top)
        render_new_block_form()

        st.markdown("<br/>", unsafe_allow_html=True)

        # Add strike form (shown when user clicks "Add Strike")
        add_block_id = st.session_state.get("add_strike_block")
        if add_block_id:
            with st.container():
                render_add_strike_form(add_block_id)
            st.markdown("---")

        # Block cards
        block_pnls = portfolio.get("block_pnls", [])

        if not block_pnls:
            st.markdown("""
            <div style="text-align:center;padding:60px 0;color:#374151;">
                <div style="font-size:3rem;">📦</div>
                <div style="font-size:1.1rem;font-weight:600;color:#6b7280;margin-top:12px;">No Active Blocks</div>
                <div style="font-size:0.85rem;color:#374151;margin-top:6px;">
                    Create your first block above to start trading
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown('<p class="section-title">ACTIVE BLOCKS</p>', unsafe_allow_html=True)

            for bp in block_pnls:
                with st.container():
                    st.markdown('<div class="block-card">', unsafe_allow_html=True)
                    render_block_card(bp)
                    st.markdown('</div>', unsafe_allow_html=True)
                st.markdown("<br/>", unsafe_allow_html=True)

        # Edit anchor price form
        render_edit_anchor_form()

        # Block management (archive/delete)
        block_mgmt_expanded = st.session_state.pop("block_mgmt_expanded", False) or st.session_state.get("edit_block_id") is not None
        with st.expander("⚙️ Block Management (Archive / Delete)", expanded=block_mgmt_expanded):
            render_block_management()

        # Trade history log
        if st.session_state.get("show_trade_log"):
            render_trade_log()

        # Paper Mode notice removed

        # Footer
        st.markdown("---")
        updated = portfolio.get("last_updated", "--")
        st.markdown(
            f'<div style="text-align:center;font-size:0.68rem;color:#374151;">'
            f'Zerodha OptionSelling Engine v1.01 | NIFTY Only | Port 9007 | '
            f'Last updated: {updated}'
            f'</div>',
            unsafe_allow_html=True,
        )




    # ═══════════════════════════════════════════════════════════════
    # MCX COMMODITY FUTURES TAB (Auto-added by upgrade_add_commodity.py)
    # ═══════════════════════════════════════════════════════════════
    def render_commodity_tab():
        """Renders the MCX Commodity Futures dashboard tab."""
        import commodity_executor as comm_exec
    
        st.markdown("""
        <div style='text-align:center;padding:12px 0 4px;'>
            <h2 style='margin:0;font-size:1.5rem;'>🛢️ MCX COMMODITY FUTURES ENGINE</h2>
        </div>
        """, unsafe_allow_html=True)

        # Engine Status Badge
        comm_running = db.get("comm_engine_running", "OFF") == "ON"
        badge_color = "#22c55e" if comm_running else "#ef4444"
        badge_text = "🟢 RUNNING & MONITORING" if comm_running else "🔴 ENGINE PAUSED"
    
        st.markdown(f"""
        <div style='text-align:center;margin:8px 0 16px;'>
            <span style='font-size:0.8rem;color:#94a3b8;font-weight:700;'>COMMODITY ENGINE STATUS</span><br/>
            <span style='background:{badge_color};color:white;padding:6px 16px;border-radius:30px;font-size:0.9rem;font-weight:800;'>
                {badge_text}
            </span>
        </div>
        """, unsafe_allow_html=True)

        col_st1, col_st2, col_st3 = st.columns([1, 1, 1])
        with col_st1:
            st.markdown(
                f"<p style='font-size:0.85rem;color:#64748b;'>Contract: <b>{db.get('comm_selected_contract', 'None')}</b></p>",
                unsafe_allow_html=True
            )
        with col_st2:
            comm_toggle = st.toggle(
                "Activate Commodity Engine",
                value=comm_running,
                key="comm_engine_toggle",
                help="Turn ON to begin auto-trading on 15m candle closed boundaries."
            )
            if comm_toggle != comm_running:
                db.set("comm_engine_running", "ON" if comm_toggle else "OFF")
                if comm_toggle:
                    db.set("comm_last_check_candle_time", "")
                _flash("Commodity Engine " + ("Activated" if comm_toggle else "Paused"), "success")
                st.rerun()
        with col_st3:
            if st.button("🔄 Refresh Data", key="comm_refresh_btn", use_container_width=True):
                st.rerun()

        st.markdown("<br/>", unsafe_allow_html=True)

        # 2. Resolve Active/Selected Contract
        pos_state = db.get("comm_position_state", "FLAT")
        entry_p = float(db.get("comm_entry_price", "0.0") or 0.0)
        entry_t = db.get("comm_entry_time", "")
        saved_contract = db.get("comm_selected_contract", "")
    
        commodity_assets = [
            "GOLDPETAL", "GOLDM", "GOLD", "SILVERMIC", "SILVERM", "SILVER", 
            "CRUDEOILM", "CRUDEOIL", "NATGASMINI", "NATURALGAS", 
            "COPPER", "NICKEL", "ZINC", "ZINCM", "LEAD", "LEADM", "ALUMINIUM", "ALUMINI"
        ]
    
        widget_asset = st.session_state.get("comm_sel_asset_widget")
        if widget_asset:
            default_asset = widget_asset
        else:
            default_asset = "GOLDPETAL"
            for asset in commodity_assets:
                if saved_contract.startswith(asset):
                    default_asset = asset
                    break
                
        contracts = comm_exec.get_available_contracts(default_asset)
        contract_options = [c["trading_symbol"] for c in contracts]
    
        widget_contract = st.session_state.get("comm_sel_contract_widget")
    
        if pos_state != "FLAT" and saved_contract:
            display_contract = saved_contract
        elif widget_contract:
            display_contract = widget_contract
        elif saved_contract:
            display_contract = saved_contract
        elif contract_options:
            display_contract = contract_options[0]
        else:
            display_contract = ""
        
        ltp = 0.0
        pnl_pct = 0.0
        if display_contract:
            ltp = comm_exec.get_mcx_ltp(display_contract)
            if ltp > 0:
                db.set("comm_current_ltp", str(ltp))
                if pos_state != "FLAT" and entry_p > 0:
                    if pos_state == "LONG":
                        pnl_pct = ((ltp - entry_p) / entry_p) * 100
                    else:
                        pnl_pct = ((entry_p - ltp) / entry_p) * 100
                    db.set("comm_unrealized_pnl_pct", str(round(pnl_pct, 2)))
            else:
                try:
                    ltp = float(db.get("comm_current_ltp", "0") or 0)
                except ValueError:
                    pass
                pnl_pct = float(db.get("comm_unrealized_pnl_pct", "0") or 0)

        # Draw position card
        pos_color = "#22c55e" if pos_state == "LONG" else "#ef4444" if pos_state == "SHORT" else "#64748b"
        pnl_color = "#22c55e" if pnl_pct >= 0 else "#ef4444"
        anchor_p = float(db.get("comm_anchor_price", "0.0") or 0.0)
    
        if anchor_p > 0 and ltp > 0:
            if ltp > anchor_p:
                signal_text, signal_color, signal_bg = "🟢 BULLISH", "#22c55e", "#f0fdf4"
            elif ltp < anchor_p:
                signal_text, signal_color, signal_bg = "🔴 BEARISH", "#ef4444", "#fef2f2"
            else:
                signal_text, signal_color, signal_bg = "⚪ NEUTRAL", "#f59e0b", "#fffbeb"
        else:
            signal_text, signal_color, signal_bg = "⏸️ NO SIGNAL", "#94a3b8", "#f8fafc"

        st.markdown(f"""
        <div style='background:#ffffff;border:1px solid #e2e8f0;border-radius:10px;padding:20px;box-shadow:0 1px 3px rgba(0,0,0,0.05);'>
            <div style='display:flex;justify-content:space-between;align-items:center;'>
                <div>
                    <span style='font-size:0.78rem;color:#94a3b8;font-weight:700;'>ACTIVE CONTRACT</span><br/>
                    <span style='font-size:1.4rem;font-weight:800;color:#1e293b;'>{display_contract or "None Selected"}</span>
                </div>
                <div style='text-align:center;'>
                    <span style='font-size:0.78rem;color:#94a3b8;font-weight:700;'>SIGNAL</span><br/>
                    <span style='background:{signal_bg};color:{signal_color};padding:4px 14px;border-radius:30px;font-size:1.0rem;font-weight:800;border:2px solid {signal_color};'>
                        {signal_text}
                    </span>
                </div>
                <div style='text-align:right;'>
                    <span style='font-size:0.78rem;color:#94a3b8;font-weight:700;'>NET POSITION</span><br/>
                    <span style='background:{pos_color};color:white;padding:4px 12px;border-radius:30px;font-size:1.0rem;font-weight:800;'>
                        {pos_state}
                    </span>
                </div>
            </div>
            <hr style='margin:16px 0;border-color:#f1f5f9;' />
            <div style='display:grid;grid-template-columns:repeat(3, 1fr);gap:16px;'>
                <div>
                    <span style='font-size:0.75rem;color:#94a3b8;font-weight:600;'>Current LTP</span><br/>
                    <span style='font-size:1.15rem;font-weight:700;font-family:monospace;'>₹{ltp:,.2f}</span>
                </div>
                <div>
                    <span style='font-size:0.75rem;color:#f59e0b;font-weight:700;'>⚓ Anchor Price</span><br/>
                    <span style='font-size:1.15rem;font-weight:700;font-family:monospace;color:#f59e0b;'>₹{anchor_p:,.2f}</span>
                </div>
                <div>
                    <span style='font-size:0.75rem;color:#94a3b8;font-weight:600;'>Entry Price</span><br/>
                    <span style='font-size:1.15rem;font-weight:700;font-family:monospace;'>₹{entry_p:,.2f}</span>
                </div>
            </div>
            <div style='display:grid;grid-template-columns:repeat(3, 1fr);gap:16px;margin-top:12px;'>
                <div>
                    <span style='font-size:0.75rem;color:#94a3b8;font-weight:600;'>Entry Time</span><br/>
                    <span style='font-size:0.9rem;font-weight:600;color:#475569;'>{entry_t or "--"}</span>
                </div>
                <div>
                    <span style='font-size:0.75rem;color:#94a3b8;font-weight:600;'>LTP vs Anchor</span><br/>
                    <span style='font-size:1.0rem;font-weight:700;font-family:monospace;color:{signal_color};'>
                        {f"₹{ltp - anchor_p:+,.2f}" if anchor_p > 0 and ltp > 0 else "--"}
                    </span>
                </div>
                <div>
                    <span style='font-size:0.75rem;color:#94a3b8;font-weight:600;'>Unrealized P&L %</span><br/>
                    <span style='font-size:1.2rem;font-weight:800;font-family:monospace;color:{pnl_color};'>
                        {"+" if pnl_pct >= 0 else ""}{pnl_pct:.2f}%
                    </span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<br/>", unsafe_allow_html=True)

        # 3. Settings Form
        with st.expander("🔧 CONFIGURATION & SETTINGS", expanded=saved_contract == ""):
            col_c1, col_c2, col_c3 = st.columns([2, 2, 2])
        
            with col_c1:
                sel_asset = st.selectbox(
                    "Base Commodity Asset",
                    options=commodity_assets,
                    index=commodity_assets.index(default_asset) if default_asset in commodity_assets else 0,
                    key="comm_sel_asset_widget"
                )
            
            default_contract_idx = 0
            if saved_contract in contract_options:
                default_contract_idx = contract_options.index(saved_contract)
            
            with col_c2:
                if not contract_options:
                    st.warning("No active contracts found in CSV.")
                    sel_contract = st.text_input("Enter Trading Symbol manually", value=saved_contract, key="comm_sel_contract_widget")
                    lot_size = int(db.get("comm_lot_size", "1"))
                else:
                    sel_contract = st.selectbox(
                        "MCX Futures Contract",
                        options=contract_options,
                        index=default_contract_idx,
                        key="comm_sel_contract_widget"
                    )
                    resolved_c = [c for c in contracts if c["trading_symbol"] == sel_contract][0]
                    lot_size = resolved_c["lot_size"]
                
            with col_c3:
                st.markdown(f"<br/><p style='font-size:0.85rem;color:#475569;'><b>Lot Size</b>: {lot_size} units</p>", unsafe_allow_html=True)

            col_cfg1, col_cfg2, col_cfg3 = st.columns(3)
            with col_cfg1:
                curr_lots = int(db.get("comm_lots", "1") or 1)
                sel_lots = st.number_input("Lots", min_value=1, max_value=1000, value=curr_lots, key="comm_num_lots")
                curr_cf = db.get("comm_carry_forward", "NO") == "YES"
                sel_cf = st.checkbox("Carry Forward (Overnight)", value=curr_cf)
            with col_cfg2:
                curr_anchor = float(db.get("comm_anchor_price", "0.0") or 0.0)
                sel_anchor = st.number_input("Anchor Price (Rs)", min_value=0.0, value=curr_anchor, step=1.0, format="%.2f")
            
                if ltp > 0:
                    st.markdown(f"<p style='color:#22c55e;font-size:0.88rem;font-weight:700;'>Live Price: ₹{ltp:,.2f}</p>", unsafe_allow_html=True)
                    if st.button("🎯 Set to Live LTP", key="btn_use_live_ltp", use_container_width=True):
                        db.set("comm_anchor_price", str(ltp))
                        _flash(f"Anchor Price preset to live LTP: {ltp}", "info")
                        st.rerun()
                else:
                    st.caption("Live LTP not available to auto-set.")
            with col_cfg3:
                curr_sl = float(db.get("comm_stop_loss_pct", "0.0") or 0.0)
                sel_sl = st.number_input("Stop Loss % (0 to disable)", min_value=0.0, max_value=100.0, value=curr_sl, step=0.1, format="%.2f")
                st.caption("Anchor acts as dynamic flip/SL. Standard SL % is optional.")

            if st.button("💾 Save Commodity Config", key="comm_save_config_btn", type="primary", use_container_width=True):
                db.set("comm_selected_contract", sel_contract)
                db.set("comm_lot_size", str(lot_size))
                db.set("comm_lots", str(sel_lots))
                db.set("comm_anchor_price", str(sel_anchor))
                db.set("comm_stop_loss_pct", str(sel_sl))
                db.set("comm_carry_forward", "YES" if sel_cf else "NO")
                db.set("comm_last_check_candle_time", "")
                _flash("Commodity configuration updated successfully!", "success")
                st.rerun()

        # 4. Manual Controls
        with st.expander("🛡️ MANUAL CONTROLS (EMERGENCY)"):
            mc1, mc2, mc3 = st.columns(3)
            with mc1:
                if st.button("🟢 Force LONG", key="comm_force_long", use_container_width=True):
                    if st.session_state.get("comm_confirm_long"):
                        comm_exec.execute_commodity_flip("LONG")
                        _flash("Forced LONG position.", "success")
                        st.rerun()
                    else:
                        st.session_state["comm_confirm_long"] = True
                        _flash("Click again to confirm FORCE LONG.", "warning")
            with mc2:
                if st.button("🔴 Force SHORT", key="comm_force_short", use_container_width=True):
                    if st.session_state.get("comm_confirm_short"):
                        comm_exec.execute_commodity_flip("SHORT")
                        _flash("Forced SHORT position.", "success")
                        st.rerun()
                    else:
                        st.session_state["comm_confirm_short"] = True
                        _flash("Click again to confirm FORCE SHORT.", "warning")
            with mc3:
                if st.button("⬜ Square Off All", key="comm_square_off", use_container_width=True, type="primary"):
                    if st.session_state.get("comm_confirm_sqoff"):
                        comm_exec.square_off_all_mcx_positions()
                        _flash("Squared off all MCX positions.", "success")
                        st.rerun()
                    else:
                        st.session_state["comm_confirm_sqoff"] = True
                        _flash("Click again to confirm SQUARE OFF.", "warning")


    with tab_commodity:
        render_commodity_tab()

if __name__ == "__main__":
    main()
