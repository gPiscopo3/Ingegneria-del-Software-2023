from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication

DARK = {
    "bg": "#0F1117",
    "surface": "#171A23",
    "surface_alt": "#1F2330",
    "border": "#2A2F3D",
    "text": "#E6E8EE",
    "text_muted": "#8B91A1",
    "accent": "#6366F1",
    "accent_hover": "#7C7FF5",
    "accent_pressed": "#4F52D9",
    "success": "#22C55E",
    "danger": "#EF4444",
}

LIGHT = {
    "bg": "#F4F5F9",
    "surface": "#FFFFFF",
    "surface_alt": "#EEF0F5",
    "border": "#DADDE6",
    "text": "#1A1D26",
    "text_muted": "#646B7D",
    "accent": "#4F46E5",
    "accent_hover": "#6366F1",
    "accent_pressed": "#4338CA",
    "success": "#16A34A",
    "danger": "#DC2626",
}


def palette(dark: bool):
    return DARK if dark else LIGHT


def build_stylesheet(p: dict) -> str:
    return f"""
    QWidget {{
        color: {p['text']};
        font-family: "Segoe UI", "Inter", "Helvetica Neue", Arial, sans-serif;
        font-size: 10pt;
    }}
    QMainWindow, QWidget#central, QWidget#content {{
        background: {p['bg']};
    }}
    QFrame#sidebar {{
        background: {p['surface']};
        border-right: 1px solid {p['border']};
    }}
    QScrollArea, QScrollArea > QWidget > QWidget {{
        background: transparent;
        border: none;
    }}
    QFrame#card {{
        background: {p['surface_alt']};
        border: 1px solid {p['border']};
        border-radius: 12px;
    }}
    QFrame#graphCard {{
        background: {p['surface']};
        border: 1px solid {p['border']};
        border-radius: 14px;
    }}
    QLabel {{
        background: transparent;
    }}
    QLabel#title {{
        font-size: 18pt;
        font-weight: 700;
    }}
    QLabel#subtitle, QLabel#hint {{
        color: {p['text_muted']};
    }}
    QLabel#hint {{
        font-size: 9pt;
    }}
    QLabel#section {{
        color: {p['text_muted']};
        font-size: 8pt;
        font-weight: 700;
        letter-spacing: 1px;
    }}
    QLabel#graphTitle {{
        font-size: 14pt;
        font-weight: 600;
    }}
    QLabel#chip {{
        background: {p['surface_alt']};
        border: 1px solid {p['border']};
        border-radius: 10px;
        padding: 3px 10px;
        color: {p['text_muted']};
    }}
    QLabel#badge {{
        border-radius: 8px;
        padding: 4px 8px;
        font-size: 9pt;
        background: {p['surface']};
        color: {p['text_muted']};
        border: 1px solid {p['border']};
    }}
    QLabel#badge[state="ok"] {{
        color: {p['success']};
        border-color: {p['success']};
    }}
    QLabel#badge[state="error"] {{
        color: {p['danger']};
        border-color: {p['danger']};
    }}
    QLabel#emptyIcon {{
        font-size: 42pt;
        color: {p['accent']};
    }}
    QLabel#emptyTitle {{
        font-size: 14pt;
        font-weight: 600;
    }}
    QLineEdit, QComboBox, QDateEdit {{
        background: {p['surface']};
        border: 1px solid {p['border']};
        border-radius: 8px;
        padding: 7px 10px;
        selection-background-color: {p['accent']};
        selection-color: #FFFFFF;
    }}
    QLineEdit:focus, QComboBox:focus, QDateEdit:focus {{
        border: 1px solid {p['accent']};
    }}
    QComboBox::drop-down, QDateEdit::drop-down {{
        border: none;
        width: 24px;
    }}
    QComboBox QAbstractItemView {{
        background: {p['surface']};
        border: 1px solid {p['border']};
        selection-background-color: {p['accent']};
        selection-color: #FFFFFF;
        outline: none;
    }}
    QCalendarWidget QWidget {{
        background: {p['surface']};
        alternate-background-color: {p['surface_alt']};
    }}
    QCalendarWidget QToolButton {{
        background: transparent;
        color: {p['text']};
        padding: 4px 8px;
        border-radius: 6px;
    }}
    QCalendarWidget QToolButton:hover {{
        background: {p['surface_alt']};
    }}
    QCalendarWidget QAbstractItemView:enabled {{
        selection-background-color: {p['accent']};
        selection-color: #FFFFFF;
    }}
    QPushButton {{
        background: {p['surface']};
        border: 1px solid {p['border']};
        border-radius: 8px;
        padding: 7px 14px;
    }}
    QPushButton:hover {{
        border-color: {p['accent']};
    }}
    QPushButton#primary {{
        background: {p['accent']};
        border: none;
        color: #FFFFFF;
        font-weight: 600;
        padding: 11px 14px;
    }}
    QPushButton#primary:hover {{
        background: {p['accent_hover']};
    }}
    QPushButton#primary:pressed {{
        background: {p['accent_pressed']};
    }}
    QPushButton#primary:disabled {{
        background: {p['border']};
        color: {p['text_muted']};
    }}
    QPushButton#ghost {{
        background: transparent;
        border: 1px solid {p['border']};
    }}
    QStatusBar {{
        background: {p['surface']};
        border-top: 1px solid {p['border']};
        color: {p['text_muted']};
    }}
    QToolTip {{
        background: {p['surface_alt']};
        color: {p['text']};
        border: 1px solid {p['border']};
        padding: 4px;
    }}
    QToolBar {{
        background: transparent;
        border: none;
    }}
    QToolBar QToolButton {{
        background: transparent;
        border-radius: 6px;
        padding: 3px;
    }}
    QToolBar QToolButton:hover, QToolBar QToolButton:checked {{
        background: {p['surface_alt']};
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
    }}
    QScrollBar::handle:vertical {{
        background: {p['border']};
        border-radius: 4px;
    }}
    QScrollBar::add-line, QScrollBar::sub-line {{
        height: 0;
    }}
    """


def build_qpalette(p: dict) -> QPalette:
    # la palette Qt serve anche a matplotlib per scegliere il colore delle icone della toolbar
    qp = QPalette()
    roles = {
        QPalette.ColorRole.Window: p["surface"],
        QPalette.ColorRole.WindowText: p["text"],
        QPalette.ColorRole.Base: p["surface"],
        QPalette.ColorRole.AlternateBase: p["surface_alt"],
        QPalette.ColorRole.Text: p["text"],
        QPalette.ColorRole.Button: p["surface"],
        QPalette.ColorRole.ButtonText: p["text"],
        QPalette.ColorRole.ToolTipBase: p["surface_alt"],
        QPalette.ColorRole.ToolTipText: p["text"],
        QPalette.ColorRole.PlaceholderText: p["text_muted"],
        QPalette.ColorRole.Highlight: p["accent"],
        QPalette.ColorRole.HighlightedText: "#FFFFFF",
        QPalette.ColorRole.Link: p["accent"],
    }
    for role, color in roles.items():
        qp.setColor(role, QColor(color))
    return qp


def apply_theme(app: QApplication, dark: bool):
    app.setStyle("Fusion")
    app.setPalette(build_qpalette(palette(dark)))
    app.setStyleSheet(build_stylesheet(palette(dark)))


def matplotlib_colors(dark: bool):
    p = palette(dark)
    return {
        "background": p["surface"],
        "text": p["text"],
        "node": p["accent"],
        "node_border": p["surface"],
        "edge": "#5B6275" if dark else "#A3A9B8",
        "label_bg": p["surface_alt"],
        "collaborations": "#3B82F6",
        "communications": "#EF4444",
        "composite": "#A855F7",
    }
