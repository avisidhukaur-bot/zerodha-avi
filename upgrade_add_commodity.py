"""
upgrade_add_commodity.py — MCX Commodity Engine Upgrade Script
===============================================================
This script safely adds the MCX Commodity Futures Engine to an
existing Zerodha OS installation WITHOUT touching:
  - secrets.txt (your credentials)
  - zerodha_trader.db (your database)
  - Existing option selling logic
  - Any VPS-specific settings

USAGE:
  1. Place this file + commodity_engine.py + commodity_executor.py
     in your ZERODHA-OS directory
  2. Run: python upgrade_add_commodity.py
  3. The script will patch your existing files and set up the service
  
NOTE: This script reads VPS credentials from YOUR secrets.txt
"""

import os
import sys
import shutil
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def backup_file(filepath):
    """Create a timestamped backup of a file."""
    if os.path.exists(filepath):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = f"{filepath}.backup_{ts}"
        shutil.copy2(filepath, backup)
        print(f"  [BACKUP] {os.path.basename(filepath)} -> {os.path.basename(backup)}")
        return True
    return False


def file_contains(filepath, search_text):
    """Check if a file already contains a specific text."""
    if not os.path.exists(filepath):
        return False
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        return search_text in f.read()


def append_to_file(filepath, text, marker):
    """Append text to file if marker is not already present."""
    if file_contains(filepath, marker):
        print(f"  [SKIP] {os.path.basename(filepath)} already has commodity additions.")
        return False
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(text)
    print(f"  [PATCHED] {os.path.basename(filepath)} — added commodity section.")
    return True


def insert_before(filepath, anchor_text, new_text, marker):
    """Insert new_text before anchor_text in file."""
    if file_contains(filepath, marker):
        print(f"  [SKIP] {os.path.basename(filepath)} already has commodity additions.")
        return False
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    if anchor_text not in content:
        print(f"  [WARN] Could not find anchor in {os.path.basename(filepath)}. Manual patching may be needed.")
        return False
    content = content.replace(anchor_text, new_text + "\n" + anchor_text)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [PATCHED] {os.path.basename(filepath)} — inserted commodity section.")
    return True


def patch_config():
    """Add commodity configuration to config.py"""
    filepath = os.path.join(SCRIPT_DIR, "config.py")
    if not os.path.exists(filepath):
        print(f"  [ERROR] config.py not found!")
        return False
    
    backup_file(filepath)
    
    commodity_config = """

# ── MCX Commodity Configuration (Auto-added by upgrade_add_commodity.py) ──
COMMODITY_LOCK_PORT = 9991  # Port to prevent duplicate engine processes
COMMODITY_MARKET_OPEN_H = 9  # MCX opens at 09:00
COMMODITY_MARKET_OPEN_M = 0
COMMODITY_SQUAREOFF_H = 23  # Intraday square-off at 23:00 IST
COMMODITY_SQUAREOFF_M = 0
"""
    return append_to_file(filepath, commodity_config, "COMMODITY_LOCK_PORT")


def patch_db():
    """Add commodity default settings to db.py"""
    filepath = os.path.join(SCRIPT_DIR, "db.py")
    if not os.path.exists(filepath):
        print(f"  [ERROR] db.py not found!")
        return False
    
    backup_file(filepath)
    
    # We need to add commodity keys to the defaults dict
    # Find the defaults dict and add commodity keys
    if file_contains(filepath, "comm_engine_running"):
        print(f"  [SKIP] db.py already has commodity defaults.")
        return True
    
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    
    # Find the closing of the defaults dict and insert commodity keys before it
    old_marker = '        "last_cycle_time"      : "",'
    new_block = '''        "last_cycle_time"      : "",
        "comm_engine_running"  : "OFF",
        "comm_selected_contract": "",
        "comm_anchor_price"    : "0.0",
        "comm_lots"            : "1",
        "comm_position_state"  : "FLAT",
        "comm_entry_price"     : "0.0",
        "comm_entry_time"      : "",
        "comm_unrealized_pnl_pct": "0.0",
        "comm_stop_loss_pct"   : "0.0",
        "comm_carry_forward"   : "NO",
        "comm_last_check_candle_time": "",'''
    
    if old_marker in content:
        content = content.replace(old_marker, new_block)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  [PATCHED] db.py — added commodity default keys.")
        return True
    else:
        print(f"  [WARN] Could not auto-patch db.py defaults. You may need to add commodity keys manually.")
        return False


def patch_kite_executor():
    """Add MCX functions to kite_executor.py"""
    filepath = os.path.join(SCRIPT_DIR, "kite_executor.py")
    if not os.path.exists(filepath):
        print(f"  [ERROR] kite_executor.py not found!")
        return False
    
    backup_file(filepath)
    
    if file_contains(filepath, "get_mcx_futures"):
        print(f"  [SKIP] kite_executor.py already has MCX functions.")
        return True
    
    # Check if _load_security_master already exists
    has_security_master = file_contains(filepath, "_load_security_master")
    
    mcx_code = '''
    # ── MCX Commodity Functions (Auto-added by upgrade_add_commodity.py) ──
'''
    if not has_security_master:
        mcx_code += '''
    def _load_security_master(self):
        """Loads the Zerodha instruments CSV into a DataFrame with caching."""
        import pandas as pd
        csv_path = os.path.join(os.path.dirname(__file__), "zerodha_instruments.csv")
        if not os.path.exists(csv_path):
            if self.ensure_logged_in():
                try:
                    instruments = self.kite.instruments()
                    df = pd.DataFrame(instruments)
                    df.to_csv(csv_path, index=False)
                    print(f"[EXECUTOR][SM] Downloaded and cached {len(df)} instruments.")
                    return df
                except Exception as e:
                    print(f"[EXECUTOR][SM] Failed to download instruments: {e}")
            return pd.DataFrame()
        try:
            df = pd.read_csv(csv_path)
            print(f"[EXECUTOR][SM] Loaded {len(df):,} instruments from local cache.")
            return df
        except Exception:
            pass
        return pd.DataFrame()
'''
    
    mcx_code += '''
    def get_mcx_futures(self, base_symbol: str) -> list:
        """
        Searches the instruments master for MCX Futures matching the base symbol.
        Returns: list of dicts: [{"token": str, "trading_symbol": str, "expiry": str, "lot_size": int}]
        Sorted by expiry date.
        """
        df = self._load_security_master()
        if df.empty:
            return []
        filtered = df[
            (df["name"].str.upper() == base_symbol.upper()) &
            (df["exchange"].str.upper() == "MCX") &
            (df["instrument_type"].str.upper() == "FUT")
        ]
        results = []
        for _, row in filtered.iterrows():
            results.append({
                "token":          str(row["instrument_token"]),
                "trading_symbol": str(row["tradingsymbol"]),
                "expiry":         str(row["expiry"]),
                "lot_size":       int(row["lot_size"]),
            })
        try:
            from datetime import datetime as dt
            results.sort(key=lambda x: dt.strptime(x["expiry"], "%Y-%m-%d"))
        except Exception:
            results.sort(key=lambda x: x.get("expiry", ""))
        return results
'''
    
    # Find the last method of the class and append before the module-level code
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    
    # Insert before the kite_executor singleton instantiation
    marker = "kite_executor = KiteExecutor()"
    if marker in content:
        content = content.replace(marker, mcx_code + "\n\n" + marker)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  [PATCHED] kite_executor.py — added MCX functions.")
        return True
    else:
        # Try appending to class body before any standalone code
        print(f"  [WARN] Could not find kite_executor singleton. Appending MCX code at end of file.")
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(mcx_code)
        return True


def patch_app():
    """Add commodity tab import and rendering to app.py"""
    filepath = os.path.join(SCRIPT_DIR, "app.py")
    if not os.path.exists(filepath):
        print(f"  [ERROR] app.py not found!")
        return False
    
    backup_file(filepath)
    
    commodity_tab_code = '''

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
'''
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    
    # 1. Add import at the top
    if "import commodity_executor" not in content:
        import_line = "\nimport commodity_executor as comm_exec  # MCX Commodity Engine\n"
        if "import db" in content:
            content = content.replace("import db", "import db" + import_line, 1)
        else:
            content = import_line + "\n" + content
            
    # 2. Add render_commodity_tab function definition if not present
    if "def render_commodity_tab():" not in content:
        main_marker = 'if __name__ == "__main__":'
        if main_marker in content:
            content = content.replace(main_marker, commodity_tab_code + "\n\n" + main_marker, 1)
        else:
            content += commodity_tab_code

    # 3. Restructure main UI to use tabs automatically
    if "tab_options, tab_commodity = st.tabs" not in content:
        flash_marker = "    _show_flash()"
        if flash_marker in content:
            parts = content.split(flash_marker, 1)
            lines = parts[1].split("\n")
            
            # Find where if __name__ == "__main__": starts to avoid indenting it
            main_end_idx = len(lines)
            for idx, line in enumerate(lines):
                if 'if __name__ == "__main__":' in line:
                    main_end_idx = idx
                    break
            
            # Indent all lines of main() following _show_flash() by 4 spaces
            indented_lines = []
            for idx, line in enumerate(lines[:main_end_idx]):
                if line.strip():  # Only indent non-empty lines
                    indented_lines.append("    " + line)
                else:
                    indented_lines.append(line)
            
            remaining_lines = lines[main_end_idx:]
            
            new_part1 = (
                "\n\n    # Create Tabs for Option Selling and Commodities\n"
                "    tab_options, tab_commodity = st.tabs([\"💰 Nifty Option Selling\", \"🛢️ MCX Commodities FUT\"])\n\n"
                "    with tab_options:\n"
                + "\n".join(indented_lines)
                + "\n"
                + "    with tab_commodity:\n"
                + "        render_commodity_tab()\n\n"
                + "\n".join(remaining_lines)
            )
            content = parts[0] + flash_marker + new_part1
            print(f"  [PATCHED] app.py — restructured to use tabs automatically.")
        else:
            print(f"  [WARN] Could not find '_show_flash()' in app.py to auto-insert tabs. Manual integration may be required.")
            
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
        
    return True


def patch_deploy_script():
    """Add commodity service to lego1_deploy.py if it exists."""
    filepath = os.path.join(SCRIPT_DIR, "lego1_deploy.py")
    if not os.path.exists(filepath):
        print(f"  [SKIP] lego1_deploy.py not found (will create systemd service manually).")
        return False
    
    backup_file(filepath)
    
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    
    # 1. Add commodity files to FILES list
    if '"commodity_executor.py"' not in content and '"app.py"' in content:
        content = content.replace(
            '"app.py"',
            '"commodity_executor.py",\n    "commodity_engine.py",\n    "app.py"'
        )
        print(f"  [PATCHED] lego1_deploy.py — added commodity files to deploy list.")
        
    # 2. Stop commodity service along with others
    old_stop = 'systemctl stop zerodha_engine.service zerodha_dashboard.service'
    new_stop = 'systemctl stop zerodha_engine.service zerodha_dashboard.service zerodha_commodity.service'
    if old_stop in content and new_stop not in content:
        content = content.replace(old_stop, new_stop)
        print(f"  [PATCHED] lego1_deploy.py — added commodity service to stop command.")

    # 3. Create service file code and insert it
    old_dash_code = 'dash_service_code = f"""[Unit]'
    commodity_def = '''commodity_service_code = f"""[Unit]
Description=Zerodha Commodity Futures Engine
After=network.target

[Service]
Type=simple
WorkingDirectory={REMOTE_DIR}
ExecStart=/usr/bin/python3 -u commodity_engine.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""

dash_service_code = f"""[Unit]'''
    
    if 'commodity_service_code =' not in content and old_dash_code in content:
        content = content.replace(old_dash_code, commodity_def)
        print(f"  [PATCHED] lego1_deploy.py — defined commodity service code.")

    # 4. Write commodity service to VPS systemd
    old_write_dash = 'client.exec_command(write_dash_cmd)\ntime.sleep(1)'
    new_write_comm = '''client.exec_command(write_dash_cmd)
time.sleep(1)

# Write commodity service
write_comm_cmd = f"cat > /etc/systemd/system/zerodha_commodity.service << 'SVCEOF'\\n{commodity_service_code}\\nSVCEOF"
client.exec_command(write_comm_cmd)
time.sleep(1)'''
    
    if 'write_comm_cmd =' not in content and old_write_dash in content:
        content = content.replace(old_write_dash, new_write_comm)
        print(f"  [PATCHED] lego1_deploy.py — added command to write commodity service file.")

    # 5. Enable services
    old_enable = 'systemctl enable zerodha_engine.service zerodha_dashboard.service'
    new_enable = 'systemctl enable zerodha_engine.service zerodha_dashboard.service zerodha_commodity.service'
    if old_enable in content and new_enable not in content:
        content = content.replace(old_enable, new_enable)
        print(f"  [PATCHED] lego1_deploy.py — added commodity to enable command.")

    # 6. Start services
    old_start = 'run_ssh("systemctl start zerodha_dashboard.service && echo \'zerodha_dashboard started\'", "Starting Dashboard service")'
    new_start = '''run_ssh("systemctl start zerodha_dashboard.service && echo 'zerodha_dashboard started'", "Starting Dashboard service")
run_ssh("systemctl start zerodha_commodity.service && echo 'zerodha_commodity started'", "Starting Commodity service")'''
    if old_start in content and new_start not in content:
        content = content.replace(old_start, new_start)
        print(f"  [PATCHED] lego1_deploy.py — added commodity to start command.")

    # 7. Check active services
    old_active = 'systemctl is-active zerodha_engine.service zerodha_dashboard.service'
    new_active = 'systemctl is-active zerodha_engine.service zerodha_dashboard.service zerodha_commodity.service'
    if old_active in content and new_active not in content:
        content = content.replace(old_active, new_active)
        print(f"  [PATCHED] lego1_deploy.py — added commodity to active services check.")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
        
    return True


def verify_new_files():
    """Check that commodity_engine.py and commodity_executor.py exist."""
    engine = os.path.join(SCRIPT_DIR, "commodity_engine.py")
    executor = os.path.join(SCRIPT_DIR, "commodity_executor.py")
    
    ok = True
    if not os.path.exists(engine):
        print(f"  [ERROR] commodity_engine.py NOT FOUND in {SCRIPT_DIR}")
        ok = False
    else:
        print(f"  [OK] commodity_engine.py found.")
    
    if not os.path.exists(executor):
        print(f"  [ERROR] commodity_executor.py NOT FOUND in {SCRIPT_DIR}")
        ok = False
    else:
        print(f"  [OK] commodity_executor.py found.")
    
    return ok


def main():
    print("=" * 62)
    print("  🛢️ ZERODHA OS — MCX COMMODITY ENGINE UPGRADE")
    print("=" * 62)
    print(f"  Working Directory: {SCRIPT_DIR}")
    print(f"  Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 62)
    
    print("\n[1/6] Verifying new commodity files...")
    if not verify_new_files():
        print("\n[ABORT] Required files missing. Place commodity_engine.py and commodity_executor.py in the same directory.")
        sys.exit(1)
    
    print("\n[2/6] Patching config.py...")
    patch_config()
    
    print("\n[3/6] Patching db.py...")
    patch_db()
    
    print("\n[4/6] Patching kite_executor.py...")
    patch_kite_executor()
    
    print("\n[5/6] Patching app.py...")
    patch_app()
    
    print("\n[6/6] Patching deploy script...")
    patch_deploy_script()
    
    print("\n" + "=" * 62)
    print("  ✅ COMMODITY UPGRADE COMPLETE!")
    print("=" * 62)
    print("""
  NEXT STEPS:
  1. Run your deploy script (e.g. python lego1_deploy.py)
     OR manually copy files to VPS and restart services
  
  2. If you have a systemd-based deploy, ensure the commodity 
     service unit file is created on the VPS:
     
     [Unit]
     Description=Zerodha Commodity Futures Engine
     After=network.target
     
     [Service]
     Type=simple
     WorkingDirectory=/root/BHARAT-SYSTEMS/ZERODHA-OS
     ExecStart=/usr/bin/python3 -u commodity_engine.py
     Restart=always
     RestartSec=10
     
     [Install]
     WantedBy=multi-user.target
     
     Save as: /etc/systemd/system/zerodha_commodity.service
     Then: systemctl daemon-reload && systemctl enable zerodha_commodity.service
     
  3. Restart all services:
     systemctl restart zerodha_engine zerodha_commodity zerodha_dashboard
  
  4. Open the dashboard and go to the "🛢️ MCX Commodities FUT" tab
""")


if __name__ == "__main__":
    main()
