from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor, QTextBlockFormat, QTextCursor
from PySide6.QtWidgets import QTextEdit

from bridge import render_document_to_editor
from bridge.layout_policy import get_line_height_for_font_size
from exporters import render_document_to_markdown
from paragraphs.registry import (
    list_registered_clean_commands,
    list_registered_create_commands,
)


class WindowPreviewCoordinator:
    def __init__(self, window):
        self.window = window
        self._active_view_mode = "editor"
        self._temporary_markdown_preview = False
        self._tab_hold_pending = False
        self._tab_hold_consumed = False
        self._tab_press_origin_view = "editor"
        self._tab_hold_timer = QTimer(window)
        self._tab_hold_timer.setSingleShot(True)
        self._tab_hold_timer.timeout.connect(self.handle_tab_hold_timeout)

    def get_active_view_mode(self) -> str:
        return self._active_view_mode

    def is_markdown_active(self) -> bool:
        return self._active_view_mode == "markdown"

    def render_controller_document(self, *, initial_only: bool = False):
        if initial_only and self.window.editor.document().characterCount() > 1:
            return
        self.window._syncing_from_controller = True
        try:
            render_document_to_editor(self.window.editor, self.window.controller.get_document())
            self.refresh_markdown_preview_from_controller()
            self.window.editor_bridge.restore_editor_selection_from_controller()
            self.window._apply_content_column_layout()
        finally:
            self.window._syncing_from_controller = False

    def refresh_editor_from_controller(self):
        self.window._syncing_from_controller = True
        try:
            render_document_to_editor(self.window.editor, self.window.controller.get_document())
            self.refresh_markdown_preview_from_controller()
            self.window.editor_bridge.restore_editor_selection_from_controller()
            self.window._apply_content_column_layout()
            self.apply_command_highlights()
            self.window.editor_bridge.update_word_count()
        finally:
            self.window._syncing_from_controller = False

    def refresh_markdown_preview_from_controller(self):
        selection_state = self.get_text_edit_selection_state(self.window.markdown_preview)
        markdown_text = render_document_to_markdown(self.window.controller.get_document())
        self.window.markdown_preview.setPlainText(markdown_text)
        self.apply_markdown_preview_layout()
        self.restore_text_edit_selection_state(self.window.markdown_preview, selection_state)

    def apply_markdown_preview_layout(self):
        document = self.window.markdown_preview.document()
        target_line_height = float(
            get_line_height_for_font_size(self.window.MARKDOWN_PREVIEW_FONT_SIZE)
        )
        cursor = QTextCursor(document)
        cursor.beginEditBlock()
        try:
            block = document.firstBlock()
            while block.isValid():
                cursor.setPosition(block.position())
                block_format = block.blockFormat()
                block_format.setTopMargin(0.0)
                block_format.setBottomMargin(0.0)
                height_type = QTextBlockFormat.LineHeightTypes.MinimumHeight
                block_format.setLineHeight(target_line_height, int(height_type.value))
                cursor.setBlockFormat(block_format)
                block = block.next()
        finally:
            cursor.endEditBlock()

    def get_text_edit_selection_state(self, widget: QTextEdit) -> dict:
        cursor = widget.textCursor()
        return {
            "anchor": cursor.anchor(),
            "position": cursor.position(),
        }

    def restore_text_edit_selection_state(self, widget: QTextEdit, state: dict | None):
        if not isinstance(state, dict):
            return
        max_position = max(0, widget.document().characterCount() - 1)
        anchor = max(0, min(int(state.get("anchor", 0)), max_position))
        position = max(0, min(int(state.get("position", 0)), max_position))
        cursor = widget.textCursor()
        cursor.setPosition(anchor)
        cursor.setPosition(position, QTextCursor.KeepAnchor)
        widget.setTextCursor(cursor)

    def set_active_view_mode(self, mode: str):
        if mode == "markdown":
            self.window.editor_stack.setCurrentWidget(self.window.markdown_preview)
            self._active_view_mode = "markdown"
            self.window.markdown_preview.setFocus()
        else:
            self.window.editor_stack.setCurrentWidget(self.window.editor)
            self._active_view_mode = "editor"
            self.window.editor.setFocus()
        self.update_preview_mode_ui_state()

    def show_markdown_preview(self, *, temporary: bool = False):
        self.refresh_markdown_preview_from_controller()
        self._temporary_markdown_preview = temporary
        self.set_active_view_mode("markdown")

    def show_editor_view(self):
        self._temporary_markdown_preview = False
        self.set_active_view_mode("editor")

    def toggle_markdown_preview_view(self):
        if self.is_markdown_active():
            self.show_editor_view()
        else:
            self.show_markdown_preview()

    def handle_tab_press(self):
        if self._tab_hold_pending:
            return
        self._tab_press_origin_view = self._active_view_mode
        self._tab_hold_pending = True
        self._tab_hold_consumed = False
        self.toggle_markdown_preview_view()
        self._tab_hold_timer.start(self.window.MARKDOWN_PREVIEW_HOLD_MS)

    def handle_tab_release(self):
        if not self._tab_hold_pending:
            return
        self._tab_hold_pending = False
        self._tab_hold_timer.stop()
        if self._tab_hold_consumed:
            if self._tab_press_origin_view == "editor":
                self.show_editor_view()
            else:
                self.show_markdown_preview()
            self._tab_hold_consumed = False

    def handle_tab_hold_timeout(self):
        if not self._tab_hold_pending:
            return
        self._tab_hold_consumed = True
        self._temporary_markdown_preview = True

    def update_preview_mode_ui_state(self):
        preview_active = self.is_markdown_active()
        editable = not preview_active
        controls = [
            self.window.slider_size,
            self.window.slider_alpha,
            self.window.btn_bold,
            self.window.btn_italic,
            self.window.lbl_size_title,
            self.window.lbl_size_value,
            self.window.lbl_alpha_title,
            self.window.lbl_alpha_value,
        ]
        controls.extend(self.window.color_buttons)
        controls.extend(self.window.slot_buttons)
        if hasattr(self.window, "size_ticks"):
            controls.append(self.window.size_ticks)
        if hasattr(self.window, "alpha_ticks"):
            controls.append(self.window.alpha_ticks)
        for control in controls:
            control.setEnabled(editable)
        if editable:
            self.window.format_coordinator.update_toolbar_enabled_state()

    def apply_command_highlights(self):
        token_color = QColor("#000080")
        tokens = [
            "/block/",
            "/line/",
            "/size/",
            "/size ",
            "/alpha/",
            "/alpha ",
            "/center/",
            *list_registered_clean_commands(),
            *list_registered_create_commands(),
        ]
        selections = []

        doc = self.window.editor.document()
        block = doc.firstBlock()
        while block.isValid():
            text = block.text()
            if text:
                for token in tokens:
                    start = 0
                    while True:
                        idx = text.find(token, start)
                        if idx == -1:
                            break
                        sel = QTextEdit.ExtraSelection()
                        sel.format.setForeground(token_color)
                        cursor = QTextCursor(doc)
                        cursor.setPosition(block.position() + idx)
                        cursor.setPosition(
                            block.position() + idx + len(token),
                            QTextCursor.KeepAnchor,
                        )
                        sel.cursor = cursor
                        selections.append(sel)
                        start = idx + len(token)
            block = block.next()
        self.window.editor.setExtraSelections(selections)

    def restore_after_session_apply(self):
        # Preview mode is not persisted in session payload yet; restore stable editor mode.
        self._tab_hold_pending = False
        self._tab_hold_consumed = False
        self._tab_hold_timer.stop()
        self.show_editor_view()
        self.refresh_markdown_preview_from_controller()
        self.apply_command_highlights()
