from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QStackedWidget,
    QSizePolicy,
    QSlider,
    QStatusBar,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .styles import (
    COLOR_BORDER_DARK,
    COLOR_BORDER_LIGHT,
    COLOR_SURFACE,
    build_button_style,
    build_slider_style,
)
from .widgets import TickBar, Win98TitleBar


def apply_main_window_style(owner):
    owner.setStyleSheet(
        f"""
        QMainWindow {{
            background: {COLOR_SURFACE};
        }}
        QToolBar#ToolBar {{
            background: {COLOR_SURFACE};
            border-top: 1px solid {COLOR_BORDER_LIGHT};
            border-left: 1px solid {COLOR_BORDER_LIGHT};
            border-right: 1px solid {COLOR_BORDER_DARK};
            border-bottom: 1px solid {COLOR_BORDER_DARK};
            spacing: 0px;
            padding: 0px;
        }}
        QWidget#TitleBar {{
            background: #000080;
            border-top: 1px solid {COLOR_BORDER_LIGHT};
            border-left: 1px solid {COLOR_BORDER_LIGHT};
            border-right: 1px solid {COLOR_BORDER_DARK};
            border-bottom: 1px solid {COLOR_BORDER_DARK};
            spacing: 0px;
            padding: 0px;
        }}
        QWidget#TitleBar * {{
            background: transparent;
        }}
        QLabel#TitleLabel {{
            color: #FFFFFF;
            background: transparent;
            font-weight: bold;
        }}
        QLabel {{
            color: #000;
            background: transparent;
        }}
        QScrollBar:vertical {{
            background: transparent;
            width: 14px;
            margin: 0px 0 0px 0;
        }}
        QScrollBar::handle:vertical {{
            background: {COLOR_SURFACE};
            min-height: 20px;
            border-top: 1px solid {COLOR_BORDER_LIGHT};
            border-left: 1px solid {COLOR_BORDER_LIGHT};
            border-right: 1px solid {COLOR_BORDER_DARK};
            border-bottom: 1px solid {COLOR_BORDER_DARK};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            background: transparent;
            height: 0px;
        }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
            background: transparent;
        }}
        {build_slider_style()}
        """
    )


def build_titlebar(owner):
    owner.titlebar = Win98TitleBar(owner)
    owner.titlebar.setObjectName("TitleBar")
    owner.titlebar.setFixedHeight(26)
    owner.titlebar.setAttribute(Qt.WA_StyledBackground, True)
    owner.titlebar.setAutoFillBackground(True)
    owner.titlebar.setStyleSheet("QWidget#TitleBar { background-color: #000080; }")
    pal = owner.titlebar.palette()
    pal.setColor(QPalette.Window, QColor("#000080"))
    owner.titlebar.setPalette(pal)

    title_layout = QHBoxLayout(owner.titlebar)
    title_layout.setContentsMargins(6, 4, 6, 4)
    title_layout.setSpacing(6)

    owner.title_label = QLabel("donkeytyper")
    owner.title_label.setObjectName("TitleLabel")
    owner.title_label.setFont(QFont(owner.chrome_font_family, 9, QFont.Bold))
    owner.title_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    owner.btn_minimize = QToolButton()
    owner.btn_minimize.setText("_")
    owner.btn_minimize.setFixedSize(20, 18)
    owner.btn_minimize.setFont(QFont(owner.chrome_font_family, 8))
    owner.btn_minimize.setStyleSheet(build_button_style())

    owner.btn_maximize = QToolButton()
    owner.btn_maximize.setText("▢")
    owner.btn_maximize.setFixedSize(20, 18)
    owner.btn_maximize.setFont(QFont(owner.chrome_font_family, 8))
    owner.btn_maximize.setStyleSheet(build_button_style())

    owner.btn_close = QToolButton()
    owner.btn_close.setText("X")
    owner.btn_close.setFixedSize(20, 18)
    owner.btn_close.setFont(QFont(owner.chrome_font_family, 8))
    owner.btn_close.setStyleSheet(build_button_style())

    title_layout.addWidget(owner.title_label, alignment=Qt.AlignLeft)
    title_layout.addStretch(1)
    title_layout.addWidget(owner.btn_minimize)
    title_layout.addWidget(owner.btn_maximize)
    title_layout.addWidget(owner.btn_close)


def build_editor_frame(owner):
    shell = QWidget()
    shell_layout = QVBoxLayout(shell)
    shell_layout.setContentsMargins(8, 8, 8, 8)
    shell_layout.setSpacing(8)

    frame = QFrame()
    frame.setFrameShape(QFrame.Panel)
    frame.setFrameShadow(QFrame.Sunken)
    frame.setStyleSheet(
        f"""
        QFrame {{
            background: #E0DED4;
            border-top: 1px solid {COLOR_BORDER_DARK};
            border-left: 1px solid {COLOR_BORDER_DARK};
            border-right: 1px solid {COLOR_BORDER_LIGHT};
            border-bottom: 1px solid {COLOR_BORDER_LIGHT};
        }}
        """
    )
    frame_layout = QVBoxLayout(frame)
    frame_layout.setContentsMargins(2, 2, 2, 2)
    frame_layout.setSpacing(0)
    owner.editor_stack = QStackedWidget()
    owner.editor_stack.addWidget(owner.editor)
    owner.editor_stack.addWidget(owner.markdown_preview)
    frame_layout.addWidget(owner.editor_stack)

    shell_layout.addWidget(frame)
    owner.editor_shell = shell


def build_toolbar(owner):
    owner.toolbar = QToolBar("Tools")
    owner.toolbar.setObjectName("ToolBar")
    owner.toolbar.setMovable(False)

    root = QWidget()
    root_layout = QHBoxLayout(root)
    root_layout.setContentsMargins(12, 10, 12, 10)
    root_layout.setSpacing(12)
    root_layout.setAlignment(Qt.AlignCenter)
    owner.toolbar_root_layout = root_layout

    left = QWidget()
    left_layout = QVBoxLayout(left)
    left_layout.setContentsMargins(0, 0, 0, 0)
    left_layout.setSpacing(10)

    size_row = QWidget()
    size_row_layout = QHBoxLayout(size_row)
    size_row_layout.setContentsMargins(0, 0, 0, 0)
    size_row_layout.setSpacing(10)

    owner.lbl_size_title = QLabel("Size")
    owner.lbl_size_title.setFont(QFont(owner.chrome_font_family, 8))
    owner.lbl_size_title.setFixedWidth(32)

    owner.slider_size = QSlider(Qt.Horizontal)
    owner.slider_size.setMinimum(0)
    owner.slider_size.setMaximum(len(owner.font_sizes) - 1)
    owner.slider_size.setValue(1)
    owner.slider_size.setTickPosition(QSlider.NoTicks)
    owner.slider_size.setTickInterval(1)
    owner.slider_size.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    owner.slider_size.setMinimumWidth(256)

    size_slider_stack = QWidget()
    size_slider_layout = QVBoxLayout(size_slider_stack)
    size_slider_layout.setContentsMargins(0, 0, 0, 0)
    size_slider_layout.setSpacing(2)
    size_slider_layout.addWidget(owner.slider_size)
    owner.size_ticks = TickBar(owner.slider_size)
    size_slider_layout.addWidget(owner.size_ticks)

    owner.lbl_size_value = QLabel(f"{owner.font_sizes[1]}pt")
    owner.lbl_size_value.setFont(QFont(owner.chrome_font_family, 8))
    owner.lbl_size_value.setFixedWidth(44)

    size_row_layout.addWidget(owner.lbl_size_title)
    size_row_layout.addWidget(size_slider_stack)
    size_row_layout.addWidget(owner.lbl_size_value)

    alpha_row = QWidget()
    alpha_row_layout = QHBoxLayout(alpha_row)
    alpha_row_layout.setContentsMargins(0, 0, 0, 0)
    alpha_row_layout.setSpacing(10)

    owner.lbl_alpha_title = QLabel("Alpha")
    owner.lbl_alpha_title.setFont(QFont(owner.chrome_font_family, 8))
    owner.lbl_alpha_title.setFixedWidth(32)

    owner.slider_alpha = QSlider(Qt.Horizontal)
    owner.slider_alpha.setMinimum(0)
    owner.slider_alpha.setMaximum(len(owner.alpha_values) - 1)
    owner.slider_alpha.setValue(0)
    owner.slider_alpha.setTickPosition(QSlider.NoTicks)
    owner.slider_alpha.setTickInterval(1)
    owner.slider_alpha.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    owner.slider_alpha.setMinimumWidth(256)

    alpha_slider_stack = QWidget()
    alpha_slider_layout = QVBoxLayout(alpha_slider_stack)
    alpha_slider_layout.setContentsMargins(0, 0, 0, 0)
    alpha_slider_layout.setSpacing(2)
    alpha_slider_layout.addWidget(owner.slider_alpha)
    owner.alpha_ticks = TickBar(owner.slider_alpha)
    alpha_slider_layout.addWidget(owner.alpha_ticks)

    owner.lbl_alpha_value = QLabel("100%")
    owner.lbl_alpha_value.setFont(QFont(owner.chrome_font_family, 8))
    owner.lbl_alpha_value.setFixedWidth(44)

    alpha_row_layout.addWidget(owner.lbl_alpha_title)
    alpha_row_layout.addWidget(alpha_slider_stack)
    alpha_row_layout.addWidget(owner.lbl_alpha_value)

    left_layout.addWidget(size_row)
    left_layout.addWidget(alpha_row)

    owner.div1 = QFrame()
    owner.div1.setFrameShape(QFrame.VLine)
    owner.div1.setFrameShadow(QFrame.Sunken)
    owner.div1.setStyleSheet(f"color: {COLOR_BORDER_DARK};")
    owner.div1.setFixedHeight(56)

    middle = QWidget()
    grid = QGridLayout(middle)
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(6)
    grid.setVerticalSpacing(6)

    owner.color_buttons = []
    for i, (name, hex_color) in enumerate(owner.colors):
        btn = QToolButton()
        btn.setCheckable(True)
        btn.setToolTip(name)
        btn.setFixedSize(20, 20)
        btn.setStyleSheet(
            f"""
            QToolButton {{
                background-color: {hex_color};
                border: 1px solid {COLOR_BORDER_DARK};
            }}
            QToolButton:checked {{
                background-color: {hex_color};
                border: 2px solid #000000;
            }}
            """
        )
        owner.color_buttons.append(btn)
        r = 0 if i < 4 else 1
        c = i % 4
        grid.addWidget(btn, r, c)

    owner.color_buttons[0].setChecked(True)

    owner.div2 = QFrame()
    owner.div2.setFrameShape(QFrame.VLine)
    owner.div2.setFrameShadow(QFrame.Sunken)
    owner.div2.setStyleSheet(f"color: {COLOR_BORDER_DARK};")
    owner.div2.setFixedHeight(56)

    right = QWidget()
    right_layout = QGridLayout(right)
    right_layout.setContentsMargins(0, 0, 0, 0)
    right_layout.setSpacing(8)
    owner.right_layout = right_layout

    row1 = QWidget()
    row1_layout = QGridLayout(row1)
    row1_layout.setContentsMargins(0, 0, 0, 0)
    row1_layout.setHorizontalSpacing(6)
    row1_layout.setVerticalSpacing(0)

    owner.btn_bold = QToolButton()
    owner.btn_bold.setText("B")
    owner.btn_bold.setCheckable(True)
    owner.btn_bold.setFixedSize(18, 18)
    owner.btn_bold.setFont(QFont(owner.chrome_font_family, 8, QFont.Bold))
    owner.btn_bold.setStyleSheet(build_button_style())

    owner.btn_italic = QToolButton()
    owner.btn_italic.setText("I")
    owner.btn_italic.setCheckable(True)
    owner.btn_italic.setFixedSize(18, 18)
    italic_font = QFont(owner.chrome_font_family, 8)
    italic_font.setItalic(True)
    owner.btn_italic.setFont(italic_font)
    owner.btn_italic.setStyleSheet(build_button_style())

    row2 = QWidget()
    row2_layout = QGridLayout(row2)
    row2_layout.setContentsMargins(0, 0, 0, 0)
    row2_layout.setHorizontalSpacing(6)
    row2_layout.setVerticalSpacing(0)
    owner.slot_row_layout = row2_layout

    owner.slot_buttons = []
    for i in range(3):
        btn = QToolButton()
        btn.setText(str(i + 1))
        btn.setCheckable(True)
        btn.setFixedSize(18, 18)
        btn.setFont(QFont(owner.chrome_font_family, 8))
        btn.setStyleSheet(build_button_style())
        owner.slot_buttons.append(btn)
        row2_layout.addWidget(btn, 0, i)

    row1_layout.addWidget(owner.btn_bold, 0, 0)
    row1_layout.addWidget(owner.btn_italic, 0, 1)
    row1_layout.setColumnStretch(2, 1)

    right_layout.addWidget(row1, 0, 0, alignment=Qt.AlignLeft | Qt.AlignVCenter)
    right_layout.addWidget(row2, 1, 0, alignment=Qt.AlignLeft | Qt.AlignVCenter)

    file_row = QWidget()
    file_row_layout = QHBoxLayout(file_row)
    file_row_layout.setContentsMargins(0, 0, 0, 0)
    file_row_layout.setSpacing(6)

    owner.btn_open = QToolButton()
    owner.btn_open.setText("Open")
    owner.btn_open.setFixedSize(56, 22)
    owner.btn_open.setFont(QFont(owner.chrome_font_family, 8))
    owner.btn_open.setStyleSheet(build_button_style())

    owner.btn_save = QToolButton()
    owner.btn_save.setText("Save")
    owner.btn_save.setFixedSize(56, 22)
    owner.btn_save.setFont(QFont(owner.chrome_font_family, 8))
    owner.btn_save.setStyleSheet(build_button_style())

    file_row_layout.addWidget(owner.btn_open)
    file_row_layout.addWidget(owner.btn_save)
    right_layout.addWidget(file_row, 2, 0, alignment=Qt.AlignLeft | Qt.AlignVCenter)
    right_layout.setRowStretch(0, 1)
    right_layout.setRowStretch(1, 1)
    right_layout.setRowStretch(2, 1)
    owner.right_rows = [row1, row2, file_row]

    spacer_a = QWidget()
    spacer_a.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    spacer_b = QWidget()
    spacer_b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    spacer_c = QWidget()
    spacer_c.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    spacer_d = QWidget()
    spacer_d.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    owner.toolbar_spacers = [spacer_a, spacer_b, spacer_c, spacer_d]

    root_layout.addStretch(1)
    root_layout.addWidget(left)
    root_layout.addWidget(spacer_a)
    root_layout.addWidget(owner.div1)
    root_layout.addWidget(spacer_b)
    root_layout.addWidget(middle)
    root_layout.addWidget(spacer_c)
    root_layout.addWidget(owner.div2)
    root_layout.addWidget(spacer_d)
    root_layout.addWidget(right)
    root_layout.addStretch(1)

    owner.toolbar.addWidget(root)


def build_main_layout(owner):
    root = QWidget()
    layout = QVBoxLayout(root)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    layout.addWidget(owner.titlebar)
    layout.addWidget(owner.toolbar)
    layout.addWidget(owner.editor_shell)
    owner.setCentralWidget(root)


def build_statusbar(owner):
    owner.status = QStatusBar()
    owner.status.setSizeGripEnabled(False)
    owner.lbl_word_count = QLabel("Words: 0")
    owner.lbl_word_count.setFont(QFont(owner.chrome_font_family, 8))
    owner.status.addWidget(owner.lbl_word_count)
    owner.lbl_word_count.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    owner.setStatusBar(owner.status)
    owner.editor_bridge.update_word_count()


def apply_ui_scale(owner):
    if not hasattr(owner, "_base_window_height"):
        return
    scale = max(0.8, min(1.6, owner.height() / float(owner._base_window_height)))

    title_scale = scale
    if owner.isMaximized() or owner.isFullScreen():
        title_scale = scale * 0.9
    title_h = max(20, int(owner._base_titlebar_height * title_scale))
    owner.titlebar.setFixedHeight(title_h)

    toolbar_h = max(48, int(owner._base_toolbar_height * 0.8) + 42)
    owner.toolbar.setFixedHeight(toolbar_h)

    btn_w = max(16, int(owner._base_title_button_size[0] * scale))
    btn_h = max(14, int(owner._base_title_button_size[1] * scale))
    for btn in (owner.btn_minimize, owner.btn_maximize, owner.btn_close):
        btn.setFixedSize(btn_w, btn_h)

    title_font = QFont(owner.chrome_font_family, max(8, int(owner._base_title_font_size * scale)))
    for widget in owner.titlebar.findChildren(QLabel, "TitleLabel"):
        widget.setFont(title_font)

    toolbar_scale = 1.0

    bold_w = max(28, int(owner._base_bold_size[0] * toolbar_scale))
    bold_h = max(24, int(owner._base_bold_size[1] * toolbar_scale))
    owner.btn_bold.setFixedSize(bold_w, bold_h)
    owner.btn_italic.setFixedSize(bold_w, bold_h)

    slot_w = max(18, int(owner._base_slot_size[0] * toolbar_scale))
    slot_h = max(16, int(owner._base_slot_size[1] * toolbar_scale))
    for btn in owner.slot_buttons:
        btn.setFixedSize(slot_w, slot_h)

    open_w = max(34, int(owner._base_open_size[0] * toolbar_scale))
    open_h = max(18, int(owner._base_open_size[1] * toolbar_scale))
    owner.btn_open.setFixedSize(open_w, open_h)
    owner.btn_save.setFixedSize(open_w, open_h)

    color_w = max(16, int(owner._base_color_size[0] * toolbar_scale))
    for btn in owner.color_buttons:
        btn.setFixedSize(color_w, color_w)

    owner.btn_bold.setFixedSize(color_w - 2, color_w - 2)
    owner.btn_italic.setFixedSize(color_w - 2, color_w - 2)
    for btn in owner.slot_buttons:
        btn.setFixedSize(color_w - 2, color_w - 2)

    div_h = max(44, int(owner._base_div_height * toolbar_scale))
    owner.div1.setFixedHeight(div_h)
    owner.div2.setFixedHeight(div_h)

    if owner.isMaximized() or owner.isFullScreen():
        owner.right_layout.setSpacing(14)
        owner.slot_row_layout.setSpacing(8)
        owner.toolbar_root_layout.setSpacing(18)
        for sp in owner.toolbar_spacers:
            sp.setMinimumWidth(18)
    else:
        owner.right_layout.setSpacing(10)
        owner.slot_row_layout.setSpacing(6)
        owner.toolbar_root_layout.setSpacing(12)
        for sp in owner.toolbar_spacers:
            sp.setMinimumWidth(0)

    if hasattr(owner, "right_rows"):
        for row in owner.right_rows:
            row.setMinimumHeight(22)
