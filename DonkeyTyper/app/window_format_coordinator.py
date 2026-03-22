from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor

from editor import InputStyleState
from model import filter_display_style_changes


class WindowFormatCoordinator:
    def __init__(self, window):
        self.window = window
        self._active_slot: int | None = None
        self._slot_states = [self.get_ui_state() for _ in range(3)]
        self._last_one_shot_alignment_key: tuple | None = None
        self.sync_controller_state()

    def handle_format_changed(self, sender=None, *args):
        if self.window.preview_coordinator.is_markdown_active():
            return
        if sender is None:
            sender = self.window.sender()
        size_changed = sender is self.window.slider_size and self.apply_font_size_change_from_ui()
        inline_style_changed = False
        if sender is self.window.btn_bold:
            inline_style_changed = self.apply_inline_style_change_from_ui(
                transaction_kind="selection_bold_change",
                changes={"bold": self.window.btn_bold.isChecked()},
            )
        elif sender is self.window.btn_italic:
            inline_style_changed = self.apply_inline_style_change_from_ui(
                transaction_kind="selection_italic_change",
                changes={"italic": self.window.btn_italic.isChecked()},
            )
        elif sender is self.window.slider_alpha:
            inline_style_changed = self.apply_inline_style_change_from_ui(
                transaction_kind="selection_alpha_change",
                changes={"alpha": self.get_selected_color().alpha()},
            )
        self.sync_controller_input_style_from_ui()
        if not size_changed and not inline_style_changed:
            self.apply_format_from_ui(allow_selection_apply=sender is not self.window.slider_size)
        if self._active_slot is not None:
            self.store_ui_to_slot(self._active_slot)
        self.sync_controller_slot_state_from_ui()

    def handle_color_toggled(self, checked: bool, sender=None):
        if sender is None:
            sender = self.window.sender()
        if sender is None:
            return
        if not checked:
            if not any(btn.isChecked() for btn in self.window.color_buttons):
                sender.blockSignals(True)
                sender.setChecked(True)
                sender.blockSignals(False)
            return

        for btn in self.window.color_buttons:
            if btn is not sender:
                btn.blockSignals(True)
                btn.setChecked(False)
                btn.blockSignals(False)
        sender_index = self.window.color_buttons.index(sender)
        self.window.controller.set_color_index(sender_index)
        inline_style_changed = self.apply_inline_style_change_from_ui(
            transaction_kind="selection_color_change",
            changes={"color": self.get_selected_color().name()},
        )
        if not inline_style_changed:
            self.apply_format_from_ui()
        if self._active_slot is not None:
            self.store_ui_to_slot(self._active_slot)
        self.sync_controller_state()

    def handle_slot_clicked(self, idx: int, checked: bool):
        if checked:
            self.toggle_slot(idx)
            return
        if self._active_slot == idx:
            self._active_slot = None
            self.window.controller.clear_active_slot()
            self.sync_controller_state()

    def toggle_slot(self, idx: int):
        controller_slot, controller_style = self.window.controller.toggle_slot(idx)
        if controller_slot is None and self._active_slot == idx:
            self.window.slot_buttons[idx].blockSignals(True)
            self.window.slot_buttons[idx].setChecked(False)
            self.window.slot_buttons[idx].blockSignals(False)
            self._active_slot = None
            self.sync_controller_state()
            return

        self._active_slot = controller_slot
        for i, btn in enumerate(self.window.slot_buttons):
            btn.blockSignals(True)
            btn.setChecked(i == self._active_slot)
            btn.blockSignals(False)

        if controller_style is not None:
            self.set_ui_state(controller_style.to_dict())
        self.apply_format_from_ui()
        self.sync_controller_state()

    def toggle_bold_via_controller(self):
        if self.window.preview_coordinator.is_markdown_active():
            return
        style = self.window.controller.toggle_bold()
        self.window.btn_bold.setChecked(style.bold)

    def toggle_italic_via_controller(self):
        if self.window.preview_coordinator.is_markdown_active():
            return
        style = self.window.controller.toggle_italic()
        self.window.btn_italic.setChecked(style.italic)

    def get_selected_color(self) -> QColor:
        idx = self.get_selected_color_index()
        base = QColor(self.window.colors[idx][1])
        alpha_index = max(0, min(self.window.slider_alpha.value(), len(self.window.alpha_values) - 1))
        base.setAlpha(self.window.alpha_values[alpha_index])
        return base

    def get_selected_color_index(self) -> int:
        for i, btn in enumerate(self.window.color_buttons):
            if btn.isChecked():
                return i
        return 0

    def get_size_from_input_style(self, style: InputStyleState) -> int:
        idx = self.clamp_index(style.size_index, 0, len(self.window.font_sizes) - 1, 1)
        return self.window.font_sizes[idx]

    def get_effective_input_point_size(self, requested_size: int, paragraph_index: int | None = None) -> int:
        return int(requested_size)

    def get_color_from_input_style(self, style: InputStyleState) -> QColor:
        color_index = self.clamp_index(style.color_index, 0, len(self.window.colors) - 1, 0)
        alpha_index = self.clamp_index(style.alpha_index, 0, len(self.window.alpha_values) - 1, 0)
        color = QColor(self.window.colors[color_index][1])
        color.setAlpha(self.window.alpha_values[alpha_index])
        return color

    def set_size_by_value(self, size_value: float):
        closest_index = 0
        closest_diff = None
        for i, size in enumerate(self.window.font_sizes):
            diff = abs(float(size) - float(size_value))
            if closest_diff is None or diff < closest_diff:
                closest_diff = diff
                closest_index = i
        self.window.slider_size.blockSignals(True)
        self.window.slider_size.setValue(closest_index)
        self.window.slider_size.blockSignals(False)

    def get_desired_size(self) -> int:
        size_index = max(0, min(self.window.slider_size.value(), len(self.window.font_sizes) - 1))
        return self.window.font_sizes[size_index]

    def get_ui_state(self) -> dict:
        return {
            "size_index": self.window.slider_size.value(),
            "alpha_index": self.window.slider_alpha.value(),
            "color_index": self.get_selected_color_index(),
            "bold": self.window.btn_bold.isChecked(),
            "italic": self.window.btn_italic.isChecked(),
        }

    def get_controller_input_style(self) -> InputStyleState:
        state = self.sanitize_ui_state(self.get_ui_state())
        return InputStyleState.from_dict(state)

    @staticmethod
    def clamp_index(value, minimum: int, maximum: int, default: int) -> int:
        try:
            index = int(value)
        except (TypeError, ValueError):
            index = default
        return max(minimum, min(index, maximum))

    def sanitize_ui_state(self, state: dict | None) -> dict:
        if not isinstance(state, dict):
            state = {}
        return {
            "size_index": self.clamp_index(state.get("size_index", 1), 0, max(0, len(self.window.font_sizes) - 1), 1),
            "alpha_index": self.clamp_index(state.get("alpha_index", 0), 0, max(0, len(self.window.alpha_values) - 1), 0),
            "color_index": self.clamp_index(state.get("color_index", 0), 0, max(0, len(self.window.color_buttons) - 1), 0),
            "bold": bool(state.get("bold", False)),
            "italic": bool(state.get("italic", False)),
        }

    def set_ui_state(self, state: dict):
        state = self.sanitize_ui_state(state)
        self.window.slider_size.blockSignals(True)
        self.window.slider_alpha.blockSignals(True)
        self.window.btn_bold.blockSignals(True)
        self.window.btn_italic.blockSignals(True)
        for btn in self.window.color_buttons:
            btn.blockSignals(True)

        self.window.slider_size.setValue(state.get("size_index", 1))
        self.window.slider_alpha.setValue(state.get("alpha_index", 0))
        self.window.btn_bold.setChecked(state.get("bold", False))
        self.window.btn_italic.setChecked(state.get("italic", False))

        color_index = max(0, min(state.get("color_index", 0), len(self.window.color_buttons) - 1))
        for i, btn in enumerate(self.window.color_buttons):
            btn.setChecked(i == color_index)

        self.window.slider_size.blockSignals(False)
        self.window.slider_alpha.blockSignals(False)
        self.window.btn_bold.blockSignals(False)
        self.window.btn_italic.blockSignals(False)
        for btn in self.window.color_buttons:
            btn.blockSignals(False)
        self.sync_controller_input_style_from_ui()

    def set_slot_states(self, slot_states: list[dict]):
        self._slot_states = [self.sanitize_ui_state(state) for state in slot_states]

    def get_slot_states(self) -> list[dict]:
        return [dict(state) for state in self._slot_states]

    def set_active_slot(self, active_slot: int | None):
        self._active_slot = active_slot

    def get_active_slot(self) -> int | None:
        return self._active_slot

    def store_ui_to_slot(self, idx: int):
        if 0 <= idx < len(self._slot_states):
            self._slot_states[idx] = self.get_ui_state()
            self.window.controller.set_slot_state(idx, InputStyleState.from_dict(self._slot_states[idx]))

    def sync_controller_input_style_from_ui(self):
        self.window.controller.set_input_style(self.get_controller_input_style())

    def sync_controller_slot_state_from_ui(self):
        self.window.controller.set_active_slot(self._active_slot)
        for idx, state in enumerate(self._slot_states):
            self.window.controller.set_slot_state(idx, InputStyleState.from_dict(state))

    def sync_controller_state(self):
        self.sync_controller_input_style_from_ui()
        self.sync_controller_slot_state_from_ui()

    def clear_active_slot_ui(self):
        if self._active_slot is None:
            return
        active = self._active_slot
        self.window.slot_buttons[active].blockSignals(True)
        self.window.slot_buttons[active].setChecked(False)
        self.window.slot_buttons[active].blockSignals(False)
        self._active_slot = None
        self.window.controller.clear_active_slot()

    def update_toolbar_enabled_state(self):
        size_enabled = self.should_enable_size_controls(
            active_view_mode=self.window.preview_coordinator.get_active_view_mode(),
            selection_spans_multiple_paragraphs=self.selection_spans_multiple_paragraphs(),
        )
        self.window.slider_size.setEnabled(size_enabled)
        if hasattr(self.window, "size_ticks"):
            self.window.size_ticks.setEnabled(size_enabled)
        self.window.lbl_size_title.setEnabled(size_enabled)
        self.window.lbl_size_value.setEnabled(size_enabled)
        for btn in self.window.slot_buttons:
            btn.setEnabled(size_enabled)

    @staticmethod
    def should_enable_size_controls(*, active_view_mode: str, selection_spans_multiple_paragraphs: bool) -> bool:
        if active_view_mode == "markdown":
            return False
        return not selection_spans_multiple_paragraphs

    def get_single_paragraph_selection_bounds(self) -> tuple[int, int, int] | None:
        cursor = self.window.editor.textCursor()
        if not cursor.hasSelection() or self.selection_spans_multiple_paragraphs():
            return None
        start_pos = cursor.selectionStart()
        end_pos = cursor.selectionEnd()
        document = self.window.editor.document()
        block = document.findBlock(start_pos)
        if not block.isValid():
            return None
        paragraph_index = block.blockNumber()
        block_position = block.position()
        start_offset = max(0, start_pos - block_position)
        end_offset = max(0, end_pos - block_position)
        return paragraph_index, start_offset, end_offset

    def selection_covers_entire_paragraph(self) -> bool:
        selection_bounds = self.get_single_paragraph_selection_bounds()
        if selection_bounds is None:
            return False
        paragraph_index, start_offset, end_offset = selection_bounds
        paragraph_text = self.window.controller.get_paragraph_text(paragraph_index)
        return start_offset == 0 and end_offset == len(paragraph_text)

    def apply_font_size_change_from_ui(self) -> bool:
        cursor = self.window.editor.textCursor()
        if not cursor.hasSelection():
            return False
        if self.selection_spans_multiple_paragraphs():
            return False

        desired_size = self.get_desired_size()
        selection_bounds = self.get_single_paragraph_selection_bounds()
        if selection_bounds is None:
            return False
        paragraph_index, start_offset, end_offset = selection_bounds
        whole_paragraph = self.selection_covers_entire_paragraph()
        current_size = self.get_model_paragraph_font_size(paragraph_index)

        def transaction():
            self.window.editor_bridge.sync_controller_selection_from_editor()
            if whole_paragraph:
                return self.window.controller.set_paragraph_font_size(paragraph_index, desired_size)
            return self.window.controller.apply_font_size_to_selection(desired_size)

        transaction_kind = "paragraph_size_change" if whole_paragraph else "selection_size_change"
        if current_size is not None and int(current_size) == int(desired_size) and not whole_paragraph:
            return False
        if not self.window.controller.run_document_transaction(
            transaction_kind,
            transaction,
            metadata={
                "paragraph_index": paragraph_index,
                "size": int(desired_size),
                "whole_paragraph": whole_paragraph,
                "selection_start": start_offset,
                "selection_end": end_offset,
            },
        ):
            return False
        self.window.editor_bridge.apply_controller_transaction(apply_current_char_format=False)
        return True

    def build_insert_run_style(self) -> dict:
        style = self.get_controller_input_style()
        color = self.get_color_from_input_style(style)
        requested_size = self.get_size_from_input_style(style)
        return {
            "paragraph_font_size": self.get_effective_input_point_size(requested_size),
            "bold": style.bold,
            "italic": style.italic,
            "color": color.name(),
            "alpha": color.alpha(),
            "underline": False,
        }

    def apply_inline_style_change_from_ui(self, *, transaction_kind: str, changes: dict) -> bool:
        if not self.window.editor.textCursor().hasSelection():
            return False

        display_style_changes = self.extract_display_style_changes(changes)
        use_display_style = self.should_use_display_style_path(
            display_style_changes=display_style_changes,
            whole_paragraph=self.selection_covers_entire_paragraph(),
        )

        def transaction():
            self.window.editor_bridge.sync_controller_selection_from_editor()
            if use_display_style:
                return self.window.controller.apply_display_style_to_selection(**display_style_changes)
            return self.window.controller.apply_inline_style_to_selection(**changes)

        if not self.window.controller.run_document_transaction(
            transaction_kind,
            transaction,
            metadata={
                "replaces_selection": True,
                "uses_display_style": use_display_style,
                **changes,
            },
        ):
            return False
        self.window.editor_bridge.apply_controller_transaction(apply_current_char_format=False)
        return True

    @staticmethod
    def should_use_display_style_path(*, display_style_changes: dict, whole_paragraph: bool) -> bool:
        return bool(display_style_changes) and bool(whole_paragraph)

    @staticmethod
    def extract_display_style_changes(changes: dict) -> dict:
        return filter_display_style_changes(changes)

    def update_format_value_labels(self):
        self.window.lbl_size_value.setText(f"{self.get_desired_size()}pt")
        alpha_index = max(0, min(self.window.slider_alpha.value(), len(self.window.alpha_values) - 1))
        alpha = self.window.alpha_values[alpha_index]
        self.window.lbl_alpha_value.setText(f"{int(alpha / 255 * 100)}%")

    def apply_current_char_format_from_ui(self, allow_selection_apply: bool = False):
        cursor = self.window.editor.textCursor()
        if cursor.hasSelection() and not allow_selection_apply:
            return

        style = self.window.controller.get_input_style()
        color = self.get_color_from_input_style(style)
        point_size = self.get_effective_input_point_size(
            self.get_size_from_input_style(style),
            cursor.blockNumber(),
        )

        fmt = self.window.editor.currentCharFormat()
        fmt.setFont(QFont(self.window.ui_font_family))
        fmt.setFontPointSize(point_size)
        fmt.setFontWeight(QFont.Bold if style.bold else QFont.Normal)
        fmt.setFontItalic(style.italic)
        fmt.setForeground(color)
        self.window.editor.setCurrentCharFormat(fmt)

    def apply_format_from_ui(self, allow_selection_apply: bool = False):
        if getattr(self.window, "_suppress_format_apply", False):
            return

        self.window._suppress_format_apply = True
        self.window.editor.blockSignals(True)
        try:
            self.sync_controller_input_style_from_ui()
            self.update_format_value_labels()
            self.apply_current_char_format_from_ui(allow_selection_apply=allow_selection_apply)
        finally:
            self.window.editor.blockSignals(False)
            self.window._suppress_format_apply = False
            self.window.editor.setFocus()

    def is_placeholder_fragment(self, text: str) -> bool:
        return (text or "") == self.window.EMPTY_PARAGRAPH_PLACEHOLDER

    def get_char_format_at_position(self, position: int) -> QTextCharFormat | None:
        document = self.window.editor.document()
        if position < 0:
            return None

        block = document.findBlock(position)
        if not block.isValid():
            return None

        iterator = block.begin()
        while not iterator.atEnd():
            fragment = iterator.fragment()
            if fragment.isValid() and fragment.length() > 0:
                if self.is_placeholder_fragment(fragment.text()):
                    iterator += 1
                    continue
                start = fragment.position()
                end = start + fragment.length()
                if start <= position < end:
                    return fragment.charFormat()
            iterator += 1
        return None

    def get_reference_char_format(self, cursor: QTextCursor) -> QTextCharFormat | None:
        if cursor.hasSelection():
            return self.get_char_format_at_position(cursor.selectionStart())

        block = cursor.block()
        if not block.isValid():
            return None

        position = cursor.position()
        block_start = block.position()
        block_end = block_start + max(0, block.length() - 1)

        if block.length() <= 1:
            return None
        if position > block_start:
            return self.get_char_format_at_position(position - 1)
        if block_start < block_end:
            return self.get_char_format_at_position(block_start)
        return None

    def find_color_index_for_qcolor(self, color: QColor) -> int:
        if not color.isValid():
            return 0
        best_index = 0
        best_distance = None
        for i, (_, hex_color) in enumerate(self.window.colors):
            candidate = QColor(hex_color)
            distance = (
                abs(candidate.red() - color.red())
                + abs(candidate.green() - color.green())
                + abs(candidate.blue() - color.blue())
            )
            if best_distance is None or distance < best_distance:
                best_distance = distance
                best_index = i
        return best_index

    def find_alpha_index_for_qcolor(self, color: QColor) -> int:
        best_index = 0
        best_distance = None
        for i, value in enumerate(self.window.alpha_values):
            distance = abs(int(value) - int(color.alpha()))
            if best_distance is None or distance < best_distance:
                best_distance = distance
                best_index = i
        return best_index

    def build_ui_state_from_char_format(self, fmt: QTextCharFormat) -> dict:
        color = fmt.foreground().color()
        size_value = fmt.fontPointSize()
        if size_value <= 0:
            size_value = fmt.font().pointSizeF()
        if size_value <= 0:
            size_value = float(self.get_desired_size())

        closest_index = 0
        closest_diff = None
        for index, size in enumerate(self.window.font_sizes):
            diff = abs(float(size) - float(size_value))
            if closest_diff is None or diff < closest_diff:
                closest_diff = diff
                closest_index = index

        return {
            "size_index": closest_index,
            "alpha_index": self.find_alpha_index_for_qcolor(color),
            "color_index": self.find_color_index_for_qcolor(color),
            "bold": fmt.fontWeight() >= QFont.Bold,
            "italic": fmt.fontItalic(),
        }

    def get_model_paragraph_font_size(self, paragraph_index: int) -> int | None:
        document = self.window.controller.get_document()
        if not (0 <= paragraph_index < len(document.paragraphs)):
            return None
        paragraph = document.paragraphs[paragraph_index]
        display_style = paragraph.get_display_style()
        size_value = display_style.get("font_size")
        if size_value is not None:
            return int(size_value)
        return int(paragraph.default_font_size)

    def apply_one_shot_alignment_from_reference_char(self) -> bool:
        cursor = self.window.editor.textCursor()
        reference_format = self.get_reference_char_format(cursor)
        if reference_format is None:
            return False
        current_state = self.sanitize_ui_state(self.get_ui_state())
        target_state = self.build_ui_state_from_char_format(reference_format)
        if self.window.controller.is_prefixed_paragraph(cursor.blockNumber()):
            target_state["size_index"] = current_state["size_index"]

        if target_state == current_state:
            return False

        self.clear_active_slot_ui()
        self.set_ui_state(target_state)
        return True

    def build_one_shot_alignment_key(self) -> tuple | None:
        cursor = self.window.editor.textCursor()
        if cursor.hasSelection():
            if not self.selection_is_single_paragraph():
                return None
            return ("single_selection", cursor.selectionStart(), cursor.selectionEnd())
        return ("collapsed", cursor.position())

    def apply_one_shot_alignment_for_current_state(self):
        cursor = self.window.editor.textCursor()
        key = self.build_one_shot_alignment_key()
        if key is None:
            self._last_one_shot_alignment_key = None
            return
        if key == self._last_one_shot_alignment_key:
            return
        self._last_one_shot_alignment_key = key
        if self.apply_one_shot_alignment_from_reference_char():
            if cursor.hasSelection():
                self.sync_controller_input_style_from_ui()
                self.update_format_value_labels()
            else:
                self.apply_format_from_ui(allow_selection_apply=False)

    def reassert_format(self):
        if self.window._syncing_from_controller:
            return
        if getattr(self.window, "_suppress_format_apply", False):
            return
        if self.window.preview_coordinator.get_active_view_mode() != "editor":
            return
        if not self.window.editor_bridge.editor_has_active_focus():
            return
        self.update_toolbar_enabled_state()
        self.window.editor_bridge.sync_controller_cursor_state_from_editor()
        if self.window.editor_bridge.cleanup_pending_special_paragraphs_for_current_cursor():
            return
        self.apply_one_shot_alignment_for_current_state()
        self.window.preview_coordinator.apply_command_highlights()
        self.update_format_value_labels()

    def sync_format_after_controller_transaction(self, apply_current_char_format: bool = True):
        if self.window._syncing_from_controller:
            return
        if getattr(self.window, "_suppress_format_apply", False):
            return
        self.update_toolbar_enabled_state()
        self.window.editor_bridge.sync_controller_cursor_state_from_editor()
        if self.window.editor_bridge.cleanup_pending_special_paragraphs_for_current_cursor():
            return
        self.window.preview_coordinator.apply_command_highlights()
        self.update_format_value_labels()
        if apply_current_char_format:
            self.apply_current_char_format_from_ui(allow_selection_apply=False)

    def selection_spans_multiple_paragraphs(self) -> bool:
        cursor = self.window.editor.textCursor()
        if not cursor.hasSelection():
            return False
        start_block = self.window.editor.document().findBlock(cursor.selectionStart())
        end_block = self.window.editor.document().findBlock(max(0, cursor.selectionEnd() - 1))
        if not start_block.isValid() or not end_block.isValid():
            return False
        return start_block.blockNumber() != end_block.blockNumber()

    def selection_is_single_paragraph(self) -> bool:
        cursor = self.window.editor.textCursor()
        return cursor.hasSelection() and not self.selection_spans_multiple_paragraphs()
