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
            'v1.01 BASE MODEL | NIFTY Only<br/>VPS 46.224.133.16:9007'
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
                NIFTY Options SELL | Port 9007 | VPS 46.224.133.16 &nbsp;
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

    col_ap1, col_ap2, col_ap3 = st.columns([1.5, 1.5, 1.2])
    with col_ap1:
        use_live_anchor = st.checkbox("Use Live LTP as Anchor", value=True, key=f"use_live_ap_{block_id}")
        if use_live_anchor:
            anchor_price = sell_ltp if sell_ltp > 0 else 10.0  # safe default if LTP is 0
            st.markdown(f"**⚓ Anchor Price**: ₹{anchor_price:.2f}")
        else:
            anchor_price = st.number_input(
                "Manual Anchor Price (₹)",
                min_value = 0.05,
                max_value = 5000.00,
                value     = sell_ltp if sell_ltp > 0 else 100.00,
                step      = 0.05,
                format    = "%.2f",
                key       = f"manual_ap_{block_id}"
            )
    with col_ap2:
        default_sl_p = float(anchor_price) * 1.25 if float(anchor_price) > 0 else 125.0
        custom_sl_price = st.number_input(
            "🛑 Stop Loss Price (₹)",
            min_value = 0.05,
            max_value = 10000.00,
            value     = float(default_sl_p),
            step      = 0.50,
            format    = "%.2f",
            key       = f"direct_sl_price_{block_id}",
            help      = "Exact stop loss exit price in rupees (e.g. 61.00, 75.00)"
        )
    with col_ap3:
        sl_choice = st.selectbox("SL % Presets", options=["25% (Standard)", "10%", "20%", "30%", "40%", "Custom"], index=0, key=f"sl_choice_{block_id}")
        sl_pct = 25.0
        if sl_choice == "10%": sl_pct = 10.0
        elif sl_choice == "20%": sl_pct = 20.0
        elif sl_choice == "25% (Standard)": sl_pct = 25.0
        elif sl_choice == "30%": sl_pct = 30.0
        elif sl_choice == "40%": sl_pct = 40.0
        elif sl_choice == "Custom":
            sl_pct = st.number_input("Custom SL %", min_value=1.0, max_value=200.0, value=25.0, step=1.0, key=f"custom_sl_{block_id}")
        
        sl_calc_price = float(custom_sl_price)
        if float(anchor_price) > 0 and sl_calc_price > float(anchor_price):
            sl_pct_display = ((sl_calc_price - float(anchor_price)) / float(anchor_price)) * 100.0
        else:
            sl_pct_display = float(sl_pct)

    st.markdown(
        f'<div style="background:#fff1f2;border:1px dashed #f43f5e;border-radius:8px;padding:6px 12px;margin:4px 0 8px 0;font-size:0.82rem;">'
        f'🛑 <b>Configured SL Trigger:</b> <span style="color:#b91c1c;font-weight:800;font-size:0.95rem;">₹{sl_calc_price:,.2f}</span> '
        f'<span style="color:#64748b;">(+{sl_pct_display:.1f}% on Anchor ₹{float(anchor_price):,.2f})</span>'
        f'</div>',
        unsafe_allow_html=True
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
                    expiries_list = sorted(list(set(expiries_list)), key=lambda x: datetime.strptime(x, "%d-%b-%Y"))
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
                sl_pct       = float(sl_pct),
                sl_price     = float(sl_calc_price)
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
                sl_pct       = float(sl_pct),
                sl_price     = float(sl_calc_price)
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
def render_sub_block(block_pnl: dict, unit_name: str):
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
        is_active = st.toggle("Enable Engine", value=(is_enabled == 1), key=f"toggle_block_enable_{block_id}")
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
            sl_pct_val = float(s.get("sl_pct") or 25.0)
            if s["leg_type"] == "SELL":
                if sl_p > 0:
                    sl_str = f"₹{sl_p:.2f} (+{sl_pct_val:.0f}%)"
                elif s["anchor_price"] > 0:
                    sl_str = f"₹{s['anchor_price'] * (1.0 + sl_pct_val / 100.0):.2f} (+{sl_pct_val:.0f}%)"
                else:
                    sl_str = f"+{sl_pct_val:.0f}%"
            else:
                sl_str = "🛡️ HEDGE"

            trade_st = str(s.get("trade_state") or s.get("status") or "OPEN").upper()

            row = {
                "Strike"     : s["strike_price"],
                "Type"       : s["option_type"],
                "Leg"        : s["leg_type"],
                "Regime"     : reg_status,
                "Anchor"     : anchor_str,
                "LTP"        : ltp_str,
                "SL Trigger" : sl_str,
                "Lots"       : s["lots"],
                "Qty"        : s.get("qty", s["lots"] * int(db.get("lot_size","65"))),
                "P&L"        : pnl_str,
                "P&L%"       : pct_str,
                "Decay%"     : decay_str,
                "State"      : trade_st,
            }

            if s["option_type"] == "CE":
                call_rows.append(row)
            else:
                put_rows.append(row)

        col_cfg = {
            "Strike": st.column_config.NumberColumn("Strike", format="%d"),
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
                    if st.button(btn_text, key=f"close_orphaned_{h['strike_id']}", use_container_width=True, type="primary" if pnl_val > 0 else "secondary"):
                        res = bm.close_hedge_strike_now(h["strike_id"])
                        if res["ok"]:
                            _flash(res["message"], "success")
                        else:
                            _flash(res["message"], "error")
                        st.rerun()

    else:
        st.markdown('<p style="color:#64748b;font-size:0.85rem;padding:6px 0;">No strikes in this block.</p>', unsafe_allow_html=True)

    # ── Inline Add Strike Form Container (Right inside Block) ──
    if st.session_state.get("add_strike_block") == block_id:
        st.markdown("<div style='background:#f8fafc;border:2px solid #3b82f6;border-radius:10px;padding:16px;margin:12px 0;'>", unsafe_allow_html=True)
        render_add_strike_form(block_id)
        st.markdown("</div>", unsafe_allow_html=True)

    # ── Inline Strike Anchor & Stop-Loss Price Editor (Right inside Block) ──
    all_b_strikes = db.get_strikes_by_block(block_id)
    if all_b_strikes:
        with st.expander(f"⚙️ Quick Edit Strikes: Anchor Price & Stop Loss (Block {block_num})", expanded=False):
            strike_map = {
                f"{s['strike_price']} {s['option_type']} {s['leg_type']} (#{s['strike_id']}) — [{s['status']}] | Anchor: ₹{s['anchor_price']:.2f} | SL: ₹{float(s.get('sl_price') or (s['anchor_price']*1.25)):.2f}": s["strike_id"]
                for s in all_b_strikes
            }
            sel_s_label = st.selectbox("Select Strike to Configure", list(strike_map.keys()), key=f"inline_sel_strike_{block_id}")
            sel_sid = strike_map[sel_s_label]
            target_s = db.get_strike(sel_sid)

            if target_s:
                is_sell_leg = target_s.get("leg_type") == "SELL"
                cur_anc = float(target_s.get("anchor_price") or 0.0)
                cur_sl_p = float(target_s.get("sl_price") or 0.0)
                cur_sl_pct = float(target_s.get("sl_pct") or 25.0)
                if cur_sl_p <= 0 and cur_anc > 0:
                    cur_sl_p = cur_anc * (1.0 + cur_sl_pct / 100.0)
                
                # Header card for the selected strike
                st.markdown(
                    f'<div style="background:#f1f5f9;border:1px solid #cbd5e1;border-radius:8px;padding:8px 12px;margin:8px 0 12px 0;">'
                    f'<b>Selected Strike:</b> <span style="color:#0f172a;font-weight:800;">{target_s["strike_price"]} {target_s["option_type"]} {target_s["leg_type"]} (#{target_s["strike_id"]})</span> '
                    f'| Status: <span style="font-weight:700;">{target_s["status"]}</span> '
                    f'| Current Anchor: <b>₹{cur_anc:.2f}</b> '
                    f'| Current SL Trigger: <b style="color:#b91c1c;">₹{cur_sl_p:.2f}</b> (+{cur_sl_pct:.1f}%)'
                    f'</div>',
                    unsafe_allow_html=True
                )

                if is_sell_leg:
                    c_e1, c_e2, c_e3, c_e4 = st.columns([1.5, 1.5, 1.2, 1.2])
                    with c_e1:
                        new_anc = st.number_input(
                            "Anchor Price (₹)",
                            min_value=0.05,
                            max_value=10000.00,
                            value=float(cur_anc),
                            step=0.50,
                            format="%.2f",
                            key=f"inline_anc_val_{sel_sid}",
                            help="Anchor price for entry calculation"
                        )
                    with c_e2:
                        new_sl_p = st.number_input(
                            "Stop Loss Price (₹)",
                            min_value=0.05,
                            max_value=20000.00,
                            value=float(cur_sl_p),
                            step=0.50,
                            format="%.2f",
                            key=f"inline_slp_val_{sel_sid}",
                            help="Exact stop loss exit price in rupees"
                        )
                    with c_e3:
                        new_sl_pct = st.number_input(
                            "SL %",
                            min_value=0.1,
                            max_value=200.0,
                            value=float(cur_sl_pct),
                            step=1.0,
                            format="%.1f",
                            key=f"inline_slpct_val_{sel_sid}"
                        )
                    with c_e4:
                        new_lots = st.number_input(
                            "Lots",
                            min_value=1,
                            max_value=100,
                            value=int(target_s["lots"]),
                            step=1,
                            key=f"inline_lots_val_{sel_sid}"
                        )
                else:
                    c_e1, c_e2 = st.columns([2, 2])
                    with c_e1:
                        new_anc = st.number_input(
                            "Hedge Anchor Price (₹)",
                            min_value=0.05,
                            max_value=10000.00,
                            value=float(cur_anc),
                            step=0.50,
                            format="%.2f",
                            key=f"inline_anc_val_{sel_sid}"
                        )
                        new_sl_p = 0.0
                        new_sl_pct = 0.0
                    with c_e2:
                        new_lots = st.number_input(
                            "Lots",
                            min_value=1,
                            max_value=100,
                            value=int(target_s["lots"]),
                            step=1,
                            key=f"inline_lots_val_{sel_sid}"
                        )

                sync_zerodha = False
                if target_s["status"] == "OPEN" and is_sell_leg:
                    sync_zerodha = st.checkbox("Live Sync Lot Delta on Zerodha Broker", value=False, key=f"inline_sync_{sel_sid}", help="Places delta market order on Zerodha if lot count is changed")

                col_act1, col_act2 = st.columns([3, 1])
                with col_act1:
                    if st.button("💾 Save Price, Stop-Loss & Lots Settings", key=f"btn_save_all_inline_{sel_sid}", use_container_width=True, type="primary"):
                        res_update = bm.update_strike_price_and_sl(
                            strike_id=sel_sid,
                            new_anchor=float(new_anc),
                            new_sl_price=float(new_sl_p) if is_sell_leg else None,
                            new_sl_pct=float(new_sl_pct) if is_sell_leg else None,
                            new_lots=int(new_lots)
                        )
                        if sync_zerodha and int(new_lots) != int(target_s["lots"]):
                            bm.change_strike_lots(sel_sid, int(new_lots), sync_live=True)
                        if res_update["ok"]:
                            _flash(res_update["message"], "success")
                        else:
                            _flash(res_update["message"], "error")
                        st.rerun()

                with col_act2:
                    if target_s["status"] == "PENDING":
                        if st.button("🗑 Remove Strike", key=f"btn_del_strike_{sel_sid}", use_container_width=True):
                            res_del = bm.remove_strike(sel_sid)
                            if res_del["ok"]:
                                _flash(res_del["message"], "success")
                            else:
                                _flash(res_del["message"], "error")
                            st.rerun()

            # Batch lot scaling for this block
            st.markdown("<hr style='margin:12px 0 8px 0;border:0;border-top:1px dashed #cbd5e1;'/>", unsafe_allow_html=True)
            col_b1, col_b2 = st.columns([2, 3])
            with col_b1:
                default_batch = int(target_s["lots"]) if target_s else 1
                batch_lots = st.number_input(f"Batch Scale All Strikes in Block {block_num}", min_value=1, max_value=100, value=default_batch, key=f"batch_lots_{block_id}")
            with col_b2:
                st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
                if st.button(f"⚡ Set ALL Strikes in Block {block_num} to {batch_lots} Lots", key=f"btn_batch_scale_{block_id}", use_container_width=True):
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
                rv_strike = st.number_input("New Strike", min_value=10000, max_value=50000, value=int(default_rv_strike), step=50, key=f"rv_strike_{sell_sid}")

            with rv_col2:
                rv_expiries = get_sorted_nifty_expiries()
                current_exp = linked_hedge.get("expiry_date", "") if linked_hedge else ""
                default_rv_exp_idx = 0
                for i, e in enumerate(rv_expiries):
                    if e != current_exp:
                        default_rv_exp_idx = i
                        break
                rv_expiry = st.selectbox("New Expiry", options=rv_expiries, index=default_rv_exp_idx, key=f"rv_expiry_{sell_sid}")

            with rv_col3:
                rv_lots = st.number_input("Lots", min_value=1, max_value=100, value=sell_s.get("lots", 1), key=f"rv_lots_{sell_sid}")

            if st.button("🔄 Execute Rollover", key=f"btn_rollover_{sell_sid}", use_container_width=True, type="primary"):
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
        col_a, col_b, col_c, col_d = st.columns([1.5, 1.8, 1.8, 1.2])

        with col_a:
            is_adding = (st.session_state.get("add_strike_block") == block_id)
            add_lbl = "✖ Close Form" if is_adding else "➕ Add Strike"
            if st.button(add_lbl, key=f"add_strike_{block_id}", use_container_width=True, type="secondary" if is_adding else "primary"):
                st.session_state["add_strike_block"] = None if is_adding else block_id
                st.rerun()

        with col_b:
            block_sum_strikes = bm.get_block_summary(block_id)["strikes"]
            all_pending = [s for s in block_sum_strikes if s["status"] == "PENDING"]
            all_closed = [s for s in block_sum_strikes if s["status"] == "CLOSED"]
            if all_pending:
                if st.button(f"▶ Execute Block ({len(all_pending)})", key=f"exec_block_{block_id}", use_container_width=True, type="primary"):
                    r = bm.execute_block(block_id)
                    if r["ok"]:
                        _flash(r["message"], "success")
                        tg.alert_engine_started()
                    else:
                        _flash(r["message"], "error")
                    st.rerun()
            elif all_closed:
                if st.button(f"🔄 Re-Arm Strikes ({len(all_closed)})", key=f"rearm_block_{block_id}", use_container_width=True, help="Resets closed strikes to PENDING"):
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
                sel_label = st.selectbox("Close Strike", options=list(strike_options.keys()), key=f"close_sel_{block_id}", label_visibility="collapsed")
                if st.button(f"✖ Close Strike", key=f"close_btn_{block_id}", use_container_width=True):
                    sid = strike_options[sel_label]
                    result = bm.close_strike(sid)
                    if result["ok"]:
                        _flash(result["message"], "success")
                    else:
                        _flash(result["message"], "error")
                    st.rerun()

        with col_d:
            if st.button(f"📊 Summary", key=f"daily_sum_{block_id}", use_container_width=True):
                pnl_data = pe.calc_block_pnl(block_id)
                tg.alert_block_daily_summary(pnl_data)
                _flash(f"Block {block_num} summary sent to Telegram!", "success")
                st.rerun()

    st.markdown('<div style="margin-bottom:12px;"></div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# UNIT POD CONTAINER RENDERER (Brick 4 / V3.0 Autonomous Pod Architecture)
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
        render_sub_block(bp, unit_name)

    st.markdown('</div>', unsafe_allow_html=True)  # Close Pod Container


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
        '<div style="background:linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0369a1 100%);border:2px solid #38bdf8;border-radius:12px;padding:16px 20px;margin-bottom:14px;box-shadow:0 4px 18px rgba(56,189,248,0.25);">'
        '<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;">'
        '<div>'
        '<span style="font-size:1.25rem;font-weight:900;color:#ffffff;letter-spacing:0.5px;">🎯 MASTER NIFTY CONTROLLER</span>'
        '<span style="background:#38bdf8;color:#0f172a;font-size:0.75rem;font-weight:800;padding:3px 10px;border-radius:12px;margin-left:8px;">V5.0 "OLD & GOLD" ARCHITECTURE</span>'
        '</div>'
        '<div style="font-size:0.82rem;color:#cbd5e1;font-weight:500;">Unified Console • Decoupled M1 Anchor • 3:00 PM Continuation • Preserved Orphan Hedges</div>'
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


def render_unified_v5_console():
    """
    V5.0 'Old & Gold' Architecture: Unified Single-Window Console ('Ek Hi Jagah Saari Chijen').
    Configures both Call Sell Wing and Put Sell Wing side-by-side on one single screen,
    with dynamic 1-click Selective Deployment governed by live Spot vs Master Anchor.
    """
    import regime_engine as re_eng
    live_spot = re_eng.get_current_nifty_spot()
    expiries_list = get_sorted_nifty_expiries()
    
    with st.expander("🚀 UNIFIED V5 CONSOLE — EK HI JAGAH SAARI CHIJEN (M1, M2... Deployer)", expanded=True):
        st.markdown(
            '<div style="background:linear-gradient(135deg, #0f172a 0%, #1e293b 100%);color:#ffffff;border-radius:12px;padding:16px 20px;margin-bottom:16px;box-shadow:0 4px 15px rgba(0,0,0,0.15);">'
            '<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;">'
            '<div>'
            '<span style="font-size:1.15rem;font-weight:900;color:#38bdf8;">🚀 UNIFIED SINGLE-WINDOW V5.0 MASTER DEPLOYER</span>'
            '<div style="font-size:0.8rem;color:#cbd5e1;margin-top:2px;">Configure Call Wing & Put Wing side-by-side with decoupled M1 Anchor & 3:00 PM Continuation.</div>'
            '</div>'
            f'<div style="background:#0284c7;color:#ffffff;padding:4px 12px;border-radius:20px;font-weight:800;font-size:0.85rem;">Live Spot: ₹{live_spot:,.2f}</div>'
            '</div>'
            '</div>',
            unsafe_allow_html=True
        )

        # Top Macro Config Row
        c1, c2, c3, c4 = st.columns([2, 1.5, 2, 1.5])
        with c1:
            expiry_val = st.selectbox("Expiry Date", options=expiries_list, key="v5_exp_select")
        with c2:
            suggested_u = db.get_next_unit_name(expiry_val) if expiry_val else "M1"
            unit_val = st.text_input("Unit Pod", value=suggested_u, key="v5_unit_name", help="e.g. M1, M2, M3")
        with c3:
            default_anc = float(live_spot) if live_spot > 0 else 24500.0
            anchor_val = st.number_input("Master Anchor Price (₹)", min_value=0.0, max_value=100000.0, value=default_anc, step=50.0, format="%.2f", key="v5_anchor_price")
        with c4:
            lots_val = st.number_input("Lots per Wing", min_value=1, max_value=100, value=1, step=1, key="v5_lots_val")

        st.markdown('<hr style="margin:12px 0 16px 0;border:0;border-top:1px solid #e2e8f0;"/>', unsafe_allow_html=True)

        # Helper to fetch live option LTP
        def _fetch_opt_live_price(exp_date, strike, opt_type):
            try:
                sym_info = kite_executor.search_option_contract(exp_date, int(strike), opt_type)
                if sym_info:
                    p = kite_executor.get_ltp(sym_info.get("token"), sym_info.get("trading_symbol"))
                    if p > 0:
                        return float(p)
            except Exception:
                pass
            return 0.0

        # Side-by-side Wings: LEFT = CALL WING, RIGHT = PUT WING
        col_call, col_put = st.columns(2)

        with col_call:
            st.markdown(
                '<div style="background:#fef2f2;border:2px solid #fecaca;border-radius:10px;padding:12px 16px;margin-bottom:12px;">'
                '<div style="font-weight:900;color:#991b1b;font-size:1rem;display:flex;align-items:center;gap:6px;">'
                '🔴 CALL SELL WING (BEARISH TREND)'
                '</div>'
                '<div style="font-size:0.75rem;color:#b91c1c;">Executes LIVE when Spot &lt; Master Anchor. Held in PENDING if Bullish.</div>'
                '</div>',
                unsafe_allow_html=True
            )
            c_s1, c_s2 = st.columns(2)
            with c_s1:
                ce_sell_strike = st.number_input("CE Sell Strike", min_value=0, max_value=100000, value=int(round(live_spot + 300, -2)) if live_spot > 0 else 24800, step=50, key="v5_ce_sell_strike")
                ce_sell_live = _fetch_opt_live_price(expiry_val, ce_sell_strike, "CE")
            with c_s2:
                default_ce_anchor = float(ce_sell_live) if ce_sell_live > 0 else 75.00
                ce_sell_anchor = st.number_input("CE Sell Anchor (Auto-LTP ₹)", min_value=0.0, max_value=5000.0, value=default_ce_anchor, step=0.5, format="%.2f", key="v5_ce_sell_anchor", help="Defaults to live market LTP. Trade triggers when LTP <= Anchor.")

            c_h1, c_h2 = st.columns(2)
            with c_h1:
                ce_hedge_strike = st.number_input("CE Hedge Strike (OTM)", min_value=0, max_value=100000, value=int(ce_sell_strike + 300), step=50, key="v5_ce_hedge_strike")
                ce_hedge_live = _fetch_opt_live_price(expiry_val, ce_hedge_strike, "CE")
            with c_h2:
                default_ce_h_anchor = float(ce_hedge_live) if ce_hedge_live > 0 else 15.00
                ce_hedge_anchor = st.number_input("CE Hedge Anchor (Auto-LTP ₹)", min_value=0.0, max_value=5000.0, value=default_ce_h_anchor, step=0.5, format="%.2f", key="v5_ce_hedge_anchor", help="Defaults to live hedge market LTP.")

            c_sl1, c_sl2, c_sl3 = st.columns([1.5, 1.5, 1.0])
            with c_sl1:
                default_ce_sl = float(ce_sell_anchor) * 1.25 if float(ce_sell_anchor) > 0 else 93.75
                ce_sl_price_val = st.number_input(
                    "CE Stop Loss Price (₹)",
                    min_value=0.05,
                    max_value=10000.0,
                    value=float(default_ce_sl),
                    step=0.5,
                    format="%.2f",
                    key="v5_ce_sl_price_input",
                    help="Exact SL trigger in rupees (e.g. 61.00, 75.00)"
                )
            with c_sl2:
                ce_sl_choice = st.selectbox("CE SL % Presets", options=["25% (Standard)", "10%", "20%", "30%", "40%", "Custom"], index=0, key="v5_ce_sl_choice")
                ce_sl_pct = 25.0
                if ce_sl_choice == "10%": ce_sl_pct = 10.0
                elif ce_sl_choice == "20%": ce_sl_pct = 20.0
                elif ce_sl_choice == "25% (Standard)": ce_sl_pct = 25.0
                elif ce_sl_choice == "30%": ce_sl_pct = 30.0
                elif ce_sl_choice == "40%": ce_sl_pct = 40.0
                elif ce_sl_choice == "Custom":
                    ce_sl_pct = st.number_input("Custom CE SL %", min_value=1.0, max_value=200.0, value=25.0, step=1.0, key="v5_ce_custom_sl")
                
                if float(ce_sl_price_val) > float(ce_sell_anchor) and float(ce_sell_anchor) > 0:
                    ce_effective_pct = ((float(ce_sl_price_val) - float(ce_sell_anchor)) / float(ce_sell_anchor)) * 100.0
                else:
                    ce_effective_pct = float(ce_sl_pct)
            with c_sl3:
                st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)
                ce_reentry = st.checkbox("Re-entry", value=True, key="v5_ce_reentry")

            # Dynamic Live Metrics & SL Preview Card
            st.markdown(
                f'<div style="background:#fff1f2;border:1px dashed #f43f5e;border-radius:8px;padding:8px 12px;margin-top:6px;font-size:0.82rem;">'
                f'📈 <b>Live LTP:</b> ₹{ce_sell_live:,.2f} &nbsp;|&nbsp; 🛡️ <b>Hedge LTP:</b> ₹{ce_hedge_live:,.2f}<br/>'
                f'🛑 <b>Stop-Loss Trigger:</b> <span style="color:#b91c1c;font-weight:800;font-size:0.95rem;">₹{float(ce_sl_price_val):,.2f}</span> '
                f'<span style="color:#64748b;">(+{ce_effective_pct:.1f}% on Anchor ₹{float(ce_sell_anchor):,.2f})</span>'
                f'</div>',
                unsafe_allow_html=True
            )

        with col_put:
            st.markdown(
                '<div style="background:#ecfdf5;border:2px solid #a7f3d0;border-radius:10px;padding:12px 16px;margin-bottom:12px;">'
                '<div style="font-weight:900;color:#065f46;font-size:1rem;display:flex;align-items:center;gap:6px;">'
                '🟢 PUT SELL WING (BULLISH TREND)'
                '</div>'
                '<div style="font-size:0.75rem;color:#047857;">Executes LIVE when Spot &ge; Master Anchor. Held in PENDING if Bearish.</div>'
                '</div>',
                unsafe_allow_html=True
            )
            p_s1, p_s2 = st.columns(2)
            with p_s1:
                pe_sell_strike = st.number_input("PE Sell Strike", min_value=0, max_value=100000, value=int(round(live_spot - 300, -2)) if live_spot > 0 else 24200, step=50, key="v5_pe_sell_strike")
                pe_sell_live = _fetch_opt_live_price(expiry_val, pe_sell_strike, "PE")
            with p_s2:
                default_pe_anchor = float(pe_sell_live) if pe_sell_live > 0 else 75.00
                pe_sell_anchor = st.number_input("PE Sell Anchor (Auto-LTP ₹)", min_value=0.0, max_value=5000.0, value=default_pe_anchor, step=0.5, format="%.2f", key="v5_pe_sell_anchor", help="Defaults to live market LTP. Trade triggers when LTP <= Anchor.")

            p_h1, p_h2 = st.columns(2)
            with p_h1:
                pe_hedge_strike = st.number_input("PE Hedge Strike (OTM)", min_value=0, max_value=100000, value=int(pe_sell_strike - 300), step=50, key="v5_pe_hedge_strike")
                pe_hedge_live = _fetch_opt_live_price(expiry_val, pe_hedge_strike, "PE")
            with p_h2:
                default_pe_h_anchor = float(pe_hedge_live) if pe_hedge_live > 0 else 15.00
                pe_hedge_anchor = st.number_input("PE Hedge Anchor (Auto-LTP ₹)", min_value=0.0, max_value=5000.0, value=default_pe_h_anchor, step=0.5, format="%.2f", key="v5_pe_hedge_anchor", help="Defaults to live hedge market LTP.")

            p_sl1, p_sl2, p_sl3 = st.columns([1.5, 1.5, 1.0])
            with p_sl1:
                default_pe_sl = float(pe_sell_anchor) * 1.25 if float(pe_sell_anchor) > 0 else 93.75
                pe_sl_price_val = st.number_input(
                    "PE Stop Loss Price (₹)",
                    min_value=0.05,
                    max_value=10000.0,
                    value=float(default_pe_sl),
                    step=0.5,
                    format="%.2f",
                    key="v5_pe_sl_price_input",
                    help="Exact SL trigger in rupees (e.g. 61.00, 75.00)"
                )
            with p_sl2:
                pe_sl_choice = st.selectbox("PE SL % Presets", options=["25% (Standard)", "10%", "20%", "30%", "40%", "Custom"], index=0, key="v5_pe_sl_choice")
                pe_sl_pct = 25.0
                if pe_sl_choice == "10%": pe_sl_pct = 10.0
                elif pe_sl_choice == "20%": pe_sl_pct = 20.0
                elif pe_sl_choice == "25% (Standard)": pe_sl_pct = 25.0
                elif pe_sl_choice == "30%": pe_sl_pct = 30.0
                elif pe_sl_choice == "40%": pe_sl_pct = 40.0
                elif pe_sl_choice == "Custom":
                    pe_sl_pct = st.number_input("Custom PE SL %", min_value=1.0, max_value=200.0, value=25.0, step=1.0, key="v5_pe_custom_sl")
                
                if float(pe_sl_price_val) > float(pe_sell_anchor) and float(pe_sell_anchor) > 0:
                    pe_effective_pct = ((float(pe_sl_price_val) - float(pe_sell_anchor)) / float(pe_sell_anchor)) * 100.0
                else:
                    pe_effective_pct = float(pe_sl_pct)
            with p_sl3:
                st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)
                pe_reentry = st.checkbox("Re-entry", value=True, key="v5_pe_reentry", help="Auto re-entry upon SL trigger")

            # Dynamic Live Metrics & SL Preview Card
            st.markdown(
                f'<div style="background:#f0fdf4;border:1px dashed #22c55e;border-radius:8px;padding:8px 12px;margin-top:6px;font-size:0.82rem;">'
                f'📈 <b>Live LTP:</b> ₹{pe_sell_live:,.2f} &nbsp;|&nbsp; 🛡️ <b>Hedge LTP:</b> ₹{pe_hedge_live:,.2f}<br/>'
                f'🛑 <b>Stop-Loss Trigger:</b> <span style="color:#15803d;font-weight:800;font-size:0.95rem;">₹{float(pe_sl_price_val):,.2f}</span> '
                f'<span style="color:#64748b;">(+{pe_effective_pct:.1f}% on Anchor ₹{float(pe_sell_anchor):,.2f})</span>'
                f'</div>',
                unsafe_allow_html=True
            )

        # 📖 Embedded Student-Friendly Guide
        with st.expander("📖 10TH CLASS STUDENT GUIDE — KAISE TRADE KAREIN & RULES (Click to Read)", expanded=False):
            st.markdown(
                """
                ### 🌟 Bharat V5 Simple Trading Rules (10th/12th Class Level):
                1. **Master Anchor (Direction):** 
                   - Spot >= Anchor $\\rightarrow$ **BULLISH**: Put Wing Live bikega (Zerodha me order jayega), Call Wing wait karega.
                   - Spot < Anchor $\\rightarrow$ **BEARISH**: Call Wing Live bikega (Zerodha me order jayega), Put Wing wait karega.
                2. **Auto LTP & Anchor:**
                   - System automatically Live Market Price (LTP) ko Anchor bana leta hai taaki trade turant execute ho sake.
                3. **Stop Loss Customization:**
                   - Aap chahein toh Stop Loss Price (₹) ko seedhe change kar sakte hain (jaise ₹60 ka anchor aur ₹61 ya ₹75 ka SL).
                4. **Hedge-First Safety:**
                   - Zerodha me pehle Hedge Buy order execute hota hai taaki margin kam lage, fir Sell leg execute hoti hai.
                5. **3:00 PM Continuation:**
                   - 3:00 PM par agar trend aapke favor me hai toh overnight hold rahega, opposing side close ho jayegi.
                """
            )

        # Live Directional Indicator Banner
        is_bullish_preview = live_spot >= anchor_val
        if is_bullish_preview:
            preview_banner = (
                f'<div style="background:#ecfdf5;border:2px solid #10b981;border-radius:10px;padding:12px 18px;margin:16px 0;text-align:center;">'
                f'<span style="color:#065f46;font-weight:900;font-size:1.05rem;">🟢 LIVE BULLISH SIGNAL (Spot ₹{live_spot:,.2f} &ge; Anchor ₹{anchor_val:,.2f})</span><br/>'
                f'<span style="color:#047857;font-size:0.85rem;font-weight:600;">⚡ <b>PUT WING</b> will execute LIVE (Buy Hedge ₹{pe_hedge_strike} ➔ Sell PE ₹{pe_sell_strike} | SL: ₹{float(pe_sl_price_val):,.2f}). <b>CALL WING</b> held in PENDING.</span>'
                f'</div>'
            )
        else:
            preview_banner = (
                f'<div style="background:#fef2f2;border:2px solid #ef4444;border-radius:10px;padding:12px 18px;margin:16px 0;text-align:center;">'
                f'<span style="color:#991b1b;font-weight:900;font-size:1.05rem;">🔴 LIVE BEARISH SIGNAL (Spot ₹{live_spot:,.2f} &lt; Anchor ₹{anchor_val:,.2f})</span><br/>'
                f'<span style="color:#b91c1c;font-size:0.85rem;font-weight:600;">⚡ <b>CALL WING</b> will execute LIVE (Buy Hedge ₹{ce_hedge_strike} ➔ Sell CE ₹{ce_sell_strike} | SL: ₹{float(ce_sl_price_val):,.2f}). <b>PUT WING</b> held in PENDING.</span>'
                f'</div>'
            )
        st.markdown(preview_banner, unsafe_allow_html=True)

        # Deploy Button
        if st.button("🚀 DEPLOY UNIFIED MASTER UNIT NOW", key="btn_deploy_v5_master_unit", type="primary", use_container_width=True):
            with st.spinner("Deploying V5 Unified Master Unit..."):
                res_dep = bm.deploy_unified_master_unit(
                    expiry_date=expiry_val,
                    anchor_unit_name=unit_val,
                    master_anchor_price=float(anchor_val),
                    regime_buffer=15.0,
                    recommended_lots=int(lots_val),
                    ce_sell_strike=int(ce_sell_strike),
                    ce_sell_anchor=float(ce_sell_anchor),
                    ce_hedge_strike=int(ce_hedge_strike),
                    ce_hedge_anchor=float(ce_hedge_anchor),
                    ce_sl_pct=float(ce_sl_pct),
                    ce_sl_price=float(ce_sl_price_val),
                    ce_reentry_enabled=1 if ce_reentry else 0,
                    pe_sell_strike=int(pe_sell_strike),
                    pe_sell_anchor=float(pe_sell_anchor),
                    pe_hedge_strike=int(pe_hedge_strike),
                    pe_hedge_anchor=float(pe_hedge_anchor),
                    pe_sl_pct=float(pe_sl_pct),
                    pe_sl_price=float(pe_sl_price_val),
                    pe_reentry_enabled=1 if pe_reentry else 0,
                    execute_live=True,
                    current_spot=live_spot
                )
                if res_dep.get("ok"):
                    _flash(f"✅ {res_dep.get('message')}", "success")
                    st.rerun()
                else:
                    _flash(f"❌ Deployment failed: {res_dep.get('message')}", "error")



# ─────────────────────────────────────────────────────────────────────────────
# NEW BLOCK FORM (V3.0 MULTI-ANCHOR POD SETUP)
# ─────────────────────────────────────────────────────────────────────────────
def render_new_block_form():
    import regime_engine as re_eng
    live_spot = re_eng.get_current_nifty_spot()

    with st.expander("➕ CREATE NEW BLOCK / UNIT (M1, M2, M3...)", expanded=False):
        st.markdown('<p class="section-title">New Block Setup (V3.0 Autonomous Pod Architecture)</p>', unsafe_allow_html=True)
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

    # Fetch portfolio P&L
    portfolio = _get_portfolio()
    st.session_state["portfolio_pnl"] = portfolio

    # Header
    render_header(portfolio)

    # Flash messages
    _show_flash()

    # Metrics row
    render_metrics(portfolio)

    st.markdown("<br/>", unsafe_allow_html=True)

    # Global Red Alert Popup Banner (appears across all 3 pages if any holding < 200 DMA)
    eq_engine.render_global_red_alert_banner()

    tab_options, tab_commodity, tab_equity = st.tabs([
        "💰 Nifty Option Selling", 
        "🛢️ MCX Commodities FUT", 
        "📊 Equity & Gold (200 DMA Monitor)"
    ])

    with tab_options:
        # Master Nifty Anchor & Single-Directional Regime Governor (Brick 4)
        render_master_regime_controller()

        # V5.0 Unified Single-Window Console ("Ek Hi Jagah Saari Chijen")
        render_unified_v5_console()

        # New block form (Legacy fallback)
        render_new_block_form()

        # Active & Orphan Hedges Profit Lock Monitor
        render_hedges_profit_lock_monitor(portfolio)

        st.markdown("<br/>", unsafe_allow_html=True)

        # Unit Pod Containers
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
            from collections import OrderedDict
            unit_groups = OrderedDict()
            for bp in block_pnls:
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

        # Block management (archive/delete)
        with st.expander("⚙️ Block Management (Archive / Delete)", expanded=False):
            render_block_management()

    with tab_commodity:
        render_commodity_tab()

    with tab_equity:
        eq_engine.render_equity_tab()


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


if __name__ == "__main__":
    main()
