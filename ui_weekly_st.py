"""
ui_weekly_st.py — Weekly ST-2H Cockpit (W1 — V7.5 Master Edition) (Zerodha OS)
=============================================================================
Tab 3:
  • Autonomous ON/OFF Toggle
  • 2H SuperTrend (8,3) Metrics & Pulse Countdown
  • Row 2.5 Single Authoritative Decide & Lock Console (O(1) Strike Hunter)
  • Active W1 Spread Pod (Margin-Safe 1-Click Clean Exit)
  • Force Pulse Diagnostic Tool
"""

from nicegui import ui
from typing import Callable
import terminal_backend as tb
import weekly_st_engine as wst_engine


def render_weekly_st_tab(refresh_all_callback: Callable) -> Callable:
    """Renders Tab 3: Weekly ST-2H Cockpit."""

    with ui.column().classes("w-full gap-4"):
        # Header Box
        with ui.card().classes("trade-card w-full border-l-4 border-emerald-500 py-3 px-4"):
            with ui.row().classes("w-full justify-between items-center"):
                with ui.column().classes("gap-0"):
                    ui.label("⚡ WEEKLY ST-2H COCKPIT (W1 — V7.5 MASTER EDITION)").classes("font-black text-base text-white tracking-wide")
                    ui.label("SuperTrend (8,3) 2H Moat Shield • O(1) Ultra-Fast Strike Hunter • Single Authoritative Decide & Lock Console").classes("text-xs text-slate-400")
                ui.badge("V7.5 PRODUCTION", color="positive").classes("text-xs font-bold px-2 py-1")

        weekly_view_container = ui.column().classes("w-full gap-4")

    def render_weekly_view():
        weekly_view_container.clear()
        data = tb.get_weekly_st_cockpit_data()
        cfg_st = data["settings"]
        is_algo_on = data.get("is_algo_enabled", cfg_st.get("enabled", False))
        is_locked = data["is_locked"]
        trend = data["trend"]
        st_val = data["st_value"]
        spot = data["live_spot"]
        dist = data["spot_distance"]
        pulse = data["pulse_clock"]
        candidate = data["candidate"]
        pos = data["active_position"]

        with weekly_view_container:
            # ── 1. AUTONOMOUS ON/OFF & 2H SUPERTREND METRICS ──
            with ui.card().classes("trade-card w-full p-4"):
                with ui.row().classes("w-full justify-between items-center border-b border-[#232d3f] pb-3 mb-3"):
                    with ui.row().classes("items-center gap-3"):
                        ui.label("AUTONOMOUS WEEKLY ALGO:").classes("text-xs font-black text-slate-300")
                        algo_btn = ui.badge("ON (ACTIVE)" if is_algo_on else "OFF (PAUSED)", color="positive" if is_algo_on else "negative").classes("font-black text-xs px-2.5 py-1")
                        def _toggle_wst():
                            res = tb.toggle_weekly_st_algo(not is_algo_on)
                            ui.notify(res.get("message"), type="info")
                            render_weekly_view()
                            refresh_all_callback()
                        ui.button("TOGGLE ENGINE", on_click=_toggle_wst).props("dense outline").classes("text-xs text-slate-300")

                    with ui.row().classes("items-center gap-2"):
                        ui.icon("timer", color="amber", size="18px")
                        ui.label(f"Next 2H Pulse: {pulse}").classes("mono text-xs text-amber-300 font-bold")

                # Metrics Row
                with ui.row().classes("w-full justify-between items-center gap-4 flex-wrap"):
                    with ui.column().classes("gap-0"):
                        ui.label("NIFTY 50 SPOT").classes("text-[10px] text-slate-400 font-bold")
                        ui.label(f"₹{spot:,.2f}").classes("mono text-2xl font-black text-white")

                    with ui.column().classes("gap-0"):
                        ui.label("SUPERTREND (8,3) 2H").classes("text-[10px] text-slate-400 font-bold")
                        ui.label(f"₹{st_val:,.2f}").classes("mono text-2xl font-black text-amber-300")

                    with ui.column().classes("gap-0"):
                        ui.label("TREND REGIME").classes("text-[10px] text-slate-400 font-bold")
                        ui.badge(f"{'🟢' if trend == 'BULLISH' else '🔴'} {trend}", color="positive" if trend == "BULLISH" else "negative").classes("text-sm font-black px-3 py-1")

                    with ui.column().classes("gap-0"):
                        ui.label("DISTANCE TO TRENDLINE").classes("text-[10px] text-slate-400 font-bold")
                        ui.label(f"{dist:+,.2f} pts").classes(f"mono text-2xl font-black {'text-emerald-400' if dist >= 0 else 'text-red-400'}")

            # ── 2. ROW 2.5: UNIFIED V7.5 DECIDE & LOCK CONSOLE ──
            with ui.card().classes("trade-card w-full p-4 mt-2"):
                with ui.row().classes("w-full justify-between items-center border-b border-[#232d3f] pb-2 mb-3"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("security", color="emerald", size="1.4rem")
                        ui.label("ROW 2.5: UNIFIED DECIDE & LOCK CONSOLE (O(1) STRIKE HUNTER)").classes("font-black text-sm text-white")
                    ui.badge("ARMED & LOCKED" if is_locked else "DRAFT MODE", color="positive" if is_locked else "grey").classes("font-black text-xs px-2.5 py-1")

                with ui.row().classes("w-full gap-4 items-center flex-wrap"):
                    mode_radio = ui.radio(["Current Week Rollover", "Next Week Primary"], value="Next Week Primary").props("inline").classes("text-xs text-slate-200")
                    buffer_inp = ui.number(label="Moat Clearance Buffer (pts)", value=float(cfg_st.get("min_spot_buffer", 150.0)), step=25).classes("w-48 mono")
                    lots_inp = ui.number(label="Lots", value=int(cfg_st.get("lots", 1)), min=1, max=50, step=1).classes("w-24 mono")

                    with ui.row().classes("items-center gap-3 ml-auto"):
                        if is_locked:
                            def _unlock_w():
                                res = tb.unlock_weekly_st_strategy()
                                ui.notify(res.get("message"), type="info")
                                render_weekly_view()
                                refresh_all_callback()
                            ui.button("🔓 UNLOCK & EDIT", on_click=_unlock_w).classes("bg-slate-700 text-white font-black text-xs px-3.5 py-2")
                        else:
                            def _lock_w():
                                res = tb.lock_weekly_st_strategy(str(mode_radio.value), float(buffer_inp.value or 150.0), int(lots_inp.value or 1))
                                ui.notify(res.get("message"), type="positive")
                                render_weekly_view()
                                refresh_all_callback()
                            ui.button("🔒 LOCK & ARM STRATEGY", on_click=_lock_w).classes("bg-emerald-600 hover:bg-emerald-700 text-white font-black text-xs px-4 py-2 rounded-lg")

                # Strike Hunter Preview Card
                if candidate and candidate.get("ok", True):
                    with ui.card().classes("bg-[#0f141c] border border-emerald-900/60 p-4 rounded-lg w-full mt-3"):
                        with ui.row().classes("w-full justify-between items-center border-b border-[#232d3f] pb-2 mb-2"):
                            ui.label(f"🎯 QUALIFIED SPREAD CANDIDATE ({candidate.get('side', trend)})").classes("font-black text-xs text-emerald-400")
                            ui.label(f"Expiry: {candidate.get('expiry', 'Current')}").classes("mono text-xs text-slate-300 font-bold")

                        short_str = candidate.get('short_strike') or candidate.get('sell_strike', '--')
                        opt_t = candidate.get('option_type') or candidate.get('sell_option_type', 'CE')
                        s_ltp = float(candidate.get('short_ltp') or candidate.get('sell_ltp') or 0.0)
                        h_str = candidate.get('hedge_strike', '--')
                        h_ltp = float(candidate.get('hedge_ltp') or 0.0)
                        n_cred = float(candidate.get('net_credit') or candidate.get('estimated_net_credit') or 0.0)

                        with ui.row().classes("w-full justify-between items-center text-xs flex-wrap gap-2"):
                            ui.label(f"Short Leg: {short_str} {opt_t} @ ~₹{s_ltp:.2f}").classes("mono text-white font-bold")
                            ui.label(f"Hedge Leg: {h_str} {opt_t} @ ~₹{h_ltp:.2f}").classes("mono text-slate-300")
                            ui.label(f"Net Credit: ₹{n_cred:.2f}/sh").classes("mono text-emerald-400 font-black")
                        if candidate.get("moat_rule"):
                            ui.label(f"Moat Rule: {candidate['moat_rule']}").classes("text-[11px] text-slate-400 mt-1")
                elif data.get("candidate_info"):
                    with ui.row().classes("w-full items-center gap-2 mt-2 px-3 py-2 bg-[#161f2e] border border-amber-900/50 rounded"):
                        ui.icon("info", color="amber", size="18px")
                        ui.label(f"{data['candidate_info']}").classes("text-xs text-amber-300")

            # ── 3. ACTIVE W1 SPREAD POD ──
            if pos:
                with ui.card().classes("trade-card w-full p-4 mt-2"):
                    with ui.row().classes("w-full justify-between items-center border-b border-[#232d3f] pb-2 mb-3"):
                        ui.label(f"📦 ACTIVE W1 POSITION #{pos.get('id')}").classes("font-black text-sm text-white")
                        def _close_w():
                            res = wst_engine.close_weekly_st_position(pos["id"], exit_reason="MANUAL_UI_EXIT")
                            ui.notify(res.get("message"), type="warning")
                            render_weekly_view()
                            refresh_all_callback()
                        ui.button("1-Click Clean Exit W1", on_click=_close_w).props("dense outline").classes("text-xs text-red-400")

                    with ui.row().classes("w-full justify-between text-xs py-1"):
                        ui.label(f"Strategy: {pos.get('strategy_type')} | Expiry: {pos.get('expiry_date')}").classes("font-bold text-slate-200")
                        ui.label(f"Lots: {pos.get('lots', 1)} | Entry Time: {pos.get('entry_time', '--')}").classes("mono text-slate-300")
            else:
                with ui.card().classes("trade-card w-full p-6 text-center mt-2 items-center"):
                    ui.icon("check_circle", color="positive", size="2.5rem")
                    ui.label("No Active W1 Weekly ST Position Currently Open").classes("text-sm font-bold text-slate-300 mt-2")
                    ui.label("Strategy is armed. Will trigger autonomously on 2H pulse confirmation.").classes("text-xs text-slate-500 mt-0.5")

    render_weekly_view()
    return render_weekly_view
