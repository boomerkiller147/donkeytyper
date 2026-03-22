from PySide6.QtWidgets import QMainWindow
from PySide6.QtGui import QFont, QKeySequence, QShortcut, QFontDatabase
from PySide6.QtCore import Qt, QTimer

from bridge.layout_policy import (
    DOCUMENT_TOP_PADDING,
    compute_content_side_margin,
)
from editor import EditorController
from model import Document
from ui import (
    MarkdownPreviewEdit,
    DonkeyTextEdit,
    apply_ui_scale as build_apply_ui_scale,
    apply_main_window_style as build_apply_main_window_style,
    build_editor_frame as ui_build_editor_frame,
    build_main_layout as ui_build_main_layout,
    build_statusbar as ui_build_statusbar,
    build_titlebar as ui_build_titlebar,
    build_toolbar as ui_build_toolbar,
)
from .window_editor_bridge import WindowEditorBridge
from .window_format_coordinator import WindowFormatCoordinator
from .window_input_coordinator import WindowInputCoordinator
from .window_preview_coordinator import WindowPreviewCoordinator
from .window_session_coordinator import WindowSessionCoordinator


class DonkeyTyper(QMainWindow):
    MARKDOWN_PREVIEW_HOLD_MS = 1000
    MARKDOWN_PREVIEW_FONT_SIZE = 14
    EMPTY_PARAGRAPH_PLACEHOLDER = "\u200b"

    # -------------------------
    # Lifecycle
    # -------------------------
    def __init__(self):
        super().__init__()

        self.setWindowTitle("donkeytyper")
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.setWindowFlag(Qt.Window, True)

        # Discrete steps
        self.font_sizes = [14, 16, 18, 20, 24, 28, 32]
        self.alpha_values = [255, 220, 180, 140, 100, 70]  # 100% -> ~27%

        self.colors = [
        ("Color 1 (#3E3A39)", "#3E3A39"),
        ("Color 2 (#4D7C45)", "#4D7C45"),
        ("Color 3 (#F7B25A)", "#F7B25A"),
        ("Color 4 (#265671)", "#265671"),
        ("Color 5 (#D3624B)", "#D3624B"),
        ("Color 6 (#70A1C1)", "#70A1C1"),
        ("Color 7 (#9E1D30)", "#9E1D30"),
        ("Color 8 (#5B3D3E)", "#5B3D3E"),
                                                             ]

        self.controller = EditorController(Document())

        # Editor
        self.editor = DonkeyTextEdit(self)
        self.markdown_preview = MarkdownPreviewEdit(self)
        self.ui_font_family = self._pick_ui_font_family()
        self.chrome_font_family = self._pick_chrome_font_family()
        self.setFont(QFont(self.chrome_font_family, 9))
        self.editor.setFont(QFont(self.ui_font_family, 9))
        self.markdown_preview.setFont(QFont(self.ui_font_family, self.MARKDOWN_PREVIEW_FONT_SIZE))
        self.editor.setContextMenuPolicy(Qt.NoContextMenu)
        self.markdown_preview.setContextMenuPolicy(Qt.NoContextMenu)
        self.editor.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.editor.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.markdown_preview.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.markdown_preview.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.editor.document().setUndoRedoEnabled(False)
        self.markdown_preview.document().setUndoRedoEnabled(False)
        if hasattr(self.editor.document(), "setMaximumUndoRedoSteps"):
            self.editor.document().setMaximumUndoRedoSteps(0)
        if hasattr(self.markdown_preview.document(), "setMaximumUndoRedoSteps"):
            self.markdown_preview.document().setMaximumUndoRedoSteps(0)
        self.editor.document().setDocumentMargin(0)
        self.markdown_preview.document().setDocumentMargin(0)
        self.editor.setViewportMargins(24, int(DOCUMENT_TOP_PADDING), 24, 0)
        self.markdown_preview.setViewportMargins(24, int(DOCUMENT_TOP_PADDING), 24, 0)
        self._build_editor_frame()
        self.resize(980, 640)
        # Toolbar (strict 3-zone)
        self._build_titlebar()
        self._build_toolbar()
        self._build_main_layout()
        self.format_coordinator = WindowFormatCoordinator(self)
        self.session_coordinator = WindowSessionCoordinator(self)
        self.input_coordinator = WindowInputCoordinator(self)
        self.preview_coordinator = WindowPreviewCoordinator(self)
        self.editor_bridge = WindowEditorBridge(self)
        self._connect_signals()
        self.format_coordinator.apply_format_from_ui()
        self.session_coordinator.update_window_title()
        self._suppress_editor_backsync = False
        self._ime_replacement_selection_offsets = None

        # Keep palette-driven input stable
        self.editor.textChanged.connect(self.editor_bridge.handle_editor_text_changed)
        self.editor.cursorPositionChanged.connect(self.format_coordinator.reassert_format)

        self._apply_main_window_style()

        # Status bar (word count)
        self._build_statusbar()

        self.preview_coordinator.render_controller_document(initial_only=True)
        self.editor_bridge.update_word_count()

        self._syncing_from_controller = False
        # Default fill lengths are hard-coded (no viewport-width calculation).
        self._default_fill_base_count = 60

        # Shortcuts for slot toggles
        self._shortcut_slot1 = QShortcut(QKeySequence("Ctrl+1"), self)
        self._shortcut_slot1.activated.connect(lambda: self.format_coordinator.toggle_slot(0))
        self._shortcut_slot2 = QShortcut(QKeySequence("Ctrl+2"), self)
        self._shortcut_slot2.activated.connect(lambda: self.format_coordinator.toggle_slot(1))
        self._shortcut_slot3 = QShortcut(QKeySequence("Ctrl+3"), self)
        self._shortcut_slot3.activated.connect(lambda: self.format_coordinator.toggle_slot(2))

        # Base sizes for scaling (match initial window)
        self._base_window_height = 640
        self._base_titlebar_height = self.titlebar.height()
        self._base_toolbar_height = self.toolbar.sizeHint().height()
        self._base_title_button_size = (20, 18)
        self._base_title_font_size = 9
        self._base_bold_size = (18, 18)
        self._base_slot_size = (18, 18)
        self._base_open_size = (56, 22)
        self._base_color_size = (20, 20)
        self._base_div_height = 56
        self._apply_ui_scale()
        QTimer.singleShot(0, self._finalize_startup)

    # -------------------------
    # Font and style setup
    # -------------------------
    def _pick_ui_font_family(self) -> str:
        # Prefer CJK-capable UI fonts on Windows, fall back to Tahoma.
        preferred = [
            "Microsoft YaHei UI",
            "Microsoft YaHei",
            "SimSun",
            "NSimSun",
            "Segoe UI",
            "Tahoma",
        ]
        families = set(QFontDatabase.families())
        for name in preferred:
            if name in families:
                return name
        return "Tahoma"

    def _pick_chrome_font_family(self) -> str:
        return "Tahoma"

    def _apply_main_window_style(self):
        build_apply_main_window_style(self)

    def _build_titlebar(self):
        ui_build_titlebar(self)

    def _build_editor_frame(self):
        ui_build_editor_frame(self)

    # -------------------------
    # Toolbar and layout construction
    # -------------------------
    def _build_toolbar(self):
        ui_build_toolbar(self)

    def _build_main_layout(self):
        ui_build_main_layout(self)

    def _build_statusbar(self):
        ui_build_statusbar(self)

    # -------------------------
    # Resize and responsive scaling
    # -------------------------
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_ui_scale()
        self._apply_content_column_layout()

    def _apply_ui_scale(self):
        build_apply_ui_scale(self)

    def _finalize_startup(self):
        self.session_coordinator.rebuild_runtime_paragraph_type_registry(
            document_definitions=None
        )
        self._apply_content_column_layout()

    # -------------------------
    # Signals
    # -------------------------
    def _connect_signals(self):
        self.slider_size.valueChanged.connect(
            lambda value, sender=self.slider_size: self.format_coordinator.handle_format_changed(sender, value)
        )
        self.slider_alpha.valueChanged.connect(
            lambda value, sender=self.slider_alpha: self.format_coordinator.handle_format_changed(sender, value)
        )

        self.btn_bold.toggled.connect(
            lambda checked, sender=self.btn_bold: self.format_coordinator.handle_format_changed(sender, checked)
        )
        self.btn_italic.toggled.connect(
            lambda checked, sender=self.btn_italic: self.format_coordinator.handle_format_changed(sender, checked)
        )

        for btn in self.color_buttons:
            btn.toggled.connect(
                lambda checked, sender=btn: self.format_coordinator.handle_color_toggled(checked, sender=sender)
            )

        for i, btn in enumerate(self.slot_buttons):
            btn.clicked.connect(lambda checked, idx=i: self.format_coordinator.handle_slot_clicked(idx, checked))

        self.btn_open.clicked.connect(self.session_coordinator.open_file)
        self.btn_save.clicked.connect(self.session_coordinator.save_file)

        # Shortcuts for file ops
        self._shortcut_open = QShortcut(QKeySequence("Ctrl+O"), self)
        self._shortcut_open.activated.connect(self.session_coordinator.open_file)
        self._shortcut_save = QShortcut(QKeySequence("Ctrl+S"), self)
        self._shortcut_save.activated.connect(self.session_coordinator.save_file)
        self._shortcut_size_step = QShortcut(QKeySequence("Ctrl+Q"), self)
        self._shortcut_size_step.activated.connect(self._step_size)
        self._shortcut_alpha_step = QShortcut(QKeySequence("Ctrl+W"), self)
        self._shortcut_alpha_step.activated.connect(self._step_alpha)
        self._shortcut_color_step = QShortcut(QKeySequence("Ctrl+E"), self)
        self._shortcut_color_step.activated.connect(self._step_color)

        # Undo / Redo (custom shortcuts)
        self._shortcut_undo = QShortcut(QKeySequence("Ctrl+Z"), self)
        self._shortcut_undo.activated.connect(self._undo_via_controller)
        self._shortcut_redo = QShortcut(QKeySequence("Ctrl+R"), self)
        self._shortcut_redo.activated.connect(self._redo_via_controller)
        self._editor_shortcut_undo = QShortcut(QKeySequence("Ctrl+Z"), self.editor)
        self._editor_shortcut_undo.activated.connect(self._undo_via_controller)
        self._editor_shortcut_redo = QShortcut(QKeySequence("Ctrl+R"), self.editor)
        self._editor_shortcut_redo.activated.connect(self._redo_via_controller)
        self._shortcut_bold = QShortcut(QKeySequence("Ctrl+B"), self)
        self._shortcut_bold.activated.connect(self.format_coordinator.toggle_bold_via_controller)
        self._shortcut_italic = QShortcut(QKeySequence("Ctrl+I"), self)
        self._shortcut_italic.activated.connect(self.format_coordinator.toggle_italic_via_controller)

        # Window control buttons
        self.btn_minimize.clicked.connect(self.showMinimized)
        self.btn_maximize.clicked.connect(
            lambda: self.showNormal() if self.isMaximized() else self.showMaximized()
        )
        self.btn_close.clicked.connect(self.close)

    def _clear_ime_replacement_selection_context(self):
        self._ime_replacement_selection_offsets = None

    def _apply_content_column_layout(self):
        content_width = max(self.editor.width(), self.markdown_preview.width())
        if content_width <= 0:
            content_width = max(self.editor.viewport().width(), self.markdown_preview.viewport().width())
        side_margin = compute_content_side_margin(content_width)
        self.editor.setViewportMargins(side_margin, int(DOCUMENT_TOP_PADDING), side_margin, 0)
        self.markdown_preview.setViewportMargins(side_margin, int(DOCUMENT_TOP_PADDING), side_margin, 0)

    def _undo_via_controller(self):
        self._clear_ime_replacement_selection_context()
        if self.preview_coordinator.is_markdown_active():
            return
        if not self.controller.undo():
            return
        self.editor_bridge.apply_controller_transaction()

    def _redo_via_controller(self):
        self._clear_ime_replacement_selection_context()
        if self.preview_coordinator.is_markdown_active():
            return
        if not self.controller.redo():
            return
        self.editor_bridge.apply_controller_transaction()

    # -------------------------
    # Cursor and window helpers
    # -------------------------
    def closeEvent(self, event):
        if self.session_coordinator.confirm_discard_if_dirty():
            event.accept()
        else:
            event.ignore()

    def _step_size(self):
        if self.preview_coordinator.is_markdown_active():
            return
        i = self.slider_size.value()
        i += 1
        if i > self.slider_size.maximum():
            i = self.slider_size.minimum()
        self.slider_size.setValue(i)

    def _step_alpha(self):
        if self.preview_coordinator.is_markdown_active():
            return
        i = self.slider_alpha.value()
        i += 1
        if i > self.slider_alpha.maximum():
            i = self.slider_alpha.minimum()
        self.slider_alpha.setValue(i)

    def _step_color(self):
        if self.preview_coordinator.is_markdown_active():
            return
        if not self.color_buttons:
            return
        current_index = self.format_coordinator.get_selected_color_index()
        next_index = (current_index + 1) % len(self.color_buttons)
        self.color_buttons[next_index].setChecked(True)
