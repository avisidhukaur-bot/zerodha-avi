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
import pandas as pd
from datetime import date, datetime
import pytz

# Force UTF-8 on Windows terminals
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import db
import config as cfg
import block_manager as bm
import pnl_engine as pe
import telegram_bot as tg
import equity_200dma_engine as eq_engine
import os_engine
import weekly_st_engine as wst_engine

IST = pytz.timezone("Asia/Kolkata")

def parse_any_expiry_date(d_str: str) -> date:
    """Safely parses any expiry date string (%d-%b-%Y or %Y-%m-%d) into a date object."""
    if not d_str:
        return date.today()
    s = str(d_str).strip()
    for fmt in ("%d-%b-%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            pass
    return date.today()

def normalize_expiry_display(d_str: str) -> str:
    """Normalizes any date string (%Y-%m-%d or %d-%b-%Y) to the standard display format DD-Mon-YYYY."""
    if not d_str:
        return ""
    d = parse_any_expiry_date(d_str)
    return d.strftime("%d-%b-%Y")

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
        "About"       : "Zerodha OptionSelling Engine V5.0 Old & Gold | Port 9007 | NIFTY Only",
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
            if st.button("🔧 Reconcile / Sync DB", key="btn_reconcile", use_container_width=True, help="Scan today's orders to link any filled/pending trades that are not recorded in the DB."):
                import block_manager as bm
                reconciled = bm.reconcile_active_blocks()
                if reconciled > 0:
                    _flash(f"Reconciled: {reconciled} trade(s) synced!", "success")
                else:
                    _flash("DB is already fully synchronized with broker.", "info")
                st.rerun()
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
            if st.button("🔄 Quick Re-Login (TOTP)", use_container_width=True, key="btn_quick_relogin"):
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
                st.rerun()

        if login_status in ("EXPIRED", "PENDING", "FAILED"):
            st.markdown("### 🔌 MANUAL OTP LOGIN")
            
            # Check if there is an active sent OTP session
            sent_session = st.session_state.get("manual_login_session")
            
            if not sent_session:
                # Option A: Send SMS OTP
                if st.button("📲 Send OTP to Mobile", use_container_width=True, key="btn_send_otp_sms"):
                    from kite_executor import kite_executor as _kexec
                    with st.spinner("Requesting OTP..."):
                        res = _kexec.request_login_otp()
                    if res:
                        st.session_state["manual_login_session"] = res
                        _flash("✅ OTP sent to your registered mobile/email!", "success")
                    else:
                        _flash("❌ Failed to request OTP. Check credentials in secrets.txt.", "error")
                    st.rerun()
                
                st.markdown("<div style='text-align: center; margin: 8px 0; color: #64748b; font-size: 0.8rem;'>— OR —</div>", unsafe_allow_html=True)
                
                # Option B: Direct TOTP Entry
                manual_otp = st.text_input(
                    "Google Authenticator / TOTP",
                    max_chars=6,
                    placeholder="e.g. 123456",
                    help="Enter 6-digit code if you use Google Authenticator.",
                    key="input_manual_totp"
                )
                if st.button("🔌 Connect with TOTP", use_container_width=True, key="btn_manual_totp_login"):
                    if not manual_otp or len(manual_otp) != 6 or not manual_otp.isdigit():
                        _flash("Please enter a valid 6-digit code.", "error")
                    else:
                        from kite_executor import kite_executor as _kexec
                        _kexec.access_token  = None
                        _kexec.is_logged_in  = False
                        _kexec.login_time    = None
                        db.set("kite_access_token", "")
                        db.set("kite_is_logged_in", "False")
                        with st.spinner("Connecting with TOTP..."):
                            ok, msg = _kexec.login_with_otp(manual_otp)
                        if ok:
                            db.set("kite_login_status", "OK")
                            tg.alert_login_success()
                            _flash("✅ Login successful! Session active.", "success")
                        else:
                            db.set("kite_login_status", "FAILED")
                            _flash(f"❌ Login failed: {msg}", "error")
                        st.rerun()
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
                    if st.button("🔌 Verify & Connect", use_container_width=True, key="btn_verify_otp"):
                        if not manual_otp or len(manual_otp) != 6 or not manual_otp.isdigit():
                            _flash("Please enter a valid 6-digit OTP code.", "error")
                        else:
                            from kite_executor import kite_executor as _kexec
                            _kexec.access_token  = None
                            _kexec.is_logged_in  = False
                            _kexec.login_time    = None
                            db.set("kite_access_token", "")
                            db.set("kite_is_logged_in", "False")
                            
                            with st.spinner("Verifying OTP..."):
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
                            st.rerun()
                with col2:
                    if st.button("🔄 Cancel", use_container_width=True, key="btn_cancel_otp"):
                        st.session_state.pop("manual_login_session", None)
                        _flash("Session reset. You can request a new OTP now.", "info")
                        st.rerun()

        with st.expander("🔐 Zerodha Credentials & Login", expanded=login_status not in ("OK",)):
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
                if st.button("💾 Save Credentials", use_container_width=True, key="btn_save_credentials"):
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
                        st.rerun()
            with col_s2:
                has_totp = input_totp and input_totp.upper() not in ("YOUR_TOTP_SECRET_KEY", "")
                if st.button("🔑 Run Headless Login", use_container_width=True, key="btn_headless_login", disabled=not has_totp):
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
                    st.rerun()

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

        max_strikes = st.number_input(
            "Max Strikes / Block",
            min_value = 1,
            max_value = 1000,
            value     = int(db.get("max_strikes_per_block", "50")),
            step      = 1,
            key       = "cfg_max_strikes",
            help      = "Maximum number of strikes allowed in a block",
        )
        if max_strikes != int(db.get("max_strikes_per_block", "50")):
            db.set("max_strikes_per_block", str(max_strikes))
            _flash(f"Max strikes per block updated to {max_strikes}", "success")

        st.divider()

        # --- Test buttons ---
        st.markdown("### TOOLS")

        if st.button("📊 Refresh P&L", use_container_width=True, key="btn_refresh"):
            st.session_state["portfolio_pnl"] = _get_portfolio(sim=st.session_state.get("sim_pnl", False))
            st.session_state["last_refresh"]  = time.time()
            st.rerun()

        if st.button("📱 Send Test Alert", use_container_width=True, key="btn_test_tg"):
            r = tg.test_telegram_connection()
            _flash(r["message"], "success" if r["ok"] else "error")
            st.rerun()

        if st.button("📮 Portfolio Summary", use_container_width=True, key="btn_port_sum"):
            pnl  = _get_portfolio(sim=st.session_state.get("sim_pnl", False))
            sent = tg.alert_portfolio_summary(pnl)
            _flash("Portfolio summary sent to Telegram/ntfy!" if sent else "Alert channels not configured.", "success" if sent else "warning")
            st.rerun()

        if st.button("📋 Trade History", use_container_width=True, key="btn_history"):
            st.session_state["show_trade_log"] = not st.session_state.get("show_trade_log", False)
            st.rerun()

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
            'V6.0 ASYMMETRIC | NIFTY Only<br/>VPS 46.224.133.16:9007'
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
    try:
        import regime_engine as _re_head
        live_spot = _re_head.get_current_nifty_spot()
    except Exception:
        live_spot = 0.0

    mode_pill = '<span class="status-pill pill-live">LIVE</span>'
    algo_pill = '<span class="status-pill pill-on">ALGO ON</span>' if algo else '<span class="status-pill pill-off">ALGO OFF</span>'
    v6_pill   = '<span style="background:linear-gradient(135deg, #0284c7 0%, #0369a1 100%);color:#ffffff;padding:4px 10px;border-radius:20px;font-weight:700;font-size:0.75rem;letter-spacing:0.5px;border:1px solid #38bdf8;">⚡ V6.0 ASYMMETRIC ACTIVE</span>'

    pnl_color = "#22c55e" if total >= 0 else "#ef4444"
    pnl_sign  = "+" if total >= 0 else "-"
    spot_str  = f"₹{live_spot:,.2f}" if live_spot > 0 else "--"

    st.markdown(f"""
    <div class="zerodha-header">
        <div>
            <div class="zerodha-title">🌐 ZERODHA OPTIONSELLING ENGINE <span style="font-size:0.8rem; color:#38bdf8; font-weight:700; background:rgba(56,189,248,0.1); padding:2px 8px; border-radius:12px; border:1px solid #0284c7;">V7.5 OS ENGINE</span></div>
            <div class="zerodha-subtitle">
                NIFTY Options SELL | Port 9007 | VPS 46.224.133.16 &nbsp;
                {mode_pill} &nbsp; {algo_pill} &nbsp; {v6_pill} &nbsp;|&nbsp;
                <span style="color:#ffe0b2; font-weight:700;">🎯 NIFTY 50 LIVE SPOT: <span style="color:#38bdf8; font-weight:800; font-family:'JetBrains Mono',monospace;">{spot_str}</span></span>
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
# ADD STRIKE & EXPIRIES HELPERS (Inline per Block)
# ─────────────────────────────────────────────────────────────────────────────
def get_sorted_nifty_expiries():
    from kite_executor import kite_executor
    df = kite_executor._load_security_master()
    expiries = set()
    if not df.empty:
        # Zerodha option master contains name == "NIFTY" and exchange == "NFO"
        filtered = df[(df["name"].str.upper() == "NIFTY") & (df["exchange"].str.upper() == "NFO")]
        for e in filtered["expiry"].dropna().unique():
            expiries.add(str(e).strip())
    sorted_dates = []
    for e in expiries:
        try:
            dt = parse_any_expiry_date(e)
            sorted_dates.append(dt)
        except Exception:
            pass
    sorted_dates = sorted(list(set(sorted_dates)))
    res = [d.strftime("%d-%b-%Y") for d in sorted_dates if d >= date.today()]
    if not res:
        res = [date.today().strftime("%d-%b-%Y")]
    return res


def render_add_strike_form(block_id: int):
    block    = db.get_block(block_id)
    if not block:
        st.session_state["add_strike_block"] = None
        st.rerun()

    block_num = block["block_number"]

    st.markdown(f'<p class="section-title">➕ Add Strike to Block {block_num}</p>', unsafe_allow_html=True)

    block_side = (block.get("side_type") or "BOTH").strip().upper()
    # ── Sell Leg Inputs ──
    st.markdown(f"##### 🔴 Option Selling Leg (SELL) — Block #{block_num} [{block_side} SIDE]")
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
        if block_side == "CALL":
            option_type = "CE"
            st.selectbox(
                "Option Type (CALL)",
                options = ["CE"],
                index   = 0,
                key     = f"sell_ot_{block_id}",
                disabled= True,
                help    = "Locked to CE for Call Side Block"
            )
        elif block_side == "PUT":
            option_type = "PE"
            st.selectbox(
                "Option Type (PUT)",
                options = ["PE"],
                index   = 0,
                key     = f"sell_ot_{block_id}",
                disabled= True,
                help    = "Locked to PE for Put Side Block"
            )
        else:
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

    col_ap1, col_ap2 = st.columns([1.5, 1.2])
    with col_ap1:
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

    with col_ap2:
        add_sl_choice = st.selectbox(
            "Stop Loss %",
            ["25% (Standard Default)", "20% SL", "10% (Tight SL)", "Custom %"],
            index=0,
            key=f"add_sl_choice_{block_id}"
        )
        if add_sl_choice.startswith("25%"):
            add_sl_pct = 25.0
        elif add_sl_choice.startswith("20%"):
            add_sl_pct = 20.0
        elif add_sl_choice.startswith("10%"):
            add_sl_pct = 10.0
        else:
            add_sl_pct = st.number_input("Custom SL %", min_value=1.0, max_value=100.0, value=25.0, step=1.0, key=f"add_custom_sl_{block_id}")
        add_sl_price = round(anchor_price * (1.0 + (add_sl_pct / 100.0)), 2)
        st.caption(f"🎯 SL Trigger: **₹{add_sl_price:.2f}** (+{add_sl_pct:.0f}%)")

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
    is_spread_valid = True
    spread_err_msg = ""
    if not use_existing_hedge:
        # Checkbox to let the user decide whether to buy/add a fresh hedge leg.
        st.checkbox("Add Hedge Leg (BUY)", value=True, key=f"add_hedge_chk_{block_id}")
        if st.session_state.get(f"add_hedge_chk_{block_id}"):
            st.markdown("##### 🟢 Hedge Leg (BUY)")
            hcol1, hcol2 = st.columns([2, 2])
            
            # Dynamic calculation to ensure hedge defaults correctly when strike_price or option_type changes
            expected_hedge_sp = strike_price + 300 if option_type == "CE" else strike_price - 300
            last_sell_key = f"last_sell_sp_{block_id}"
            last_ot_key = f"last_sell_ot_{block_id}"
            hedge_sp_key = f"hedge_sp_{block_id}"

            if (st.session_state.get(last_sell_key) != strike_price) or (st.session_state.get(last_ot_key) != option_type):
                st.session_state[hedge_sp_key] = expected_hedge_sp
                st.session_state[last_sell_key] = strike_price
                st.session_state[last_ot_key] = option_type
            
            with hcol1:
                st.number_input(
                    "Hedge Strike Price",
                    min_value = 10000,
                    max_value = 50000,
                    value     = int(st.session_state.get(hedge_sp_key, expected_hedge_sp)),
                    step      = 50,
                    key       = hedge_sp_key,
                    help      = "CE Hedge must be > Sell Strike. PE Hedge must be < Sell Strike."
                )
                
            with hcol2:
                expiries_list = get_sorted_nifty_expiries()
                block_exp = block["expiry_date"]
                default_idx = 0
                if block_exp in expiries_list:
                    default_idx = expiries_list.index(block_exp)
                elif expiries_list:
                    expiries_list.append(block_exp)
                    def _sort_exp(x):
                        for f in ("%d-%b-%Y", "%Y-%m-%d"):
                            try:
                                return datetime.strptime(str(x).strip(), f)
                            except Exception:
                                pass
                        return datetime.min
                    expiries_list = sorted(list(set(expiries_list)), key=_sort_exp)
                    default_idx = expiries_list.index(block_exp)
                    
                st.selectbox(
                    "Hedge Expiry Date",
                    options = expiries_list,
                    index   = default_idx,
                    key     = f"hedge_exp_{block_id}",
                )

            # Fetch and show live LTP of the Hedge strike
            h_sp = int(st.session_state.get(hedge_sp_key, expected_hedge_sp))
            h_exp = st.session_state.get(f"hedge_exp_{block_id}")
            hedge_sym_info = kite_executor.search_option_symbol(h_exp, h_sp, option_type)
            if hedge_sym_info:
                hedge_ltp = kite_executor.get_ltp(hedge_sym_info["token"], hedge_sym_info["trading_symbol"])
                st.info(f"🛡️ **Hedge Leg Live LTP**: ₹{hedge_ltp:.2f} ({hedge_sym_info['trading_symbol']})")
            else:
                st.warning("⚠️ Hedge option symbol not found in Security Master.")

            # ── Spread Geometry Verification & Visual Badge ──
            if option_type == "CE":
                if h_sp <= strike_price:
                    is_spread_valid = False
                    spread_err_msg = f"🚨 INVALID CE SPREAD: Hedge strike ({h_sp} CE) must be HIGHER than Sell strike ({strike_price} CE) for Option Selling. (Currently Inverted Debit Spread!)"
                else:
                    dist = h_sp - strike_price
                    st.success(f"🟢 **Valid Option Selling Credit Spread**: Sell {strike_price} CE + Buy {h_sp} CE Hedge (+{dist}pts OTM)")
            elif option_type == "PE":
                if h_sp >= strike_price:
                    is_spread_valid = False
                    spread_err_msg = f"🚨 INVALID PE SPREAD: Hedge strike ({h_sp} PE) must be LOWER than Sell strike ({strike_price} PE) for Option Selling. (Currently Inverted Debit Spread!)"
                else:
                    dist = strike_price - h_sp
                    st.success(f"🟢 **Valid Option Selling Credit Spread**: Sell {strike_price} PE + Buy {h_sp} PE Hedge (-{dist}pts OTM)")

            if not is_spread_valid:
                st.error(spread_err_msg)

    st.markdown("---")

    # ── Action Buttons ──
    col_btn1, col_btn2, col_btn3 = st.columns([2, 2, 1])

    with col_btn1:
        if st.button("▶ Execute Live Trade", key=f"btn_exec_trade_{block_id}", type="primary", use_container_width=True, disabled=not is_spread_valid):
            if not is_spread_valid:
                _flash(spread_err_msg, "error")
                st.rerun()
            if anchor_price <= 0:
                _flash("Sell anchor price must be greater than 0.", "error")
                st.rerun()
                
            # Add Sell strike
            sell_res = bm.add_strike_to_block(
                block_id     = block_id,
                strike_price = int(strike_price),
                option_type  = option_type,
                leg_type     = "SELL",
                anchor_price = float(anchor_price),
                lots         = int(lots),
                sl_price     = float(add_sl_price),
                sl_pct       = float(add_sl_pct)
            )
            
            if not sell_res["ok"]:
                _flash(sell_res["message"], "error")
                st.rerun()
                
            sell_strike_id = sell_res["strike_id"]

            # Feature B: If using existing hedge, link it instead of buying new
            if use_existing_hedge and selected_existing_hedge:
                link_res = bm.link_hedge_to_sell(sell_strike_id, selected_existing_hedge["strike_id"])
                if not link_res["ok"]:
                    _flash(f"Hedge linking failed: {link_res['message']}", "error")
                    bm.remove_strike(sell_strike_id)
                    st.rerun()
                _flash_msg_suffix = f" (Using existing hedge {selected_existing_hedge['strike_price']} {selected_existing_hedge['option_type']})"
            elif st.session_state.get(f"add_hedge_chk_{block_id}", False):
                # Add Hedge strike if requested
                hedge_sym_info = kite_executor.search_option_symbol(st.session_state.get(f"hedge_exp_{block_id}"), st.session_state.get(f"hedge_sp_{block_id}"), option_type)
                hedge_ltp = kite_executor.get_ltp(hedge_sym_info["token"], hedge_sym_info["trading_symbol"]) if hedge_sym_info else 0.0
                eff_hedge_anchor = hedge_ltp if hedge_ltp > 0 else 1.0
                h_sp = st.session_state.get(f"hedge_sp_{block_id}", 0)
                h_exp = st.session_state.get(f"hedge_exp_{block_id}", None)
                
                hedge_res = bm.add_strike_to_block(
                    block_id     = block_id,
                    strike_price = int(h_sp),
                    option_type  = option_type,
                    leg_type     = "HEDGE_BUY",
                    anchor_price = eff_hedge_anchor,
                    lots         = int(lots),
                    expiry_date  = h_exp
                )
                
                if hedge_res["ok"]:
                    link_res = bm.link_hedge_to_sell(sell_strike_id, hedge_res["strike_id"])
                    if not link_res["ok"]:
                        _flash(f"Hedge linking failed: {link_res['message']}. Aborting trade.", "error")
                        bm.remove_strike(hedge_res["strike_id"])
                        bm.remove_strike(sell_strike_id)
                        st.rerun()
                else:
                    _flash(f"Hedge creation failed: {hedge_res['message']}. Aborting trade.", "error")
                    bm.remove_strike(sell_strike_id)
                    st.rerun()
                _flash_msg_suffix = ""
            else:
                _flash_msg_suffix = " (No hedge — unhedged sell!)"
                
            # Execute immediately
            r = bm.execute_strike(sell_strike_id)
            if r["ok"]:
                _flash(f"Live trade executed successfully! {r['message']}{_flash_msg_suffix}", "success")
                st.session_state["add_strike_block"] = None
                tg.alert_engine_started()
            else:
                _flash(f"Execution failed: {r['message']}", "error")
            st.rerun()

    with col_btn2:
        if st.button("💾 Save as Pending", key=f"btn_save_pending_{block_id}", use_container_width=True, disabled=not is_spread_valid):
            if not is_spread_valid:
                _flash(spread_err_msg, "error")
                st.rerun()
            if anchor_price <= 0:
                _flash("Sell anchor price must be greater than 0.", "error")
                st.rerun()
                
            # Add Sell strike
            sell_res = bm.add_strike_to_block(
                block_id     = block_id,
                strike_price = int(strike_price),
                option_type  = option_type,
                leg_type     = "SELL",
                anchor_price = float(anchor_price),
                lots         = int(lots),
                sl_price     = float(add_sl_price),
                sl_pct       = float(add_sl_pct)
            )
            
            if not sell_res["ok"]:
                _flash(sell_res["message"], "error")
                st.rerun()
                
            sell_strike_id = sell_res["strike_id"]

            # Feature B: If using existing hedge, link it (no buy needed for pending)
            if use_existing_hedge and selected_existing_hedge:
                link_res = bm.link_hedge_to_sell(sell_strike_id, selected_existing_hedge["strike_id"])
                if not link_res["ok"]:
                    _flash(f"Hedge linking failed: {link_res['message']}", "error")
                    bm.remove_strike(sell_strike_id)
                    st.rerun()
                _flash(
                    f"Sell strike saved as PENDING. Linked to existing hedge "
                    f"{selected_existing_hedge['strike_price']} {selected_existing_hedge['option_type']}.",
                    "success"
                )
            elif st.session_state.get(f"add_hedge_chk_{block_id}", False):
                h_sp = st.session_state.get(f"hedge_sp_{block_id}", 0)
                h_exp = st.session_state.get(f"hedge_exp_{block_id}", None)
                hedge_sym_info = kite_executor.search_option_symbol(h_exp, h_sp, option_type)
                hedge_ltp = kite_executor.get_ltp(hedge_sym_info["token"], hedge_sym_info["trading_symbol"]) if hedge_sym_info else 0.0
                eff_hedge_anchor = hedge_ltp if hedge_ltp > 0 else 1.0
                
                hedge_res = bm.add_strike_to_block(
                    block_id     = block_id,
                    strike_price = int(h_sp),
                    option_type  = option_type,
                    leg_type     = "HEDGE_BUY",
                    anchor_price = eff_hedge_anchor,
                    lots         = int(lots),
                    expiry_date  = h_exp
                )
                
                if hedge_res["ok"]:
                    link_res = bm.link_hedge_to_sell(sell_strike_id, hedge_res["strike_id"])
                    if not link_res["ok"]:
                        _flash(f"Hedge linking failed: {link_res['message']}. Aborting trade.", "error")
                        bm.remove_strike(hedge_res["strike_id"])
                        bm.remove_strike(sell_strike_id)
                        st.rerun()
                    _flash("Sell & Hedge strikes saved as PENDING.", "success")
                else:
                    _flash(f"Hedge creation failed: {hedge_res['message']}. Aborting trade.", "error")
                    bm.remove_strike(sell_strike_id)
                    st.rerun()
            else:
                _flash("Sell strike saved as PENDING.", "success")
                
            st.session_state["add_strike_block"] = None
            st.rerun()

    with col_btn3:
        if st.button("✖ Cancel", key=f"cancel_add_{block_id}", use_container_width=True):
            st.session_state["add_strike_block"] = None
            st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# SUB-BLOCK RENDERER (Inside Unit Pod)
# ─────────────────────────────────────────────────────────────────────────────
def render_sub_block(block_pnl: dict, unit_name: str, key_suffix: str = ""):
    """
    Renders an individual block (e.g. Block 1 CALL or Block 2 PUT) inside its parent Unit Pod.
    Features:
      - Block Header & Side Badge
      - Live Strike Table with Regime Indicators
      - Orphan Hedge Auto-Detector & Profit Lock
      - Inline Add Strike Form (Scoped to this block)
      - Inline Quick Strike Settings: Anchor Price & Lots (Scoped to this block)
      - Action Controls: Execute Block, Re-Arm, Close Strike, Summary
    """
    import regime_engine as re_eng
    import pnl_engine as pe

    ks         = f"_{key_suffix}" if key_suffix else ""
    b          = block_pnl["block"]
    block_id   = b["block_id"]
    block_num  = b["block_number"]
    expiry     = b["expiry_date"]
    exp_type   = b["expiry_type"]
    status     = b["status"]
    side_type  = b.get("side_type", "BOTH")
    is_enabled = b.get("is_enabled", 1)
    total_pnl  = block_pnl.get("total_pnl", 0.0)
    strikes    = block_pnl.get("strike_pnls", [])
    n_open     = block_pnl.get("open_strikes", 0)
    b_regime   = (b.get("current_regime") or "NEUTRAL").strip().upper()

    # Styling based on side
    if side_type == "CALL":
        side_badge = '<span style="background:#dbeafe;color:#1e40af;border:1px solid #93c5fd;padding:2px 10px;border-radius:12px;font-size:0.75rem;font-weight:800;">CALL SIDE (CE)</span>'
        card_border = "#93c5fd"
        hdr_bg = "#eff6ff"
    elif side_type == "PUT":
        side_badge = '<span style="background:#f3e8ff;color:#6b21a8;border:1px solid #d8b4fe;padding:2px 10px;border-radius:12px;font-size:0.75rem;font-weight:800;">PUT SIDE (PE)</span>'
        card_border = "#d8b4fe"
        hdr_bg = "#faf5ff"
    else:
        side_badge = '<span style="background:#ffedd5;color:#c2410c;border:1px solid #fed7aa;padding:2px 10px;border-radius:12px;font-size:0.75rem;font-weight:800;">CALL & PUT</span>'
        card_border = "#fed7aa"
        hdr_bg = "#fff7ed"

    pill_class = {"ACTIVE": "pill-active", "EXPIRED": "pill-expired", "CLOSED": "pill-closed"}.get(status, "pill-active")

    enabled_badge = (
        '<span style="background:#dcfce7;color:#166534;padding:2px 8px;border-radius:10px;font-size:0.75rem;font-weight:700;">🟢 ACTIVE</span>'
        if is_enabled == 1 else
        '<span style="background:#fee2e2;color:#991b1b;padding:2px 8px;border-radius:10px;font-size:0.75rem;font-weight:700;">⏸️ PAUSED</span>'
    )

    ltp_avail = any(s.get("ltp_available") for s in strikes)
    if not ltp_avail:
        pnl_display = '<span style="color:#6b7280;font-size:1.05rem;font-weight:700;">--</span>'
    elif total_pnl >= 0:
        pnl_display = f'<span style="color:#16a34a;font-size:1.15rem;font-weight:800;font-family:\'JetBrains Mono\',monospace;">+Rs{total_pnl:,.2f}</span>'
    else:
        pnl_display = f'<span style="color:#dc2626;font-size:1.15rem;font-weight:800;font-family:\'JetBrains Mono\',monospace;">-Rs{abs(total_pnl):,.2f}</span>'

    # Sub-block Card Header
    st.markdown(
        f'<div style="background:{hdr_bg};border:1px solid {card_border};border-left:5px solid {card_border};border-radius:10px;padding:10px 14px;margin-bottom:8px;">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;">'
        f'<div>'
        f'<span style="font-weight:800;font-size:0.95rem;color:#0f172a;">📦 BLOCK {block_num}</span> &nbsp;&nbsp;'
        f'{side_badge} &nbsp; {enabled_badge} &nbsp;&nbsp;'
        f'<span class="status-pill {pill_class}">{status}</span>'
        f'</div>'
        f'<div style="text-align:right;">'
        f'{pnl_display}'
        f'</div>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True
    )

    col_t1, col_t2 = st.columns([4, 1.2])
    with col_t2:
        is_active = st.toggle("Enable Engine", value=(is_enabled == 1), key=f"toggle_block_enable_{key_suffix}_{block_id}")
        if is_active != (is_enabled == 1):
            bm.toggle_block_enabled(block_id, is_active)
            _flash(f"Block {block_num} " + ("ENABLED" if is_active else "PAUSED"), "success" if is_active else "info")
            st.rerun()

    # Strike Table
    if strikes:
        call_rows = []
        put_rows  = []
        for s in strikes:
            ltp = s.get("ltp", 0.0)
            pnl = s.get("pnl", 0.0)
            la  = s.get("ltp_available", False)

            anchor_str = f"Rs{s['anchor_price']:.2f}"
            if s.get("is_exit_price"):
                ltp_str = f"Exit @ Rs{ltp:.2f}" if ltp > 0 else "Exited"
            elif la:
                ltp_str = f"Rs{s.get('ltp', 0.0):.2f}"
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

            if s["leg_type"] == "SELL" and la and s["anchor_price"] > 0:
                decay = ((s["anchor_price"] - ltp) / s["anchor_price"]) * 100
                decay_str = f"{decay:.1f}%"
            else:
                decay_str = "--"

            is_allowed, reg_reason = re_eng.is_strike_allowed_by_regime(s["option_type"], block=b)
            if not is_allowed:
                reg_status = "🔴 MUTED"
            elif b_regime in ("BULLISH", "BEARISH"):
                reg_status = "🟢 ACTIVE"
            else:
                reg_status = "⚪ ALLOWED"

            sl_p = float(s.get("sl_price") or 0.0)
            sl_pct = float(s.get("sl_pct") or 25.0)
            sl_str = f"₹{sl_p:.2f} (+{sl_pct:.0f}%)" if (s["leg_type"] == "SELL" and sl_p > 0) else "--"
            trade_st = s.get("trade_state") or s.get("status") or "PENDING"

            row = {
                "Strike" : s["strike_price"],
                "Type"   : s["option_type"],
                "Leg"    : s["leg_type"],
                "State"  : trade_st,
                "SL Trigger": sl_str,
                "Regime" : reg_status,
                "Anchor" : anchor_str,
                "LTP"    : ltp_str,
                "Lots"   : s["lots"],
                "Qty"    : s.get("qty", s["lots"] * int(db.get("lot_size","65"))),
                "P&L"    : pnl_str,
                "P&L%"   : pct_str,
                "Decay%" : decay_str,
                "Status" : s["status"],
            }

            if s["option_type"] == "CE":
                call_rows.append(row)
            else:
                put_rows.append(row)

        col_cfg = {
            "Strike": st.column_config.NumberColumn("Strike", format="%d"),
            "State" : st.column_config.TextColumn("V5 State"),
            "SL Trigger": st.column_config.TextColumn("SL Trigger"),
            "Regime": st.column_config.TextColumn("Regime Status"),
            "P&L"  : st.column_config.TextColumn("P&L (Rs)"),
            "P&L%" : st.column_config.TextColumn("P&L %"),
        }

        if call_rows:
            if put_rows:
                st.markdown("<span style='font-weight:700;color:#1e40af;font-size:0.85rem;'>📞 CALL SIDE (CE) STRIKES</span>", unsafe_allow_html=True)
            st.dataframe(pd.DataFrame(call_rows), use_container_width=True, hide_index=True, column_config=col_cfg)

        if put_rows:
            if call_rows:
                st.markdown("<span style='font-weight:700;color:#6b21a8;font-size:0.85rem;'>📥 PUT SIDE (PE) STRIKES</span>", unsafe_allow_html=True)
            st.dataframe(pd.DataFrame(put_rows), use_container_width=True, hide_index=True, column_config=col_cfg)

        # Orphan Hedges Check
        orphaned_hedges = []
        for s in strikes:
            if s["status"] == "OPEN" and s["leg_type"] == "HEDGE_BUY":
                sell_id = s.get("hedge_strike_id")
                is_orphan = False
                if not sell_id:
                    is_orphan = True
                else:
                    sell_strike = db.get_strike(sell_id)
                    if not sell_strike or sell_strike.get("status") != "OPEN":
                        is_orphan = True
                if is_orphan:
                    orphaned_hedges.append(s)

        if orphaned_hedges:
            st.markdown(
                "<div style='background:#fef3c7;border:2px solid #f59e0b;border-radius:8px;padding:8px 12px;margin:8px 0;'>"
                "<span style='color:#b45309;font-weight:700;font-size:0.88rem;'>🎯 ORPHAN HEDGE DETECTED (Partner Sell Leg Closed)</span>"
                "</div>",
                unsafe_allow_html=True
            )
            for h in orphaned_hedges:
                pnl_val = h.get("pnl", 0.0)
                pnl_color = "#16a34a" if pnl_val >= 0 else "#dc2626"
                pnl_prefix = "+" if pnl_val >= 0 else ""
                col_oh1, col_oh2 = st.columns([3, 2])
                with col_oh1:
                    st.markdown(
                        f"🛡️ <b>Hedge {h['strike_price']} {h['option_type']}</b> (#{h['strike_id']}) "
                        f"| Net P&L: <b style='color:{pnl_color};'>{pnl_prefix}₹{pnl_val:,.2f}</b>",
                        unsafe_allow_html=True
                    )
                with col_oh2:
                    btn_text = f"💰 Lock Profit ({pnl_prefix}₹{pnl_val:,.2f})" if pnl_val > 0 else f"✖ Close Hedge"
                    if st.button(btn_text, key=f"close_orphaned_{h['strike_id']}{ks}", use_container_width=True, type="primary" if pnl_val > 0 else "secondary"):
                        res = bm.close_hedge_strike_now(h["strike_id"])
                        if res["ok"]:
                            _flash(res["message"], "success")
                        else:
                            _flash(res["message"], "error")
                        st.rerun()

    else:
        st.markdown('<p style="color:#64748b;font-size:0.85rem;padding:6px 0;">No strikes in this block.</p>', unsafe_allow_html=True)

    # ── Inline Add Strike Form Container (Right inside Block) ──
    if st.session_state.get("add_strike_block") == block_id and key_suffix != "tab3":
        st.markdown("<div style='background:#f8fafc;border:2px solid #3b82f6;border-radius:10px;padding:16px;margin:12px 0;'>", unsafe_allow_html=True)
        render_add_strike_form(block_id)
        st.markdown("</div>", unsafe_allow_html=True)

    # ── Inline Strike Anchor, Stop Loss & Lot Size Editor (Right inside Block) ──
    all_b_strikes = db.get_strikes_by_block(block_id)
    if all_b_strikes:
        with st.expander(f"⚙️ Quick Strike Settings: Anchor Price, Stop Loss & Lots (Block {block_num})", expanded=False):
            strike_map = {
                f"{s['strike_price']} {s['option_type']} {s['leg_type']} (#{s['strike_id']}) — [{s['status']}] | Anchor: ₹{s['anchor_price']:.2f} | SL: ₹{float(s.get('sl_price') or 0):.2f} | Lots: {s['lots']}": s["strike_id"]
                for s in all_b_strikes
            }
            sel_s_label = st.selectbox("Select Strike to Edit", list(strike_map.keys()), key=f"inline_sel_strike_{key_suffix}_{block_id}")
            sel_sid = strike_map[sel_s_label]
            target_s = db.get_strike(sel_sid)

            if target_s:
                t_leg = target_s.get("leg_type", "SELL")
                t_anc = float(target_s.get("anchor_price") or 0.0)
                t_sl = float(target_s.get("sl_price") or 0.0)
                t_sl_pct = float(target_s.get("sl_pct") or 25.0)
                if t_sl <= 0 and t_anc > 0 and t_leg == "SELL":
                    t_sl = round(t_anc * (1.0 + (t_sl_pct / 100.0)), 2)

                c_e1, c_e2, c_e3, c_e4 = st.columns([1.5, 1.6, 1.3, 1.0])
                with c_e1:
                    st.markdown(f"**⚓ Strike Anchor Price** (Current: ₹{t_anc:.2f})")
                    new_anc = st.number_input(
                        "New Anchor Price (₹)",
                        min_value=0.05,
                        value=float(t_anc),
                        step=0.05,
                        format="%.2f",
                        key=f"inline_anc_val_{key_suffix}_{sel_sid}"
                    )
                    auto_recalc_sl = True
                    if t_leg == "SELL":
                        exp_sl = round(new_anc * (1.0 + (t_sl_pct / 100.0)), 2)
                        auto_recalc_sl = st.checkbox(
                            f"Auto-update SL to ₹{exp_sl:.2f} (+{t_sl_pct:.0f}%)",
                            value=True,
                            key=f"inline_auto_sl_{key_suffix}_{sel_sid}",
                            help="Automatically recalculates stop-loss trigger price when Anchor is updated."
                        )
                    if st.button("💾 Update Anchor", key=f"btn_save_inline_anc_{key_suffix}_{sel_sid}", use_container_width=True, type="primary"):
                        res_anc = bm.update_strike_anchor_price(sel_sid, new_anc, auto_recalc_sl=auto_recalc_sl)
                        if res_anc["ok"]:
                            _flash(res_anc["message"], "success")
                        else:
                            _flash(res_anc["message"], "error")
                        st.rerun()

                with c_e2:
                    if t_leg == "SELL":
                        pct_lbl = f"(+{t_sl_pct:.0f}%)" if t_sl_pct > 0 else ""
                        st.markdown(f"**🎯 Stop Loss Price** (Current: ₹{t_sl:.2f} {pct_lbl})")
                        new_sl = st.number_input(
                            "New Stop Loss (₹)",
                            min_value=0.05,
                            value=float(t_sl),
                            step=0.05,
                            format="%.2f",
                            key=f"inline_sl_val_{key_suffix}_{sel_sid}"
                        )
                        if t_anc > 0:
                            calc_diff = new_sl - t_anc
                            calc_p = (calc_diff / t_anc) * 100.0
                            st.caption(f"Distance: **+{calc_p:.1f}%** from Anchor ₹{t_anc:.2f}")

                        # Quick percentage preset buttons
                        p_c1, p_c2, p_c3 = st.columns(3)
                        with p_c1:
                            if st.button("20% SL", key=f"btn_p20_{key_suffix}_{sel_sid}", use_container_width=True, help=f"Set SL to ₹{t_anc * 1.20:.2f} (+20%)"):
                                r_sl = bm.update_strike_sl(sel_sid, round(t_anc * 1.20, 2), 20.0)
                                if r_sl["ok"]: _flash(r_sl["message"], "success")
                                st.rerun()
                        with p_c2:
                            if st.button("25% SL", key=f"btn_p25_{key_suffix}_{sel_sid}", use_container_width=True, help=f"Set SL to ₹{t_anc * 1.25:.2f} (+25%)"):
                                r_sl = bm.update_strike_sl(sel_sid, round(t_anc * 1.25, 2), 25.0)
                                if r_sl["ok"]: _flash(r_sl["message"], "success")
                                st.rerun()
                        with p_c3:
                            if st.button("10% SL", key=f"btn_p10_{key_suffix}_{sel_sid}", use_container_width=True, help=f"Set SL to ₹{t_anc * 1.10:.2f} (+10%)"):
                                r_sl = bm.update_strike_sl(sel_sid, round(t_anc * 1.10, 2), 10.0)
                                if r_sl["ok"]: _flash(r_sl["message"], "success")
                                st.rerun()

                        if st.button("💾 Update Stop Loss", key=f"btn_save_inline_sl_{key_suffix}_{sel_sid}", use_container_width=True, type="primary"):
                            res_sl = bm.update_strike_sl(sel_sid, new_sl)
                            if res_sl["ok"]:
                                _flash(res_sl["message"], "success")
                            else:
                                _flash(res_sl["message"], "error")
                            st.rerun()
                    else:
                        st.markdown("**🛡️ Protective Hedge**")
                        st.info("Hedges do not use Stop Loss triggers. Preserved open as disaster protection.")

                with c_e3:
                    st.markdown(f"**🔢 Strike Lots** (Current: {target_s['lots']} lots)")
                    new_lots = st.number_input(
                        "New Lot Count",
                        min_value=1,
                        max_value=100,
                        value=int(target_s["lots"]),
                        step=1,
                        key=f"inline_lots_val_{key_suffix}_{sel_sid}"
                    )
                    sync_zerodha = False
                    if target_s["status"] == "OPEN":
                        sync_zerodha = st.checkbox("Live Sync Order on Zerodha", value=False, key=f"inline_sync_{key_suffix}_{sel_sid}", help="Automatically places delta order on Zerodha broker")
                    if st.button("💾 Update Lots", key=f"btn_save_inline_lots_{key_suffix}_{sel_sid}", use_container_width=True, type="primary"):
                        res_lots = bm.change_strike_lots(sel_sid, int(new_lots), sync_live=sync_zerodha)
                        if res_lots["ok"]:
                            _flash(res_lots["message"], "success")
                        else:
                            _flash(res_lots["message"], "error")
                        st.rerun()

                with c_e4:
                    st.markdown("**🗑 Actions**")
                    if target_s["status"] == "PENDING":
                        if st.button("🗑 Remove Strike", key=f"btn_del_strike_{key_suffix}_{sel_sid}", use_container_width=True):
                            res_del = bm.remove_strike(sel_sid)
                            if res_del["ok"]:
                                _flash(res_del["message"], "success")
                            else:
                                _flash(res_del["message"], "error")
                            st.rerun()
                    elif target_s["status"] == "OPEN":
                        st.caption("Live position. Use 'Close Strike' button below.")

            # Batch lot scaling for this block
            st.markdown("<hr style='margin:12px 0 8px 0;border:0;border-top:1px dashed #cbd5e1;'/>", unsafe_allow_html=True)
            col_b1, col_b2 = st.columns([2, 3])
            with col_b1:
                default_batch = int(target_s["lots"]) if target_s else 1
                batch_lots = st.number_input(f"Batch Scale All Strikes in Block {block_num}", min_value=1, max_value=100, value=default_batch, key=f"batch_lots_{key_suffix}_{block_id}")
            with col_b2:
                st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
                if st.button(f"⚡ Set ALL Strikes in Block {block_num} to {batch_lots} Lots", key=f"btn_batch_scale_{key_suffix}_{block_id}", use_container_width=True):
                    res_batch = bm.scale_block_lots(block_id, int(batch_lots), sync_live=False)
                    if res_batch["ok"]:
                        _flash(res_batch["message"], "success")
                    else:
                        _flash(res_batch["message"], "error")
                    st.rerun()

    # Rollover Section for open sell strikes
    open_sell_strikes = [s for s in strikes if s["status"] == "OPEN" and s["leg_type"] == "SELL"]
    for sell_s in open_sell_strikes:
        sell_sid     = sell_s["strike_id"]
        linked_h_id  = sell_s.get("hedge_strike_id")
        linked_hedge = db.get_strike(linked_h_id) if linked_h_id else None

        if linked_hedge and linked_hedge["status"] == "OPEN":
            old_hedge_label = f"{linked_hedge['strike_price']} {linked_hedge['option_type']} (exp: {linked_hedge.get('expiry_date', '?')}) — OPEN"
        else:
            old_hedge_label = "None linked"

        with st.expander(f"🔄 Rollover Hedge — {sell_s['strike_price']} {sell_s['option_type']} SELL (#{sell_sid})", expanded=False):
            st.markdown(f"<span style='font-size:0.82rem;color:#475569;'>Current: <b>{old_hedge_label}</b></span>", unsafe_allow_html=True)
            from kite_executor import kite_executor as _kex_rv
            rv_col1, rv_col2, rv_col3 = st.columns([2, 2, 1])

            with rv_col1:
                default_rv_strike = linked_hedge["strike_price"] if linked_hedge else (sell_s["strike_price"] + 300 if sell_s["option_type"] == "CE" else sell_s["strike_price"] - 300)
                rv_strike = st.number_input("New Strike", min_value=10000, max_value=50000, value=int(default_rv_strike), step=50, key=f"rv_strike_{key_suffix}_{sell_sid}")

            with rv_col2:
                rv_expiries = get_sorted_nifty_expiries()
                current_exp = linked_hedge.get("expiry_date", "") if linked_hedge else ""
                default_rv_exp_idx = 0
                for i, e in enumerate(rv_expiries):
                    if e != current_exp:
                        default_rv_exp_idx = i
                        break
                rv_expiry = st.selectbox("New Expiry", options=rv_expiries, index=default_rv_exp_idx, key=f"rv_expiry_{key_suffix}_{sell_sid}")

            with rv_col3:
                rv_lots = st.number_input("Lots", min_value=1, max_value=100, value=sell_s.get("lots", 1), key=f"rv_lots_{key_suffix}_{sell_sid}")

            if st.button("🔄 Execute Rollover", key=f"btn_rollover_{key_suffix}_{sell_sid}", use_container_width=True, type="primary"):
                with st.spinner("Rolling over hedge..."):
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
                st.rerun()

    # Block action buttons
    if status == "ACTIVE":
        col_a, col_b, col_c, col_d, col_e = st.columns([1.3, 1.4, 1.8, 1.8, 1.0])

        with col_a:
            is_adding = (st.session_state.get("add_strike_block") == block_id)
            add_lbl = "✖ Close Form" if is_adding else "➕ Add Strike"
            if st.button(add_lbl, key=f"add_strike_{key_suffix}_{block_id}", use_container_width=True, type="secondary" if is_adding else "primary"):
                st.session_state["add_strike_block"] = None if is_adding else block_id
                st.rerun()

        with col_b:
            block_sum_strikes = bm.get_block_summary(block_id)["strikes"]
            all_pending = [s for s in block_sum_strikes if s["status"] == "PENDING"]
            all_closed = [s for s in block_sum_strikes if s["status"] == "CLOSED"]
            if all_pending:
                if st.button(f"▶ Execute Block ({len(all_pending)})", key=f"exec_block_{key_suffix}_{block_id}", use_container_width=True, type="primary"):
                    r = bm.execute_block(block_id)
                    if r["ok"]:
                        _flash(r["message"], "success")
                        tg.alert_engine_started()
                    else:
                        _flash(r["message"], "error")
                    st.rerun()
            elif all_closed:
                if st.button(f"🔄 Re-Arm Strikes ({len(all_closed)})", key=f"rearm_block_{key_suffix}_{block_id}", use_container_width=True, help="Resets closed strikes to PENDING"):
                    res = bm.rearm_block_strikes(block_id)
                    if res["ok"]:
                        _flash(res["message"], "success")
                    else:
                        _flash(res["message"], "error")
                    st.rerun()

        with col_c:
            open_sells = [s for s in bm.get_block_summary(block_id)["strikes"] if s["status"] == "OPEN" and s["leg_type"] == "SELL"]
            if open_sells:
                strike_options = {
                    f"{s['strike_price']} {s['option_type']} SELL (#{s['strike_id']})": s["strike_id"]
                    for s in open_sells
                }
                sel_label = st.selectbox("Close Strike", options=list(strike_options.keys()), key=f"close_sel_{key_suffix}_{block_id}", label_visibility="collapsed")
                if st.session_state.get(f"confirm_close_strike_{key_suffix}_{block_id}"):
                    st.markdown(f'<div style="background:#fee2e2; border:1px solid #ef4444; border-radius:6px; padding:6px; margin:4px 0; text-align:center;"><span style="color:#991b1b; font-size:0.8rem; font-weight:700;">⚠️ Confirm Square-Off on Kite Broker?</span></div>', unsafe_allow_html=True)
                    cs_yes, cs_no = st.columns(2)
                    with cs_yes:
                        if st.button("🔥 YES", key=f"btn_cs_yes_{key_suffix}_{block_id}", type="primary", use_container_width=True):
                            sid = strike_options[sel_label]
                            result = bm.close_strike(sid, close_hedge=True)
                            st.session_state[f"confirm_close_strike_{key_suffix}_{block_id}"] = False
                            if result["ok"]:
                                _flash(result["message"], "success")
                            else:
                                _flash(result["message"], "error")
                            st.rerun()
                    with cs_no:
                        if st.button("❌ Cancel", key=f"btn_cs_no_{key_suffix}_{block_id}", use_container_width=True):
                            st.session_state[f"confirm_close_strike_{key_suffix}_{block_id}"] = False
                            st.rerun()
                else:
                    if st.button(f"✖ Close Strike & Hedge", key=f"close_btn_{key_suffix}_{block_id}", use_container_width=True):
                        st.session_state[f"confirm_close_strike_{key_suffix}_{block_id}"] = True
                        st.rerun()

        with col_d:
            if st.session_state.get(f"confirm_close_blk_{key_suffix}_{block_id}"):
                st.markdown(f'<div style="background:#fee2e2; border:1px solid #ef4444; border-radius:6px; padding:6px; margin:4px 0; text-align:center;"><span style="color:#991b1b; font-size:0.8rem; font-weight:700;">⚠️ Confirm Square-Off Block #{block_num}?</span></div>', unsafe_allow_html=True)
                cb_yes, cb_no = st.columns(2)
                with cb_yes:
                    if st.button("🔥 YES, Close Block", key=f"btn_cb_yes_{key_suffix}_{block_id}", type="primary", use_container_width=True):
                        st.session_state[f"confirm_close_blk_{key_suffix}_{block_id}"] = False
                        b_rec = db.get_block(block_id)
                        u_name = (b_rec.get("anchor_unit_name") or "").strip().upper() if b_rec else ""
                        if u_name.startswith("M"):
                            res_kill = bm.wipe_out_and_reset_m_unit(u_name)
                        elif u_name.startswith("OS"):
                            res_kill = os_engine.wipe_out_and_reset_os_unit(u_name)
                        else:
                            res_kill = bm.kill_block(block_id)
                        _flash(res_kill.get("message", f"Block {block_num} closed!"), "success" if res_kill.get("ok") else "error")
                        st.rerun()
                with cb_no:
                    if st.button("❌ Cancel", key=f"btn_cb_no_{key_suffix}_{block_id}", use_container_width=True):
                        st.session_state[f"confirm_close_blk_{key_suffix}_{block_id}"] = False
                        st.rerun()
            else:
                if st.button(f"💥 Close Entire Block", key=f"btn_close_blk_{key_suffix}_{block_id}", use_container_width=True, type="primary"):
                    st.session_state[f"confirm_close_blk_{key_suffix}_{block_id}"] = True
                    st.rerun()

        with col_e:
            if st.button(f"📊 Summary", key=f"daily_sum_{key_suffix}_{block_id}", use_container_width=True):
                pnl_data = pe.calc_block_pnl(block_id)
                tg.alert_block_daily_summary(pnl_data)
                _flash(f"Block {block_num} summary sent to Telegram!", "success")
                st.rerun()

    st.markdown('<div style="margin-bottom:12px;"></div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# UNIT POD CONTAINER RENDERER (V5.0 "Old & Gold" Multi-Unit Architecture)
# ─────────────────────────────────────────────────────────────────────────────
def render_unit_pod(unit_name: str, expiry_date: str, block_pnls: list):
    """
    Renders a unified autonomous Unit Pod (e.g. UNIT M1, UNIT M2).
    Contains:
      1. Unit Header Bar (Unit Badge, Expiry, Total Unit P&L, Regime Status)
      2. Unit Master Anchor Controller (One place to edit anchor & buffer for both Call & Put blocks)
      3. Unit Batch Lot Scaler Tool (Scale all strikes in Unit in 1-click)
      4. Clean list of Sub-Blocks inside this unit
    """
    import regime_engine as re_eng

    rep_block   = block_pnls[0]["block"]
    unit_anchor = float(rep_block.get("master_anchor_price") or 0.0)
    unit_buffer = float(rep_block.get("regime_buffer") or 15.0)
    unit_regime = (rep_block.get("current_regime") or "NEUTRAL").strip().upper()
    exp_type    = rep_block.get("expiry_type", "MONTHLY")

    total_unit_pnl = sum(bp.get("total_pnl", 0.0) for bp in block_pnls)

    reg_color = "#10b981" if unit_regime == "BULLISH" else ("#ef4444" if unit_regime == "BEARISH" else "#64748b")
    reg_badge = "🟢 BULLISH (PE Active | CE Muted)" if unit_regime == "BULLISH" else ("🔴 BEARISH (CE Active | PE Muted)" if unit_regime == "BEARISH" else "⚪ NEUTRAL / UNSET")

    pnl_color = "#16a34a" if total_unit_pnl >= 0 else "#dc2626"
    pnl_sign  = "+" if total_unit_pnl >= 0 else ""
    pnl_text  = f"{pnl_sign}Rs{abs(total_unit_pnl):,.2f}"

    # Outer Pod Container Card
    st.markdown(
        f'<div style="background:#ffffff;border:2px solid #4f46e5;border-radius:14px;padding:16px 20px;margin-bottom:28px;box-shadow:0 8px 24px rgba(79,70,229,0.12);">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;border-bottom:2px solid #f1f5f9;padding-bottom:12px;margin-bottom:14px;">'
        f'<div>'
        f'<span style="background:#4f46e5;color:#ffffff;font-size:1.1rem;font-weight:900;padding:5px 16px;border-radius:12px;letter-spacing:0.5px;">🎯 UNIT POD {unit_name}</span>'
        f'<span style="margin-left:14px;font-size:1rem;font-weight:700;color:#1e293b;">Expiry: {expiry_date} ({exp_type.title()})</span>'
        f'<span style="margin-left:12px;font-size:0.82rem;font-weight:800;color:{reg_color};border:1px solid {reg_color};padding:3px 12px;border-radius:12px;background:#f8fafc;">{reg_badge}</span>'
        f'</div>'
        f'<div style="text-align:right;">'
        f'<div style="font-size:0.72rem;color:#64748b;font-weight:800;text-transform:uppercase;">Unit {unit_name} Total P&L</div>'
        f'<div style="font-size:1.5rem;font-weight:800;font-family:\'JetBrains Mono\',monospace;color:{pnl_color};">{pnl_text}</div>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True
    )

    # ── Unit Master Anchor Control Bar (Single for the entire Unit) ──
    st.markdown(
        f'<div style="background:#f8fafc;border:1px solid #e2e8f0;border-left:5px solid {reg_color};border-radius:8px;padding:10px 14px;margin-bottom:14px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;">'
        f'<div>'
        f'<span style="font-weight:800;color:#0f172a;font-size:0.92rem;">🎯 Unit {unit_name} Master Anchor Controller</span>'
        f'<span style="font-size:0.8rem;color:#64748b;margin-left:8px;">(Governs both Call & Put blocks in Unit {unit_name})</span>'
        f'</div>'
        f'<div style="font-size:0.85rem;color:#475569;font-family:\'JetBrains Mono\',monospace;">'
        f'Anchor: <b>₹{unit_anchor:,.2f}</b> | Buffer: <b>±{unit_buffer:.1f}pts</b>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True
    )

    c_anc1, c_anc2, c_anc3, c_anc4, c_anc5 = st.columns([1.6, 1.2, 1.5, 1.4, 1.2])
    with c_anc1:
        new_u_anchor = st.number_input(
            f"Unit {unit_name} Anchor (₹)",
            min_value=0.0,
            max_value=100000.0,
            value=float(unit_anchor),
            step=50.0,
            format="%.2f",
            key=f"input_pod_anchor_{unit_name}_{expiry_date}",
            help=f"Master anchor price for all blocks in Unit {unit_name}"
        )
    with c_anc2:
        new_u_buffer = st.number_input(
            "Buffer (±pts)",
            min_value=0.0,
            max_value=200.0,
            value=float(unit_buffer),
            step=5.0,
            format="%.1f",
            key=f"input_pod_buffer_{unit_name}_{expiry_date}",
            help="Hysteresis buffer to prevent whipsaw flips"
        )
    with c_anc3:
        live_spot = re_eng.get_current_nifty_spot()
        lock_lbl = f"⚡ Lock Spot ({live_spot:,.0f})" if live_spot > 0 else "⚡ Lock Spot"
        if st.button(lock_lbl, key=f"btn_lock_pod_spot_{unit_name}_{expiry_date}", use_container_width=True):
            if live_spot > 0:
                for bp in block_pnls:
                    bid = bp["block"]["block_id"]
                    db.update_block_anchor(bid, live_spot, new_u_buffer, unit_name)
                    up_b = db.get_block(bid)
                    re_eng.evaluate_block_regime(up_b, current_spot=live_spot, force_eval=True)
                _flash(f"Unit {unit_name} Master Anchor locked to live spot ₹{live_spot:,.2f} across all blocks!", "success")
                st.rerun()
            else:
                _flash("Could not fetch live spot price to lock anchor.", "error")
    with c_anc4:
        if st.button("💾 Save Unit Anchor", key=f"btn_save_pod_anchor_{unit_name}_{expiry_date}", use_container_width=True, type="primary"):
            for bp in block_pnls:
                bid = bp["block"]["block_id"]
                db.update_block_anchor(bid, new_u_anchor, new_u_buffer, unit_name)
                up_b = db.get_block(bid)
                re_res = re_eng.evaluate_block_regime(up_b, current_spot=live_spot, force_eval=True)
            _flash(f"Unit {unit_name} Master Anchor saved to ₹{new_u_anchor:,.2f} (Buffer: ±{new_u_buffer:.1f}pts)!", "success")
            st.rerun()
    with c_anc5:
        if st.button("💥 Kill Unit Pod", key=f"btn_kill_pod_{unit_name}_{expiry_date}", use_container_width=True):
            st.session_state[f"confirm_kill_pod_{unit_name}_{expiry_date}"] = True
            st.rerun()

    if st.session_state.get(f"confirm_kill_pod_{unit_name}_{expiry_date}"):
        st.warning(f"⚠️ **CONFIRM KILL SWITCH FOR UNIT POD {unit_name} ({expiry_date})**\nThis will square off all positions across all {len(block_pnls)} block(s) in Unit {unit_name} and delete them. This cannot be undone.")
        col_ky, col_kn, _ = st.columns([2, 2, 4])
        with col_ky:
            if st.button(f"🔴 YES, KILL UNIT {unit_name}", key=f"btn_confirm_kill_pod_{unit_name}_{expiry_date}", type="primary", use_container_width=True):
                st.session_state[f"confirm_kill_pod_{unit_name}_{expiry_date}"] = False
                for bp in block_pnls:
                    bm.kill_block(bp["block"]["block_id"])
                _flash(f"Unit {unit_name} Pod and all its blocks have been killed and cleared.", "success")
                st.rerun()
        with col_kn:
            if st.button("🟢 CANCEL", key=f"btn_cancel_kill_pod_{unit_name}_{expiry_date}", use_container_width=True):
                st.session_state[f"confirm_kill_pod_{unit_name}_{expiry_date}"] = False
                st.rerun()

    # ── Unit Batch Lots Scaler Expander ──
    with st.expander(f"⚡ Batch Scale All Strikes in Unit {unit_name} to N Lots", expanded=False):
        col_u_l1, col_u_l2 = st.columns([2, 3])
        with col_u_l1:
            u_batch_lots = st.number_input(f"Unit {unit_name} Lots", min_value=1, max_value=100, value=1, key=f"unit_batch_lots_{unit_name}_{expiry_date}")
        with col_u_l2:
            st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
            if st.button(f"⚡ Set ALL Strikes in Unit {unit_name} to {u_batch_lots} Lots", key=f"btn_unit_batch_scale_{unit_name}_{expiry_date}", use_container_width=True, type="primary"):
                scaled_tot = 0
                for bp in block_pnls:
                    bid = bp["block"]["block_id"]
                    res_b = bm.scale_block_lots(bid, int(u_batch_lots), sync_live=False)
                    if res_b["ok"]:
                        scaled_tot += 1
                _flash(f"Unit {unit_name}: Scaled all strikes across {scaled_tot} block(s) to {u_batch_lots} lots!", "success")
                st.rerun()

    st.markdown('<hr style="margin:12px 0 14px 0;border:0;border-top:1px solid #e2e8f0;"/>', unsafe_allow_html=True)

    # ── Sub-Blocks inside this Unit Pod ──
    for bp in block_pnls:
        render_sub_block(bp, unit_name, key_suffix="pod")

    st.markdown('</div>', unsafe_allow_html=True)  # Close Pod Container


# ─────────────────────────────────────────────────────────────────────────────
# 🏛️ ALL OPEN UNITS COCKPIT ("Ek Hi Jagah Saari Chijen")
# ─────────────────────────────────────────────────────────────────────────────
def render_all_units_cockpit(portfolio: dict):
    """
    Renders the unified 'All Open Units Cockpit' ("Ek Hi Jagah Saari Chijen").
    Shows every active independent unit (M1, M2, M3...) side-by-side with:
    - Master Anchor & Spot distance
    - Directional Regime (BULLISH / BEARISH)
    - Active Live Sold Leg + Protective Hedge + Armed Counter Wing
    - Stop-Loss price & SL %
    - Re-entry readiness
    - 3:00 PM Continuation Status
    - Live Unit M2M P&L
    - Quick Action buttons (Lock Spot, Re-evaluate, Square-Off)
    """
    import regime_engine as re_eng
    live_spot = re_eng.get_current_nifty_spot()
    if live_spot <= 0:
        try:
            live_spot = float(db.get("last_nifty_spot", "0.0") or 0.0)
        except Exception:
            live_spot = 0.0

    block_pnls = portfolio.get("block_pnls", [])
    active_bps = [
        bp for bp in block_pnls 
        if bp.get("block", {}).get("status") == "ACTIVE" 
        and not (bp.get("block", {}).get("anchor_unit_name") or "").strip().upper().startswith("OS")
    ]

    if not active_bps:
        st.markdown("""
        <div style="background:#f8fafc;border:2px dashed #cbd5e1;border-radius:12px;padding:22px;text-align:center;margin-bottom:18px;">
            <div style="font-size:1.6rem;">🏛️</div>
            <div style="font-weight:700;color:#1e293b;font-size:1.05rem;margin-top:6px;">No Active Autonomous Units Deployed</div>
            <div style="font-size:0.85rem;color:#64748b;margin-top:4px;">
                Deploy independent units (<b>M1, M2, M3...</b>) in the Single-Window Console below. All open units will appear here in one unified cockpit.
            </div>
        </div>
        """, unsafe_allow_html=True)
        return

    # Group by Unit Tag
    from collections import OrderedDict
    units_map = OrderedDict()
    for bp in active_bps:
        b = bp["block"]
        u_name = (b.get("anchor_unit_name") or f"M{b['block_number']}").strip().upper()
        if u_name not in units_map:
            units_map[u_name] = {
                "unit_name": u_name,
                "blocks": [],
                "strike_pnls": [],
                "total_pnl": 0.0,
                "expiry_date": b.get("expiry_date", ""),
                "expiry_type": b.get("expiry_type", "MONTHLY"),
                "master_anchor": float(b.get("master_anchor_price") or 0.0),
                "regime_buffer": float(b.get("regime_buffer") or 15.0),
                "current_regime": (b.get("current_regime") or "NEUTRAL").upper(),
                "lots": int(b.get("custom_lots") or b.get("recommended_lots") or 1),
            }
        units_map[u_name]["blocks"].append(b)
        units_map[u_name]["strike_pnls"].extend(bp.get("strike_pnls", []))
        units_map[u_name]["total_pnl"] += bp.get("total_pnl", 0.0)

    combined_pnl = sum(u["total_pnl"] for u in units_map.values())
    comb_color = "#10b981" if combined_pnl >= 0 else "#ef4444"
    comb_sign = "+" if combined_pnl >= 0 else ""

    # Master Header Bar
    master_hdr_html = (
        f'<div style="background:linear-gradient(135deg, #0f172a 0%, #1e293b 100%);border-left:6px solid #3b82f6;border-radius:12px;padding:16px 20px;margin-bottom:18px;color:#ffffff;box-shadow:0 4px 14px rgba(0,0,0,0.15);">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;">'
        f'<div>'
        f'<div style="font-weight:800;font-size:1.15rem;letter-spacing:0.5px;display:flex;align-items:center;gap:8px;">'
        f'<span>🏛️ ALL OPEN UNITS COCKPIT (M1, M2, M3... AT ONE PLACE)</span>'
        f'<span style="background:#3b82f6;color:#ffffff;font-size:0.75rem;font-weight:700;padding:2px 10px;border-radius:12px;">{len(units_map)} UNITS ACTIVE</span>'
        f'</div>'
        f'<div style="font-size:0.83rem;color:#94a3b8;margin-top:3px;">'
        f'Independent Master Anchors • Isolated Directional Regimes • Decoupled Stop-Loss • 3:00 PM Continuation'
        f'</div>'
        f'</div>'
        f'<div style="text-align:right;">'
        f'<div style="font-size:0.72rem;color:#94a3b8;font-weight:700;text-transform:uppercase;">Combined Units M2M P&L</div>'
        f'<div style="font-size:1.45rem;font-weight:900;font-family:\'JetBrains Mono\',monospace;color:{comb_color};">{comb_sign}₹{abs(combined_pnl):,.2f}</div>'
        f'</div>'
        f'</div>'
        f'</div>'
    )
    st.markdown(master_hdr_html, unsafe_allow_html=True)

    # Render each unit's card
    for u_name, u_data in units_map.items():
        u_pnl = u_data["total_pnl"]
        u_color = "#16a34a" if u_pnl >= 0 else "#dc2626"
        u_sign = "+" if u_pnl >= 0 else ""
        u_anc = u_data["master_anchor"]
        u_buf = u_data["regime_buffer"]
        u_reg = u_data["current_regime"]
        exp_str = u_data["expiry_date"]
        exp_type = u_data["expiry_type"]

        dist_pts = live_spot - u_anc if (live_spot > 0 and u_anc > 0) else 0.0
        dist_str = f"{dist_pts:+.2f} pts"
        dist_color = "#15803d" if dist_pts >= 0 else "#b91c1c"

        if u_reg == "BULLISH":
            reg_badge = '<span style="background:#ecfdf5;border:1px solid #10b981;color:#065f46;padding:3px 10px;border-radius:12px;font-size:0.78rem;font-weight:800;">🟢 BULLISH (PE Active | CE Opposing)</span>'
            p3m_forecast = "<b>PUT SELL</b> continues; CE Wing covered at next pulse."
        elif u_reg == "BEARISH":
            reg_badge = '<span style="background:#fef2f2;border:1px solid #ef4444;color:#991b1b;padding:3px 10px;border-radius:12px;font-size:0.78rem;font-weight:800;">🔴 BEARISH (CE Active | PE Opposing)</span>'
            p3m_forecast = "<b>CALL SELL</b> continues; PE Wing covered at next pulse."
        else:
            reg_badge = f'<span style="background:#f8fafc;border:1px solid #cbd5e1;color:#334155;padding:3px 10px;border-radius:12px;font-size:0.78rem;font-weight:800;">⚪ NEUTRAL (±{u_buf:.1f}pt Buffer Zone)</span>'
            p3m_forecast = f"Within ±{u_buf:.1f}pt Buffer: Both wings held peacefully for natural theta decay."

        # Separate open vs pending vs closed strikes
        strikes = u_data["strike_pnls"]
        open_sells = [s for s in strikes if s.get("status") == "OPEN" and s.get("leg_type") == "SELL"]
        open_hedges = [s for s in strikes if s.get("status") == "OPEN" and s.get("leg_type") == "HEDGE_BUY"]
        pending_legs = [s for s in strikes if s.get("status") == "PENDING" or s.get("trade_state") == "PENDING"]
        sl_hits = [s for s in strikes if s.get("trade_state") in ("SL_HIT", "REENTRY_ELIGIBLE")]

        with st.container():
            unit_hdr_html = (
                f'<div style="background:#ffffff;border:2px solid #e2e8f0;border-radius:12px;padding:16px 20px;margin-bottom:12px;box-shadow:0 2px 8px rgba(0,0,0,0.04);">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;border-bottom:1px solid #f1f5f9;padding-bottom:10px;margin-bottom:12px;gap:8px;">'
                f'<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">'
                f'<span style="background:#1e293b;color:#ffffff;font-size:1rem;font-weight:800;padding:4px 14px;border-radius:8px;letter-spacing:0.5px;">🎯 UNIT {u_name}</span>'
                f'<span style="font-size:0.88rem;font-weight:700;color:#334155;">Expiry: {exp_str} ({exp_type.title()})</span>'
                f'{reg_badge}'
                f'</div>'
                f'<div style="text-align:right;">'
                f'<span style="font-size:0.75rem;color:#64748b;font-weight:700;text-transform:uppercase;">Unit P&L: </span>'
                f'<span style="font-size:1.3rem;font-weight:900;font-family:\'JetBrains Mono\',monospace;color:{u_color};">{u_sign}₹{abs(u_pnl):,.2f}</span>'
                f'</div>'
                f'</div>'
                f'<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:10px 14px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;font-size:0.85rem;">'
                f'<div>'
                f'Anchor: <b>₹{u_anc:,.2f}</b> (±{u_buf:.1f}pts) &nbsp;|&nbsp; '
                f'Spot: <b>₹{live_spot:,.2f}</b> &nbsp;|&nbsp; '
                f'Distance: <b style="color:{dist_color};">{dist_str}</b>'
                f'</div>'
                f'<div style="color:#475569;font-size:0.82rem;">'
                f'⏰ 3-Pulse Cadence (11:00, 13:00, 15:00): {p3m_forecast}'
                f'</div>'
                f'</div>'
                f'</div>'
            )
            st.markdown(unit_hdr_html, unsafe_allow_html=True)

            if not strikes:
                c_emp1, c_emp2 = st.columns([4, 1])
                with c_emp1:
                    st.info(f"Unit {u_name} is created @ Anchor ₹{u_anc:,.2f}, but has no active strikes. Configure strikes in the V5 Console below.")
                with c_emp2:
                    if st.button(f"🗑️ Clear Unit {u_name}", key=f"btn_del_emp_{u_name}", use_container_width=True):
                        for b in u_data["blocks"]:
                            db.force_delete_block(b["block_id"])
                        _flash(f"Empty Unit {u_name} removed.", "info")
                        st.rerun()
            else:
                # Positions Grid (Active Sells, Hedges, Pending Wings)
                c_pos1, c_pos2, c_pos3 = st.columns([2.5, 2.5, 2])
                with c_pos1:
                    st.markdown("<div style='font-size:0.82rem;font-weight:700;color:#1e40af;margin-bottom:6px;'>🟢 ACTIVE SOLD LEGS</div>", unsafe_allow_html=True)
                    if open_sells:
                        for s in open_sells:
                            pnl_val = s.get("pnl", 0.0)
                            p_col = "#16a34a" if pnl_val >= 0 else "#dc2626"
                            p_sgn = "+" if pnl_val >= 0 else ""
                            sl_pr = float(s.get("sl_price") or 0.0)
                            sl_pct_val = float(s.get("sl_pct") or 25.0)
                            re_pr = float(s.get("reentry_price") or 0.0)
                            sl_str = f"₹{sl_pr:.2f} (+{sl_pct_val:.0f}%)" if sl_pr > 0 else "Unset"
                            re_str = f"≤ ₹{re_pr:.2f}" if re_pr > 0 else "Disabled"
                            sell_html = (
                                f"<div style='background:#f0f9ff;border:1px solid #bae6fd;border-radius:6px;padding:8px 10px;margin-bottom:6px;font-size:0.82rem;'>"
                                f"<div style='display:flex;justify-content:space-between;'>"
                                f"<b>{s['strike_price']} {s['option_type']} SELL</b>"
                                f"<b style='color:{p_col};'>{p_sgn}₹{pnl_val:,.2f}</b>"
                                f"</div>"
                                f"<div style='color:#64748b;font-size:0.75rem;margin-top:2px;'>"
                                f"Qty: {s.get('qty', 65)} ({s.get('lots', 1)} lot) | Entry: ₹{s.get('anchor_price', 0):.2f} | LTP: ₹{s.get('ltp', 0):.2f}"
                                f"</div>"
                                f"<div style='color:#475569;font-size:0.75rem;margin-top:2px;'>"
                                f"🎯 SL: <b>{sl_str}</b> | Re-entry: <b>{re_str}</b>"
                                f"</div>"
                                f"</div>"
                            )
                            st.markdown(sell_html, unsafe_allow_html=True)
                            with st.expander(f"✏️ Adjust Anchor / SL ({s['strike_price']} {s['option_type']})", expanded=False):
                                c_ck1, c_ck2 = st.columns(2)
                                with c_ck1:
                                    st.markdown(f"**Anchor**: ₹{s.get('anchor_price', 0.0):.2f}")
                                    ck_anc = st.number_input("New Anchor", min_value=0.05, value=float(s.get('anchor_price', 0.0)), step=0.05, format="%.2f", key=f"ck_anc_in_{s['strike_id']}")
                                    ck_auto_sl = st.checkbox(f"Auto SL (+{sl_pct_val:.0f}%)", value=True, key=f"ck_auto_sl_{s['strike_id']}")
                                    if st.button("💾 Set Anchor", key=f"btn_ck_save_anc_{s['strike_id']}", use_container_width=True):
                                        r = bm.update_strike_anchor_price(s['strike_id'], ck_anc, auto_recalc_sl=ck_auto_sl)
                                        if r["ok"]: _flash(r["message"], "success")
                                        st.rerun()
                                with c_ck2:
                                    ck_curr_sl = float(sl_pr if sl_pr > 0 else (float(s.get('anchor_price', 0.0)) * 1.25))
                                    st.markdown(f"**Stop Loss**: ₹{ck_curr_sl:.2f}")
                                    ck_sl = st.number_input("New SL", min_value=0.05, value=float(ck_curr_sl), step=0.05, format="%.2f", key=f"ck_sl_in_{s['strike_id']}")
                                    if st.button("💾 Set SL", key=f"btn_ck_save_sl_{s['strike_id']}", use_container_width=True):
                                        r = bm.update_strike_sl(s['strike_id'], ck_sl)
                                        if r["ok"]: _flash(r["message"], "success")
                                        st.rerun()
                    else:
                        st.caption("No open short positions currently running.")

                with c_pos2:
                    st.markdown("<div style='font-size:0.82rem;font-weight:700;color:#0369a1;margin-bottom:6px;'>🛡️ PROTECTIVE HEDGES</div>", unsafe_allow_html=True)
                    if open_hedges:
                        for h in open_hedges:
                            hpnl = h.get("pnl", 0.0)
                            hp_col = "#16a34a" if hpnl >= 0 else "#dc2626"
                            hp_sgn = "+" if hpnl >= 0 else ""
                            hedge_html = (
                                f"<div style='background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:8px 10px;margin-bottom:6px;font-size:0.82rem;'>"
                                f"<div style='display:flex;justify-content:space-between;'>"
                                f"<b>{h['strike_price']} {h['option_type']} HEDGE BUY</b>"
                                f"<b style='color:{hp_col};'>{hp_sgn}₹{hpnl:,.2f}</b>"
                                f"</div>"
                                f"<div style='color:#64748b;font-size:0.75rem;margin-top:2px;'>"
                                f"Qty: {h.get('qty', 65)} | Entry: ₹{h.get('anchor_price', 0):.2f} | LTP: ₹{h.get('ltp', 0):.2f}"
                                f"</div>"
                                f"</div>"
                            )
                            st.markdown(hedge_html, unsafe_allow_html=True)
                    else:
                        st.caption("No active hedges currently open.")

                with c_pos3:
                    st.markdown("<div style='font-size:0.82rem;font-weight:700;color:#64748b;margin-bottom:6px;'>⚪ STAGED / COUNTER WING</div>", unsafe_allow_html=True)
                    if pending_legs:
                        for p in pending_legs:
                            p_html = (
                                f"<div style='background:#f8fafc;border:1px dashed #cbd5e1;border-radius:6px;padding:6px 8px;margin-bottom:4px;font-size:0.78rem;color:#475569;'>"
                                f"<b>{p['strike_price']} {p['option_type']} {p.get('leg_type', '')}</b>"
                                f"<span style='color:#94a3b8;margin-left:4px;'>[ARMED PENDING]</span>"
                                f"</div>"
                            )
                            st.markdown(p_html, unsafe_allow_html=True)
                    elif sl_hits:
                        for sh in sl_hits:
                            sh_html = (
                                f"<div style='background:#fef2f2;border:1px solid #fecaca;border-radius:6px;padding:6px 8px;margin-bottom:4px;font-size:0.78rem;color:#991b1b;'>"
                                f"<b>{sh['strike_price']} {sh['option_type']}</b>: SL HIT (Cooldown Active)"
                                f"</div>"
                            )
                            st.markdown(sh_html, unsafe_allow_html=True)
                    else:
                        st.caption("No counter legs staged.")

            # Quick Action Buttons
            c_act1, c_act2, c_act3, _ = st.columns([1.5, 1.5, 1.5, 3.5])
            with c_act1:
                if st.button(f"⚡ Lock Spot to Unit {u_name}", key=f"btn_ck_lock_spot_{u_name}", use_container_width=True):
                    if live_spot > 0:
                        for b in u_data["blocks"]:
                            db.update_block_anchor(b["block_id"], live_spot, u_buf, u_name)
                            up_b = db.get_block(b["block_id"])
                            re_eng.evaluate_block_regime(up_b, current_spot=live_spot, force_eval=True)
                        _flash(f"Unit {u_name} Anchor locked to live spot ₹{live_spot:,.2f}!", "success")
                        st.rerun()
            with c_act2:
                if st.button(f"🔄 Re-Eval Unit {u_name}", key=f"btn_ck_reeval_{u_name}", use_container_width=True):
                    for b in u_data["blocks"]:
                        up_b = db.get_block(b["block_id"])
                        re_eng.evaluate_block_regime(up_b, current_spot=live_spot, force_eval=True)
                    _flash(f"Unit {u_name} re-evaluated against live spot ₹{live_spot:,.2f}!", "info")
                    st.rerun()
            with c_act3:
                if st.session_state.get(f"confirm_ck_kill_{u_name}"):
                    st.markdown(f'<div style="background:#fee2e2; border:1px solid #ef4444; border-radius:6px; padding:4px; margin:2px 0; text-align:center;"><span style="color:#991b1b; font-size:0.75rem; font-weight:700;">Confirm Kill {u_name}?</span></div>', unsafe_allow_html=True)
                    k_yes, k_no = st.columns(2)
                    with k_yes:
                        if st.button("🔥 YES", key=f"btn_ck_yes_{u_name}", type="primary", use_container_width=True):
                            st.session_state[f"confirm_ck_kill_{u_name}"] = False
                            if u_name.startswith("M"):
                                res_k = bm.wipe_out_and_reset_m_unit(u_name)
                            elif u_name.startswith("OS"):
                                res_k = os_engine.wipe_out_and_reset_os_unit(u_name)
                            else:
                                for b in u_data["blocks"]:
                                    bm.kill_block(b["block_id"])
                                res_k = {"ok": True, "message": f"Unit {u_name} closed."}
                            _flash(res_k.get("message", f"Unit {u_name} and all its positions squared off!"), "success" if res_k.get("ok") else "error")
                            st.rerun()
                    with k_no:
                        if st.button("❌ Cancel", key=f"btn_ck_no_{u_name}", use_container_width=True):
                            st.session_state[f"confirm_ck_kill_{u_name}"] = False
                            st.rerun()
                else:
                    if st.button(f"🛑 Kill Unit {u_name}", key=f"btn_ck_kill_{u_name}", use_container_width=True):
                        st.session_state[f"confirm_ck_kill_{u_name}"] = True
                        st.rerun()

            st.markdown("<hr style='margin:12px 0 16px 0; border:0; border-top:1px solid #e2e8f0;'/>", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# MASTER NIFTY REGIME CONTROLLER (Top Macro Summary Bar)
# ─────────────────────────────────────────────────────────────────────────────
def render_master_regime_controller():
    """
    Renders the Master Nifty Multi-Anchor Macro Strip (Top Bar).
    Provides real-time Nifty 50 spot display, quick multi-pod regime summary badges,
    and a global re-evaluate button.
    """
    import regime_engine as re_eng
    
    current_spot = re_eng.get_current_nifty_spot()
    
    # Header Banner Card
    st.markdown(
        '<div style="background:linear-gradient(135deg, #1e293b 0%, #0f172a 100%);border:2px solid #059669;border-radius:12px;padding:16px 20px;margin-bottom:14px;box-shadow:0 4px 15px rgba(5,150,105,0.25);">'
        '<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;">'
        '<div>'
        '<div style="font-size:1.2rem;font-weight:800;color:#ffffff;letter-spacing:0.5px;">🎯 MASTER NIFTY CONTROLLER (V5.0 "OLD & GOLD" ARCHITECTURE)</div>'
        '<div style="font-size:0.82rem;color:#cbd5e1;margin-top:4px;">Autonomous Multi-Unit Architecture (M1, M2, M3...) • Independent Master Anchors & Isolated Regimes • 3:00 PM Continuation Decision • Decoupled Individual Stop-Loss • Orphan Hedge Preservation</div>'
        '</div>'
        '<div>'
        '<span style="background:#059669;color:#ffffff;font-size:0.8rem;font-weight:700;padding:5px 14px;border-radius:20px;letter-spacing:0.5px;">⚡ V5.0 OLD & GOLD ACTIVE</span>'
        '</div>'
        '</div>'
        '</div>',
        unsafe_allow_html=True
    )

    # Top Macro Row
    active_blocks = db.get_all_blocks(status_filter="ACTIVE")
    
    col_spot, col_pods, col_btn = st.columns([1.5, 3.8, 1.4])
    with col_spot:
        spot_str = f"₹{current_spot:,.2f}" if current_spot > 0 else "Fetching..."
        st.markdown(
            f'<div style="background:#ffffff;border:1px solid #cbd5e1;border-radius:8px;padding:8px 12px;text-align:center;">'
            f'<div style="font-size:0.7rem;color:#64748b;font-weight:700;text-transform:uppercase;">NIFTY 50 Live Spot</div>'
            f'<div style="font-size:1.35rem;font-weight:800;color:#0f172a;font-family:\'JetBrains Mono\',monospace;">{spot_str}</div>'
            f'</div>',
            unsafe_allow_html=True
        )
        
    with col_pods:
        if active_blocks:
            pods_summary = {}
            for b in active_blocks:
                u_name = b.get("anchor_unit_name") or f"M{b['block_number']}"
                if u_name not in pods_summary:
                    pods_summary[u_name] = {
                        "anchor": float(b.get("master_anchor_price") or 0.0),
                        "regime": (b.get("current_regime") or "NEUTRAL").upper(),
                        "buffer": float(b.get("regime_buffer") or 15.0),
                        "expiry": b.get("expiry_date", "")
                    }
            
            badges_html = []
            for uname, udata in pods_summary.items():
                ureg = udata["regime"]
                uanc = udata["anchor"]
                if ureg == "BULLISH":
                    bg = "#ecfdf5"; border = "#10b981"; txt = "#065f46"; badge = "🟢 BULLISH"
                elif ureg == "BEARISH":
                    bg = "#fef2f2"; border = "#ef4444"; txt = "#991b1b"; badge = "🔴 BEARISH"
                else:
                    bg = "#f8fafc"; border = "#cbd5e1"; txt = "#334155"; badge = "⚪ NEUTRAL"
                anc_str = f"₹{uanc:,.0f}" if uanc > 0 else "Unset"
                badges_html.append(
                    f'<span style="background:{bg};border:1px solid {border};color:{txt};padding:6px 12px;border-radius:8px;font-size:0.82rem;font-weight:800;margin-right:8px;display:inline-block;margin-bottom:4px;">'
                    f'🎯 Unit {uname}: <b>{anc_str}</b> ({badge})'
                    f'</span>'
                )
            st.markdown(
                f'<div style="padding:4px 0;">'
                f'<div style="font-size:0.72rem;color:#64748b;font-weight:700;margin-bottom:4px;">ACTIVE PODS SUMMARY (Edit anchors inside each Pod card below):</div>'
                f'{"".join(badges_html)}'
                f'</div>',
                unsafe_allow_html=True
            )
        else:
            st.info("No active units currently deployed.")

    with col_btn:
        if st.button("🔄 Re-Evaluate All", key="btn_reeval_all_pods_top", use_container_width=True):
            eval_res = re_eng.evaluate_all_block_regimes(force_eval=True)
            _flash(f"All Units Re-Evaluated at Spot ₹{eval_res.get('spot', 0):,.2f}!", "info")
            st.rerun()

    st.markdown('<hr style="margin:10px 0 14px 0;border:0;border-top:1px solid #e2e8f0;"/>', unsafe_allow_html=True)



# ─────────────────────────────────────────────────────────────────────────────
# V7.0 SUPER SUKHOI AUTONOMOUS LADDERING HUD (BRICK 5)
# ─────────────────────────────────────────────────────────────────────────────
def render_super_sukhoi_radar_hud():
    """
    Renders V7.0 Super Sukhoi Autonomous Directional Laddering HUD & Telemetry Card.
    Provides 1-Click Fire-and-Forget auto scaling for M1, M2, M3.
    """
    try:
        import super_sukhoi_engine as sukhoi
    except Exception as e:
        st.error(f"Super Sukhoi Module load error: {e}")
        return

    st_data = sukhoi.get_super_sukhoi_status()
    is_active = st_data["active"]
    live_spot = st_data["live_spot"]
    m1_anchor = st_data["m1_anchor"]
    triggers = st_data["triggers"]
    m2_deployed = st_data["m2_deployed"]
    m2_dir = st_data["m2_direction"]
    m3_deployed = st_data["m3_deployed"]
    m3_dir = st_data["m3_direction"]
    sl_mode = st_data["stoploss_mode"]

    hud_border = "#10b981" if is_active else "#334155"
    hud_bg = "linear-gradient(135deg, rgba(6, 78, 59, 0.4) 0%, rgba(15, 23, 42, 0.95) 100%)" if is_active else "linear-gradient(135deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.9) 100%)"
    badge_color = "#34d399" if is_active else "#94a3b8"
    badge_bg = "rgba(52, 211, 153, 0.2)" if is_active else "rgba(148, 163, 184, 0.15)"
    badge_text = "🟢 AUTONOMOUS AUTO-PILOT ON" if is_active else "⚪ MANUAL COCKPIT MODE"

    st.markdown(f"""
    <div style="background: {hud_bg}; border: 1.5px solid {hud_border}; border-radius: 14px; padding: 18px 22px; margin-bottom: 18px; box-shadow: 0 4px 20px rgba(0,0,0,0.3);">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; margin-bottom: 14px;">
            <div style="display: flex; align-items: center; gap: 10px;">
                <span style="font-size: 1.25rem; font-weight: 800; color: #ffffff; letter-spacing: 0.5px;">
                    🦅 SUPER SUKHOI V7.0 — AUTONOMOUS DIRECTIONAL LADDERING
                </span>
            </div>
            <span style="background: {badge_bg}; border: 1px solid {badge_color}; color: {badge_color}; font-size: 0.82rem; padding: 4px 14px; border-radius: 20px; font-weight: 800; letter-spacing: 0.5px;">
                {badge_text}
            </span>
        </div>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-bottom: 12px;">
            <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 10px; padding: 12px;">
                <div style="font-size: 0.75rem; color: #94a3b8; font-weight: 700; text-transform: uppercase;">Seed Unit M1 Anchor</div>
                <div style="font-size: 1.3rem; font-weight: 800; color: #38bdf8; font-family: monospace;">₹{m1_anchor:,.2f}</div>
                <div style="font-size: 0.78rem; color: #cbd5e1; margin-top: 2px;">Lots: {st_data['m1_lots']} | Spot: ₹{live_spot:,.2f}</div>
            </div>
            <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 10px; padding: 12px;">
                <div style="font-size: 0.75rem; color: #94a3b8; font-weight: 700; text-transform: uppercase;">Tier 1: M2 Triggers (±2.00%)</div>
                <div style="font-size: 0.95rem; font-family: monospace; margin-top: 2px;">
                    📈 UP: <b style="color: #34d399;">₹{triggers['m2_up']:,.2f}</b><br/>
                    📉 DOWN: <b style="color: #f87171;">₹{triggers['m2_down']:,.2f}</b>
                </div>
                <div style="font-size: 0.78rem; color: {'#34d399' if m2_deployed else '#94a3b8'}; margin-top: 3px; font-weight: 600;">
                    Status: {'✅ DEPLOYED (' + m2_dir + ')' if m2_deployed else '⏳ Standby Radar'}
                </div>
            </div>
            <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 10px; padding: 12px;">
                <div style="font-size: 0.75rem; color: #94a3b8; font-weight: 700; text-transform: uppercase;">Tier 2: M3 Triggers (±4.00%)</div>
                <div style="font-size: 0.95rem; font-family: monospace; margin-top: 2px;">
                    📈 UP: <b style="color: #34d399;">₹{triggers['m3_up']:,.2f}</b><br/>
                    📉 DOWN: <b style="color: #f87171;">₹{triggers['m3_down']:,.2f}</b>
                </div>
                <div style="font-size: 0.78rem; color: {'#34d399' if m3_deployed else '#94a3b8'}; margin-top: 3px; font-weight: 600;">
                    Status: {'✅ DEPLOYED (' + m3_dir + ')' if m3_deployed else '⏳ Standby Radar'}
                </div>
            </div>
        </div>
        <div style="display: flex; gap: 16px; flex-wrap: wrap; font-size: 0.8rem; color: #cbd5e1; border-top: 1px solid rgba(255, 255, 255, 0.08); padding-top: 8px;">
            <span>🛡️ <b>Compulsory Hedge Helmet:</b> 100% ACTIVE (±500 pts)</span>
            <span>✂️ <b>25% Midday Stop-Loss:</b> <b style="color: {'#34d399' if sl_mode == 'DISABLED' else '#fbbf24'};">{sl_mode} (Theta Harvest)</b></span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Confirmation Modal state
    if st.session_state.get("confirm_activate_super_sukhoi"):
        st.warning(
            f"⚠️ **CONFIRM SUPER SUKHOI V7.1 ACTIVATION**\n\n"
            f"Are you sure you want to activate Full Autonomous Super Sukhoi Mode?\n\n"
            f"• **Seed Anchor (M1)**: ₹{m1_anchor:,.2f}\n"
            f"• **Inherited Lot Size**: {st_data['m1_lots']} Lots ({st_data['m1_lots'] * 65} Qty)\n"
            f"• **Tier 1 (M2)**: Auto-deploys Bull Put Spread at ≥ ₹{triggers['m2_up']:,.2f} OR Bear Call Spread at ≤ ₹{triggers['m2_down']:,.2f}\n"
            f"• **Dynamic Re-Anchoring**: At fill, M2 anchor locks to actual execution spot price (Round to nearest 50).\n"
            f"• **Sequential Chaining**: M3 derives exclusively from M2 actual anchor (never double-triggers with M2).\n"
            f"• **Compulsory Hedge Helmet**: Zerodha pre-buys 500-pt hedge FIRST, sells short SECOND.\n\n"
            f"Once activated, the engine will manage directional scaling autonomously without requiring screen time."
        )
        col_yes, col_no = st.columns(2)
        with col_yes:
            if st.button("🚀 YES, START SUPER SUKHOI NOW", type="primary", use_container_width=True, key="btn_confirm_sukhoi_yes"):
                res = sukhoi.activate_super_sukhoi(
                    m1_anchor=m1_anchor,
                    expiry_date=st_data.get("m1_expiry", ""),
                    lots=int(st_data.get("m1_lots", 3))
                )
                st.session_state["confirm_activate_super_sukhoi"] = False
                _flash(res.get("message", "Super Sukhoi Activated"), "success" if res.get("ok") else "error")
                st.rerun()
        with col_no:
            if st.button("❌ Cancel", use_container_width=True, key="btn_confirm_sukhoi_no"):
                st.session_state["confirm_activate_super_sukhoi"] = False
                st.rerun()
    elif not is_active:
        if st.button("🚀 ACTIVATE SUPER SUKHOI AUTO-MODE (M2/M3 FIRE & FORGET)", type="primary", use_container_width=True, key="btn_req_sukhoi_activate"):
            st.session_state["confirm_activate_super_sukhoi"] = True
            st.rerun()
    else:
        col_d1, col_d2, col_d3 = st.columns([2, 1, 1])
        with col_d1:
            st.success("🦅 **Super Sukhoi Auto-Pilot is Running**: Continuously monitoring Nifty Spot every 30 seconds.")
        with col_d2:
            if st.button("🛑 Deactivate Auto-Mode", use_container_width=True, key="btn_sukhoi_deact"):
                sukhoi.deactivate_super_sukhoi()
                _flash("Super Sukhoi Deactivated back to Manual Cockpit.", "info")
                st.rerun()
        with col_d3:
            if st.button("🔄 Reset M2/M3 Locks", use_container_width=True, key="btn_sukhoi_reset_locks"):
                sukhoi.reset_super_sukhoi_deployments()
                _flash("M2/M3 deployment locks reset.", "info")
                st.rerun()

    st.markdown('<div style="margin-bottom: 16px;"></div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# V5.0 UNIFIED MASTER STRATEGY CONSOLE ("Ek Hi Jagah Saari Chijen")
# ─────────────────────────────────────────────────────────────────────────────
def render_unified_v5_master_console():
    # ── Super Sukhoi Autonomous Directional Radar HUD (Brick 5) ──
    render_super_sukhoi_radar_hud()

    st.markdown("""
    <div style="background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border: 1.5px solid #0284c7; border-radius: 12px; padding: 18px 24px; margin-bottom: 20px;">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
            <div>
                <span style="font-size: 1.25rem; font-weight: 700; color: #ffffff;">
                    🏛️ Directional M-Units Cockpit (V6.0 — Asymmetric Trend & Auto-Hunter)
                </span>
                <div style="font-size: 0.85rem; color: #cbd5e1; margin-top: 4px;">
                    User-Defined Spot Anchor &bull; ~₹200 Premium Hunter (EVEN 100s) &bull; 500-pt Hedge Helmet &bull; Strict 25% SL on Entry Fill
                </div>
            </div>
            <div style="margin-top: 8px;">
                <span style="background: rgba(2, 132, 199, 0.2); border: 1px solid #0284c7; color: #38bdf8; font-size: 0.75rem; padding: 4px 12px; border-radius: 20px; font-weight: 600;">
                    V6.0 ACTIVE
                </span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 1. Pod Selection (M1, M2, M3, M4)
    selected_pod = st.selectbox("Select Directional M-Unit Pod", ["M1", "M2", "M3", "M4"], index=0, key="m_cockpit_pod_select")

    m_cfg = db.get_m_unit_settings(selected_pod)
    is_locked = m_cfg.get("locked", False)


    cat_expiries = os_engine.get_categorized_expiries()
    all_expiries = cat_expiries.get("all", ["2026-10-27"])

    from kite_executor import kite_executor
    live_spot = kite_executor.get_nifty_spot()
    if live_spot <= 0:
        live_spot = float(db.get("last_nifty_spot_price", "23200.0") or "23200.0")

    # ── CASE A: LOCKED & ARMED MODE ──────────────────────────────────────────
    if is_locked:
        s_anchor = m_cfg.get("anchor_price", 23350.0)
        s_horizon = m_cfg.get("horizon", "Monthly Expiry")
        s_exp = m_cfg.get("expiry_date", "")
        s_lots = m_cfg.get("lots", 1)
        s_ls = m_cfg.get("lot_size", 65)
        s_total_qty = s_lots * s_ls
        s_mode = m_cfg.get("mode", "AUTO")
        s_ce = m_cfg.get("manual_ce", 0)
        s_pe = m_cfg.get("manual_pe", 0)
        s_tp = m_cfg.get("target_premium", 200.0)
        s_locked_at = m_cfg.get("locked_at", "")

        regime = "BULLISH" if live_spot >= s_anchor else "BEARISH"
        diff = live_spot - s_anchor
        diff_str = f"+{diff:.2f}" if diff >= 0 else f"{diff:.2f}"
        reg_badge = '<span style="background: #10b981; color: #ffffff; padding: 3px 10px; border-radius: 6px; font-weight: 800; font-size: 0.85rem;">🟢 BULLISH (Spot ≥ Anchor)</span>' if regime == "BULLISH" else '<span style="background: #ef4444; color: #ffffff; padding: 3px 10px; border-radius: 6px; font-weight: 800; font-size: 0.85rem;">🔴 BEARISH (Spot < Anchor)</span>'
        mode_badge = f"🎯 Manual Strikes ({s_ce} CE / {s_pe} PE)" if s_mode == "MANUAL" else f"🏹 Auto Hunter (~₹{s_tp:.0f} on EVEN 100s)"

        st.markdown(f'''
        <div style="background: #04241a; border: 2px solid #10b981; border-radius: 12px; padding: 18px 24px; margin-bottom: 20px; color: #ffffff;">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
                <div>
                    <span style="font-size: 1.2rem; font-weight: 800; color: #34d399;">
                        🔒 {selected_pod} SETTINGS LOCKED & ARMED
                    </span>
                    <span style="background: #064e3b; color: #a7f3d0; font-size: 0.75rem; padding: 2px 10px; border-radius: 12px; font-weight: 700; margin-left: 10px;">
                        SYSTEM ACTIVE
                    </span>
                    <div style="font-size: 0.90rem; color: #ffffff; margin-top: 6px;">
                        Locked on: <b style="color: #a7f3d0;">{s_locked_at}</b> &bull; Watching Spot vs User-Set Anchor for continuation.
                    </div>
                </div>
                <div>
                    {reg_badge}
                </div>
            </div>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin-top: 14px; background: #021a13; padding: 14px; border-radius: 8px; font-size: 0.92rem; color: #ffffff;">
                <div>🏛️ <b style="color: #93c5fd;">User Anchor:</b> <span style="font-size: 1.1rem; color: #38bdf8; font-weight: 700;">₹{s_anchor:,.2f}</span></div>
                <div>📊 <b style="color: #93c5fd;">Live Spot:</b> <b>₹{live_spot:,.2f}</b> <span style="color: {'#4ade80' if diff >= 0 else '#f87171'}; font-weight: 600;">({diff_str})</span></div>
                <div>🎯 <b style="color: #93c5fd;">Expiry Date:</b> {s_exp} ({s_horizon})</div>
                <div>📦 <b style="color: #93c5fd;">Lots & Size:</b> {s_lots} Lot(s) &times; {s_ls} Qty = <b style="color: #fde047;">{s_total_qty} units</b></div>
                <div>⚡ <b style="color: #93c5fd;">Strategy Mode:</b> <span style="color: #34d399; font-weight: 700;">{mode_badge}</span></div>
            </div>
        </div>
        ''', unsafe_allow_html=True)

        col_l1, col_l2, col_l3 = st.columns([1.2, 1.8, 2.0])
        with col_l1:
            if st.button(f"🔓 Unlock {selected_pod} Settings", key=f"btn_m_unlock_{selected_pod}", use_container_width=True):
                db.unlock_m_unit_settings(selected_pod)
                st.session_state.pop(f"m_inspection_{selected_pod}", None)
                _flash(f"{selected_pod} settings unlocked. Returned to Draft Mode.", "info")
                st.rerun()

        with col_l2:
            if st.session_state.get(f"confirm_wipe_m_{selected_pod}"):
                st.markdown(f'<div style="background:#fee2e2; border:1px solid #ef4444; border-radius:6px; padding:4px; margin:2px 0; text-align:center;"><span style="color:#991b1b; font-size:0.75rem; font-weight:700;">Confirm Wipe {selected_pod}?</span></div>', unsafe_allow_html=True)
                w_yes, w_no = st.columns(2)
                with w_yes:
                    if st.button(f"🔥 YES, Wipe", key=f"btn_wipe_yes_{selected_pod}", type="primary", use_container_width=True):
                        st.session_state[f"confirm_wipe_m_{selected_pod}"] = False
                        res_w = bm.wipe_out_and_reset_m_unit(selected_pod)
                        st.session_state.pop(f"m_inspection_{selected_pod}", None)
                        if res_w.get("ok"):
                            _flash(res_w.get("message"), "success")
                        else:
                            _flash(res_w.get("message"), "error")
                        st.rerun()
                with w_no:
                    if st.button("❌ Cancel", key=f"btn_wipe_no_{selected_pod}", use_container_width=True):
                        st.session_state[f"confirm_wipe_m_{selected_pod}"] = False
            else:
                if st.button(f"💥 Wipe Out & Reset {selected_pod}", key=f"btn_m_wipe_{selected_pod}", use_container_width=True, type="primary", help="Safely closes broker legs, purges DB records for this pod, and unlocks settings."):
                    st.session_state[f"confirm_wipe_m_{selected_pod}"] = True
                    st.rerun()

        with col_l3:
            btn_fetch_locked = st.button("🔍 Fetch Live Candidate Prices & Regime Status", key=f"btn_m_fetch_locked_{selected_pod}", use_container_width=True)

        if btn_fetch_locked or f"m_inspection_{selected_pod}" not in st.session_state:
            with st.spinner(f"Fetching live EVEN 100 contracts for {selected_pod}..."):
                st.session_state[f"m_inspection_{selected_pod}"] = bm.inspect_m_unit_candidates(
                    expiry_date=s_exp,
                    unit_name=selected_pod,
                    master_anchor_price=s_anchor,
                    target_premium=s_tp,
                    manual_ce_strike=s_ce if s_mode == "MANUAL" else None,
                    manual_pe_strike=s_pe if s_mode == "MANUAL" else None,
                    hedge_dist=500
                )

        selected_exp = s_exp
        user_anchor = s_anchor
        lots = s_lots
        user_lot_size = s_ls
        target_prem = s_tp
        m_ce = s_ce if s_mode == "MANUAL" else None
        m_pe = s_pe if s_mode == "MANUAL" else None

    # ── CASE B: UNLOCKED DRAFT MODE ──────────────────────────────────────────
    else:
        st.markdown(f'''
        <div style="background: #1e1b10; border: 2px solid #f59e0b; border-radius: 12px; padding: 18px 24px; margin-bottom: 20px; color: #ffffff;">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
                <div>
                    <span style="font-size: 1.2rem; font-weight: 800; color: #fbbf24;">
                        ⚠️ {selected_pod} IN UNLOCKED DRAFT MODE
                    </span>
                    <span style="background: #451a03; color: #fde68a; font-size: 0.75rem; padding: 2px 10px; border-radius: 12px; font-weight: 700; margin-left: 10px;">
                        NO TRADES ALLOWED
                    </span>
                    <div style="font-size: 0.90rem; color: #ffffff; margin-top: 6px; line-height: 1.5;">
                        Configure your <b>Master Anchor Price</b>, Expiry, Lots, and Strike Mode below, preview candidate strikes, and click <b style="color: #fbbf24;">'🔒 Lock & Arm {selected_pod} Settings'</b> to activate.
                    </div>
                </div>
            </div>
        </div>
        ''', unsafe_allow_html=True)

        st.markdown(f'<p class="section-title">🎛️ STEP 1: CONFIGURE & PREVIEW STRIKES ({selected_pod} DRAFT)</p>', unsafe_allow_html=True)

        with st.container():
            st.markdown('<div class="block-card">', unsafe_allow_html=True)
            col_h1, col_h2, col_h3, col_h4, col_h5 = st.columns([1.5, 2, 1.4, 0.9, 1.2])

            with col_h1:
                cur_hor = m_cfg.get("horizon", "Monthly Expiry")
                horizon = st.radio("Expiry Horizon", ["Monthly Expiry", "Weekly Expiry"], index=0 if cur_hor == "Monthly Expiry" else 1, horizontal=True, key=f"m_tab_horizon_{selected_pod}")
                active_list = cat_expiries.get("monthly", []) if horizon == "Monthly Expiry" else cat_expiries.get("weekly", [])
                if not active_list:
                    active_list = all_expiries

            with col_h2:
                cur_exp = m_cfg.get("expiry_date", "")
                exp_idx = active_list.index(cur_exp) if cur_exp in active_list else 0
                selected_exp = st.selectbox(f"Select {horizon} Date", active_list, index=exp_idx, key=f"m_tab_exp_{selected_pod}")

            with col_h3:
                user_anchor = st.number_input(
                    f"🏛️ {selected_pod} Anchor (Nifty Spot)",
                    value=float(m_cfg.get("anchor_price", 23350.0)),
                    step=25.0,
                    format="%.2f",
                    key=f"m_tab_user_anchor_{selected_pod}",
                    help="Benchmark Anchor Price strictly specified by the user for this pod."
                )

            with col_h4:
                lots = st.number_input("Lots", min_value=1, max_value=50, value=m_cfg.get("lots", 1), step=1, key=f"m_tab_lots_{selected_pod}")
                user_lot_size = int(db.get("lot_size", "65") or "65")

            with col_h5:
                target_prem = st.number_input("Target Premium (~₹)", value=m_cfg.get("target_premium", 200.0), step=10.0, format="%.1f", key=f"m_tab_tp_{selected_pod}")

            calc_qty = lots * user_lot_size
            st.markdown(f'''
            <div style="background: #0f172a; border: 1.5px solid #0284c7; border-radius: 8px; padding: 10px 16px; margin: 8px 0 14px 0; font-size: 0.92rem; color: #ffffff; display: flex; justify-content: space-between; align-items: center;">
                <span>🏛️ <b style="color: #93c5fd;">{selected_pod} User Anchor:</b> ₹{user_anchor:,.2f} &bull; Spot: ₹{live_spot:,.2f}</span>
                <span style="background: #0369a1; color: #e0f2fe; font-weight: 700; padding: 4px 12px; border-radius: 12px;">Total Order Qty: {calc_qty} units ({lots} Lots &times; {user_lot_size})</span>
            </div>
            ''', unsafe_allow_html=True)

            col_adv1, col_adv2 = st.columns([2, 2])
            with col_adv1:
                cur_mode_idx = 0 if m_cfg.get("mode", "AUTO") == "AUTO" else 1
                stk_mode = st.radio("Strike Hunter Mode", [f"Auto Hunter (~₹{target_prem:.0f} on EVEN 100s)", "Manual Strike Override"], index=cur_mode_idx, horizontal=True, key=f"m_tab_stk_mode_{selected_pod}")

            m_ce = None
            m_pe = None
            with col_adv2:
                if stk_mode == "Manual Strike Override":
                    cm1, cm2 = st.columns(2)
                    nearest_even = int(round(live_spot / 200.0) * 200)
                    def_ce = m_cfg.get("manual_ce") or (nearest_even + 200)
                    def_pe = m_cfg.get("manual_pe") or (nearest_even - 200)
                    with cm1:
                        m_ce = st.number_input("Manual CE Strike", value=int(def_ce), step=100, key=f"m_tab_man_ce_{selected_pod}")
                    with cm2:
                        m_pe = st.number_input("Manual PE Strike", value=int(def_pe), step=100, key=f"m_tab_man_pe_{selected_pod}")

            st.markdown("<hr style='margin: 12px 0;'/>", unsafe_allow_html=True)
            btn_fetch = st.button(f"🔍 STEP 1: FETCH & PREVIEW LIVE STRIKES FOR {selected_pod}", key=f"btn_m_fetch_{selected_pod}", use_container_width=True, type="primary")

            if btn_fetch:
                with st.spinner(f"Scanning option chain for {selected_pod}..."):
                    st.session_state[f"m_inspection_{selected_pod}"] = bm.inspect_m_unit_candidates(
                        expiry_date=selected_exp,
                        unit_name=selected_pod,
                        master_anchor_price=user_anchor,
                        target_premium=target_prem,
                        manual_ce_strike=m_ce,
                        manual_pe_strike=m_pe,
                        hedge_dist=500
                    )

            st.markdown('</div>', unsafe_allow_html=True)

    # ─────────────────────────────────────────────────────────────────────────
    # INSPECTION RESULTS DISPLAY (PREVIEW CARDS)
    # ─────────────────────────────────────────────────────────────────────────
    inspection = st.session_state.get(f"m_inspection_{selected_pod}")
    if inspection and inspection.get("ok"):
        h_ce = inspection.get("ce", {})
        h_pe = inspection.get("pe", {})
        unit_regime = inspection.get("regime", "BEARISH")

        col_prev_head, col_prev_clear = st.columns([3.2, 1.2])
        with col_prev_head:
            st.markdown(
                '<div style="background: rgba(14, 165, 233, 0.12); border-left: 4px solid #0284c7; padding: 8px 14px; border-radius: 6px; font-size: 0.84rem; color: #bae6fd; margin-top: 10px;">'
                '🔍 <b>LIVE SCANNER PREVIEW ONLY:</b> These candidate strikes are fetched from Kite for inspection. '
                '<b style="color: #fde047;">Zero orders are active or placed on your broker.</b>'
                '</div>',
                unsafe_allow_html=True
            )
        with col_prev_clear:
            st.markdown('<div style="margin-top: 10px;"></div>', unsafe_allow_html=True)
            if st.button("🧹 Clear Preview", key=f"btn_clear_prev_{selected_pod}", use_container_width=True, help="Removes these scanner cards and clears the screen."):
                st.session_state.pop(f"m_inspection_{selected_pod}", None)
                st.rerun()

        col_ce_box, col_pe_box = st.columns(2)

        with col_ce_box:
            if h_ce.get("sell_strike"):
                is_qual_ce = (unit_regime == "BEARISH")
                ce_border = "#3b82f6" if is_qual_ce else "#94a3b8"
                ce_badge = "🟢 RECOMMENDED (BEARISH REGIME)" if is_qual_ce else "⚪ INACTIVE CANDIDATE (STANDBY)"

                st.markdown(f'''
                <div style="background: #0f172a; border: 2px solid {ce_border}; border-radius: 12px; padding: 20px; margin-top: 10px; color: #ffffff; box-shadow: 0 4px 12px rgba(0,0,0,0.3);">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; border-bottom: 1px solid #334155; padding-bottom: 8px;">
                        <span style="font-weight:800; font-size:1.15rem; color:#ffffff;">📞 CALL WING: {h_ce.get('sell_strike', '--')} CE</span>
                        <span style="font-size:0.80rem; font-weight:800; color:{ce_border}; background: #1e293b; padding: 4px 10px; border-radius: 6px; border: 1px solid {ce_border};">{ce_badge}</span>
                    </div>
                    <div style="font-size:0.95rem; color:#ffffff; line-height:1.8;">
                        &bull; SELL Strike: <b style="color:#ffffff; font-size:1.05rem;">{h_ce.get('sell_strike')} CE</b> (LTP: ₹{h_ce.get('sell_ltp', 0.0):.2f})<br/>
                        &bull; 500-pt Hedge Helmet: <b style="color:#60a5fa; font-weight:700;">{h_ce.get('hedge_strike', '--')} CE</b> (LTP: ₹{h_ce.get('hedge_ltp', 0.0):.2f})<br/>
                        &bull; Strict 25% SL Trigger: <b style="color:#fca5a5; font-weight:700;">₹{h_ce.get('sl_price', 0.0):.2f}</b> (+25% on entry fill)<br/>
                        &bull; Net Credit: ₹{(h_ce.get('sell_ltp', 0.0) - h_ce.get('hedge_ltp', 0.0)):.2f} pts
                    </div>
                </div>
                ''', unsafe_allow_html=True)
            else:
                st.markdown(f'''
                <div style="background: #1e1b10; border: 2px solid #ef4444; border-radius: 12px; padding: 20px; margin-top: 10px; color: #ffffff;">
                    <span style="font-weight:800; font-size:1.15rem; color:#f87171;">📞 CALL WING: NOT AVAILABLE</span>
                </div>
                ''', unsafe_allow_html=True)

        with col_pe_box:
            if h_pe.get("sell_strike"):
                is_qual_pe = (unit_regime == "BULLISH")
                pe_border = "#10b981" if is_qual_pe else "#94a3b8"
                pe_badge = "🟢 RECOMMENDED (BULLISH REGIME)" if is_qual_pe else "⚪ INACTIVE CANDIDATE (STANDBY)"

                st.markdown(f'''
                <div style="background: #0f172a; border: 2px solid {pe_border}; border-radius: 12px; padding: 20px; margin-top: 10px; color: #ffffff; box-shadow: 0 4px 12px rgba(0,0,0,0.3);">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; border-bottom: 1px solid #334155; padding-bottom: 8px;">
                        <span style="font-weight:800; font-size:1.15rem; color:#ffffff;">📉 PUT WING: {h_pe.get('sell_strike', '--')} PE</span>
                        <span style="font-size:0.80rem; font-weight:800; color:{pe_border}; background: #1e293b; padding: 4px 10px; border-radius: 6px; border: 1px solid {pe_border};">{pe_badge}</span>
                    </div>
                    <div style="font-size:0.95rem; color:#ffffff; line-height:1.8;">
                        &bull; SELL Strike: <b style="color:#ffffff; font-size:1.05rem;">{h_pe.get('sell_strike')} PE</b> (LTP: ₹{h_pe.get('sell_ltp', 0.0):.2f})<br/>
                        &bull; 500-pt Hedge Helmet: <b style="color:#60a5fa; font-weight:700;">{h_pe.get('hedge_strike', '--')} PE</b> (LTP: ₹{h_pe.get('hedge_ltp', 0.0):.2f})<br/>
                        &bull; Strict 25% SL Trigger: <b style="color:#fca5a5; font-weight:700;">₹{h_pe.get('sl_price', 0.0):.2f}</b> (+25% on entry fill)<br/>
                        &bull; Net Credit: ₹{(h_pe.get('sell_ltp', 0.0) - h_pe.get('hedge_ltp', 0.0)):.2f} pts
                    </div>
                </div>
                ''', unsafe_allow_html=True)
            else:
                st.markdown(f'''
                <div style="background: #1e1b10; border: 2px solid #ef4444; border-radius: 12px; padding: 20px; margin-top: 10px; color: #ffffff;">
                    <span style="font-weight:800; font-size:1.15rem; color:#f87171;">📉 PUT WING: NOT AVAILABLE</span>
                </div>
                ''', unsafe_allow_html=True)

        # ── STEP 2: REVIEW & LOCK STRATEGY PARAMETERS ────────────────────────
        st.markdown(f'<p class="section-title" style="margin-top:24px;">🔒 STEP 2: REVIEW & LOCK {selected_pod} STRATEGY</p>', unsafe_allow_html=True)

        if not is_locked:
            st.markdown(
                f'<div style="background: rgba(245, 158, 11, 0.12); border-left: 4px solid #f59e0b; padding: 10px 16px; border-radius: 8px; font-size: 0.90rem; color: #fde68a; margin-bottom: 12px;">'
                f'👉 <b>Step 1 Complete!</b> Live candidate strikes fetched from Kite. Review the strikes, SL trigger, and Net Credit above. '
                f'Click below to lock your parameters and unlock Step 3 Execution choices.'
                f'</div>',
                unsafe_allow_html=True
            )
            if st.button(f"🔒 STEP 2: CONFIRM & LOCK {selected_pod} STRATEGY PARAMETERS", key=f"btn_m_lock_{selected_pod}", use_container_width=True, type="primary"):
                db.set_m_unit_settings(
                    unit_name=selected_pod,
                    locked=True,
                    anchor_price=user_anchor,
                    horizon=horizon if 'horizon' in locals() else "Monthly Expiry",
                    expiry_date=selected_exp,
                    lots=lots,
                    lot_size=user_lot_size,
                    mode="MANUAL" if ('stk_mode' in locals() and stk_mode == "Manual Strike Override") else "AUTO",
                    manual_ce=m_ce or 0,
                    manual_pe=m_pe or 0,
                    target_premium=target_prem
                )
                _flash(f"✅ {selected_pod} Settings LOCKED & ARMED with Anchor ₹{user_anchor:,.2f}!", "success")
                st.rerun()
        else:
            st.markdown(
                f'<div style="background: rgba(16, 185, 129, 0.12); border-left: 4px solid #10b981; padding: 10px 16px; border-radius: 8px; font-size: 0.90rem; color: #a7f3d0; margin-bottom: 12px;">'
                f'✅ <b>STEP 2 COMPLETE:</b> {selected_pod} Strategy Parameters are LOCKED in database with Anchor ₹{user_anchor:,.2f}.'
                f'</div>',
                unsafe_allow_html=True
            )

        # ── STEP 3: CHOOSE EXECUTION ROUTE ───────────────────────────────────
        st.markdown(f'<p class="section-title" style="margin-top:20px;">🚀 STEP 3: CHOOSE EXECUTION ROUTE FOR {selected_pod}</p>', unsafe_allow_html=True)

        if not is_locked:
            st.markdown(
                '<div style="background: #1e293b; border: 1.5px dashed #64748b; padding: 14px 18px; border-radius: 8px; font-size: 0.90rem; color: #94a3b8; margin-top: 8px; text-align: center;">'
                '🔒 <b>STEP 3 LOCKED:</b> Complete <b>Step 2 (Confirm & Lock)</b> above to enable Execution Options.'
                '</div>',
                unsafe_allow_html=True
            )
        else:
            qual_wing_name = "CALL WING (BEARISH)" if unit_regime == "BEARISH" else "PUT WING (BULLISH)"
            btn_c1, btn_c2 = st.columns([1.5, 1.5])

            with btn_c1:
                if st.button(f"🚀 Option A: Execute Qualified {qual_wing_name} Now (Instant Fill)", key=f"btn_m_exec_now_{selected_pod}", use_container_width=True, type="primary"):
                    res = bm.deploy_or_update_m_unit(
                        unit_name=selected_pod,
                        expiry_date=selected_exp,
                        master_anchor_price=user_anchor,
                        lots=lots,
                        ce_sell_strike=h_ce.get("sell_strike", 0),
                        ce_hedge_strike=h_ce.get("hedge_strike", 0),
                        ce_sell_ltp=h_ce.get("sell_ltp", 0.0),
                        ce_hedge_ltp=h_ce.get("hedge_ltp", 0.0),
                        pe_sell_strike=h_pe.get("sell_strike", 0),
                        pe_hedge_strike=h_pe.get("hedge_strike", 0),
                        pe_sell_ltp=h_pe.get("sell_ltp", 0.0),
                        pe_hedge_ltp=h_pe.get("hedge_ltp", 0.0),
                        sl_pct=25.0,
                        deploy_now=True
                    )
                    if res.get("ok"):
                        _flash(f"🚀 {res.get('message')}", "success")
                    else:
                        _flash(f"Execution note: {res.get('message')}", "error")
                    st.rerun()

            with btn_c2:
                if st.button(f"⏱️ Option B: Arm Both Wings in PENDING (Standby for Evening/Pulse)", key=f"btn_m_arm_pending_{selected_pod}", use_container_width=True):
                    res = bm.deploy_or_update_m_unit(
                        unit_name=selected_pod,
                        expiry_date=selected_exp,
                        master_anchor_price=user_anchor,
                        lots=lots,
                        ce_sell_strike=h_ce.get("sell_strike", 0),
                        ce_hedge_strike=h_ce.get("hedge_strike", 0),
                        ce_sell_ltp=h_ce.get("sell_ltp", 0.0),
                        ce_hedge_ltp=h_ce.get("hedge_ltp", 0.0),
                        pe_sell_strike=h_pe.get("sell_strike", 0),
                        pe_hedge_strike=h_pe.get("hedge_strike", 0),
                        pe_sell_ltp=h_pe.get("sell_ltp", 0.0),
                        pe_hedge_ltp=h_pe.get("hedge_ltp", 0.0),
                        sl_pct=25.0,
                        deploy_now=False
                    )
                    if res.get("ok"):
                        _flash(f"⏱️ {selected_pod} both wings armed in PENDING in database.", "info")
                    else:
                        _flash(f"Arming failed: {res.get('message')}", "error")
                    st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# NEW BLOCK FORM (V5.0 "OLD & GOLD" MULTI-UNIT ARCHITECTURE)
# ─────────────────────────────────────────────────────────────────────────────
def render_new_block_form():
    import regime_engine as re_eng
    live_spot = re_eng.get_current_nifty_spot()

    with st.expander("➕ CREATE NEW BLOCK / UNIT (M1, M2, M3...)", expanded=False):
        st.markdown('<p class="section-title">New Block Setup (V5.0 "Old & Gold" Multi-Unit Architecture)</p>', unsafe_allow_html=True)
        col1, col2, col3 = st.columns([2, 2, 2])

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
            suggested_unit = db.get_next_unit_name(expiry_str)
            unit_name = st.text_input(
                "Unit Identifier (e.g. M1, M2, M3)",
                value = suggested_unit,
                key   = "new_block_unit_name",
                help  = "Independent Pod Identifier. Multiple units can run in the same expiry month."
            )

        col_u1, col_u2, col_u3, col_u4 = st.columns([2, 2, 2, 2])
        with col_u1:
            default_anc = float(live_spot) if live_spot > 0 else 24000.0
            unit_anchor = st.number_input(
                "Unit Master Anchor (₹)",
                min_value = 0.0,
                max_value = 100000.0,
                value     = default_anc,
                step      = 50.0,
                format    = "%.2f",
                key       = "new_block_master_anchor",
                help      = "Target anchor level for this unit (e.g. 24000, 24400, 24800)"
            )
        with col_u2:
            unit_buffer = st.number_input(
                "Buffer (±pts)",
                min_value = 0.0,
                max_value = 200.0,
                value     = 15.0,
                step      = 5.0,
                format    = "%.1f",
                key       = "new_block_buffer",
                help      = "Hysteresis buffer (default ±15 pts)"
            )
        with col_u3:
            side_type_label = st.selectbox(
                "Block Side Type",
                options = [
                    "⚡ SEPARATE CALL & PUT BLOCKS (Recommended)",
                    "CALL SIDE ONLY",
                    "PUT SIDE ONLY",
                    "BOTH (COMBINED LEGACY)",
                ],
                index   = 0,
                key     = "new_block_side",
                help    = "Create separate Call and Put blocks or a single combined block"
            )
        with col_u4:
            notes = st.text_input(
                "Notes (optional)",
                placeholder = f"e.g. {unit_name} Breakout Level",
                key         = "new_block_notes",
            )

        if st.button("🆕 Create Block(s) for Unit", key="btn_create_block", type="primary"):
            clean_unit = unit_name.strip().upper() if unit_name.strip() else db.get_next_unit_name(expiry_str)
            if side_type_label.startswith("⚡ SEPARATE"):
                res = bm.create_separate_blocks(
                    expiry_date=expiry_str,
                    expiry_type=expiry_type,
                    notes=notes,
                    anchor_unit_name=clean_unit,
                    master_anchor_price=unit_anchor,
                    regime_buffer=unit_buffer
                )
                if res["ok"]:
                    # Auto-evaluate new unit regime
                    if res.get("call_block_id"):
                        cb = db.get_block(res["call_block_id"])
                        if cb: re_eng.evaluate_block_regime(cb, current_spot=live_spot, force_eval=True)
                    if res.get("put_block_id"):
                        pb = db.get_block(res["put_block_id"])
                        if pb: re_eng.evaluate_block_regime(pb, current_spot=live_spot, force_eval=True)
                    _flash(res["message"], "success")
                else:
                    _flash(res["message"], "warning")
            else:
                side_map = {
                    "CALL SIDE ONLY": "CALL",
                    "PUT SIDE ONLY": "PUT",
                    "BOTH (COMBINED LEGACY)": "BOTH",
                }
                side_type = side_map.get(side_type_label, "CALL")
                result = bm.create_block(
                    expiry_date=expiry_str,
                    expiry_type=expiry_type,
                    side_type=side_type,
                    notes=notes,
                    anchor_unit_name=clean_unit,
                    master_anchor_price=unit_anchor,
                    regime_buffer=unit_buffer
                )
                if result["ok"]:
                    nb = db.get_block(result["block_id"])
                    if nb: re_eng.evaluate_block_regime(nb, current_spot=live_spot, force_eval=True)
                    _flash(f"Block #{result['block_number']} [Unit {clean_unit}] ({side_type}) created for {expiry_str} ({expiry_type}) @ Anchor ₹{unit_anchor:,.2f}", "success")
                else:
                    if result.get("duplicate"):
                        _flash(result["message"], "warning")
                    else:
                        _flash(result["message"], "error")
            st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# ACTIVE & ORPHAN HEDGES PROFIT LOCK MONITOR
# ─────────────────────────────────────────────────────────────────────────────
def render_hedges_profit_lock_monitor(portfolio: dict):
    """
    Renders the dedicated Active & Orphan Hedges Monitor with one-click profit locking.
    Allows closing individual hedges or batch closing orphan hedges to secure gains.
    """
    block_pnls = portfolio.get("block_pnls", [])
    if not block_pnls:
        return

    open_hedges = []
    for bp in block_pnls:
        b_num = bp.get("block_number", "?")
        b_id  = bp.get("block_id")
        for s in bp.get("strike_pnls", []):
            if s.get("status") == "OPEN" and s.get("leg_type") == "HEDGE_BUY":
                sell_id = s.get("hedge_strike_id")
                is_orphan = False
                sell_strike = None
                if not sell_id:
                    is_orphan = True
                else:
                    sell_strike = db.get_strike(sell_id)
                    if not sell_strike or sell_strike.get("status") != "OPEN":
                        is_orphan = True
                
                open_hedges.append({
                    "strike": s,
                    "block_id": b_id,
                    "block_number": b_num,
                    "is_orphan": is_orphan,
                    "sell_strike": sell_strike,
                })

    if not open_hedges:
        return

    orphan_count = sum(1 for h in open_hedges if h["is_orphan"])
    total_hedge_pnl = sum(h["strike"].get("pnl", 0.0) for h in open_hedges)
    orphan_pnl = sum(h["strike"].get("pnl", 0.0) for h in open_hedges if h["is_orphan"])
    total_pnl_color = "#16a34a" if total_hedge_pnl >= 0 else "#dc2626"
    total_prefix = "+" if total_hedge_pnl >= 0 else ""

    badge_html = f"<span style='background:#fef3c7;color:#b45309;padding:3px 10px;border-radius:12px;font-size:0.8rem;font-weight:700;margin-left:10px;'>⚡ {orphan_count} ORPHAN HEDGE(S)</span>" if orphan_count > 0 else ""

    with st.expander(f"🛡️ Active & Orphan Hedges Monitor ({len(open_hedges)} Open) — Total P&L: {total_prefix}₹{total_hedge_pnl:,.2f}", expanded=(orphan_count > 0)):
        col_hdr1, col_hdr2 = st.columns([3, 2])
        with col_hdr1:
            st.markdown(
                f"<div style='font-size:0.9rem;color:#334155;'>"
                f"Active Protective Hedges: <b>{len(open_hedges)}</b> {badge_html}<br/>"
                f"Combined Hedge P&L: <b style='color:{total_pnl_color};font-size:1.1rem;'>{total_prefix}₹{total_hedge_pnl:,.2f}</b>"
                f"</div>",
                unsafe_allow_html=True
            )
        with col_hdr2:
            if orphan_count > 0:
                batch_btn_text = f"⚡ Close All {orphan_count} Orphan Hedges (+₹{orphan_pnl:,.2f})" if orphan_pnl > 0 else f"⚡ Close All {orphan_count} Orphan Hedges"
                if st.button(batch_btn_text, key="btn_close_all_orphans", type="primary", use_container_width=True):
                    closed_cnt = 0
                    with st.spinner("Closing all orphan hedges on broker to lock profit..."):
                        for h in open_hedges:
                            if h["is_orphan"]:
                                res = bm.close_hedge_strike_now(h["strike"]["strike_id"])
                                if res["ok"]:
                                    closed_cnt += 1
                    _flash(f"Successfully closed {closed_cnt} orphan hedge(s) and locked profits!", "success")
                    st.rerun()

        st.markdown("<hr style='margin:10px 0;'/>", unsafe_allow_html=True)

        for item in open_hedges:
            s = item["strike"]
            is_orphan = item["is_orphan"]
            pnl_val = s.get("pnl", 0.0)
            pnl_color = "#16a34a" if pnl_val >= 0 else "#dc2626"
            pnl_prefix = "+" if pnl_val >= 0 else ""
            sid = s["strike_id"]
            
            if is_orphan:
                status_badge = "<span style='background:#fef3c7;color:#b45309;border:1px solid #fde68a;padding:2px 8px;border-radius:10px;font-size:0.75rem;font-weight:700;'>⚡ ORPHAN (LOCK PROFIT)</span>"
                card_border = "border: 1.5px solid #f59e0b; background: #fffbeb;"
            else:
                status_badge = "<span style='background:#e0f2fe;color:#0369a1;border:1px solid #bae6fd;padding:2px 8px;border-radius:10px;font-size:0.75rem;font-weight:600;'>🔗 LINKED ACTIVE</span>"
                card_border = "border: 1px solid #e2e8f0; background: #ffffff;"

            opt_color = "#1e40af" if s["option_type"] == "CE" else "#6b21a8"

            st.markdown(
                f"""
                <div style='{card_border}border-radius:8px;padding:10px 14px;margin-bottom:8px;'>
                    <div style='display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;'>
                        <div>
                            <span style='font-weight:700;color:{opt_color};font-size:0.95rem;'>Block {item['block_number']} | {s['strike_price']} {s['option_type']} HEDGE</span>
                            &nbsp;&nbsp; {status_badge}
                            <span style='color:#64748b;font-size:0.8rem;margin-left:8px;'>Strike #{sid} | Lots: {s['lots']} ({s['qty']} qty)</span>
                        </div>
                        <div style='text-align:right;'>
                            <span style='font-size:0.8rem;color:#64748b;'>Anchor: ₹{s['anchor_price']:.2f} | LTP: ₹{s.get('ltp', 0.0):.2f}</span> &nbsp;&nbsp;
                            <span style='font-weight:700;font-size:1.05rem;color:{pnl_color};'>{pnl_prefix}₹{pnl_val:,.2f}</span>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

            col_btn1, col_btn2 = st.columns([4, 1])
            with col_btn2:
                btn_lbl = f"💰 Lock Profit ({pnl_prefix}₹{pnl_val:,.2f})" if pnl_val > 0 else f"✖ Close Hedge #{sid}"
                if st.button(btn_lbl, key=f"btn_lock_hedge_{sid}", use_container_width=True, type="primary" if (is_orphan or pnl_val > 0) else "secondary"):
                    with st.spinner(f"Closing hedge strike {sid} on broker..."):
                        res = bm.close_hedge_strike_now(sid)
                    if res["ok"]:
                        _flash(res["message"], "success")
                    else:
                        _flash(res["message"], "error")
                    st.rerun()


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


def render_block_management():
    all_blocks = db.get_all_blocks()
    if not all_blocks:
        return

    st.markdown("---")
    st.markdown("### BLOCK MANAGEMENT")

    for b in all_blocks:
        status_class = {"ACTIVE":"pill-active","EXPIRED":"pill-expired","CLOSED":"pill-closed"}.get(b["status"],"pill-active")
        col1, col2, col3, col4, col5 = st.columns([3, 1, 1, 1, 1])
        with col1:
            st.markdown(
                f'Block {b["block_number"]} — {b["expiry_date"]} ({b["expiry_type"]}) '
                f'<span class="status-pill {status_class}">{b["status"]}</span>',
                unsafe_allow_html=True,
            )
        with col2:
            if st.button("✏️ Edit", key=f"edit_{b['block_id']}", use_container_width=True):
                st.session_state["edit_block_id"] = b["block_id"]
                st.rerun()
        with col3:
            if b["status"] == "ACTIVE":
                if st.button("Archive", key=f"arch_{b['block_id']}", use_container_width=True):
                    r = bm.archive_block(b["block_id"])
                    _flash(r["message"], "success" if r["ok"] else "error")
                    st.rerun()
        with col4:
            if st.button("🗑 Delete", key=f"del_{b['block_id']}", use_container_width=True):
                r = bm.delete_block(b["block_id"])
                _flash(r["message"], "success" if r["ok"] else "error")
                st.rerun()
        with col5:
            if st.button("💥 Kill", key=f"kill_mgt_{b['block_id']}", use_container_width=True):
                st.session_state[f"confirm_kill_mgt_{b['block_id']}"] = True
                st.rerun()

        # Kill confirmation under columns
        if st.session_state.get(f"confirm_kill_mgt_{b['block_id']}"):
            st.warning(f"⚠️ **CONFIRM KILL SWITCH FOR BLOCK {b['block_number']}**\nThis will attempt to close all open positions immediately and **FORCE DELETE** the block from the system. This cannot be undone.")
            col_myes, col_mno, _ = st.columns([2, 2, 4])
            with col_myes:
                if st.button("🔴 YES, KILL IT", key=f"confirm_kill_myes_{b['block_id']}", type="primary", use_container_width=True):
                    st.session_state[f"confirm_kill_mgt_{b['block_id']}"] = False
                    with st.spinner(f"Executing Kill Switch for Block {b['block_number']}..."):
                        u_name = (b.get("anchor_unit_name") or "").strip().upper()
                        if u_name.startswith("M"):
                            r = bm.wipe_out_and_reset_m_unit(u_name)
                        elif u_name.startswith("OS"):
                            r = os_engine.wipe_out_and_reset_os_unit(u_name)
                        else:
                            r = bm.kill_block(b["block_id"])
                    if r["ok"]:
                        _flash(r["message"], "success")
                    else:
                        _flash(r["message"], "error")
                    st.rerun()
            with col_mno:
                if st.button("🟢 NO, CANCEL", key=f"confirm_kill_mno_{b['block_id']}", use_container_width=True):
                    st.session_state[f"confirm_kill_mgt_{b['block_id']}"] = False
                    st.rerun()


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
                save_edit = st.form_submit_button("💾 Save Changes", use_container_width=True)

            if save_edit:
                if new_expiry.strip():
                    db.update_block_expiry(b["block_id"], new_expiry.strip(), new_exp_type)
                    _flash(f"Block {b['block_number']} expiry updated to {new_expiry}", "success")
                    st.session_state["edit_block_id"] = None
                else:
                    _flash("Expiry date cannot be empty.", "error")
                st.rerun()

            if st.button("Cancel Edit", key=f"cancel_edit_{b['block_id']}"):
                st.session_state["edit_block_id"] = None
                st.rerun()


def render_commodity_tab():
    import commodity_executor as comm_exec
    
    st.markdown('<p class="section-title">🛢️ MCX COMMODITY FUTURES ENGINE</p>', unsafe_allow_html=True)
    
    # 1. Status Bar & Engine Control
    comm_running = db.get("comm_engine_running", "OFF") == "ON"
    
    col_st1, col_st2, col_st3 = st.columns([3, 2, 3])
    with col_st1:
        st.markdown(
            f"""
            <div style='background:#f1f5f9;border-left:5px solid #ff5722;padding:12px 18px;border-radius:6px;'>
                <span style='font-size:0.75rem;color:#64748b;font-weight:700;'>COMMODITY ENGINE STATUS</span><br/>
                <span style='font-size:1.15rem;font-weight:800;color:{"#22c55e" if comm_running else "#64748b"};'>
                    {"🟢 RUNNING & MONITORING" if comm_running else "⚪ PAUSED / OFF"}
                </span>
            </div>
            """,
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
    
    # Extract asset from widget or database
    widget_asset = st.session_state.get("comm_sel_asset_widget")
    if widget_asset:
        default_asset = widget_asset
    else:
        default_asset = "GOLDPETAL"
        for asset in commodity_assets:
            if saved_contract.startswith(asset):
                default_asset = asset
                break
                
    # Retrieve active contracts for this asset
    contracts = comm_exec.get_available_contracts(default_asset)
    contract_options = [c["trading_symbol"] for c in contracts]
    
    # Extract contract symbol from widget or database
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
        
    # Live LTP & P&L calculation for the resolved contract
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
            
    # Draw position card colors
    pos_color = "#22c55e" if pos_state == "LONG" else "#ef4444" if pos_state == "SHORT" else "#64748b"
    pnl_color = "#22c55e" if pnl_pct >= 0 else "#ef4444"

    # Anchor Price for the card
    anchor_p = float(db.get("comm_anchor_price", "0.0") or 0.0)
    
    # Determine Bull/Bear signal based on LTP vs Anchor
    if anchor_p > 0 and ltp > 0:
        if ltp > anchor_p:
            signal_text = "🟢 BULLISH"
            signal_color = "#22c55e"
            signal_bg = "#f0fdf4"
        elif ltp < anchor_p:
            signal_text = "🔴 BEARISH"
            signal_color = "#ef4444"
            signal_bg = "#fef2f2"
        else:
            signal_text = "⚪ NEUTRAL"
            signal_color = "#f59e0b"
            signal_bg = "#fffbeb"
    else:
        signal_text = "⏸️ NO SIGNAL"
        signal_color = "#94a3b8"
        signal_bg = "#f8fafc"

    st.markdown(
        f"""
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
        """,
        unsafe_allow_html=True
    )

    st.markdown("<br/>", unsafe_allow_html=True)

    # 3. Settings Form
    with st.expander("🔧 CONFIGURATION & SETTINGS", expanded=saved_contract == ""):
        col_c1, col_c2, col_c3 = st.columns([2, 2, 2])
        
        with col_c1:
            sel_asset = st.selectbox(
                "Base Commodity Asset",
                options=commodity_assets,
                index=commodity_assets.index(default_asset),
                key="comm_sel_asset_widget"
            )
            
        # Re-resolve default index for selectbox
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
                # Resolve lot size automatically
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
            
            # Button to copy current LTP to anchor price
            if ltp > 0:
                st.markdown(f"<p style='color:#22c55e;font-size:0.88rem;font-weight:700;'>Live Price: ₹{ltp:,.2f}</p>", unsafe_allow_html=True)
                if st.button("🎯 Set to Live LTP", key="btn_use_live_ltp", use_container_width=True, help=f"Click to preset anchor price to the live price: {ltp}"):
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

    st.markdown("<br/>", unsafe_allow_html=True)

    # 4. Manual / Safety Actions
    st.markdown("### 🛡️ MANUAL CONTROLS (EMERGENCY)")
    
    col_act1, col_act2, col_act3 = st.columns(3)
    with col_act1:
        if st.button("🟢 Force LONG Entry", key="btn_force_long", use_container_width=True):
            st.session_state["confirm_force_long"] = True
            
        if st.session_state.get("confirm_force_long"):
            st.info("Double check: Force LONG reversal?")
            col_l1, col_l2 = st.columns(2)
            with col_l1:
                if st.button("Confirm YES", key="btn_confirm_long", type="primary", use_container_width=True):
                    st.session_state["confirm_force_long"] = False
                    with st.spinner("Executing LONG flip..."):
                        comm_exec.execute_commodity_flip("LONG")
                    st.rerun()
            with col_l2:
                if st.button("Cancel", key="btn_cancel_long", use_container_width=True):
                    st.session_state["confirm_force_long"] = False
                    st.rerun()
                    
    with col_act2:
        if st.button("🔴 Force SHORT Entry", key="btn_force_short", use_container_width=True):
            st.session_state["confirm_force_short"] = True
            
        if st.session_state.get("confirm_force_short"):
            st.info("Double check: Force SHORT reversal?")
            col_s1, col_s2 = st.columns(2)
            with col_s1:
                if st.button("Confirm YES", key="btn_confirm_short", type="primary", use_container_width=True):
                    st.session_state["confirm_force_short"] = False
                    with st.spinner("Executing SHORT flip..."):
                        comm_exec.execute_commodity_flip("SHORT")
                    st.rerun()
            with col_s2:
                if st.button("Cancel", key="btn_cancel_short", use_container_width=True):
                    st.session_state["confirm_force_short"] = False
                    st.rerun()
                    
    with col_act3:
        if st.button("🛑 FORCE SQUARE OFF ALL", key="btn_force_sqoff", use_container_width=True):
            st.session_state["confirm_force_sqoff"] = True
            
        if st.session_state.get("confirm_force_sqoff"):
            st.warning("⚠️ Double check: SQUARE OFF ALL?")
            col_q1, col_q2 = st.columns(2)
            with col_q1:
                if st.button("SQUARE OFF", key="btn_confirm_sqoff", type="primary", use_container_width=True):
                    st.session_state["confirm_force_sqoff"] = False
                    with st.spinner("Squaring off all MCX positions..."):
                        comm_exec.square_off_all_mcx_positions()
                    st.rerun()
            with col_q2:
                if st.button("Cancel", key="btn_cancel_sqoff", use_container_width=True):
                    st.session_state["confirm_force_sqoff"] = False
                    st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# EMERGENCY SYSTEM SHUTDOWN & SQUARE-OFF CONSOLE (2-STEP CONFIRMED)
# ─────────────────────────────────────────────────────────────────────────────
def render_emergency_shutdown_bar():
    st.markdown("""
    <div style="background: linear-gradient(135deg, #450a0a 0%, #7f1d1d 50%, #991b1b 100%); border: 2px solid #ef4444; border-radius: 12px; padding: 14px 20px; margin-bottom: 16px; box-shadow: 0 4px 14px rgba(239,68,68,0.35);">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <div>
                <span style="font-size:1.20rem; font-weight:900; color:#ffffff; letter-spacing:0.5px;">🚨 EMERGENCY SYSTEM SHUTDOWN &amp; 1-CLICK CLOSE CONSOLE</span>
                <div style="font-size:0.85rem; color:#fecaca; margin-top:3px; font-weight:600;">
                    Instant 1-Click Square-Off on Zerodha Kite Broker &bull; Protected by 2-Step Confirmation &bull; High Visibility for Mobile &amp; Senior Operators
                </div>
            </div>
            <span style="background:#dc2626; color:#ffffff; padding:4px 12px; border-radius:8px; font-weight:800; font-size:0.85rem; border:1px solid #fca5a5;">2-STEP VERIFIED</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── MASTER DIRECT BROKER SQUARE-OFF (100% FAILSAFE) ──
    if st.session_state.get("confirm_direct_broker_sqoff"):
        st.markdown("""
        <div style="background:#fee2e2; border:2.5px solid #b91c1c; border-radius:10px; padding:14px; margin-bottom:12px; text-align:center;">
            <b style="color:#7f1d1d; font-size:1.10rem;">🚨 CRITICAL ACTION: MARKET SQUARE-OFF ALL TRADES ON ZERODHA BROKER</b><br/>
            <span style="color:#991b1b; font-size:0.86rem;">This will query Zerodha Kite API directly and immediately close ALL open derivative positions (Cover Shorts FIRST, Sell Hedges SECOND).</span>
        </div>
        """, unsafe_allow_html=True)
        sq_yes, sq_no = st.columns(2)
        with sq_yes:
            if st.button("🔥 YES, CLOSE ALL POSITIONS ON BROKER NOW", key="btn_confirm_direct_sqoff_yes", type="primary", use_container_width=True):
                with st.spinner("Executing direct broker market square-off on Zerodha Kite..."):
                    res_sq = bm.emergency_direct_broker_square_off_all()
                    st.session_state["confirm_direct_broker_sqoff"] = False
                    if res_sq.get("ok"):
                        _flash(f"✅ {res_sq.get('message')}", "success")
                    else:
                        _flash(f"Square-off: {res_sq.get('message')}", "error")
                    st.rerun()
        with sq_no:
            if st.button("❌ Cancel Full Square-Off", key="btn_confirm_direct_sqoff_no", use_container_width=True):
                st.session_state["confirm_direct_broker_sqoff"] = False
                st.rerun()
    else:
        if st.button("🛑 1-CLICK EMERGENCY SQUARE-OFF ENTIRE ACCOUNT (DIRECT BROKER EXIT)", key="btn_direct_broker_sqoff", use_container_width=True, type="primary", help="Directly queries Zerodha Kite and places market exit orders for all open contracts. Margin-safe: shorts covered first."):
            st.session_state["confirm_direct_broker_sqoff"] = True
            st.rerun()

    st.markdown("<div style='margin-top: 8px;'></div>", unsafe_allow_html=True)
    c_m1, c_m2, c_m3, c_os = st.columns(4)

    # ── M1 CLOSE ──
    with c_m1:
        if st.session_state.get("confirm_close_m1"):
            st.markdown("""
            <div style="background:#fee2e2; border:2px solid #dc2626; border-radius:10px; padding:10px; margin-bottom:8px; text-align:center;">
                <b style="color:#991b1b; font-size:0.90rem;">⚠️ CLOSE M1?</b><br/>
                <span style="color:#7f1d1d; font-size:0.75rem;">Market Exit on Zerodha!</span>
            </div>
            """, unsafe_allow_html=True)
            b1, b2 = st.columns(2)
            with b1:
                if st.button("🔥 YES, CLOSE M1", key="btn_confirm_close_m1_yes", type="primary", use_container_width=True):
                    with st.spinner("Squaring off M1 on Zerodha Kite..."):
                        res = bm.wipe_out_and_reset_m_unit("M1")
                        st.session_state["confirm_close_m1"] = False
                        _flash(res.get("message", "M1 Closed"), "success" if res.get("ok") else "error")
                        st.rerun()
            with b2:
                if st.button("❌ Cancel", key="btn_confirm_close_m1_no", use_container_width=True):
                    st.session_state["confirm_close_m1"] = False
                    st.rerun()
        else:
            if st.button("🚨 CLOSE WHOLE M1", key="btn_req_close_m1", use_container_width=True, type="primary", help="Immediately squares off all M1 trades on Zerodha Kite broker, purges DB records, and resets M1 to idle."):
                st.session_state["confirm_close_m1"] = True
                st.rerun()

    # ── M2 CLOSE ──
    with c_m2:
        if st.session_state.get("confirm_close_m2"):
            st.markdown("""
            <div style="background:#fee2e2; border:2px solid #dc2626; border-radius:10px; padding:10px; margin-bottom:8px; text-align:center;">
                <b style="color:#991b1b; font-size:0.90rem;">⚠️ CLOSE M2?</b><br/>
                <span style="color:#7f1d1d; font-size:0.75rem;">Market Exit on Zerodha!</span>
            </div>
            """, unsafe_allow_html=True)
            b1, b2 = st.columns(2)
            with b1:
                if st.button("🔥 YES, CLOSE M2", key="btn_confirm_close_m2_yes", type="primary", use_container_width=True):
                    with st.spinner("Squaring off M2 on Zerodha Kite..."):
                        res = bm.wipe_out_and_reset_m_unit("M2")
                        st.session_state["confirm_close_m2"] = False
                        _flash(res.get("message", "M2 Closed"), "success" if res.get("ok") else "error")
                        st.rerun()
            with b2:
                if st.button("❌ Cancel", key="btn_confirm_close_m2_no", use_container_width=True):
                    st.session_state["confirm_close_m2"] = False
                    st.rerun()
        else:
            if st.button("🚨 CLOSE WHOLE M2", key="btn_req_close_m2", use_container_width=True, type="primary", help="Immediately squares off all M2 trades on Zerodha Kite broker, purges DB records, and resets M2 to idle."):
                st.session_state["confirm_close_m2"] = True
                st.rerun()

    # ── M3 CLOSE (NEW!) ──
    with c_m3:
        if st.session_state.get("confirm_close_m3"):
            st.markdown("""
            <div style="background:#fee2e2; border:2px solid #dc2626; border-radius:10px; padding:10px; margin-bottom:8px; text-align:center;">
                <b style="color:#991b1b; font-size:0.90rem;">⚠️ CLOSE M3?</b><br/>
                <span style="color:#7f1d1d; font-size:0.75rem;">Market Exit on Zerodha!</span>
            </div>
            """, unsafe_allow_html=True)
            b1, b2 = st.columns(2)
            with b1:
                if st.button("🔥 YES, CLOSE M3", key="btn_confirm_close_m3_yes", type="primary", use_container_width=True):
                    with st.spinner("Squaring off M3 on Zerodha Kite..."):
                        res = bm.wipe_out_and_reset_m_unit("M3")
                        st.session_state["confirm_close_m3"] = False
                        _flash(res.get("message", "M3 Closed"), "success" if res.get("ok") else "error")
                        st.rerun()
            with b2:
                if st.button("❌ Cancel", key="btn_confirm_close_m3_no", use_container_width=True):
                    st.session_state["confirm_close_m3"] = False
                    st.rerun()
        else:
            if st.button("🚨 CLOSE WHOLE M3", key="btn_req_close_m3", use_container_width=True, type="primary", help="Immediately squares off all M3 trades on Zerodha Kite broker, purges DB records, and resets M3 to idle."):
                st.session_state["confirm_close_m3"] = True
                st.rerun()

    # ── WHOLE OS SYSTEM CLOSE ──
    with c_os:
        if st.session_state.get("confirm_close_os_all"):
            st.markdown("""
            <div style="background:#fef3c7; border:2px solid #d97706; border-radius:10px; padding:10px; margin-bottom:8px; text-align:center;">
                <b style="color:#92400e; font-size:0.90rem;">⚠️ CLOSE OS?</b><br/>
                <span style="color:#78350f; font-size:0.75rem;">Market Exit on Zerodha!</span>
            </div>
            """, unsafe_allow_html=True)
            b1, b2 = st.columns(2)
            with b1:
                if st.button("🔥 YES, CLOSE OS", key="btn_confirm_close_os_yes", type="primary", use_container_width=True):
                    with st.spinner("Squaring off all OS units on Zerodha Kite..."):
                        res = bm.wipe_out_and_reset_whole_os_system()
                        st.session_state["confirm_close_os_all"] = False
                        _flash(res.get("message", "OS System Closed"), "success" if res.get("ok") else "error")
                        st.rerun()
            with b2:
                if st.button("❌ Cancel", key="btn_confirm_close_os_no", use_container_width=True):
                    st.session_state["confirm_close_os_all"] = False
                    st.rerun()
        else:
            if st.button("🚨 CLOSE WHOLE OS", key="btn_req_close_os_all", use_container_width=True, type="primary", help="Immediately squares off all OS units (OS1–OS5) on Zerodha Kite broker, purges DB records, and resets OS to idle."):
                st.session_state["confirm_close_os_all"] = True
                st.rerun()

    st.markdown("<div style='margin-bottom: 12px;'></div>", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# EXECUTIVE POD MATRIX (Zerodha — Instant M-Unit & OS-Unit Clarity at Top)
# ─────────────────────────────────────────────────────────────────────────────
def render_executive_pod_matrix(portfolio: dict):
    """
    Provides 100% immediate clarity at the very top of the dashboard:
    - Left: Directional M-Units (M1, M2, M3) with Spot vs Anchor & regime.
    - Right: Momentum OS-Units (OS1..OS5) with 3:00 PM decay status.
    - Direct 1-Click Quick Close buttons with 2-step confirmation.
    """
    block_pnls = portfolio.get("block_pnls", [])
    try:
        import regime_engine as _re_mat
        live_spot = _re_mat.get_current_nifty_spot()
    except Exception:
        live_spot = 0.0

    m_units  = [bp for bp in block_pnls if not (bp.get("block", {}).get("anchor_unit_name") or "").strip().upper().startswith("OS")]
    os_units = [bp for bp in block_pnls if (bp.get("block", {}).get("anchor_unit_name") or "").strip().upper().startswith("OS")]

    col_m, col_os = st.columns(2)

    with col_m:
        st.markdown("""
        <div style="background: linear-gradient(135deg, #1f1f2e 0%, #111119 100%); border: 2px solid #f4511e; border-radius: 10px; padding: 12px 16px; margin-bottom: 10px; color: #ffffff;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <span style="font-weight:800; font-size:1.05rem; color:#ff8a65;">🏛️ DIRECTIONAL M-UNITS (M1–M3)</span>
                <span style="font-size:0.75rem; background:#3e1a07; color:#ffcc80; padding:2px 10px; border-radius:12px; font-weight:700;">Spot Anchor Regime</span>
            </div>
            <div style="font-size:0.75rem; color:#cbd5e1; margin-top:3px;">
                Directional credit spreads governed by Spot vs Master Anchor with 25% Autonomous SL.
            </div>
        </div>
        """, unsafe_allow_html=True)

        if not m_units:
            st.info("⚪ **All M-Units are currently IDLE / FLAT.** (No active positions)")
        else:
            for bp in m_units:
                b   = bp.get("block") or {}
                bid = bp["block_id"]
                uname = (b.get("anchor_unit_name") or f"M{b.get('block_number',1)}").strip().upper()
                strikes = bp.get("strikes", [])
                open_s  = [s for s in strikes if s.get("status") in ("OPEN", "EXECUTED", "PENDING")]
                anc_price = float(b.get("master_anchor_price") or 0.0)
                tot_pnl   = bp.get("total_pnl", 0.0)
                expiry    = b.get("expiry_date", "")

                if open_s:
                    pnl_col = "#22c55e" if tot_pnl >= 0 else "#ef4444"
                    sign    = "+" if tot_pnl >= 0 else ""
                    regime_tag = "🟢 BULLISH" if (live_spot >= anc_price if anc_price > 0 else True) else "🔴 BEARISH"
                    legs_str   = ", ".join(f"{s['strike_price']} {s['option_type']}" for s in open_s)
                    st.markdown(f"""
                    <div style="background:#ffffff; border:1.5px solid #f4511e; border-radius:8px; padding:12px 14px; margin-bottom:8px; box-shadow:0 2px 4px rgba(0,0,0,0.05);">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <span style="font-weight:800; color:#b71c1c; font-size:0.95rem;">🟢 {uname} ACTIVE &bull; Exp: {expiry}</span>
                            <span style="font-weight:800; font-family:'JetBrains Mono',monospace; color:{pnl_col}; font-size:1.05rem;">{sign}₹{abs(tot_pnl):,.2f}</span>
                        </div>
                        <div style="font-size:0.80rem; color:#475569; margin-top:4px;">
                            <b>Regime:</b> {regime_tag} | <b>Anchor:</b> ₹{anc_price:,.1f} | <b>Legs:</b> {legs_str}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    if st.session_state.get(f"confirm_qclose_m_{bid}"):
                        st.markdown(f'<div style="background:#fee2e2; border:1px solid #ef4444; border-radius:6px; padding:6px; margin:4px 0; text-align:center;"><span style="color:#991b1b; font-size:0.8rem; font-weight:700;">Are you sure to close {uname}?</span></div>', unsafe_allow_html=True)
                        c_yes, c_no = st.columns(2)
                        with c_yes:
                            if st.button(f"🔥 YES, Close {uname}", key=f"btn_confirm_m_{bid}_yes", type="primary", use_container_width=True):
                                res_w = bm.wipe_out_and_reset_m_unit(uname)
                                st.session_state[f"confirm_qclose_m_{bid}"] = False
                                _flash(f"✅ {uname} closed on Zerodha Kite!", "success")
                                st.rerun()
                        with c_no:
                            if st.button("❌ Cancel", key=f"btn_confirm_m_{bid}_no", use_container_width=True):
                                st.session_state[f"confirm_qclose_m_{bid}"] = False
                                st.rerun()
                    else:
                        if st.button(f"💥 1-Click Close {uname}", key=f"zrd_qclose_m_{bid}", use_container_width=True, type="secondary"):
                            st.session_state[f"confirm_qclose_m_{bid}"] = True
                            st.rerun()
                else:
                    st.markdown(f"""
                    <div style="background:#f8fafc; border:1px dashed #94a3b8; border-radius:8px; padding:10px 14px; margin-bottom:8px; display:flex; justify-content:space-between; align-items:center;">
                        <div>
                            <span style="color:#334155; font-size:0.90rem; font-weight:700;">⚪ {uname}: IDLE / FLAT</span>
                            <span style="font-size:0.75rem; color:#64748b; margin-left:8px;">(0 Open Strikes &bull; Exp: {expiry})</span>
                        </div>
                        <span style="font-size:0.80rem; color:#ff5722; font-weight:600;">Anchor: ₹{anc_price:,.1f}</span>
                    </div>
                    """, unsafe_allow_html=True)

    with col_os:
        st.markdown("""
        <div style="background: linear-gradient(135deg, #1f1f2e 0%, #111119 100%); border: 2px solid #10b981; border-radius: 10px; padding: 12px 16px; margin-bottom: 10px; color: #ffffff;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <span style="font-weight:800; font-size:1.05rem; color:#34d399;">🎯 MOMENTUM OS-UNITS (OS1–OS5)</span>
                <span style="font-size:0.75rem; background:#064e3b; color:#6ee7b7; padding:2px 10px; border-radius:12px; font-weight:700;">3:00 PM Option Decay</span>
            </div>
            <div style="font-size:0.75rem; color:#cbd5e1; margin-top:3px;">
                Pure option decay momentum engine with OTM hedge helmet and 1.382 SL multiplier.
            </div>
        </div>
        """, unsafe_allow_html=True)

        if not os_units:
            st.info("⚪ **All OS-Units are currently IDLE / ARMED.** (No active positions)")
        else:
            for bp in os_units:
                b   = bp.get("block") or {}
                bid = bp["block_id"]
                uname  = (b.get("anchor_unit_name") or "OS1").strip().upper()
                strikes = bp.get("strikes", [])
                open_s  = [s for s in strikes if s.get("status") in ("OPEN", "EXECUTED", "PENDING")]
                tot_pnl = bp.get("total_pnl", 0.0)
                expiry  = b.get("expiry_date", "")

                if open_s:
                    pnl_col    = "#22c55e" if tot_pnl >= 0 else "#ef4444"
                    sign       = "+" if tot_pnl >= 0 else ""
                    legs_detail = ", ".join(f"{s['strike_price']} {s['option_type']} ({s.get('leg_type','')})" for s in open_s)
                    st.markdown(f"""
                    <div style="background:#ffffff; border:1.5px solid #10b981; border-radius:8px; padding:12px 14px; margin-bottom:8px; box-shadow:0 2px 4px rgba(0,0,0,0.05);">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <span style="font-weight:800; color:#065f46; font-size:0.95rem;">🟢 {uname} ACTIVE &bull; Exp: {expiry}</span>
                            <span style="font-weight:800; font-family:'JetBrains Mono',monospace; color:{pnl_col}; font-size:1.05rem;">{sign}₹{abs(tot_pnl):,.2f}</span>
                        </div>
                        <div style="font-size:0.80rem; color:#047857; margin-top:4px;">
                            <b>Hedge Security:</b> 🛡️ 100% Hedged | <b>Legs ({len(open_s)}):</b> {legs_detail}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    if st.session_state.get(f"confirm_qclose_os_{bid}"):
                        st.markdown(f'<div style="background:#fef3c7; border:1px solid #f59e0b; border-radius:6px; padding:6px; margin:4px 0; text-align:center;"><span style="color:#92400e; font-size:0.8rem; font-weight:700;">Are you sure to close {uname}?</span></div>', unsafe_allow_html=True)
                        c_yes, c_no = st.columns(2)
                        with c_yes:
                            if st.button(f"🔥 YES, Close {uname}", key=f"btn_confirm_os_{bid}_yes", type="primary", use_container_width=True):
                                import os_engine
                                res_w = os_engine.wipe_out_and_reset_os_unit(uname)
                                st.session_state[f"confirm_qclose_os_{bid}"] = False
                                _flash(f"✅ {uname} closed on Zerodha Kite!", "success")
                                st.rerun()
                        with c_no:
                            if st.button("❌ Cancel", key=f"btn_confirm_os_{bid}_no", use_container_width=True):
                                st.session_state[f"confirm_qclose_os_{bid}"] = False
                                st.rerun()
                    else:
                        if st.button(f"💥 1-Click Close {uname} Entire Unit", key=f"zrd_qclose_os_{bid}", use_container_width=True, type="secondary"):
                            st.session_state[f"confirm_qclose_os_{bid}"] = True
                            st.rerun()
                else:
                    st.markdown(f"""
                    <div style="background:#f8fafc; border:1px dashed #94a3b8; border-radius:8px; padding:10px 14px; margin-bottom:8px; display:flex; justify-content:space-between; align-items:center;">
                        <div>
                            <span style="color:#334155; font-size:0.90rem; font-weight:700;">⚪ {uname}: IDLE / ARMED</span>
                            <span style="font-size:0.75rem; color:#64748b; margin-left:8px;">(0 Open Strikes &bull; Exp: {expiry})</span>
                        </div>
                        <span style="font-size:0.80rem; color:#10b981; font-weight:600;">Armed for 3:00 PM</span>
                    </div>
                    """, unsafe_allow_html=True)



# ─────────────────────────────────────────────────────────────────────────────
# MAIN APP
# ─────────────────────────────────────────────────────────────────────────────
def main():
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

    # Fetch portfolio P&L (uses cached LTP — never blocks)
    portfolio = _get_portfolio()
    st.session_state["portfolio_pnl"] = portfolio

    # Header
    render_header(portfolio)

    # Flash messages
    _show_flash()

    # Metrics row
    render_metrics(portfolio)

    st.markdown("<br/>", unsafe_allow_html=True)

    # Global Red Alert Popup Banner (200 DMA watch)
    eq_engine.render_global_red_alert_banner()

    # ── EMERGENCY SHUTDOWN & 1-CLICK CLOSE BAR (2-Step Verified) ──
    render_emergency_shutdown_bar()

    # ── EXECUTIVE POD MATRIX (M-Units LEFT | OS-Units RIGHT) ──
    render_executive_pod_matrix(portfolio)

    st.divider()

    # ── CLEAN 7-TAB ARCHITECTURE ───────────────────────────────────────────
    tab_m, tab_os, tab_weekly_st, tab_blocks, tab_commodity, tab_equity, tab_logs = st.tabs([
        "🏛️ Directional M-Units Cockpit (M1–M4)",
        "🎯 Momentum OS-Units Cockpit (OS1–OS5)",
        "⚡ Weekly ST-2H Cockpit (W1 — V7.5)",
        "📦 Active Expiry Blocks & Live Positions",
        "🛢️ MCX Commodities FUT",
        "📊 Equity & Gold (200 DMA Monitor)",
        "📜 Order History & Audit Logs"
    ])

    # ── TAB 1: M-UNITS NIFTY COCKPIT ────────────────────────────────────
    with tab_m:
        # V6.0 Directional M-Units Cockpit (Asymmetric Trend & Auto-Hunter)
        render_unified_v5_master_console()

        st.markdown("<br/>", unsafe_allow_html=True)

        with st.expander("➕ Deploy New Expiry Block", expanded=False):
            render_new_block_form()

        # Active & Orphan Hedges Monitor
        render_hedges_profit_lock_monitor(portfolio)

        st.markdown("<br/>", unsafe_allow_html=True)

        # Unit Pod Containers (M-Series Only)
        block_pnls = portfolio.get("block_pnls", [])
        m_block_pnls = [
            bp for bp in block_pnls
            if not (bp["block"].get("anchor_unit_name") or "").strip().upper().startswith("OS")
        ]

        if not m_block_pnls:
            st.info("📦 No Active M-Series Blocks. Deploy using the form above.")
        else:
            from collections import OrderedDict
            unit_groups = OrderedDict()
            for bp in m_block_pnls:
                b = bp["block"]
                unit_name = (b.get("anchor_unit_name") or f"M{b['block_number']}").strip().upper()
                exp = b.get("expiry_date", "").strip()
                key = (unit_name, exp)
                if key not in unit_groups:
                    unit_groups[key] = []
                unit_groups[key].append(bp)

            st.markdown('<p class="section-title">ACTIVE AUTONOMOUS UNITS (PODS)</p>', unsafe_allow_html=True)

            for (unit_name, exp_date), unit_bps in unit_groups.items():
                render_unit_pod(unit_name, exp_date, unit_bps)

        with st.expander("⚙️ Block Management (Archive / Delete)", expanded=False):
            render_block_management()

    # ── TAB 2: OS-UNITS COCKPIT ───────────────────────────────────────
    with tab_os:
        import os_engine
        os_engine.render_os_tab(portfolio)

    # ── TAB 3: WEEKLY ST-2H COCKPIT (W1) ──────────────────────────────
    with tab_weekly_st:
        wst_engine.render_weekly_st_tab(portfolio)

    # ── TAB 3: ACTIVE BLOCKS ──────────────────────────────────────────
    with tab_blocks:
        st.markdown('<p class="section-title">📦 Active Expiry Blocks & Live Positions</p>', unsafe_allow_html=True)
        block_pnls_all = portfolio.get("block_pnls", [])
        if not block_pnls_all:
            st.info("✨ **CLEAN SLATE: 0 Active Blocks.** Deploy from the M-Units tab.")
        else:
            for bp in block_pnls_all:
                b = bp.get("block") or {}
                u_name = (b.get("anchor_unit_name") or f"M{b.get('block_number',1)}").strip().upper()
                render_sub_block(bp, u_name, key_suffix="tab3")

    # ── TAB 4: MCX COMMODITIES ─────────────────────────────────────────
    with tab_commodity:
        render_commodity_tab()

    # ── TAB 5: EQUITY 200 DMA ─────────────────────────────────────────
    with tab_equity:
        eq_engine.render_equity_tab()

    # ── TAB 6: AUDIT LOGS ───────────────────────────────────────────
    with tab_logs:
        render_trade_log()

    # Footer
    st.markdown("---")
    updated = portfolio.get("last_updated", "--")
    st.markdown(
        f'<div style="text-align:center;font-size:0.68rem;color:#374151;">'
        f'Zerodha OptionSelling Engine V5.0 Old & Gold | NIFTY Only | Port 9007 | '
        f'Last updated: {updated}'
        f'</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
