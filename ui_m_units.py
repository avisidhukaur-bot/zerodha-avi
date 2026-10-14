"""
ui_m_units.py — Directional M-Units Cockpit (M1–M4) (Zerodha OS)
================================================================
Tab 1:
  • Unit Selector (M1, M2, M3, M4)
  • Spot vs Anchor Asymmetric Regime Gauge
  • Dynamic JIT Auto-Hunter & Minimum Premium Floor Guard (₹140)
  • 14:55 Entry Freeze Indicator
  • Candidate Strikes Recommendation
  • 1-Click Deploy / Arm
  • Active Pod Telemetry & Leg Table
"""

from nicegui import ui
from typing import Callable
import terminal_backend as tb
import config as cfg
import db


def render_m_units_tab(refresh_all_callback: Callable) -> Callable:
    """Renders Tab 1: Directional M-Units Cockpit."""

    current_unit = {"name": "M1"}

    with ui.column().classes("w-full gap-4"):
        # Header Box
        with ui.card().classes("trade-card w-full border-l-4 border-sky-500 py-3 px-4"):
            with ui.row().classes("w-full justify-between items-center"):
                with ui.column().classes("gap-0"):
                    ui.label("🏛️ DIRECTIONAL M-UNITS COCKPIT (V6.3)").classes("font-black text-base text-white tracking-wide")
                    ui.label("Spot vs Anchor Regime • JIT Dynamic Auto-Hunter (~₹200 on EVEN 100s) • ₹140 Floor Guard • 14:55 Freeze").classes("text-xs text-slate-400")
                with ui.row().classes("items-center gap-2"):
                    ui.badge("ASYMMETRIC REGIME ACTIVE", color="primary").classes("text-xs font-bold px-2 py-1")

        # Unit Selection Pills (M1, M2, M3, M4)
        with ui.row().classes("w-full gap-2 items-center bg-[#0f141c] p-2 rounded-xl border border-[#232d3f]"):
            ui.label("SELECT M-UNIT:").classes("text-xs font-black text-slate-400 ml-2")
            unit_buttons = {}
            for u in ["M1", "M2", "M3", "M4"]:
                def _make_click(uname=u):
                    def _sel():
                        current_unit["name"] = uname
                        for k, btn in unit_buttons.items():
                            if k == uname:
                                btn.classes(replace="bg-sky-600 text-white font-black text-xs px-3 py-1.5 shadow")
                            else:
                                btn.classes(replace="bg-[#1a2230] text-slate-300 font-bold text-xs px-3 py-1.5")
                        render_m_view()
                    return _sel
                btn = ui.button(u, on_click=_make_click(u)).classes("bg-[#1a2230] text-slate-300 font-bold text-xs px-3 py-1.5 rounded-lg")
                unit_buttons[u] = btn
            unit_buttons["M1"].classes(replace="bg-sky-600 text-white font-black text-xs px-3 py-1.5 shadow")

        # Dynamic Content Container
        m_view_container = ui.column().classes("w-full gap-4")

    def render_m_view():
        m_view_container.clear()
        uname = current_unit["name"]
        data = tb.get_m_unit_cockpit_data(uname)
        live_spot = data["live_spot"]
        anchor = data["anchor_price"]
        reg = data["regime"]
        diff = data["diff"]
        candidates = data["candidates"]

        with m_view_container:
            # ── 1. REGIME & ASYMMETRIC CONTROLLER GAUGE ──
            with ui.row().classes("w-full gap-4"):
                # Spot vs Anchor Card
                with ui.card().classes("trade-card flex-1 p-4"):
                    with ui.row().classes("w-full justify-between items-center"):
                        ui.label(f"{uname} SPOT vs ANCHOR REGIME").classes("text-xs font-bold text-slate-400 tracking-wider")
                        ui.badge(f"{'🟢' if reg == 'BULLISH' else '🔴'} {reg}", color="positive" if reg == "BULLISH" else "negative").classes("font-black text-xs px-2 py-0.5")

                    with ui.row().classes("items-baseline gap-4 mt-2"):
                        with ui.column().classes("gap-0"):
                            ui.label("LIVE SPOT").classes("text-[10px] text-slate-400 font-bold")
                            ui.label(f"₹{live_spot:,.2f}").classes("mono text-2xl font-black text-white")
                        with ui.column().classes("gap-0"):
                            ui.label("UNIT ANCHOR").classes("text-[10px] text-slate-400 font-bold")
                            ui.label(f"₹{anchor:,.2f}").classes("mono text-2xl font-black text-amber-300")
                        with ui.column().classes("gap-0"):
                            ui.label("DISTANCE").classes("text-[10px] text-slate-400 font-bold")
                            ui.label(f"{diff:+,.2f} pts").classes(f"mono text-xl font-black {'text-emerald-400' if diff >= 0 else 'text-red-400'}")

                    # Permission Rules
                    with ui.card().classes(f"w-full mt-3 p-2.5 rounded-lg {'bg-emerald-950/40 border border-emerald-500/40' if reg == 'BULLISH' else 'bg-red-950/40 border border-red-500/40'}"):
                        if reg == "BULLISH":
                            ui.label("✅ BULLISH QUALIFIED: PUT Selling (PE) is ACTIVE & Permitted. Call Selling (CE) is Locked in STANDBY.").classes("text-xs font-black text-emerald-300")
                        else:
                            ui.label("✅ BEARISH QUALIFIED: CALL Selling (CE) is ACTIVE & Permitted. Put Selling (PE) is Locked in STANDBY.").classes("text-xs font-black text-red-300")

                # Strategy Controls & 14:55 Freeze
                with ui.card().classes("trade-card flex-1 p-4"):
                    with ui.row().classes("w-full justify-between items-center"):
                        ui.label(f"{uname} PROTOCOL CONTROLS").classes("text-xs font-bold text-slate-400 tracking-wider")
                        freeze_on = data["freeze_active"]
                        ui.badge("14:55 ENTRY FREEZE: " + ("ACTIVE" if freeze_on else "OFF"), color="warning" if freeze_on else "positive").classes("text-[10px] font-bold px-2 py-0.5")

                    with ui.row().classes("w-full gap-3 mt-3 items-center"):
                        anchor_input = ui.number(label="Master Anchor (₹)", value=anchor, step=25, format="%.2f").classes("w-40 mono")
                        lots_input = ui.number(label="Lots", value=data["settings"].get("lots", 1), min=1, max=50, step=1).classes("w-24 mono")

                        def _save_anchor():
                            db.set_m_unit_anchor(uname, float(anchor_input.value or 0))
                            ui.notify(f"{uname} Anchor updated to ₹{anchor_input.value}", type="positive")
                            render_m_view()
                            refresh_all_callback()
                        ui.button("SAVE ANCHOR", on_click=_save_anchor).classes("bg-cyan-600 text-white font-bold text-xs")

                        def _lock_live():
                            db.set_m_unit_anchor(uname, live_spot)
                            ui.notify(f"{uname} Anchor Locked to Live Spot ₹{live_spot:,.2f}", type="positive")
                            render_m_view()
                            refresh_all_callback()
                        ui.button("⚡ LOCK SPOT", on_click=_lock_live).classes("bg-slate-700 text-amber-300 font-bold text-xs")

            # ── 2. JIT DYNAMIC AUTO-HUNTER CANDIDATE PREVIEW ──
            with ui.card().classes("trade-card w-full p-4 mt-2"):
                with ui.row().classes("w-full justify-between items-center border-b border-[#232d3f] pb-2 mb-3"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("radar", color="amber", size="1.4rem")
                        ui.label("JIT DYNAMIC STRIKE HUNTER PREVIEW (~₹200 on EVEN 100s)").classes("font-black text-sm text-white")
                    ui.label(f"Hard Floor Guard: Enforced ≥ ₹{data['min_floor']:.0f} (Rejects decayed junk)").classes("text-xs text-slate-400")

                with ui.row().classes("w-full gap-4"):
                    # CALL (CE) CANDIDATE
                    with ui.card().classes("bg-[#0f141c] border border-blue-900/60 p-3 rounded-lg flex-1"):
                        with ui.row().classes("w-full justify-between items-center"):
                            ui.label("BEARISH CALL WING").classes("font-bold text-xs text-blue-400")
                            ui.badge("SELL" if reg == "BEARISH" else "STANDBY", color="primary" if reg == "BEARISH" else "grey").classes("text-[10px]")
                        ui.label(f"Short: {candidates['ce_sell']} CE (EVEN 100)").classes("mono font-black text-sm text-white mt-1")
                        ui.label(f"Hedge: {candidates['ce_hedge']} CE (+500 OTM Safety)").classes("text-xs text-slate-400 mono")
                        ui.label(f"Target: ~₹{candidates['target_premium']:.0f} | Floor: ₹{data['min_floor']:.0f}").classes("text-[10px] text-amber-300 mt-1")

                    # PUT (PE) CANDIDATE
                    with ui.card().classes("bg-[#0f141c] border border-emerald-900/60 p-3 rounded-lg flex-1"):
                        with ui.row().classes("w-full justify-between items-center"):
                            ui.label("BULLISH PUT WING").classes("font-bold text-xs text-emerald-400")
                            ui.badge("SELL" if reg == "BULLISH" else "STANDBY", color="positive" if reg == "BULLISH" else "grey").classes("text-[10px]")
                        ui.label(f"Short: {candidates['pe_sell']} PE (EVEN 100)").classes("mono font-black text-sm text-white mt-1")
                        ui.label(f"Hedge: {candidates['pe_hedge']} PE (-500 OTM Safety)").classes("text-xs text-slate-400 mono")
                        ui.label(f"Target: ~₹{candidates['target_premium']:.0f} | Floor: ₹{data['min_floor']:.0f}").classes("text-[10px] text-amber-300 mt-1")

                with ui.row().classes("w-full justify-end mt-4 gap-3"):
                    m_exp_opts = list(data.get("all_expiries", []))
                    m_exp_val = m_exp_opts[0] if m_exp_opts else "2026-10-29"
                    if m_exp_val not in m_exp_opts:
                        m_exp_opts.append(m_exp_val)
                    exp_select = ui.select(label="Target Expiry", options=m_exp_opts, value=m_exp_val).classes("w-48")

                    def _deploy_qualified():
                        res = tb.deploy_or_update_m_unit_action(
                            unit_name=uname,
                            expiry_date=str(exp_select.value),
                            anchor_price=anchor,
                            lots=int(lots_input.value or 1),
                            ce_sell_strike=candidates["ce_sell"],
                            ce_hedge_strike=candidates["ce_hedge"],
                            pe_sell_strike=candidates["pe_sell"],
                            pe_hedge_strike=candidates["pe_hedge"],
                            deploy_now=True
                        )
                        if res.get("ok"):
                            ui.notify(res.get("message"), type="positive")
                        else:
                            ui.notify(res.get("message"), type="negative")
                        render_m_view()
                        refresh_all_callback()

                    ui.button("🚀 DEPLOY QUALIFIED WING NOW", on_click=_deploy_qualified).classes("bg-emerald-600 hover:bg-emerald-700 text-white font-black text-xs px-4 py-2 rounded-lg")

            # ── 3. ACTIVE POD LEGS TELEMETRY ──
            if data["has_active"]:
                blk = data["block"]
                b_id = blk.get("block_id") or blk.get("id")
                with ui.card().classes("trade-card w-full p-4 mt-2"):
                    with ui.row().classes("w-full justify-between items-center border-b border-[#232d3f] pb-2 mb-3"):
                        with ui.row().classes("items-center gap-2"):
                            ui.label(f"📦 ACTIVE BLOCK #{b_id} ({uname})").classes("font-black text-sm text-white")
                            ui.badge("LIVE POD", color="positive").classes("text-[10px] font-bold")
                        def _close_pod():
                            res = tb.square_off_block(b_id)
                            ui.notify(res.get("message"), type="warning")
                            render_m_view()
                            refresh_all_callback()
                        ui.button(f"Square Off {uname} Block", on_click=_close_pod).props("dense outline").classes("text-xs text-red-400")

                    for s in data["strikes"]:
                        with ui.row().classes("w-full justify-between items-center py-1.5 border-b border-slate-800 text-xs"):
                            with ui.row().classes("items-center gap-2"):
                                ui.badge(s.get("option_type"), color="primary" if s.get("option_type") == "CE" else "positive").classes("text-[10px]")
                                ui.label(f"{s.get('strike_price')} {s.get('option_type')} ({s.get('action', 'SELL')})").classes("font-bold text-white mono")
                            ui.label(f"Entry: ₹{float(s.get('fill_price') or s.get('anchor_price') or 0):.2f} | LTP: ₹{float(s.get('current_price') or s.get('ltp') or 0):.2f}").classes("text-slate-300 mono")
                            ui.badge(s.get("status", "OPEN"), color="positive" if s.get("status") in ("OPEN", "EXECUTED") else "grey").classes("text-[10px]")
            else:
                with ui.card().classes("trade-card w-full p-6 text-center mt-2 items-center"):
                    ui.icon("hourglass_empty", color="grey", size="2.5rem")
                    ui.label(f"No Active Block Open for {uname}").classes("text-sm font-bold text-slate-300 mt-2")
                    ui.label("Click 'Deploy Qualified Wing Now' above to initiate trades.").classes("text-xs text-slate-500 mt-0.5")

    render_m_view()
    return render_m_view
