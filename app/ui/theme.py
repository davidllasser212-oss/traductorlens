APP_NAME = "TraductorLens"
VERSION = "1.1.0"

# tokens de color (dark theme, estilo Windows 11 oscuro)
BG_PANEL = "#202020"
BG_HEADER = "#262626"
BG_HOVER = "#2F2F2F"
BG_TITLE = "#2A2A2A"
ACCENT = "#00E5A0"
ACCENT_DIM = "#0FA57A"
TEXT_PRIMARY = "#F2F2F2"
TEXT_SECONDARY = "#A0A0A0"
BORDER = "#00E5A0"
BORDER_SOFT = "#3A3A3A"
ERROR = "#C42B1C"
AMBER = "#FFB84D"
BLUE = "#4DA3FF"
SHADOW_COLOR = "rgba(0, 0, 0, 160)"

# fuentes
FONT_UI = "Segoe UI Variable"
FONT_MONO = "Cascadia Code"

RADIUS = 10
TITLE_H = 36
HEADER_H = 44
SHADOW_MARGIN = 14
BORDER_W = 2
MIN_W = 360
MIN_H = 220
LENS_PAD = 10          # margen entre el borde del lente y el hueco transparente
LENS_CORNER = 6        # radio de las esquinas del hueco del lente

QSS = f"""
QWidget {{
    font-family: "{FONT_UI}";
    color: {TEXT_PRIMARY};
    font-size: 12px;
}}

#TitleBar {{
    background-color: {BG_TITLE};
    border-top-left-radius: {RADIUS}px;
    border-top-right-radius: {RADIUS}px;
}}

#TitleLabel {{
    color: {TEXT_PRIMARY};
    font-size: 12px;
    font-weight: 500;
}}

#HeaderBar {{
    background-color: {BG_HEADER};
}}

QPushButton#MinButton, QPushButton#CloseButton {{
    background-color: transparent;
    color: {TEXT_SECONDARY};
    border: none;
    border-radius: 6px;
    padding: 0 12px;
    font-size: 14px;
    min-height: 26px;
}}
QPushButton#MinButton:hover {{
    background-color: {BG_HOVER};
    color: {TEXT_PRIMARY};
}}
QPushButton#CloseButton:hover {{
    background-color: {ERROR};
    color: white;
}}

#TranslatePanel {{
    background-color: {BG_PANEL};
    border-bottom-left-radius: {RADIUS}px;
    border-bottom-right-radius: {RADIUS}px;
}}

QComboBox {{
    background-color: {BG_HOVER};
    color: {TEXT_PRIMARY};
    border: 1px solid {BG_HOVER};
    border-radius: 6px;
    padding: 4px 8px;
    min-width: 120px;
}}
QComboBox:hover {{
    border: 1px solid {ACCENT_DIM};
}}
QComboBox::drop-down {{
    border: none;
    width: 18px;
}}
QComboBox QAbstractItemView {{
    background-color: {BG_HEADER};
    color: {TEXT_PRIMARY};
    selection-background-color: {ACCENT_DIM};
    border: 1px solid {ACCENT_DIM};
    border-radius: 4px;
}}

QPushButton {{
    background-color: transparent;
    color: {TEXT_SECONDARY};
    border: none;
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 13px;
}}
QPushButton:hover {{
    background-color: {BG_HOVER};
    color: {TEXT_PRIMARY};
}}
QPushButton#SwapButton {{
    color: {ACCENT};
    font-weight: bold;
    font-size: 16px;
    padding: 2px 8px;
}}

QScrollArea {{
    background: transparent;
    border: none;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
}}
QScrollBar::handle:vertical {{
    background: {BG_HOVER};
    border-radius: 4px;
    min-height: 24px;
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    height: 0;
}}
"""
