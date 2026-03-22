COLOR_SURFACE = "#C0C0C0"
COLOR_BORDER_LIGHT = "#FFFFFF"
COLOR_BORDER_DARK = "#808080"
COLOR_PANEL = "#DFDFDF"


def build_button_style() -> str:
    return f"""
    QToolButton {{
        background: {COLOR_SURFACE};
        border-top: 1px solid {COLOR_BORDER_LIGHT};
        border-left: 1px solid {COLOR_BORDER_LIGHT};
        border-right: 1px solid {COLOR_BORDER_DARK};
        border-bottom: 1px solid {COLOR_BORDER_DARK};
        padding: 0px;
        color: #000;
    }}
    QToolButton:pressed, QToolButton:checked {{
        background: {COLOR_SURFACE};
        border-top: 1px solid {COLOR_BORDER_DARK};
        border-left: 1px solid {COLOR_BORDER_DARK};
        border-right: 1px solid {COLOR_BORDER_LIGHT};
        border-bottom: 1px solid {COLOR_BORDER_LIGHT};
        color: #000;
    }}
    """


def build_slider_style() -> str:
    return f"""
    QSlider {{
        padding-left: 0px;
        padding-right: 0px;
    }}
    QSlider::groove:horizontal {{
        height: 12px;
        background: {COLOR_PANEL};
        border-top: 1px solid {COLOR_BORDER_DARK};
        border-left: 1px solid {COLOR_BORDER_DARK};
        border-right: 1px solid {COLOR_BORDER_LIGHT};
        border-bottom: 1px solid {COLOR_BORDER_LIGHT};
        margin: 0px;
    }}
    QSlider::handle:horizontal {{
        width: 16px;
        margin: 0px;
        background: {COLOR_SURFACE};
        border-top: 1px solid {COLOR_BORDER_LIGHT};
        border-left: 1px solid {COLOR_BORDER_LIGHT};
        border-right: 1px solid {COLOR_BORDER_DARK};
        border-bottom: 1px solid {COLOR_BORDER_DARK};
    }}
    QSlider::sub-page:horizontal {{
        background: {COLOR_PANEL};
    }}
    QSlider::add-page:horizontal {{
        background: {COLOR_PANEL};
    }}
    QSlider::tick-mark:horizontal {{
        width: 1px;
        height: 6px;
        background: {COLOR_BORDER_DARK};
        margin-top: 12px;
    }}
    """
