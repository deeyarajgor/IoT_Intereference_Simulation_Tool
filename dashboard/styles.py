# dashboard/styles.py

COLORS = {
    "sidebar": "#07111F",
    "sidebar_text": "#A8B4C7",
    "background": "#08111F",
    "card": "#101C2B",
    "card_2": "#132235",
    "primary": "#2F80FF",
    "green": "#31D37D",
    "orange": "#FFB020",
    "red": "#FF4D5A",
    "purple": "#8B5CF6",
    "cyan": "#2DD4BF",
    "text": "#F8FAFC",
    "muted": "#9CAEC8",
    "border": "rgba(148, 163, 184, 0.22)",
}

LAYOUT = {
    "sidebar_width": "270px",
    "page_padding": "28px 34px",
    "font": "'Inter', 'Segoe UI', Arial, sans-serif",
}

CARD = {
    "background": "linear-gradient(180deg, rgba(18,32,49,0.97), rgba(13,25,40,0.97))",
    "borderRadius": "18px",
    "padding": "24px",
    "boxShadow": "0 18px 45px rgba(0, 0, 0, 0.28)",
    "border": f"1px solid {COLORS['border']}",
}

SMALL_CARD = {
    **CARD,
    "padding": "16px",
}

BUTTON_PRIMARY = {
    "background": "linear-gradient(135deg, #2F80FF, #1D4ED8)",
    "color": "white",
    "border": "1px solid rgba(255,255,255,0.12)",
    "borderRadius": "12px",
    "padding": "13px 18px",
    "fontSize": "16px",
    "fontWeight": "850",
    "cursor": "pointer",
    "width": "100%",
    "boxShadow": "0 10px 26px rgba(47,128,255,0.28)",
}

BUTTON_GREEN = {
    **BUTTON_PRIMARY,
    "background": "linear-gradient(135deg, #31D37D, #16A34A)",
}

BUTTON_OUTLINE = {
    "background": "rgba(255,255,255,0.03)",
    "color": COLORS["primary"],
    "border": f"1px solid {COLORS['primary']}",
    "borderRadius": "12px",
    "padding": "10px 16px",
    "fontSize": "15px",
    "fontWeight": "800",
    "cursor": "pointer",
}
