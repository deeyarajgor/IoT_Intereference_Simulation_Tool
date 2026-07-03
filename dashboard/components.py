# dashboard/components.py

from dash import html, dcc
from .styles import COLORS, CARD, SMALL_CARD, LAYOUT, BUTTON_GREEN, BUTTON_OUTLINE, BUTTON_PRIMARY


def svg_icon(name, color=None, size=24):
    """Small inline SVG icons as data-uri images.

    Dash's html module does not expose SVG child elements such as Path/Circle,
    so we render the SVG as an <img> data URI instead. This keeps the dashboard
    dependency-free and avoids emoji-style icons.
    """
    from urllib.parse import quote

    color = color or COLORS["primary"]
    stroke = color.replace("#", "%23")
    icons = {
        "wifi": '<path d="M5 13a10 10 0 0 1 14 0"/><path d="M8.5 16.5a5 5 0 0 1 7 0"/><path d="M12 20h.01"/>',
        "bluetooth": '<path d="M7 7l10 10-5 5V2l5 5L7 17"/>',
        "router": '<rect x="4" y="11" width="16" height="7" rx="2"/><path d="M8 11V7"/><path d="M16 11V7"/><path d="M9 15h.01"/><path d="M13 15h2"/>',
        "camera": '<rect x="3" y="7" width="18" height="12" rx="2"/><circle cx="12" cy="13" r="3"/><path d="M8 7l1.5-2h5L16 7"/>',
        "temp": '<path d="M14 14.76V5a4 4 0 1 0-8 0v9.76a6 6 0 1 0 8 0z"/><path d="M10 9v7"/>',
        "bulb": '<path d="M9 18h6"/><path d="M10 22h4"/><path d="M8 14a6 6 0 1 1 8 0c-1 1-1.5 2-1.5 3h-5C9.5 16 9 15 8 14z"/>',
        "door": '<path d="M6 21V3h12v18"/><path d="M10 12h.01"/>',
        "lock": '<rect x="5" y="10" width="14" height="10" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>',
        "hub": '<circle cx="12" cy="12" r="3"/><circle cx="5" cy="5" r="2"/><circle cx="19" cy="5" r="2"/><circle cx="5" cy="19" r="2"/><circle cx="19" cy="19" r="2"/><path d="M7 7l3 3"/><path d="M17 7l-3 3"/><path d="M7 17l3-3"/><path d="M17 17l-3-3"/>',
        "plug": '<path d="M8 2v6"/><path d="M16 2v6"/><path d="M7 8h10v4a5 5 0 0 1-10 0V8z"/><path d="M12 17v5"/>',
        "motion": '<path d="M5 12a7 7 0 0 1 14 0"/><path d="M8 12a4 4 0 0 1 8 0"/><path d="M12 12h.01"/><path d="M4 20l16-16"/>',
        "warning": '<path d="M10.3 3.9L1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
        "signal": '<path d="M2 20h3"/><path d="M8 20h3V10H8z"/><path d="M14 20h3V6h-3z"/><path d="M20 20h2V3h-2z"/>',
        "database": '<path d="M4 6c0-2 16-2 16 0s-16 2-16 0"/><path d="M4 6v12c0 2 16 2 16 0V6"/><path d="M4 12c0 2 16 2 16 0"/>',
    }
    body = icons.get(name, icons["signal"])
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{stroke}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{body}</svg>'
    return html.Img(src="data:image/svg+xml," + quote(svg), style={"width": f"{size}px", "height": f"{size}px", "display": "block"})


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