# -*- coding: utf-8 -*-
"""
apply_3step_pipeline.py
Implements the Chhoti Bahan 3-Step Sequential Pipeline across:
  1. app.py (M-Units Cockpit)
  2. os_engine.py (OS-Units Cockpit)
  3. weekly_st_engine.py (Weekly ST Cockpit)
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

# ─────────────────────────────────────────────────────────────────────────────
# 1. UPGRADE app.py (M-Units)
# ─────────────────────────────────────────────────────────────────────────────
with open('app.py', 'r', encoding='utf-8') as f:
    app_code = f.read()

# Replace Step 1 container buttons in Draft Mode (lines ~2758-2793)
old_app_step1 = '''            st.markdown("<hr style='margin: 12px 0;'/>", unsafe_allow_html=True)
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                btn_fetch = st.button("🔍 Fetch & Preview Strikes", key=f"btn_m_fetch_{selected_pod}", use_container_width=True)
            with col_b2:
                btn_lock = st.button(f"🔒 Lock & Arm {selected_pod} Settings", key=f"btn_m_lock_{selected_pod}", use_container_width=True, type="primary")

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

            if btn_lock:
                db.set_m_unit_settings(
                    unit_name=selected_pod,
                    locked=True,
                    anchor_price=user_anchor,
                    horizon=horizon,
                    expiry_date=selected_exp,
                    lots=lots,
                    lot_size=user_lot_size,
                    mode="MANUAL" if stk_mode == "Manual Strike Override" else "AUTO",
                    manual_ce=m_ce or 0,
                    manual_pe=m_pe or 0,
                    target_premium=target_prem
                )
                _flash(f"✅ {selected_pod} Settings LOCKED & ARMED with Anchor ₹{user_anchor:,.2f}!", "success")
                st.rerun()

            st.markdown('</div>', unsafe_allow_html=True)'''

new_app_step1 = '''            st.markdown("<hr style='margin: 12px 0;'/>", unsafe_allow_html=True)
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

            st.markdown('</div>', unsafe_allow_html=True)'''

assert old_app_step1 in app_code, "Failed to find old_app_step1 in app.py"
app_code = app_code.replace(old_app_step1, new_app_step1, 1)

# Now update Step 2 & Step 3 execution section in app.py
old_app_exec = '''        # ── STEP 2: EXECUTION ACTION ─────────────────────────────────────────
        st.markdown(f'<p class="section-title" style="margin-top:20px;">🚀 STEP 2: EXECUTE OR ARM {selected_pod} (TREND DEPLOY)</p>', unsafe_allow_html=True)

        qual_wing_name = "CALL WING (BEARISH)" if unit_regime == "BEARISH" else "PUT WING (BULLISH)"
        btn_c1, btn_c2 = st.columns([2, 1])

        with btn_c1:
            if st.button(f"🚀 Execute Qualified {qual_wing_name} Now (Manual Deploy)", key=f"btn_m_exec_now_{selected_pod}", use_container_width=True, type="primary"):
                if not is_locked:
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
            if st.button(f"⏱️ Arm Both Wings in PENDING (Standby)", key=f"btn_m_arm_pending_{selected_pod}", use_container_width=True):
                if not is_locked:
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
                st.rerun()'''

new_app_exec = '''        # ── STEP 2: REVIEW & LOCK STRATEGY PARAMETERS ────────────────────────
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
                    st.rerun()'''

assert old_app_exec in app_code, "Failed to find old_app_exec in app.py"
app_code = app_code.replace(old_app_exec, new_app_exec, 1)

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(app_code)
print("✅ Successfully upgraded app.py with 3-Step Sequential Pipeline.")


# ─────────────────────────────────────────────────────────────────────────────
# 2. UPGRADE os_engine.py (OS-Units)
# ─────────────────────────────────────────────────────────────────────────────
with open('os_engine.py', 'r', encoding='utf-8') as f:
    os_code = f.read()

old_os_step1 = '''            st.markdown("<hr style='margin: 12px 0;'/>", unsafe_allow_html=True)
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                btn_fetch = st.button("🔍 Fetch & Preview Strikes", key="btn_os_fetch_strikes", use_container_width=True)
            with col_b2:
                btn_lock = st.button("🔒 Lock & Arm Pod Settings", key="btn_os_lock_settings", use_container_width=True)

            if btn_fetch:
                with st.spinner("Fetching strikes..."):
                    st.session_state["os_inspection_data"] = inspect_os_candidates(
                        expiry_date=selected_exp,
                        target_premium=target_prem,
                        manual_ce_strike=m_ce,
                        manual_pe_strike=m_pe,
                        hedge_dist=DEFAULT_HEDGE_DISTANCE
                    )

            if btn_lock:
                db.set_os_settings(
                    locked=True,
                    horizon=horizon,
                    expiry_date=selected_exp,
                    lots=lots,
                    lot_size=user_lot_size,
                    mode="MANUAL" if stk_mode == "Manual Strike Override" else "AUTO",
                    manual_ce=m_ce or 0,
                    manual_pe=m_pe or 0,
                    target_premium=target_prem
                )
                db.set_os_lot_size(user_lot_size)
                st.success("✅ Settings LOCKED & ARMED! System is now active.")
                st.rerun()

            st.markdown('</div>', unsafe_allow_html=True)'''

new_os_step1 = '''            st.markdown("<hr style='margin: 12px 0;'/>", unsafe_allow_html=True)
            btn_fetch = st.button("🔍 STEP 1: FETCH & PREVIEW LIVE STRIKES", key="btn_os_fetch_strikes", use_container_width=True, type="primary")

            if btn_fetch:
                with st.spinner("Fetching strikes..."):
                    st.session_state["os_inspection_data"] = inspect_os_candidates(
                        expiry_date=selected_exp,
                        target_premium=target_prem,
                        manual_ce_strike=m_ce,
                        manual_pe_strike=m_pe,
                        hedge_dist=DEFAULT_HEDGE_DISTANCE
                    )

            st.markdown('</div>', unsafe_allow_html=True)'''

assert old_os_step1 in os_code, "Failed to find old_os_step1 in os_engine.py"
os_code = os_code.replace(old_os_step1, new_os_step1, 1)

old_os_exec_hdr = '''    # STEP 2: EXECUTION BUTTONS (AUTO & MANUAL DEPLOY)
    st.markdown('<p class="section-title" style="margin-top:16px;">🚀 STEP 2: EXECUTE OR ARM POD (AUTO & MANUAL DEPLOY)</p>', unsafe_allow_html=True)'''

new_os_exec_hdr = '''    # ── STEP 2: REVIEW & LOCK OS POD SETTINGS ─────────────────────────────
    st.markdown('<p class="section-title" style="margin-top:24px;">🔒 STEP 2: REVIEW & LOCK OS POD SETTINGS</p>', unsafe_allow_html=True)
    if not is_locked:
        st.markdown(
            '<div style="background: rgba(245, 158, 11, 0.12); border-left: 4px solid #f59e0b; padding: 10px 16px; border-radius: 8px; font-size: 0.90rem; color: #fde68a; margin-bottom: 12px;">'
            '👉 <b>Step 1 Complete!</b> Review decaying candidate contracts above. Click below to lock settings and unlock Step 3 Execution options.'
            '</div>',
            unsafe_allow_html=True
        )
        if st.button("🔒 STEP 2: CONFIRM & LOCK OS POD SETTINGS", key="btn_os_lock_settings", use_container_width=True, type="primary"):
            db.set_os_settings(
                locked=True,
                horizon=horizon if 'horizon' in locals() else "Weekly Expiry",
                expiry_date=selected_exp,
                lots=lots,
                lot_size=user_lot_size,
                mode="MANUAL" if ('stk_mode' in locals() and stk_mode == "Manual Strike Override") else "AUTO",
                manual_ce=m_ce or 0,
                manual_pe=m_pe or 0,
                target_premium=target_prem
            )
            db.set_os_lot_size(user_lot_size)
            st.success("✅ Settings LOCKED! You can now proceed to Step 3.")
            st.rerun()
    else:
        st.markdown(
            '<div style="background: rgba(16, 185, 129, 0.12); border-left: 4px solid #10b981; padding: 10px 16px; border-radius: 8px; font-size: 0.90rem; color: #a7f3d0; margin-bottom: 12px;">'
            '✅ <b>STEP 2 COMPLETE:</b> OS Pod Settings are LOCKED in database.'
            '</div>',
            unsafe_allow_html=True
        )

    # ── STEP 3: EXECUTION ROUTING ─────────────────────────────────────────
    st.markdown('<p class="section-title" style="margin-top:20px;">🚀 STEP 3: EXECUTE OR ARM OS POD</p>', unsafe_allow_html=True)'''

assert old_os_exec_hdr in os_code, "Failed to find old_os_exec_hdr in os_engine.py"
os_code = os_code.replace(old_os_exec_hdr, new_os_exec_hdr, 1)

with open('os_engine.py', 'w', encoding='utf-8') as f:
    f.write(os_code)
print("✅ Successfully upgraded os_engine.py with 3-Step Sequential Pipeline.")


# ─────────────────────────────────────────────────────────────────────────────
# 3. UPGRADE weekly_st_engine.py (Weekly ST)
# ─────────────────────────────────────────────────────────────────────────────
with open('weekly_st_engine.py', 'r', encoding='utf-8') as f:
    w_code = f.read()

old_w_act = '''        c_act1, c_act2 = st.columns([1.5, 1.5])
        with c_act1:
            if st.button("🔒 LOCK & ARM EXPIRY STRATEGY", key="btn_w_lock", type="primary", use_container_width=True):
                set_weekly_st_settings(
                    locked=True,
                    expiry_mode=new_mode,
                    target_expiry=sel_target_exp,
                    min_spot_buffer=float(new_spot_buf),
                    st_clearance=float(new_st_moat)
                )
                st.toast(f"✅ Expiry Strategy LOCKED: {new_mode}", icon="🔒")
                st.rerun()
        with c_act2:
            if st.button("🎯 Preview Strike Selection with this Strategy", key="btn_w_test_preview", use_container_width=True):
                with st.spinner("Hunting compliant strikes..."):
                    preview_res = hunt_weekly_st_spread(
                        direction=cur_regime,
                        min_prem=cfg_st["min_prem"],
                        max_prem=cfg_st["max_prem"],
                        hedge_distance=cfg_st["hedge_dist"],
                        expiry_mode=new_mode,
                        target_expiry=sel_target_exp,
                        min_spot_buffer=float(new_spot_buf),
                        st_clearance=float(new_st_moat),
                        st_value=cur_st,
                        spot_val=cur_spot
                    )
                    st.session_state["w_hunter_preview"] = preview_res
                    st.rerun()'''

new_w_act = '''        # ── STEP 1: PREVIEW & HUNT CANDIDATE SPREAD ──────────────────────────
        if st.button("🎯 STEP 1: PREVIEW & HUNT STRIKES WITH THIS STRATEGY", key="btn_w_test_preview", use_container_width=True, type="primary"):
            with st.spinner("Hunting compliant strikes..."):
                preview_res = hunt_weekly_st_spread(
                    direction=cur_regime,
                    min_prem=cfg_st["min_prem"],
                    max_prem=cfg_st["max_prem"],
                    hedge_distance=cfg_st["hedge_dist"],
                    expiry_mode=new_mode,
                    target_expiry=sel_target_exp,
                    min_spot_buffer=float(new_spot_buf),
                    st_clearance=float(new_st_moat),
                    st_value=cur_st,
                    spot_val=cur_spot
                )
                st.session_state["w_hunter_preview"] = preview_res
                st.rerun()'''

assert old_w_act in w_code, "Failed to find old_w_act in weekly_st_engine.py"
w_code = w_code.replace(old_w_act, new_w_act, 1)

# Now in weekly_st_engine.py, add Step 2 Lock button right after preview card
old_w_card_render = '''        # In-Place Strategy Preview Display Card in Row 2.5 (Draft Mode)
        prev_draft = st.session_state.get("w_hunter_preview")
        if prev_draft:
            _render_strike_preview_card(prev_draft, all_weekly_expiries, cfg_st, mode_label=new_mode)'''

new_w_card_render = '''        # In-Place Strategy Preview Display Card in Row 2.5 (Draft Mode)
        prev_draft = st.session_state.get("w_hunter_preview")
        if prev_draft:
            _render_strike_preview_card(prev_draft, all_weekly_expiries, cfg_st, mode_label=new_mode)
            st.markdown('<div style="margin-top:12px;"></div>', unsafe_allow_html=True)
            if st.button("🔒 STEP 2: CONFIRM & LOCK EXPIRY STRATEGY", key="btn_w_lock", type="primary", use_container_width=True):
                set_weekly_st_settings(
                    locked=True,
                    expiry_mode=new_mode,
                    target_expiry=sel_target_exp,
                    min_spot_buffer=float(new_spot_buf),
                    st_clearance=float(new_st_moat)
                )
                st.toast(f"✅ Expiry Strategy LOCKED: {new_mode}", icon="🔒")
                st.rerun()'''

assert old_w_card_render in w_code, "Failed to find old_w_card_render in weekly_st_engine.py"
w_code = w_code.replace(old_w_card_render, new_w_card_render, 1)

with open('weekly_st_engine.py', 'w', encoding='utf-8') as f:
    f.write(w_code)
print("✅ Successfully upgraded weekly_st_engine.py with 3-Step Sequential Pipeline.")

