"""
ui_os_units.py — Momentum OS-Units Cockpit (OS1–OS5) (Zerodha OS)
================================================================
Tab 2:
  • OS Stepper (OS1, OS2, OS3, OS4, OS5)
  • 3:00 PM Momentum Decision & Decay Benchmarks
  • 500-pt Odd vs 100-pt Even Strike Strategy Mode
  • Lock & Arm Strategy Controller
  • Active OS Positions Telemetry
"""

from nicegui import ui
from typing import Callable
import terminal_backend as tb
import db


def render_os_units_tab(refresh_all_callback: Callable) -> Callable:
    """Renders Tab 2: Momentum OS-Units Cockpit."""

    current_os = {"name": "OS1"}

    with ui.column().classes("w-full gap-4"):
        # Header Box
        with ui.card().classes("trade-card w-full border-l-4 border-amber-500 py-3 px-4"):
            with ui.row().classes("w-full justify-between items-center"):
                with ui.column().classes("gap-0"):
                    ui.label("🎯 MOMENTUM OS-UNITS COCKPIT (OS1–OS5)").classes("font-black text-base text-white tracking-wide")
                    ui.label("3:00 PM Momentum Decay Engine • Yesterday Benchmark Comparison • 500-pt / 100-pt Step Options").classes("text-xs text-slate-400")
                ui.badge("OS MOMENTUM ENGINE", color="warning").classes("text-xs font-bold px-2 py-1")

        # Step Selector Pills (OS1 to OS5)
        with ui.row().classes("w-full gap-2 items-center bg-[#0f141c] p-2 rounded-xl border border-[#232d3f]"):
            ui.label("SELECT OS-UNIT:").classes("text-xs font-black text-slate-400 ml-2")
            os_buttons = {}
            for u in ["OS1", "OS2", "OS3", "OS4", "OS5"]:
                def _make_click(uname=u):
                    def _sel():
                        current_os["name"] = uname
                        for k, btn in os_buttons.items():
                            if k == uname:
                                btn.classes(replace="bg-amber-600 text-white font-black text-xs px-3 py-1.5 shadow")
                            else:
                                btn.classes(replace="bg-[#1a2230] text-slate-300 font-bold text-xs px-3 py-1.5")
                        render_os_view()
                    return _sel
                btn = ui.button(u, on_click=_make_click(u)).classes("bg-[#1a2230] text-slate-300 font-bold text-xs px-3 py-1.5 rounded-lg")
                os_buttons[u] = btn
            os_buttons["OS1"].classes(replace="bg-amber-600 text-white font-black text-xs px-3 py-1.5 shadow")

        os_view_container = ui.column().classes("w-full gap-4")

    def render_os_view():
        os_view_container.clear()
        uname = current_os["name"]
        data = tb.get_os_unit_cockpit_data(uname)
        is_locked = data["is_locked"]

        with os_view_container:
            # ── 1. STRATEGY LOCK & PARAMETER CONTROLLER ──
            with ui.card().classes("trade-card w-full p-4"):
                with ui.row().classes("w-full justify-between items-center border-b border-[#232d3f] pb-2 mb-3"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("tune", color="amber", size="1.4rem")
                        ui.label(f"{uname} PARAMETER HORIZON & ARMED STATUS").classes("font-black text-sm text-white")
                    ui.badge("LOCKED & ARMED" if is_locked else "DRAFT MODE", color="positive" if is_locked else "grey").classes("font-black text-xs px-2.5 py-1")

                with ui.row().classes("w-full gap-4 items-center flex-wrap"):
                    all_exp = list(data.get("all_expiries", []))
                    exp_val = data["settings"].get("expiry_date") or (all_exp[0] if all_exp else "")
                    if exp_val and exp_val not in all_exp:
                        all_exp.insert(0, exp_val)
                    elif not exp_val and all_exp:
                        exp_val = all_exp[0]
                    exp_select = ui.select(label="Target Expiry", options=all_exp, value=exp_val).classes("w-48")
                    step_select = ui.select(label="Strike Multiples", options=["100-pt Even Multiples", "500-pt Major Boundaries"], value="100-pt Even Multiples").classes("w-52")
                    lots_input = ui.number(label="Lots", value=data["settings"].get("lots", 1), min=1, max=50, step=1).classes("w-24 mono")

                    with ui.row().classes("items-center gap-3 ml-auto"):
                        if is_locked:
                            def _unlock():
                                db.set_os_unit_settings(uname, {"locked": False})
                                ui.notify(f"{uname} Unlocked for editing.", type="info")
                                render_os_view()
                                refresh_all_callback()
                            ui.button("🔓 UNLOCK & EDIT", on_click=_unlock).classes("bg-slate-700 text-white font-black text-xs px-3.5 py-2")
                        else:
                            def _lock_arm():
                                db.set_os_unit_settings(uname, {
                                    "locked": True,
                                    "expiry_date": str(exp_select.value),
                                    "lots": int(lots_input.value or 1)
                                })
                                ui.notify(f"{uname} Locked & Armed for 3:00 PM Momentum Decision.", type="positive")
                                render_os_view()
                                refresh_all_callback()
                            ui.button("🔒 LOCK & ARM STRATEGY", on_click=_lock_arm).classes("bg-amber-600 hover:bg-amber-700 text-white font-black text-xs px-4 py-2 rounded-lg")

            # ── 2. 3:00 PM MOMENTUM DECISION BENCHMARK ──
            with ui.card().classes("trade-card w-full p-4 mt-2"):
                with ui.row().classes("w-full justify-between items-center border-b border-[#232d3f] pb-2 mb-3"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("access_time", color="sky", size="1.4rem")
                        ui.label("3:00 PM MOMENTUM DECAY BENCHMARK").classes("font-black text-sm text-white")
                    ui.label("Executes at 15:00 IST on high-decay candidates").classes("text-xs text-slate-400")

                with ui.row().classes("w-full gap-4"):
                    with ui.card().classes("bg-[#0f141c] border border-slate-700 p-3 rounded-lg flex-1"):
                        ui.label("MINIMUM REQUIRED DECAY").classes("text-[10px] text-slate-400 font-bold")
                        ui.label("≥ 15.0%").classes("mono text-xl font-black text-emerald-400 mt-1")
                        ui.label("Compared against yesterday's 3:00 PM closing benchmark").classes("text-[10px] text-slate-500 mt-0.5")

                    with ui.card().classes("bg-[#0f141c] border border-slate-700 p-3 rounded-lg flex-1"):
                        ui.label("TODAY'S EXECUTION STATUS").classes("text-[10px] text-slate-400 font-bold")
                        ui.label("PENDING 15:00 IST").classes("mono text-xl font-black text-sky-400 mt-1")
                        ui.label("Autonomous watchdog evaluates at candle close").classes("text-[10px] text-slate-500 mt-0.5")

            # ── 3. ACTIVE OS POSITIONS ──
            os_blks = data["active_os_blocks"]
            if os_blks:
                with ui.card().classes("trade-card w-full p-4 mt-2"):
                    ui.label("📦 ACTIVE MOMENTUM OS POSITIONS").classes("font-black text-sm text-white mb-3")
                    for b in os_blks:
                        b_id = b.get("block_id") or b.get("id")
                        u_tag = b.get("anchor_unit_name", uname)
                        with ui.card().classes("bg-[#0f141c] border border-amber-900/60 p-3 rounded-lg mb-2 w-full"):
                            with ui.row().classes("w-full justify-between items-center border-b border-[#232d3f] pb-2 mb-2"):
                                ui.label(f"Block #{b_id} ({u_tag}) • Expiry: {b.get('expiry_date')}").classes("font-bold text-xs text-amber-300")
                                def _close_os(bid=b_id):
                                    res = tb.square_off_block(bid)
                                    ui.notify(res.get("message"), type="warning")
                                    render_os_view()
                                    refresh_all_callback()
                                ui.button("Square Off OS Block", on_click=_close_os).props("dense outline").classes("text-xs text-red-400")

                            for s in b.get("strikes", []):
                                with ui.row().classes("w-full justify-between py-1 text-xs text-slate-300 border-b border-slate-800"):
                                    ui.label(f"{s.get('strike_price')} {s.get('option_type')} ({s.get('action')})").classes("font-bold mono text-white")
                                    ui.label(f"Fill: ₹{float(s.get('fill_price') or s.get('anchor_price') or 0):.2f} | LTP: ₹{float(s.get('current_price') or s.get('ltp') or 0):.2f}").classes("mono text-slate-300")
                                    ui.badge(s.get("status", "OPEN"), color="positive" if s.get("status") in ("OPEN", "EXECUTED") else "grey").classes("text-[10px]")

    render_os_view()
    return render_os_view
