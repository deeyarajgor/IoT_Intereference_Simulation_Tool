# dashboard/layouts.py

import config
from dash import html, dcc, dash_table

from .styles import COLORS, LAYOUT, CARD
from .components import (
    card,
    label,
    page_title,
    sidebar,
    status_badge,
    svg_icon,
    primary_button,
    outline_button,
)

SCENARIOS = {
    "normal": {
        "title": "Normal Operation",
        "subtitle": "Baseline run with no intentional interference.",
        "wifi": 0,
        "bt": 0,
        "accent": COLORS["green"],
        "badge": "CLEAN",
    },
    "wifi": {
        "title": "Wi-Fi Interference",
        "subtitle": "Broadband Wi-Fi congestion affecting nearby 2.4 GHz IoT channels.",
        "wifi": 1,
        "bt": 0,
        "accent": COLORS["red"],
        "badge": "WI-FI",
    },
    "bluetooth": {
        "title": "Bluetooth Interference",
        "subtitle": "Narrowband hopping interference that changes affected channels over time.",
        "wifi": 0,
        "bt": 2,
        "accent": "#8B5CF6",
        "badge": "BT",
    },
}


def num_input(input_id, value, min_value=0, max_value=999):
    return dcc.Input(
        id=input_id,
        type="number",
        value=value,
        min=min_value,
        max=max_value,
        style={
            "width": "100%",
            "padding": "13px 14px",
            "borderRadius": "12px",
            "border": f"1px solid {COLORS['border']}",
            "fontSize": "14px",
            "fontWeight": "700",
            "color": COLORS["text"],
            "boxSizing": "border-box",
            "background": "rgba(255,255,255,0.05)",
        },
    )


def field(label_text, control, helper=None):
    children = [label(label_text), control]
    if helper:
        children.append(html.Div(helper, style={"fontSize": "12px", "color": COLORS["muted"], "marginTop": "6px"}))
    return html.Div(children, style={"marginBottom": "18px"})


def page_shell(active_page, children):
    return html.Div(
        [
            sidebar(active_page),
            html.Div(
                children,
                style={
                    "marginLeft": LAYOUT["sidebar_width"],
                    "padding": LAYOUT["page_padding"],
                    "background": "radial-gradient(circle at top left, rgba(47,128,255,0.16), transparent 34%), radial-gradient(circle at top right, rgba(139,92,246,0.12), transparent 30%), #08111F",
                    "minHeight": "100vh",
                    "boxSizing": "border-box",
                },
            ),
        ],
        style={"fontFamily": LAYOUT["font"], "background": COLORS["background"], "minHeight": "100vh"},
    )


def scenario_card(key, title, subtitle, badge, accent):
    return html.Label(
        [
            dcc.RadioItems(
                id={"type": "scenario-radio", "index": key},
                options=[{"label": "", "value": key}],
                value=None,
                style={"display": "none"},
            ),
            html.Div(
                [
                    html.Div(badge, style={
                        "width": "52px", "height": "52px", "borderRadius": "16px",
                        "background": f"{accent}18", "border": f"1px solid {accent}55",
                        "color": accent, "display": "flex", "alignItems": "center", "justifyContent": "center",
                        "fontWeight": "900", "fontSize": "12px", "letterSpacing": "0.06em",
                    }),
                    html.Div([
                        html.Div(title, style={"fontSize": "15px", "fontWeight": "900", "color": COLORS["text"]}),
                        html.Div(subtitle, style={"fontSize": "12px", "lineHeight": "1.45", "color": COLORS["muted"], "marginTop": "4px"}),
                    ], style={"marginLeft": "14px"}),
                ],
                id=f"scenario-card-{key}",
                style={
                    "display": "flex", "alignItems": "center", "padding": "16px",
                    "borderRadius": "18px", "border": f"1px solid {COLORS['border']}",
                    "background": "rgba(255,255,255,0.05)", "cursor": "pointer", "height": "100%",
                },
            ),
        ],
        style={"display": "block"},
    )


def setup_page(state):
    return page_shell(
        "setup",
        [
            html.Div(
                [
                    page_title("Scenario Setup", "Choose a small, clear simulation scenario for the live demonstration."),
                    status_badge(state.get("status", "idle")),
                ],
                style={"display": "flex", "justifyContent": "space-between", "alignItems": "flex-start"},
            ),
            card(
                [
                    label("1. Select scenario"),
                    dcc.RadioItems(
                        id="s-scenario",
                        options=[
                            {"label": SCENARIOS["normal"]["title"], "value": "normal"},
                            {"label": SCENARIOS["wifi"]["title"], "value": "wifi"},
                            {"label": SCENARIOS["bluetooth"]["title"], "value": "bluetooth"},
                        ],
                        value="wifi",
                        labelStyle={"display": "inline-block", "marginRight": "28px", "fontWeight": "900", "fontSize": "17px", "color": "white"},
                        inputStyle={"marginRight": "9px"},
                        style={"marginBottom": "16px", "color": COLORS["text"]},
                    ),
                    html.Div(
                        [
                            html.Div(id="s-scenario-preview", style={"gridColumn": "1 / span 3"}),
                        ],
                        style={"display": "grid", "gridTemplateColumns": "1fr 1fr 1fr", "gap": "14px"},
                    ),
                    html.Hr(style={"border": "none", "borderTop": f"1px solid {COLORS['border']}", "margin": "24px 0"}),
                    html.Div(
                        [
                            field(
                                "ACS Algorithm",
                                dcc.Dropdown(
                                    id="s-algorithm",
                                    options=[
                                        {"label": "RTDS — Reactive Threshold Detection", "value": "threshold"},
                                        {"label": "PPCS — Weighted Channel Scoring", "value": "weighted"},
                                    ],
                                    value="threshold",
                                    clearable=False,
                                    style={"fontSize": "16px"},
                                ),
                                html.Div(id="s-algorithm-help", style={"fontSize": "14px", "lineHeight": "1.55", "color": COLORS["text"], "background": "rgba(47,128,255,0.10)", "border": f"1px solid {COLORS['primary']}45", "borderRadius": "14px", "padding": "12px 14px", "marginTop": "10px"}),
                            ),
                            field("Number of IoT Devices", num_input("s-num-devices", min(config.NUM_IOT_DEVICES, 8), 3, 8), "Keep this to 3–8 devices so the topology stays readable."),
                            field("Simulation Duration", num_input("s-duration", config.SIMULATION_DURATION_S, 10, 120), "Shorter runs are better for demonstration."),
                        ],
                        style={"display": "grid", "gridTemplateColumns": "1fr 1fr 1fr", "gap": "18px"},
                    ),
                    html.Div(id="s-ticks-hint", style={"fontSize": "12px", "color": COLORS["muted"], "marginTop": "-10px", "marginBottom": "18px"}),
                    html.Div(
                        [
                            html.Div(id="s-scenario-values", style={"fontSize": "13px", "color": COLORS["muted"], "lineHeight": "1.55"}),
                            primary_button("▶ Start Live Simulation", "s-run-btn"),
                        ],
                        style={"display": "grid", "gridTemplateColumns": "1.5fr 1fr", "gap": "18px", "alignItems": "center"},
                    ),
                    html.Div(id="s-feedback", style={"fontSize": "13px", "fontWeight": "800", "marginTop": "14px"}),
                ]
            ),
        ],
    )


def phase_pill(num, text, color):
    return html.Div([
        html.Span(num, style={"background": color, "color": "white", "borderRadius": "999px", "padding": "4px 8px", "fontSize": "11px", "fontWeight": "900", "marginRight": "8px"}),
        html.Span(text),
    ], style={"padding": "10px 13px", "borderRadius": "999px", "background": f"{color}12", "color": COLORS["text"], "fontWeight": "850", "fontSize": "13px"})


def phase_arrow():
    return html.Div("→", style={"fontSize": "18px", "fontWeight": "900", "color": COLORS["muted"]})


def progress_bar_block():
    return card(
        [
            html.Div(
                [
                    html.Div([label("Simulation progress"), html.Div(id="m-progress-text", style={"fontSize": "13px", "fontWeight": "850", "color": COLORS["text"]})]),
                    html.Div(id="m-progress-pct", style={"fontSize": "22px", "fontWeight": "950", "color": COLORS["primary"]}),
                ],
                style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "marginBottom": "12px"},
            ),
            html.Div(html.Div(id="m-progress-bar"), style={"height": "12px", "borderRadius": "999px", "background": "#E5E7EB", "overflow": "hidden"}),
        ],
        style={"padding": "16px 18px"},
    )


def kpi_box(title, value_id, subtitle, accent):
    return html.Div(
        [
            html.Div(title, style={"fontSize": "11px", "fontWeight": "900", "letterSpacing": "0.06em", "textTransform": "uppercase", "color": COLORS["muted"]}),
            html.Div(id=value_id, children="—", style={"fontSize": "25px", "fontWeight": "950", "color": COLORS["text"], "marginTop": "8px"}),
            html.Div(subtitle, style={"fontSize": "12px", "color": COLORS["muted"], "marginTop": "4px"}),
        ],
        style={"padding": "16px", "borderRadius": "18px", "background": f"linear-gradient(135deg, {accent}25, rgba(255,255,255,0.03))", "border": f"1px solid {accent}55", "boxShadow": f"inset 0 0 30px {accent}10"},
    )


def monitor_page(state):
    return page_shell(
        "monitor",
        [
            html.Div(
                [
                    page_title("2.4 GHz IoT Interference Simulation", "Visual live view: interferer → affected channels → degraded devices → ACS recovery."),
                    html.Div([html.Div(id="mon-status-badge", children=status_badge(state.get("status", "idle"))), html.Div(id="mon-timer", style={"fontSize": "13px", "fontWeight": "850", "color": COLORS["muted"], "marginLeft": "12px"})], style={"display": "flex", "alignItems": "center"}),
                ],
                style={"display": "flex", "justifyContent": "space-between", "alignItems": "flex-start"},
            ),
            html.Div(
                [
                    progress_bar_block(),
                    card([label("Current phase"), html.Div(id="m-phase", style={"fontSize": "18px", "fontWeight": "950", "color": COLORS["text"]}), html.Div(id="m-scenario-summary", style={"fontSize": "12px", "color": COLORS["muted"], "marginTop": "6px", "lineHeight": "1.5"})], style={"padding": "16px 18px"}),
                ],
                style={"display": "grid", "gridTemplateColumns": "2fr 1fr", "gap": "16px", "marginBottom": "16px"},
            ),
            html.Div(
                [
                    card([label("Scenario topology"), html.Div(id="m-topology")], style={"minHeight": "420px"}),
                    card([label("2.4 GHz channel spectrum"), dcc.Graph(id="g-spectrum", config={"displayModeBar": False}, style={"height": "360px"}), html.Div(id="m-spectrum-legend", style={"fontSize": "12px", "color": COLORS["muted"], "marginTop": "4px"})], style={"minHeight": "420px"}),
                    card([
                        label("Live KPIs"),
                        html.Div([
                            kpi_box("Packet loss", "m-loss", "Current network average", COLORS["red"]),
                            kpi_box("SINR", "m-sinr", "Average channel quality", COLORS["primary"]),
                            kpi_box("Healthy devices", "m-healthy", "Recovered/normal nodes", COLORS["green"]),
                            kpi_box("Switch events", "m-switches", "ACS channel moves", COLORS["orange"]),
                        ], style={"display": "grid", "gap": "12px"}),
                    ], style={"minHeight": "420px"}),
                ],
                style={"display": "grid", "gridTemplateColumns": "1.05fr 1.55fr 0.9fr", "gap": "16px", "marginBottom": "16px"},
            ),
            html.Div(
                [
                    card([label("Simulation timeline"), html.Div(id="m-timeline")]),
                    card([
                        label("Live IoT device impact"),
                        html.Div("Each card represents one simulated IoT device. Red means it is currently affected by interference; blue means ACS has switched/recovered it.", style={"fontSize": "14px", "lineHeight": "1.5", "color": COLORS["muted"], "marginBottom": "12px"}),
                        html.Div(id="m-device-impact"),
                    ]),
                    card([label("Event log"), html.Div(id="m-event-log")]),
                ],
                style={"display": "grid", "gridTemplateColumns": "0.9fr 1.45fr 1fr", "gap": "16px", "marginBottom": "16px"},
            ),
            card(
                [
                    label("Detailed channel table"),
                    dash_table.DataTable(
                        id="t-channels",
                        columns=[
                            {"name": "Channel", "id": "channel"},
                            {"name": "SINR", "id": "sinr"},
                            {"name": "Loss", "id": "loss"},
                            {"name": "Interfered", "id": "interfered"},
                            {"name": "Active", "id": "active"},
                        ],
                        data=[],
                        page_size=16,
                        style_table={"overflowX": "auto"},
                        style_cell={"fontFamily": LAYOUT["font"], "fontSize": "12px", "padding": "9px", "textAlign": "center", "backgroundColor":"#101C2B", "color": COLORS["text"], "border":"1px solid rgba(148,163,184,0.18)"},
                        style_header={"backgroundColor": "#0B1627", "fontWeight": "900", "color": COLORS["text"], "border":"1px solid rgba(148,163,184,0.22)"},
                        style_data_conditional=[
                            {"if": {"filter_query": "{interfered} = Yes"}, "backgroundColor": "rgba(255,77,90,0.16)", "color": "#FFD0D3"},
                            {"if": {"filter_query": "{active} = Yes"}, "backgroundColor": "rgba(49,211,125,0.16)", "fontWeight": "800", "color":"#B9F8D3"},
                        ],
                    ),
                ]
            ),
        ],
    )


def results_page(state):
    return page_shell(
        "results",
        [
            html.Div(
                [
                    page_title("Results & Performance Analysis", "Overall summary after the simulation completes."),
                    status_badge(state.get("status", "idle")),
                ],
                style={"display": "flex", "justifyContent": "space-between", "alignItems": "flex-start"},
            ),
            html.Div(
                [
                    algorithm_summary_card("RTDS — Reactive Threshold", "r-rtds-stats", COLORS["primary"], "Fast reaction: switches when SINR goes below the threshold and chooses the cleanest channel."),
                    algorithm_summary_card("PPCS — Weighted Scoring", "r-ppcs-stats", COLORS["green"], "More selective: scores channels using SINR, stability, and device crowding before switching."),
                ],
                style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "18px", "marginBottom": "18px"},
            ),
            html.Div(
                [
                    card([label("Packet loss comparison"), html.Div("Lower lines are better. The dashed 5% line is the project target for acceptable packet loss after mitigation.", style={"fontSize": "14px", "color": COLORS["muted"], "marginBottom": "8px"}), dcc.Graph(id="r-comparison", config={"displayModeBar": False}, style={"height": "330px"})]),
                    card([label("Cumulative channel switches"), html.Div("A switch means ACS moved a device to another channel. Too many switches may indicate instability or over-reaction.", style={"fontSize": "14px", "color": COLORS["muted"], "marginBottom": "8px"}), dcc.Graph(id="r-switches", config={"displayModeBar": False}, style={"height": "330px"})]),
                ],
                style={"display": "grid", "gridTemplateColumns": "1.25fr 1fr", "gap": "18px", "marginBottom": "18px"},
            ),
            card(
                [
                    label("Export & Reset"),
                    html.Div(
                        [
                            outline_button("Export RTDS CSV", "btn-export-rtds", COLORS["primary"]),
                            outline_button("Export PPCS CSV", "btn-export-ppcs", COLORS["green"]),
                            outline_button("Export Both", "btn-export-both", COLORS["orange"]),
                            outline_button("Reset Results", "btn-reset-results", COLORS["red"]),
                            dcc.Download(id="download-csv"),
                        ],
                        style={"display": "flex", "gap": "12px", "flexWrap": "wrap", "marginTop": "12px"},
                    ),
                    html.Div(id="r-export-msg", style={"fontSize": "13px", "fontWeight": "800", "color": COLORS["muted"], "marginTop": "14px"}),
                ]
            ),
        ],
    )


def algorithm_summary_card(title, stats_id, color, description):
    return card(
        [
            html.Div(
                [
                    html.Div(style={"width": "10px", "height": "48px", "borderRadius": "999px", "background": color, "marginRight": "14px"}),
                    html.Div([html.H3(title, style={"fontSize": "20px", "fontWeight": "950", "margin": 0, "color": COLORS["text"]}), html.Div(description, style={"fontSize": "14px", "lineHeight": "1.5", "color": COLORS["muted"], "marginTop": "6px"})]),
                ],
                style={"display": "flex", "alignItems": "center", "marginBottom": "18px"},
            ),
            html.Div(id=stats_id),
        ]
    )
