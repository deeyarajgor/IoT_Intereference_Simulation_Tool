# dashboard/components.py

from dash import html, dcc

try:
    from dash_iconify import DashIconify
except Exception:
    DashIconify = None

from .styles import COLORS, CARD, SMALL_CARD, LAYOUT, BUTTON_GREEN, BUTTON_OUTLINE, BUTTON_PRIMARY


def svg_icon(name, color=None, size=24):
    """Render professional Tabler icons using dash-iconify.

    Install once: pip install dash-iconify
    """
    color = color or COLORS["primary"]
    icon_map = {
        "wifi": "tabler:wifi",
        "bluetooth": "tabler:bluetooth",
        "router": "tabler:router",
        "camera": "tabler:camera",
        "temp": "tabler:temperature",
        "bulb": "tabler:bulb",
        "door": "tabler:door",
        "lock": "tabler:lock",
        "hub": "tabler:server",
        "plug": "tabler:plug",
        "motion": "tabler:radar",
        "warning": "tabler:alert-triangle",
        "signal": "tabler:activity",
        "database": "tabler:database",
        "download": "tabler:download",
        "switch": "tabler:arrows-exchange",
        "healthy": "tabler:circle-check",
        "degraded": "tabler:alert-circle",
    }
    if DashIconify is not None:
        return DashIconify(
            icon=icon_map.get(name, "tabler:activity"),
            width=size,
            height=size,
            color=color,
            style={"display": "block"},
        )

    # Fallback so the dashboard does not crash if dash-iconify is not installed yet.
    fallback = {
            "wifi": "Wi-Fi", "bluetooth": "BT", "router": "Router",
            "camera": "Cam", "temp": "Temp", "bulb": "Bulb",
            "door": "Door", "lock": "Lock", "hub": "Hub",
            "plug": "Plug", "motion": "Motion", "database": "DB",
            "signal": "Sim", "warning": "!",
        }.get(name, "•")
    return html.Span(fallback, style={"fontSize": f"{max(10, size//2)}px", "fontWeight": "900", "color": color})


def card(children, style=None):
    base = CARD.copy()
    if style:
        base.update(style)
    return html.Div(children, style=base)


def small_card(children, style=None):
    base = SMALL_CARD.copy()
    if style:
        base.update(style)
    return html.Div(children, style=base)


def label(text):
    return html.Div(
        text,
        style={
            "fontSize": "13px",
            "fontWeight": "850",
            "letterSpacing": "0.08em",
            "textTransform": "uppercase",
            "color": COLORS["muted"],
            "marginBottom": "8px",
        },
    )


def page_title(title, subtitle=None):
    return html.Div(
        [
            html.H1(
                title,
                style={
                    "margin": 0,
                    "fontSize": "32px",
                    "fontWeight": "900",
                    "color": COLORS["text"],
                },
            ),
            html.P(
                subtitle or "",
                style={
                    "margin": "6px 0 0",
                    "fontSize": "17px",
                    "lineHeight": "1.45",
                    "color": COLORS["muted"],
                },
            ),
        ],
        style={"marginBottom": "24px"},
    )


def sidebar(active="setup"):
    pages = [
        ("setup", "signal", "Simulation Setup"),
        ("monitor", "wifi", "Live Monitoring"),
        ("results", "database", "Results"),
    ]

    def nav_item(page, icon, title):
        is_active = active == page
        return dcc.Link(
            [
                html.Span(svg_icon(icon, "white" if is_active else COLORS["sidebar_text"], 18), style={"marginRight": "10px", "display":"flex"}),
                html.Span(title),
            ],
            href=f"/{page}",
            style={
                "display": "flex",
                "alignItems": "center",
                "padding": "13px 16px",
                "borderRadius": "14px",
                "marginBottom": "8px",
                "textDecoration": "none",
                "fontSize": "16px",
                "fontWeight": "800" if is_active else "500",
                "background": COLORS["primary"] if is_active else "transparent",
                "color": "white" if is_active else COLORS["sidebar_text"],
            },
        )

    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        svg_icon("wifi", "white", 24),
                        style={
                            "width": "42px",
                            "height": "42px",
                            "borderRadius": "14px",
                            "background": "linear-gradient(135deg, #2F80FF, #06B6D4)",
                            "display": "flex",
                            "alignItems": "center",
                            "justifyContent": "center",
                            "boxShadow": "0 12px 28px rgba(47,128,255,0.28)",
                        },
                    ),
                    html.Div(
                        [
                            html.Div(
                                "IoT Interference",
                                style={
                                    "fontSize": "15px",
                                    "fontWeight": "800",
                                    "color": "white",
                                },
                            ),
                            html.Div(
                                "Simulation Tool",
                                style={
                                    "fontSize": "12px",
                                    "color": COLORS["sidebar_text"],
                                },
                            ),
                        ],
                        style={"marginLeft": "12px"},
                    ),
                ],
                style={
                    "display": "flex",
                    "alignItems": "center",
                    "padding": "24px 18px 30px",
                },
            ),
            html.Div(
                [nav_item(page, icon, title) for page, icon, title in pages],
                style={"padding": "0 14px"},
            ),
            html.Div(
                [
                    html.Div(
                        "Research Focus",
                        style={
                            "fontSize": "11px",
                            "fontWeight": "800",
                            "letterSpacing": "0.08em",
                            "textTransform": "uppercase",
                            "color": COLORS["muted"],
                            "marginBottom": "8px",
                        },
                    ),
                    html.Div(
                        "2.4 GHz IoT interference detection and adaptive channel selection.",
                        style={
                            "fontSize": "12px",
                            "lineHeight": "1.5",
                            "color": COLORS["sidebar_text"],
                        },
                    ),
                ],
                style={
                    "position": "absolute",
                    "bottom": "22px",
                    "left": "18px",
                    "right": "18px",
                    "padding": "16px",
                    "borderRadius": "16px",
                    "background": "rgba(255,255,255,0.06)",
                },
            ),
        ],
        style={
            "width": LAYOUT["sidebar_width"],
            "minWidth": LAYOUT["sidebar_width"],
            "height": "100vh",
            "position": "fixed",
            "top": 0,
            "left": 0,
            "background": COLORS["sidebar"],
            "zIndex": 100,
        },
    )


def status_badge(status):
    status = status or "idle"

    color = {
        "running": COLORS["green"],
        "completed": COLORS["primary"],
        "error": COLORS["red"],
        "idle": COLORS["orange"],
    }.get(status, COLORS["muted"])

    label_text = {
        "running": "Running",
        "completed": "Completed",
        "error": "Error",
        "idle": "Idle",
    }.get(status, status.title())

    return html.Div(
        [
            html.Span(
                "●",
                style={"color": color, "fontSize": "14px", "marginRight": "8px"},
            ),
            html.Span(label_text),
        ],
        style={
            "display": "inline-flex",
            "alignItems": "center",
            "padding": "8px 12px",
            "borderRadius": "999px",
            "background": "rgba(255,255,255,0.06)",
            "border": f"1px solid {COLORS['border']}",
            "fontSize": "15px",
            "fontWeight": "850",
            "color": COLORS["text"],
        },
    )


def kpi_card(title, value_id, subtitle, icon):
    return small_card(
        [
            html.Div(
                [
                    html.Div(
                        icon,
                        style={
                            "width": "38px",
                            "height": "38px",
                            "borderRadius": "12px",
                            "background": "#EFF6FF",
                            "display": "flex",
                            "alignItems": "center",
                            "justifyContent": "center",
                            "fontSize": "18px",
                        },
                    ),
                    html.Div(label(title), style={"marginLeft": "12px"}),
                ],
                style={"display": "flex", "alignItems": "center"},
            ),
            html.Div(
                id=value_id,
                style={
                    "fontSize": "30px",
                    "fontWeight": "850",
                    "color": COLORS["text"],
                    "marginTop": "14px",
                },
            ),
            html.Div(
                subtitle,
                style={
                    "fontSize": "12px",
                    "color": COLORS["muted"],
                    "marginTop": "4px",
                },
            ),
        ],
        style={"flex": "1", "minWidth": "180px"},
    )


def progress_card():
    return card(
        [
            html.Div(
                [
                    html.Div(
                        [
                            label("Simulation Progress"),
                            html.Div(
                                id="m-progress-text",
                                style={
                                    "fontSize": "15px",
                                    "fontWeight": "800",
                                    "color": COLORS["text"],
                                },
                            ),
                        ]
                    ),
                    html.Div(id="m-progress-pct", style={"fontSize": "22px", "fontWeight": "850"}),
                ],
                style={
                    "display": "flex",
                    "justifyContent": "space-between",
                    "alignItems": "center",
                    "marginBottom": "14px",
                },
            ),
            html.Div(
                [
                    html.Div(
                        id="m-progress-bar",
                        style={
                            "height": "100%",
                            "width": "0%",
                            "background": COLORS["primary"],
                            "borderRadius": "999px",
                        },
                    )
                ],
                style={
                    "height": "12px",
                    "background": "#E2E8F0",
                    "borderRadius": "999px",
                    "overflow": "hidden",
                },
            ),
        ]
    )


def primary_button(text, btn_id):
    return html.Button(text, id=btn_id, style=BUTTON_PRIMARY)


def outline_button(text, btn_id, color=None):
    style = BUTTON_OUTLINE.copy()
    if color:
        style["color"] = color
        style["border"] = f"1px solid {color}"
    return html.Button(text, id=btn_id, style=style)