# dashboard/callbacks.py

import threading
import dash
from dash import Input, Output, State, ctx, html, dcc
import plotly.graph_objects as go

import config
from .styles import COLORS
from .layouts import setup_page, monitor_page, results_page, SCENARIOS
from .components import status_badge, svg_icon

# The Dash UI and the simulation loop run in different threads.
# _simulation_runner stores the function that starts the simulation,
# while _state_lock protects the shared state dictionary below.
_simulation_runner = None
_state_lock = threading.Lock()
_sim_state = {
    "status": "idle",
    "algorithm": "threshold",
    "scenario": "wifi",
    "num_devices": config.NUM_IOT_DEVICES,
    "num_wifi": config.NUM_WIFI_INTERFERERS,
    "num_bt": config.NUM_BT_INTERFERERS,
    "tick": 0,
    "total_ticks": config.TOTAL_TICKS,
    "final_loss": None,
    "total_switches": 0,
}

DEVICE_PROFILES = [
    {"icon": "camera", "name": "IP Camera", "traffic": "Video stream", "rate": "High traffic", "priority": "High priority", "risk": 3},
    {"icon": "temp", "name": "Temperature Sensor", "traffic": "Periodic sensing", "rate": "Low traffic", "priority": "Low priority", "risk": 1},
    {"icon": "bulb", "name": "Smart Bulb", "traffic": "Control message", "rate": "Low traffic", "priority": "Medium priority", "risk": 1},
    {"icon": "door", "name": "Door Sensor", "traffic": "Event alert", "rate": "Burst traffic", "priority": "High priority", "risk": 2},
    {"icon": "lock", "name": "Smart Lock", "traffic": "Security command", "rate": "Low traffic", "priority": "High priority", "risk": 2},
    {"icon": "hub", "name": "IoT Hub", "traffic": "Coordinator", "rate": "Medium traffic", "priority": "Critical node", "risk": 3},
    {"icon": "plug", "name": "Smart Plug", "traffic": "Control message", "rate": "Low traffic", "priority": "Medium priority", "risk": 1},
    {"icon": "motion", "name": "Motion Sensor", "traffic": "Motion burst", "rate": "Burst traffic", "priority": "High priority", "risk": 2},
]

# Backwards-compatible tuple list for older helper code.
DEVICE_TYPES = [(p["icon"], p["name"]) for p in DEVICE_PROFILES]

def register_runner(fn):
    global _simulation_runner
    _simulation_runner = fn


def set_simulation_state(**kwargs):
    with _state_lock:
        _sim_state.update(kwargs)


def get_simulation_state():
    with _state_lock:
        return dict(_sim_state)


def _empty_fig(message="Waiting for simulation data..."):
    fig = go.Figure()
    fig.add_annotation(text=message, xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False, font=dict(size=14, color=COLORS["muted"]))
    fig.update_layout(plot_bgcolor="#101C2B", paper_bgcolor="#101C2B", height=260, margin=dict(l=20, r=20, t=20, b=20))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return fig


def _chart_layout(x_title, y_title, height=300):
    return dict(
        height=height,
        margin=dict(l=55, r=25, t=28, b=45),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(size=15, color=COLORS["text"]),
        xaxis=dict(title=x_title, showgrid=True, gridcolor="rgba(148,163,184,0.16)", zeroline=False),
        yaxis=dict(title=y_title, showgrid=True, gridcolor="rgba(148,163,184,0.16)", zeroline=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )


def _phase_from_data(state, rows, events):
    status = state.get("status", "idle")
    if status == "idle":
        return "Idle — choose a scenario and start the simulation", COLORS["muted"]
    if status == "error":
        return "Error — simulation stopped unexpectedly", COLORS["red"]
    if not rows:
        return "Starting — initialising channels and devices", COLORS["primary"]

    latest_loss = rows[-1][2] * 100
    degraded = rows[-1][4]
    if status == "completed":
        return "Complete — open Results for the final summary", COLORS["green"]
    if events and latest_loss <= 5:
        return "Recovery — ACS has moved devices to cleaner channels", COLORS["green"]
    if events:
        return "ACS switching — devices are being moved", COLORS["primary"]
    if latest_loss > 5 or degraded > 0:
        return "Interference detected — packet loss/SINR degraded", COLORS["red"]
    return "Healthy operation — network is stable", COLORS["green"]


def _row_stat(label_text, value_text, meaning_text=None):
    """Build one readable result row for the Results page.

    meaning_text explains what the metric means, so a non-technical user
    can interpret the numbers rather than only seeing raw percentages.
    """
    return html.Div(
        [
            html.Div([
                html.Div(label_text, style={"fontSize": "14px", "fontWeight": "850", "color": COLORS["text"]}),
                html.Div(meaning_text or "", style={"fontSize": "12px", "lineHeight": "1.45", "color": COLORS["muted"], "marginTop": "3px"}),
            ]),
            html.Div(value_text, style={"fontSize": "18px", "fontWeight": "950", "color": COLORS["text"], "marginLeft": "16px"}),
        ],
        style={"display": "flex", "justifyContent": "space-between", "alignItems": "flex-start", "gap": "12px", "padding": "12px 0", "borderBottom": "1px solid rgba(148,163,184,0.18)"},
    )


def _device_card(idx, degraded_ids, switched_ids, degraded_remaining):
    icon_name, name = DEVICE_TYPES[(idx - 1) % len(DEVICE_TYPES)]
    if idx in degraded_ids or degraded_remaining > 0:
        status = "Degraded"
        color = COLORS["red"]
        degraded_remaining -= 1
        ring = "0 0 0 4px rgba(255,77,90,0.12), 0 0 26px rgba(255,77,90,0.35)"
    elif idx in switched_ids:
        status = "Recovered / switched"
        color = COLORS["primary"]
        ring = "0 0 0 4px rgba(47,128,255,0.12), 0 0 26px rgba(47,128,255,0.35)"
    else:
        status = "Healthy"
        color = COLORS["green"]
        ring = "0 0 0 4px rgba(49,211,125,0.10)"

    return html.Div(
        [
            html.Div(svg_icon(icon_name, color, 24), style={"width": "50px", "height": "50px", "borderRadius": "16px", "display": "flex", "alignItems": "center", "justifyContent": "center", "background": f"{color}18", "border": f"1px solid {color}60", "boxShadow": ring}),
            html.Div([html.Div(name, style={"fontSize": "15px", "fontWeight": "950", "color": COLORS["text"]}), html.Div(f"D{idx:02d} • {status}", style={"fontSize": "13px", "color": color, "fontWeight": "900", "marginTop": "3px"})], style={"marginLeft": "10px"}),
        ],
        style={"display": "flex", "alignItems": "center", "padding": "10px", "borderRadius": "16px", "background": "rgba(255,255,255,0.035)", "border": f"1px solid {COLORS['border']}"},
    ), degraded_remaining

def register_callbacks(app, logger):
    @app.callback(Output("page-content", "children"), Input("url", "pathname"))
    def route(pathname):
        state = get_simulation_state()
        page = (pathname or "/setup").strip("/") or "setup"
        if page == "monitor":
            return monitor_page(state)
        if page == "results":
            return results_page(state)
        return setup_page(state)

    @app.callback(
        Output("s-scenario-preview", "children"),
        Output("s-scenario-values", "children"),
        Input("s-scenario", "value"),
    )
    def update_scenario_preview(scenario):
        scenario = scenario or "wifi"
        s = SCENARIOS[scenario]
        icon_name = "router" if scenario == "wifi" else ("bluetooth" if scenario == "bluetooth" else "hub")
        preview = html.Div(
            [
                html.Div(svg_icon(icon_name, s["accent"], 34), style={"width": "68px", "height": "68px", "borderRadius": "20px", "background": f"{s['accent']}18", "border": f"1px solid {s['accent']}66", "display": "flex", "alignItems": "center", "justifyContent": "center", "boxShadow": f"0 0 28px {s['accent']}22"}),
                html.Div([html.Div(s["title"], style={"fontSize": "18px", "fontWeight": "950", "color": COLORS["text"]}), html.Div(s["subtitle"], style={"fontSize": "13px", "color": COLORS["muted"], "marginTop": "4px"})], style={"marginLeft": "16px"}),
            ],
            style={"display": "flex", "alignItems": "center", "padding": "16px", "borderRadius": "18px", "background": "rgba(255,255,255,0.04)", "border": f"1px solid {COLORS['border']}"},
        )
        vals = f"Scenario will run with {s['wifi']} Wi-Fi interferer(s) and {s['bt']} Bluetooth interferer(s). These are applied automatically so the demo stays manageable."
        return preview, vals

    @app.callback(Output("s-ticks-hint", "children"), Input("s-duration", "value"))
    def update_ticks_hint(duration):
        if not duration:
            return ""
        ticks = (int(duration) * 1000) // config.TICK_INTERVAL_MS
        return f"Estimated: {ticks:,} simulation ticks at {config.TICK_INTERVAL_MS} ms per tick."

    @app.callback(Output("s-algorithm-help", "children"), Input("s-algorithm", "value"))
    def update_algorithm_help(algorithm):
        """Explain the selected ACS algorithm in simple user-facing language."""
        if algorithm == "weighted":
            return "PPCS compares channels using a weighted score: current SINR, recent stability, and how crowded each channel is. It is useful when you want fewer unnecessary switches."
        return "RTDS is the simpler and faster option. It waits until the current channel falls below the SINR threshold, then moves the affected device to the channel with the strongest SINR."

    @app.callback(
        Output("s-feedback", "children"),
        Output("s-feedback", "style"),
        Output("store-algo", "data"),
        Output("url", "pathname"),
        Input("s-run-btn", "n_clicks"),
        State("s-scenario", "value"),
        State("s-algorithm", "value"),
        State("s-num-devices", "value"),
        State("s-duration", "value"),
        State("url", "pathname"),
        prevent_initial_call=True,
    )
    def handle_start(n_clicks, scenario, algorithm, num_devices, duration, current_path):
        if not n_clicks:
            return "", {}, {}, current_path
        state = get_simulation_state()
        if state.get("status") == "running":
            return "A simulation is already running.", {"color": COLORS["orange"], "marginTop": "14px"}, {}, current_path

        scenario = scenario or "wifi"
        algorithm = algorithm or "threshold"
        logger.algorithm_name = "Threshold-Based ACS" if algorithm == "threshold" else "Weighted Scoring ACS"
        s = SCENARIOS.get(scenario, SCENARIOS["wifi"])
        if not num_devices or int(num_devices) < 3 or int(num_devices) > 8:
            return "Use 3–8 devices so the live topology remains clear.", {"color": COLORS["red"], "marginTop": "14px"}, {}, current_path
        if not duration or int(duration) < 10:
            return "Duration must be at least 10 seconds.", {"color": COLORS["red"], "marginTop": "14px"}, {}, current_path
        if _simulation_runner is None:
            return "Simulation runner is not connected. Start the app through main.py.", {"color": COLORS["orange"], "marginTop": "14px"}, {}, current_path

        set_simulation_state(scenario=scenario, num_devices=int(num_devices), num_wifi=s["wifi"], num_bt=s["bt"], tick=0)
        t = threading.Thread(target=_simulation_runner, args=(algorithm, int(num_devices), int(duration), int(s["wifi"]), int(s["bt"])), daemon=True)
        t.start()
        label = "RTDS" if algorithm == "threshold" else "PPCS"
        return f"Started {s['title']} using {label}.", {"color": COLORS["green"], "marginTop": "14px"}, {"algorithm": algorithm, "scenario": scenario}, "/monitor"

    @app.callback(Output("mon-status-badge", "children"), Input("tick", "n_intervals"), Input("url", "pathname"))
    def update_monitor_status(_, pathname):
        if (pathname or "").strip("/") != "monitor":
            return dash.no_update
        return status_badge(get_simulation_state().get("status", "idle"))

    @app.callback(
        Output("mon-timer", "children"),
        Output("m-progress-text", "children"),
        Output("m-progress-pct", "children"),
        Output("m-progress-bar", "style"),
        Output("m-phase", "children"),
        Output("m-phase", "style"),
        Output("m-scenario-summary", "children"),
        Input("tick", "n_intervals"),
        Input("url", "pathname"),
    )
    def update_progress(_, pathname):
        if (pathname or "").strip("/") != "monitor":
            return "", "", "", {"width": "0%"}, "", {}, ""
        state = get_simulation_state()
        tick = int(state.get("tick", 0) or 0)
        total = int(state.get("total_ticks", config.TOTAL_TICKS) or config.TOTAL_TICKS)
        elapsed_s = (tick * config.TICK_INTERVAL_MS) // 1000
        pct = 0 if total <= 0 else min(100, (tick / total) * 100)
        rows = logger.get_recent_tick_metrics(limit=250)
        events = logger.get_switch_events(only_approved=True)
        phase, phase_color = _phase_from_data(state, rows, events)
        bar_style = {"height": "100%", "width": f"{pct:.1f}%", "background": phase_color if state.get("status") != "error" else COLORS["red"], "borderRadius": "999px", "transition": "width 0.35s ease"}
        scenario = SCENARIOS.get(state.get("scenario", "wifi"), SCENARIOS["wifi"])
        summary = f"{scenario['title']} • {state.get('num_devices', config.NUM_IOT_DEVICES)} IoT devices • {state.get('num_wifi', 0)} Wi-Fi interferer(s) • {state.get('num_bt', 0)} Bluetooth interferer(s)"
        return f"Elapsed {elapsed_s // 60:02d}:{elapsed_s % 60:02d}", f"{tick:,} / {total:,} ticks", f"{pct:.0f}%", bar_style, phase, {"fontSize": "18px", "fontWeight": "950", "color": phase_color}, summary

    @app.callback(
        Output("m-loss", "children"),
        Output("m-sinr", "children"),
        Output("m-healthy", "children"),
        Output("m-switches", "children"),
        Input("tick", "n_intervals"),
        Input("url", "pathname"),
    )
    def update_kpis(_, pathname):
        if (pathname or "").strip("/") != "monitor":
            return "—", "—", "—", "—"
        rows = logger.get_recent_tick_metrics(limit=1)
        ch_rows = logger.get_latest_channel_snapshot()
        events = logger.get_switch_events(only_approved=True)
        if not rows:
            return "—", "—", "—", "—"
        avg_loss = rows[0][2] * 100
        degraded = int(rows[0][4] or 0)
        total_devices = int(get_simulation_state().get("num_devices", config.NUM_IOT_DEVICES) or config.NUM_IOT_DEVICES)
        healthy = max(0, total_devices - degraded)
        avg_sinr = sum(r[1] for r in ch_rows) / len(ch_rows) if ch_rows else None
        return f"{avg_loss:.1f}%", f"{avg_sinr:.1f} dB" if avg_sinr is not None else "—", f"{healthy}/{total_devices}", str(len(events))

    @app.callback(Output("m-topology", "children"), Input("tick", "n_intervals"), Input("url", "pathname"))
    def update_topology(_, pathname):
        """Render the live network topology.

        The Wi-Fi/Bluetooth device is shown as an interference source, not as
        a connection point for the IoT nodes. The individual IoT nodes use
        software profiles (traffic type, packet rate, and priority) so the
        labels mean more than icons only.
        """
        if (pathname or "").strip("/") != "monitor":
            return ""

        state = get_simulation_state()
        rows = logger.get_recent_tick_metrics(limit=1)
        events = logger.get_switch_events(only_approved=True)

        total_devices = int(state.get("num_devices", config.NUM_IOT_DEVICES) or config.NUM_IOT_DEVICES)
        degraded = int(rows[0][4] or 0) if rows else 0
        # Keep interference visible briefly before/around ACS recovery.
        # This prevents the UI from jumping directly from Healthy to ACS Recovery.
        
        tick = int(state.get("tick", 0) or 0)

        # Only show ACS Recovery for recent switch events.
        # Otherwise old switches make devices stay blue forever.
        recent_window_ticks = 15
        switched_ids = {
            int(e[1])
            for e in events
            if tick - int(e[0]) <= recent_window_ticks
        }

        # Pick degraded devices using profile risk plus a slow moving offset.
        # This avoids always colouring the first row red and makes the demo
        # look more natural while still favouring high-traffic/critical nodes.
        device_scores = []
        for device_id in range(1, total_devices + 1):
            profile = DEVICE_PROFILES[(device_id - 1) % len(DEVICE_PROFILES)]
            movement = (tick // 3 + device_id) % max(1, total_devices)
            score = profile["risk"] * 10 + movement
            device_scores.append((score, device_id))
        device_scores.sort(reverse=True)
                # Limit visible degraded devices so the topology does not show every
        # device failing at the same time. This better represents mixed IoT
        # behaviour under one Wi-Fi/Bluetooth scenario.
        visible_degraded = min(degraded, max(1, total_devices // 2))

        degraded_ids = {
            device_id
            for _, device_id in device_scores[:visible_degraded]
        }

        if state.get("num_wifi", 0) > 0:
            interferer_icon = "router"
            interferer_label = "Wi-Fi Router Interferer"
            interferer_meta = "Broadband 20/40 MHz interference in the 2.4 GHz band"
            interferer_color = COLORS["red"]
        elif state.get("num_bt", 0) > 0:
            interferer_icon = "bluetooth"
            interferer_label = "Bluetooth Hopping Interferer"
            interferer_meta = "FHSS narrowband interference moving across channels"
            interferer_color = "#8B5CF6"
        else:
            interferer_icon = "hub"
            interferer_label = "Clean Spectrum"
            interferer_meta = "No intentional interference source"
            interferer_color = COLORS["green"]

        source = html.Div(
            [
                html.Div(
                    svg_icon(interferer_icon, interferer_color, 58),
                    style={
                        "width": "102px", "height": "102px", "borderRadius": "30px",
                        "background": f"{interferer_color}18",
                        "border": f"1px solid {interferer_color}66",
                        "display": "flex", "alignItems": "center", "justifyContent": "center",
                        "margin": "0 auto", "boxShadow": f"0 0 36px {interferer_color}33",
                    },
                ),
                html.Div(interferer_label, style={"fontSize": "19px", "fontWeight": "950", "color": COLORS["text"], "textAlign": "center", "marginTop": "12px"}),
                html.Div(interferer_meta, style={"fontSize": "13px", "color": COLORS["muted"], "textAlign": "center", "marginTop": "4px"}),
            ],
            style={"marginBottom": "18px"},
        )

        # Visual radio-wave rings. These are deliberately not connection lines;
        # they show interference radiating through shared spectrum.
        rings = html.Div(
            [
                html.Div(style={"width": "90px", "height": "22px", "border": f"2px solid {interferer_color}55", "borderTop": "none", "borderRadius": "0 0 90px 90px", "margin": "0 auto"}),
                html.Div(style={"width": "160px", "height": "34px", "border": f"2px solid {interferer_color}38", "borderTop": "none", "borderRadius": "0 0 160px 160px", "margin": "-6px auto 0"}),
                html.Div(style={"width": "230px", "height": "46px", "border": f"2px solid {interferer_color}24", "borderTop": "none", "borderRadius": "0 0 230px 230px", "margin": "-8px auto 0"}),
            ],
            style={"height": "72px", "marginBottom": "12px"},
        )

        nodes = []
        for device_id in range(1, total_devices + 1):
            profile = DEVICE_PROFILES[(device_id - 1) % len(DEVICE_PROFILES)]

            if device_id in degraded_ids:
                colour = COLORS["red"]
                device_state = "Interference"
                state_detail = "Packet loss increasing"
            elif device_id in switched_ids:
                colour = COLORS["primary"]
                device_state = "ACS Recovery"
                state_detail = "Cleaner channel selected"
            else:
                colour = COLORS["green"]
                device_state = "Healthy"
                state_detail = "Stable communication"

            nodes.append(
                html.Div(
                    [
                        html.Div(
                            svg_icon(profile["icon"], colour, 40),
                            style={
                                "width": "72px", "height": "72px", "borderRadius": "22px",
                                "background": f"{colour}18", "border": f"1px solid {colour}66",
                                "display": "flex", "alignItems": "center", "justifyContent": "center",
                                "margin": "0 auto 10px", "boxShadow": f"0 0 18px {colour}22",
                            },
                        ),
                        html.Div(profile["name"], style={"fontSize": "14px", "fontWeight": "950", "color": COLORS["text"], "textAlign": "center"}),
                        html.Div(f"D{device_id:02d} • {profile['traffic']}", style={"fontSize": "12px", "color": COLORS["muted"], "textAlign": "center", "marginTop": "3px"}),
                        html.Div(f"{profile['rate']} • {profile['priority']}", style={"fontSize": "11px", "color": COLORS["muted"], "textAlign": "center", "marginTop": "2px"}),
                        html.Div(device_state, style={"fontSize": "12px", "fontWeight": "950", "color": colour, "textAlign": "center", "marginTop": "7px"}),
                        html.Div(state_detail, style={"fontSize": "11px", "color": COLORS["muted"], "textAlign": "center", "marginTop": "2px"}),
                    ],
                    style={
                        "padding": "14px 10px", "borderRadius": "18px",
                        "background": "rgba(255,255,255,0.035)",
                        "border": f"1px solid {COLORS['border']}",
                    },
                )
            )

        explanation = html.Div(
            "Device labels are software profiles: e.g., the camera represents high-rate video traffic, while sensors represent lower-rate periodic or event-driven traffic.",
            style={"fontSize": "12px", "color": COLORS["muted"], "lineHeight": "1.5", "textAlign": "center", "marginTop": "16px"},
        )

        return html.Div(
            [
                source,
                rings,
                html.Div(nodes, style={"display": "grid", "gridTemplateColumns": "repeat(4, minmax(0, 1fr))", "gap": "18px"}),
                explanation,
                html.Div("Legend: 🟢 Healthy   🔴 Interference   🔵 ACS Recovery", style={"fontSize": "13px", "color": COLORS["muted"], "marginTop": "14px", "textAlign": "center"}),
            ]
        )

    @app.callback(Output("m-timeline", "children"), Output("m-event-log", "children"), Input("tick", "n_intervals"), Input("url", "pathname"))
    def update_timeline_log(_, pathname):
        if (pathname or "").strip("/") != "monitor":
            return "", ""
        state = get_simulation_state()
        rows = logger.get_recent_tick_metrics(limit=250)
        events = logger.get_switch_events(only_approved=True)
        phase, _ = _phase_from_data(state, rows, events)
        latest_loss = rows[-1][2] * 100 if rows else 0
        degraded = int(rows[-1][4]) if rows else 0
        steps = [
            ("Simulation started", bool(rows) or state.get("status") in ["running", "completed"], COLORS["green"]),
            ("Interference visible", latest_loss > 5 or degraded > 0 or bool(events), COLORS["red"]),
            ("Network degradation detected", degraded > 0 or latest_loss > 5 or bool(events), COLORS["orange"]),
            ("ACS channel switch executed", bool(events), COLORS["primary"]),
            ("Packet loss below 5% target", bool(rows) and latest_loss <= 5 and (bool(events) or state.get("status") == "completed"), COLORS["green"]),
        ]
        timeline = html.Div([
            html.Div([html.Span("✓" if done else "○", style={"color": color if done else COLORS["muted"], "fontWeight": "950", "marginRight": "8px"}), html.Span(text)], style={"fontSize": "13px", "fontWeight": "850", "color": COLORS["text"] if done else COLORS["muted"], "padding": "9px 0", "borderBottom": "1px solid rgba(148,163,184,0.16)"})
            for text, done, color in steps
        ])
        log_items = []
        if rows:
            log_items.append((rows[-1][1], phase))
            log_items.append((rows[-1][1], f"Packet loss {latest_loss:.1f}%, degraded devices {degraded}."))
        for tick, device_id, target_channel, reason in events[-5:]:
            log_items.append((tick * config.TICK_INTERVAL_MS, f"Device {device_id} moved to Ch {target_channel}. {reason[:70]}"))
        if not log_items:
            log_items = [(0, "Start a scenario to see live simulation events.")]
        event_log = html.Div([
            html.Div([html.Div(f"{int(t/1000):02d}s", style={"fontSize": "11px", "fontWeight": "950", "color": COLORS["primary"], "minWidth": "36px"}), html.Div(msg, style={"fontSize": "12px", "lineHeight": "1.45", "color": COLORS["text"]})], style={"display": "flex", "gap": "10px", "padding": "9px 0", "borderBottom": "1px solid rgba(148,163,184,0.16)"})
            for t, msg in reversed(log_items[-7:])
        ])
        return timeline, event_log

    @app.callback(Output("m-device-impact", "children"), Input("tick", "n_intervals"), Input("url", "pathname"))
    def update_device_impact(_, pathname):
        """Show how individual IoT devices are affected during the live run.

        The simulation currently logs network-level degraded device counts,
        not full per-device packet traces. To keep the UI honest, this panel
        maps the latest degraded count onto visible device cards and uses
        approved switch events to mark devices that ACS has recovered.
        """
        if (pathname or "").strip("/") != "monitor":
            return ""

        state = get_simulation_state()
        rows = logger.get_recent_tick_metrics(limit=1)
        events = logger.get_switch_events(only_approved=True)

        total_devices = int(state.get("num_devices", config.NUM_IOT_DEVICES) or config.NUM_IOT_DEVICES)
        degraded_count = int(rows[0][4] or 0) if rows else 0
        # Keep degradation visible for the demo so it does not flash too quickly
        # degraded_count = max(degraded_count, 1) if state.get("status") == "running" else degraded_count 
        tick = int(state.get("tick", 0) or 0)
        recent_window_ticks = 15

        switched_ids = {
            int(e[1])
            for e in events
            if tick - int(e[0]) <= recent_window_ticks
        }
        visible_degraded = min(degraded_count, max(1, total_devices // 2))
        degraded_ids = set(range(1, visible_degraded + 1))
        degraded_count = visible_degraded

        cards = []
        remaining = degraded_count
        for device_id in range(1, total_devices + 1):
            card_component, remaining = _device_card(device_id, degraded_ids, switched_ids, remaining)
            cards.append(card_component)

        affected_text = (
            f"{degraded_count} of {total_devices} device(s) are currently affected."
            if rows else "Start the simulation to see device status changes."
        )

        return html.Div([
            html.Div(affected_text, style={"fontSize": "16px", "fontWeight": "900", "color": COLORS["text"], "marginBottom": "12px"}),
            html.Div(cards, style={"display": "grid", "gridTemplateColumns": "repeat(2, minmax(0, 1fr))", "gap": "12px"}),
        ])

    @app.callback(Output("g-spectrum", "figure"), Output("m-spectrum-legend", "children"), Input("tick", "n_intervals"), Input("url", "pathname"))
    def update_spectrum(_, pathname):
        if (pathname or "").strip("/") != "monitor":
            return _empty_fig(), ""
        rows = logger.get_latest_channel_snapshot()
        if not rows:
            return _empty_fig("Waiting for channel snapshot..."), "Green = active/healthy, red = interfered, blue = available."
        channels = [f"{r[0]}" for r in rows]
        loss = [r[2] * 100 for r in rows]
        hover = [f"Ch {r[0]}<br>SINR {r[1]:.1f} dB<br>Packet loss {r[2]*100:.1f}%" for r in rows]
        state = get_simulation_state()
        bt_mode = int(state.get("num_bt", 0) or 0) > 0
        colours = []
        for ch_id, sinr, loss_rate, interfered, active in rows:
            if active:
                colours.append(COLORS["green"])
            elif interfered and bt_mode:
                colours.append(COLORS["purple"])
            elif interfered:
                colours.append(COLORS["red"])
            elif loss_rate > 0.05:
                colours.append(COLORS["orange"])
            else:
                colours.append(COLORS["primary"])
        fig = go.Figure()
        fig.add_trace(go.Bar(x=channels, y=loss, marker_color=colours, customdata=hover, hovertemplate="%{customdata}<extra></extra>", text=[f"{v:.0f}%" for v in loss], textposition="outside", name="Packet loss by channel"))
        fig.add_hline(y=5, line_dash="dash", line_color=COLORS["green"], annotation_text="acceptable loss", annotation_font_size=10)
        fig.update_layout(**_chart_layout("2.4 GHz channel", "Loss / congestion (%)", height=360))
        fig.update_yaxes(range=[0, 100])
        fig.update_layout(showlegend=False)
        interferer = "Bluetooth hopping" if bt_mode else ("Wi-Fi broadband" if int(state.get("num_wifi", 0) or 0) > 0 else "No intentional")
        return fig, f"Interferer shown: {interferer}. Red/purple channels are affected; green is the selected active channel."

    @app.callback(Output("t-channels", "data"), Input("tick", "n_intervals"), Input("url", "pathname"))
    def update_channel_table(_, pathname):
        if (pathname or "").strip("/") != "monitor":
            return []
        rows = logger.get_latest_channel_snapshot()
        return [{"channel": f"Ch {ch_id}", "sinr": f"{sinr_db:.1f} dB", "loss": f"{loss_rate * 100:.1f}%", "interfered": "Yes" if interfered else "No", "active": "Yes" if active else "No"} for ch_id, sinr_db, loss_rate, interfered, active in rows]

    @app.callback(Output("r-rtds-stats", "children"), Output("r-ppcs-stats", "children"), Input("tick", "n_intervals"), Input("url", "pathname"))
    def update_results_stats(_, pathname):
        if (pathname or "").strip("/") != "results":
            return "", ""

        def stats_for(algo_label):
            original = logger.algorithm_name
            logger.algorithm_name = algo_label
            rows = logger.get_recent_tick_metrics(limit=9999)
            events = logger.get_switch_events(only_approved=True)
            ch_rows = logger.get_latest_channel_snapshot()
            logger.algorithm_name = original
            if not rows:
                return html.Div("No data yet. Run this algorithm first.", style={"fontSize": "13px", "color": COLORS["muted"]})
            losses = [r[2] for r in rows]
            avg_loss = sum(losses) / len(losses) * 100
            peak_loss = max(losses) * 100
            final_loss = losses[-1] * 100
            avg_sinr = sum(r[1] for r in ch_rows) / len(ch_rows) if ch_rows else None
            recovery = 100 if final_loss <= 5 else max(0, 100 - final_loss)
            items = [
                ("Average Packet Loss", f"{avg_loss:.2f}%", "Overall proportion of packets lost during the run. Lower is better."),
                ("Peak Packet Loss", f"{peak_loss:.2f}%", "Worst recorded loss point. Shows how severe the interference became."),
                ("Final Packet Loss", f"{final_loss:.2f}%", "Loss at the end of the run. This should ideally fall below the 5% target."),
                ("Recovery Rate", f"{recovery:.0f}%", "Simple recovery indicator based on whether final loss returned to an acceptable level."),
                ("Channel Switches", str(len(events)), "How many times ACS moved devices away from poor channels."),
                ("Average SINR", f"{avg_sinr:.1f} dB" if avg_sinr is not None else "—", "Average signal quality. Higher SINR usually means cleaner communication."),
                ("Ticks Logged", str(len(rows)), "Number of time steps saved for this algorithm's run."),
            ]
            return html.Div([_row_stat(k, v, m) for k, v, m in items])
        return stats_for("Threshold-Based ACS"), stats_for("Weighted Scoring ACS")

    @app.callback(Output("r-comparison", "figure"), Input("tick", "n_intervals"), Input("url", "pathname"))
    def update_comparison_graph(_, pathname):
        if (pathname or "").strip("/") != "results":
            return _empty_fig()
        fig = go.Figure()
        for algo_label, display, color in [("Threshold-Based ACS", "RTDS", COLORS["primary"]), ("Weighted Scoring ACS", "PPCS", COLORS["green"] )]:
            original = logger.algorithm_name
            logger.algorithm_name = algo_label
            rows = logger.get_recent_tick_metrics(limit=9999)
            logger.algorithm_name = original
            if rows:
                fig.add_trace(go.Scatter(x=[r[1] for r in rows], y=[r[2] * 100 for r in rows], mode="lines", line=dict(width=4, color=color), name=display))
        if not fig.data:
            return _empty_fig("Run RTDS and/or PPCS to compare packet loss.")
        fig.add_hline(y=5, line_dash="dash", line_color=COLORS["green"], annotation_text="Performance target 5%", annotation_font_size=11)
        fig.update_layout(**_chart_layout("Time (ms)", "Packet loss (%)", height=330))
        fig.update_yaxes(range=[0, 100])
        return fig

    @app.callback(Output("r-switches", "figure"), Input("tick", "n_intervals"), Input("url", "pathname"))
    def update_switch_graph(_, pathname):
        if (pathname or "").strip("/") != "results":
            return _empty_fig()
        fig = go.Figure()
        for algo_label, display, color in [("Threshold-Based ACS", "RTDS", COLORS["primary"]), ("Weighted Scoring ACS", "PPCS", COLORS["green"] )]:
            original = logger.algorithm_name
            logger.algorithm_name = algo_label
            events = logger.get_switch_events(only_approved=True)
            logger.algorithm_name = original
            if events:
                fig.add_trace(go.Scatter(x=[e[0] for e in events], y=list(range(1, len(events) + 1)), mode="lines+markers", line=dict(width=3, color=color), marker=dict(size=8), name=display))
        if not fig.data:
            return _empty_fig("No channel switch events logged yet.")
        fig.update_layout(**_chart_layout("Tick", "Cumulative switches", height=330))
        fig.update_yaxes(rangemode="nonnegative")
        return fig

    @app.callback(
        Output("download-csv", "data"),
        Output("r-export-msg", "children"),
        Input("btn-export-rtds", "n_clicks"),
        Input("btn-export-ppcs", "n_clicks"),
        Input("btn-export-both", "n_clicks"),
        Input("btn-reset-results", "n_clicks"),
        prevent_initial_call=True,
    )
    def handle_export_reset(rtds_clicks, ppcs_clicks, both_clicks, reset_clicks):
        triggered = ctx.triggered_id
        if not triggered:
            return dash.no_update, ""
        if triggered == "btn-reset-results":
            if get_simulation_state().get("status") == "running":
                return dash.no_update, "Cannot reset while simulation is running."
            logger.clear_all_data()
            set_simulation_state(status="idle", tick=0, total_ticks=config.TOTAL_TICKS, final_loss=None, total_switches=0)
            return dash.no_update, "All results cleared."
        algo_map = {"btn-export-rtds": "Threshold-Based ACS", "btn-export-ppcs": "Weighted Scoring ACS"}
        if triggered == "btn-export-both":
            original = logger.algorithm_name
            lines = ["algorithm,tick,timestamp_ms,avg_packet_loss,num_degraded_channels,num_degraded_devices"]
            for algo in ["Threshold-Based ACS", "Weighted Scoring ACS"]:
                logger.algorithm_name = algo
                for r in logger.get_recent_tick_metrics(limit=9999):
                    lines.append(f"{algo},{r[0]},{r[1]},{r[2]},{r[3]},{r[4]}")
            logger.algorithm_name = original
            return dcc.send_string("\n".join(lines), "simulation_results_both.csv"), "Exported combined RTDS and PPCS results."
        algo = algo_map.get(triggered)
        if not algo:
            return dash.no_update, ""
        original = logger.algorithm_name
        logger.algorithm_name = algo
        rows = logger.get_recent_tick_metrics(limit=9999)
        logger.algorithm_name = original
        if not rows:
            return dash.no_update, f"No data available for {algo}."
        lines = ["tick,timestamp_ms,avg_packet_loss,num_degraded_channels,num_degraded_devices"]
        for r in rows:
            lines.append(f"{r[0]},{r[1]},{r[2]},{r[3]},{r[4]}")
        safe_name = algo.lower().replace(" ", "_").replace("-", "")
        return dcc.send_string("\n".join(lines), f"simulation_{safe_name}.csv"), f"Exported {len(rows)} rows."
