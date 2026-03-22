from __future__ import annotations

from PySide6.QtGui import QTextCursor

from bridge import extract_document_from_editor


class WindowEditorBridge:
    def __init__(self, window):
        self.window = window

    def sync_controller_document_from_editor(self):
        if self.window._syncing_from_controller:
            return
        self.window.controller.set_document(
            extract_document_from_editor(self.window.editor),
            reset_history=False,
        )

    def sync_controller_caret_from_editor(self):
        cursor = self.window.editor.textCursor()
        paragraph_index = max(0, cursor.blockNumber())
        paragraph_offset = max(0, cursor.positionInBlock())
        self.window.controller.set_caret_from_paragraph_offset(paragraph_index, paragraph_offset)

    def sync_controller_cursor_state_from_editor(self):
        cursor = self.window.editor.textCursor()
        if cursor.hasSelection():
            self.sync_controller_selection_from_editor()
            return
        self.sync_controller_caret_from_editor()

    def sync_controller_selection_from_editor(self):
        cursor = self.window.editor.textCursor()
        if not cursor.hasSelection():
            self.window.controller.clear_selection()
            self.sync_controller_caret_from_editor()
            return

        selection_offsets = self.get_editor_selection_paragraph_offsets(cursor)
        if selection_offsets is None:
            self.window.controller.clear_selection()
            self.sync_controller_caret_from_editor()
            return

        self.window.controller.set_selection_from_paragraph_offsets(*selection_offsets)

    def get_editor_selection_paragraph_offsets(
        self,
        cursor: QTextCursor | None = None,
    ) -> tuple[int, int, int, int] | None:
        if cursor is None:
            cursor = self.window.editor.textCursor()
        if not cursor.hasSelection():
            return None

        start_pos = cursor.selectionStart()
        end_pos = cursor.selectionEnd()
        start_block = self.window.editor.document().findBlock(start_pos)
        end_probe = max(start_pos, end_pos - 1)
        end_block = self.window.editor.document().findBlock(end_probe)
        if not start_block.isValid() or not end_block.isValid():
            return None
        start_offset = max(0, start_pos - start_block.position())
        end_offset = max(0, end_pos - end_block.position())
        return (
            start_block.blockNumber(),
            start_offset,
            end_block.blockNumber(),
            end_offset,
        )

    def restore_editor_caret_from_controller(self):
        caret = self.window.controller.get_caret()
        block = self.window.editor.document().findBlockByNumber(caret.paragraph_index)
        if not block.isValid():
            return
        cursor = self.window.editor.textCursor()
        cursor.setPosition(block.position() + self.window.controller.get_caret_paragraph_offset())
        self.window.editor.setTextCursor(cursor)

    def restore_editor_selection_from_controller(self):
        selection = self.window.controller.get_selection_paragraph_offsets()
        if selection is None:
            self.restore_editor_caret_from_controller()
            return

        start_paragraph, start_offset, end_paragraph, end_offset = selection
        start_block = self.window.editor.document().findBlockByNumber(start_paragraph)
        end_block = self.window.editor.document().findBlockByNumber(end_paragraph)
        if not start_block.isValid() or not end_block.isValid():
            self.restore_editor_caret_from_controller()
            return

        cursor = self.window.editor.textCursor()
        cursor.setPosition(start_block.position() + start_offset)
        cursor.setPosition(end_block.position() + end_offset, QTextCursor.KeepAnchor)
        self.window.editor.setTextCursor(cursor)

    def update_word_count(self):
        text = self.window.editor.toPlainText()
        count = len(text.replace("\n", ""))
        if hasattr(self.window, "lbl_word_count"):
            self.window.lbl_word_count.setText(f"Words: {count}")

    def apply_controller_transaction(self, apply_current_char_format: bool = True):
        self.window.preview_coordinator.refresh_editor_from_controller()
        self.window.session_coordinator.mark_dirty()
        self.window.format_coordinator.sync_format_after_controller_transaction(
            apply_current_char_format=apply_current_char_format
        )

    def handle_editor_text_changed(self):
        if self.window._syncing_from_controller:
            return
        if getattr(self.window, "_suppress_editor_backsync", False):
            return
        if getattr(self.window, "_suppress_format_apply", False):
            return
        self.window.preview_coordinator.apply_command_highlights()
        self.update_word_count()
        self.window.session_coordinator.mark_dirty()
        self.sync_controller_document_from_editor()
        if self.window.editor.document().isEmpty():
            self.window.format_coordinator.apply_format_from_ui()

    def editor_has_active_focus(self) -> bool:
        return self.window.editor.hasFocus() or self.window.editor.viewport().hasFocus()

    def cleanup_pending_special_paragraphs_for_current_cursor(self) -> bool:
        cursor = self.window.editor.textCursor()
        active_paragraph_index = cursor.blockNumber() if cursor.block().isValid() else None
        if not self.window.controller.cleanup_pending_special_paragraphs(active_paragraph_index):
            return False
        self.apply_controller_transaction(apply_current_char_format=False)
        return True
