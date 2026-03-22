from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass

from PySide6.QtCore import QTimer

from paragraphs.registry import get_command_name, list_registered_create_commands


@dataclass(slots=True)
class EnterCommandContext:
    paragraph_index: int
    text: str


class WindowInputCoordinator:
    def __init__(self, window):
        self.window = window

    def handle_model_text_input(self, text: str) -> bool:
        self.window._clear_ime_replacement_selection_context()
        merge_key = None
        if not self.window.editor.textCursor().hasSelection():
            merge_key = self._build_text_input_merge_key("text_input")
        return self._run_styled_text_commit(
            text=text,
            transaction_kind="text_input",
            source="keyboard",
            write_fn=lambda commit_text, style: self.window.controller.insert_text_at_caret(
                commit_text,
                **style,
            ),
            merge_key=merge_key,
        )

    def handle_model_ime_commit(self, text: str) -> bool:
        selection_offsets = self.window._ime_replacement_selection_offsets
        if selection_offsets is None and self.window.editor.textCursor().hasSelection():
            selection_offsets = self.window.editor_bridge.get_editor_selection_paragraph_offsets(
                self.window.editor.textCursor()
            )
        merge_key = None
        if not self.window.editor.textCursor().hasSelection():
            merge_key = self._build_text_input_merge_key("ime_commit")
        handled = self._run_styled_text_commit(
            text=text,
            transaction_kind="ime_commit",
            source="ime",
            write_fn=lambda commit_text, style: self.window.controller.insert_text_at_caret(
                commit_text,
                **style,
            ),
            apply_current_char_format=False,
            merge_key=merge_key,
            frozen_selection_offsets=selection_offsets,
        )
        if handled:
            self.window._clear_ime_replacement_selection_context()
        return handled

    def handle_model_enter(self) -> bool:
        self.window._clear_ime_replacement_selection_context()
        command_executed = False
        command_name = None
        has_selection = self.window.editor.textCursor().hasSelection()

        def transaction():
            nonlocal command_executed, command_name
            if self.window.editor.textCursor().hasSelection():
                self.window.editor_bridge.sync_controller_selection_from_editor()
                if not self.window.controller.delete_selection():
                    return False
                self.window.controller.break_paragraph_at_caret()
                return True
            self.window.editor_bridge.sync_controller_caret_from_editor()
            command_name = self.window.controller.handle_enter_at_caret(
                command_executor=self._process_enter_command_for_paragraph
            )
            command_executed = command_name is not None
            return True

        if not self.window.controller.run_document_transaction(
            "enter",
            transaction,
            metadata={"replaces_selection": has_selection},
        ):
            return False
        if command_executed:
            self.window.controller.relabel_last_transaction(
                "enter_command",
                metadata={"command": command_name},
            )
        self.window.editor_bridge.apply_controller_transaction()
        return True

    def handle_model_backspace(self) -> bool:
        self.window._clear_ime_replacement_selection_context()
        transaction_kind = "backspace"
        cursor = self.window.editor.textCursor()
        metadata = {"replaces_selection": cursor.hasSelection()}
        if cursor.hasSelection():
            transaction_kind = "delete_selection"
        else:
            self.window.editor_bridge.sync_controller_caret_from_editor()
            paragraph_offset = self.window.controller.get_caret_paragraph_offset()
            if paragraph_offset == 0:
                transaction_kind = "backspace_boundary"
            else:
                transaction_kind = "backspace_inline"
            metadata["paragraph_offset"] = paragraph_offset

        def transaction():
            if self.window.editor.textCursor().hasSelection():
                self.window.editor_bridge.sync_controller_selection_from_editor()
                return self.window.controller.delete_selection()
            self.window.editor_bridge.sync_controller_caret_from_editor()
            return self.window.controller.delete_backward_at_caret()

        if not self.window.controller.run_document_transaction(
            "backspace",
            transaction,
            metadata=metadata,
        ):
            return False
        self.window.controller.relabel_last_transaction(transaction_kind, metadata=metadata)
        self.window.editor_bridge.apply_controller_transaction()
        return True

    def handle_model_delete(self) -> bool:
        self.window._clear_ime_replacement_selection_context()
        transaction_kind = "delete"
        cursor = self.window.editor.textCursor()
        metadata = {"replaces_selection": cursor.hasSelection()}
        if cursor.hasSelection():
            transaction_kind = "delete_selection"
        else:
            self.window.editor_bridge.sync_controller_caret_from_editor()
            paragraph_index = self.window.controller.get_caret().paragraph_index
            paragraph_text = self.window.controller.get_paragraph_text(paragraph_index)
            paragraph_offset = self.window.controller.get_caret_paragraph_offset()
            if paragraph_offset >= len(paragraph_text):
                transaction_kind = "delete_boundary"
            else:
                transaction_kind = "delete_inline"
            metadata["paragraph_offset"] = paragraph_offset

        def transaction():
            if self.window.editor.textCursor().hasSelection():
                self.window.editor_bridge.sync_controller_selection_from_editor()
                return self.window.controller.delete_selection()
            self.window.editor_bridge.sync_controller_caret_from_editor()
            return self.window.controller.delete_forward_at_caret()

        if not self.window.controller.run_document_transaction(
            "delete",
            transaction,
            metadata=metadata,
        ):
            return False
        self.window.controller.relabel_last_transaction(transaction_kind, metadata=metadata)
        self.window.editor_bridge.apply_controller_transaction()
        return True

    def handle_model_cut(self) -> bool:
        self.window._clear_ime_replacement_selection_context()
        if not self.window.editor.textCursor().hasSelection():
            return False
        cursor = self.window.editor.textCursor()
        selected_text = cursor.selectedText().replace("\u2029", "\n")
        metadata = {
            "selection_length": len(selected_text),
            "multiline": "\n" in selected_text,
        }
        self.window.editor.copy()

        def transaction():
            self.window.editor_bridge.sync_controller_selection_from_editor()
            return self.window.controller.delete_selection()

        if not self.window.controller.run_document_transaction(
            "cut",
            transaction,
            metadata=metadata,
        ):
            return False
        self.window.editor_bridge.apply_controller_transaction()
        return True

    def build_internal_clipboard_payload(self) -> bytes | None:
        cursor = self.window.editor.textCursor()
        if not cursor.hasSelection():
            return None
        self.window.editor_bridge.sync_controller_selection_from_editor()
        paragraphs = self.window.controller.export_selection_for_internal_clipboard()
        if not isinstance(paragraphs, list) or not paragraphs:
            return None
        payload = {
            "version": 1,
            "paragraphs": paragraphs,
        }
        return json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def build_external_clipboard_text(self) -> str | None:
        cursor = self.window.editor.textCursor()
        if not cursor.hasSelection():
            return None
        self.window.editor_bridge.sync_controller_selection_from_editor()
        text = self.window.controller.export_selection_for_external_copy_text()
        if text == "":
            return None
        return text

    def build_external_clipboard_html(self) -> str | None:
        cursor = self.window.editor.textCursor()
        if not cursor.hasSelection():
            return None
        self.window.editor_bridge.sync_controller_selection_from_editor()
        entries = self.window.controller.export_selection_for_external_copy_entries()
        if not entries:
            return None
        base_mime = super(type(self.window.editor), self.window.editor).createMimeDataFromSelection()
        base_html = bytes(base_mime.data("text/html")).decode("utf-8", errors="replace")
        text = self.window.controller.export_selection_for_external_copy_text()
        return self._build_external_clipboard_html_document(
            entries=entries,
            base_html=base_html,
            fallback_text=text,
        )

    def handle_model_internal_paste(self, payload: bytes | bytearray | memoryview) -> bool:
        self.window._clear_ime_replacement_selection_context()
        fragments = self._parse_internal_clipboard_payload(payload)
        if not fragments:
            return False

        style = self.window.format_coordinator.build_insert_run_style()
        metadata = {
            "source": "internal_clipboard",
            "paragraph_count": len(fragments),
            "contains_semantic": True,
            "replaces_selection": self.window.editor.textCursor().hasSelection(),
        }

        def transaction():
            self.window.editor_bridge.sync_controller_cursor_state_from_editor()
            return self.window.controller.paste_internal_fragments_at_caret(
                fragments,
                **style,
            )

        if not self.window.controller.run_document_transaction(
            "paste_internal",
            transaction,
            metadata=metadata,
        ):
            return False
        self.window.editor_bridge.apply_controller_transaction()
        return True

    def handle_model_paste(self, text: str) -> bool:
        self.window._clear_ime_replacement_selection_context()
        normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n")
        return self._run_styled_text_commit(
            text=text,
            transaction_kind="paste",
            source="paste",
            write_fn=lambda commit_text, style: self.window.controller.paste_text_at_caret(
                commit_text,
                **style,
            ),
            extra_metadata={
                "multiline": "\n" in normalized,
                "text_length": len(normalized),
            },
        )

    def _build_text_input_merge_key(self, source: str) -> tuple:
        style = self.window.format_coordinator.build_insert_run_style()
        return (
            source,
            style["paragraph_font_size"],
            style["bold"],
            style["italic"],
            style["color"],
            int(style["alpha"]),
        )

    def _run_styled_text_commit(
        self,
        *,
        text: str,
        transaction_kind: str,
        source: str,
        write_fn,
        apply_current_char_format: bool = True,
        merge_key: tuple | None = None,
        extra_metadata: dict | None = None,
        frozen_selection_offsets: tuple[int, int, int, int] | None = None,
    ) -> bool:
        if not text:
            return False
        cursor = self.window.editor.textCursor()
        has_selection = cursor.hasSelection() or frozen_selection_offsets is not None
        selection_offsets = frozen_selection_offsets
        if selection_offsets is None and cursor.hasSelection():
            selection_offsets = self.window.editor_bridge.get_editor_selection_paragraph_offsets(cursor)
        if has_selection:
            if selection_offsets is None:
                return False
            self.window.controller.set_selection_from_paragraph_offsets(*selection_offsets)
        style = self.window.format_coordinator.build_insert_run_style()

        def transaction():
            self.window.editor_bridge.sync_controller_caret_from_editor()
            if has_selection:
                return self.window.controller.replace_selection_with_text(text, **style)
            write_fn(text, style)
            return True

        metadata = {
            "source": source,
            "text_length": len(text),
            "replaces_selection": has_selection,
        }
        if extra_metadata:
            metadata.update(extra_metadata)

        if not self.window.controller.run_document_transaction(
            transaction_kind,
            transaction,
            merge_key=merge_key,
            metadata=metadata,
        ):
            return False

        if apply_current_char_format:
            self.window.editor_bridge.apply_controller_transaction()
        else:
            QTimer.singleShot(
                0,
                lambda: self.window.editor_bridge.apply_controller_transaction(
                    apply_current_char_format=False
                ),
            )
        return True

    def _build_enter_command_context(self, paragraph_index: int) -> EnterCommandContext | None:
        if paragraph_index < 0:
            return None
        return EnterCommandContext(
            paragraph_index=paragraph_index,
            text=self.window.controller.get_paragraph_text(paragraph_index) or "",
        )

    def _try_execute_model_enter_command(self, context: EnterCommandContext) -> str | None:
        paragraph_index = context.paragraph_index
        if paragraph_index < 0:
            return None
        if self.window.controller.execute_clean_command(paragraph_index):
            return "clean"
        for create_command in list_registered_create_commands():
            if self.window.controller.execute_registered_create_command(
                paragraph_index,
                token=create_command,
            ):
                return get_command_name(create_command)
        if self.window.controller.execute_center_command(paragraph_index):
            return "center"

        color = self.window.format_coordinator.get_selected_color()
        fill_specs = [
            ("/line/", "━", self._get_default_fill_count("/line/")),
            ("/block/", "█", self._get_default_fill_count("/block/")),
        ]
        for token, fill_char, count in fill_specs:
            parsed_count = self._parse_fill_command_count(context.text, token)
            if parsed_count == -1:
                continue
            if parsed_count is not None:
                count = parsed_count
            if self.window.controller.execute_fill_command(
                paragraph_index,
                token=token,
                fill_char=fill_char,
                count=count,
                paragraph_font_size=self.window.format_coordinator.get_desired_size(),
                color=color.name(),
                alpha=color.alpha(),
            ):
                return "line" if token == "/line/" else "block"

        size_parsed = self._parse_size_command(context.text)
        if size_parsed is not None:
            content, size_value = size_parsed
            if self.window.controller.execute_size_command(
                paragraph_index,
                size_value,
                len(content),
                len(context.text),
            ):
                return "size"

        alpha_parsed = self._parse_alpha_command(context.text)
        if alpha_parsed is not None:
            content, alpha_value = alpha_parsed
            if self.window.controller.execute_alpha_command(
                paragraph_index,
                alpha_value,
                len(content),
                len(context.text),
            ):
                return "alpha"
        return None

    def _process_enter_command_for_paragraph(self, paragraph_index: int) -> str | None:
        context = self._build_enter_command_context(paragraph_index)
        if context is None:
            return None
        return self._try_execute_model_enter_command(context)

    def _get_default_fill_count(self, token: str) -> int:
        base = max(1, int(self.window._default_fill_base_count))
        if token == "/block/":
            return max(1, base - 6)
        if token == "/line/":
            return max(1, base + 3)
        return base

    def _parse_size_command(self, text: str):
        default_token = "/size/"
        if text.endswith(default_token):
            return text[:-len(default_token)], 16

        prefix = "/size "
        idx = text.rfind(prefix)
        if idx == -1 or not text.endswith("/"):
            return None
        raw = text[idx + len(prefix):-1].strip()
        if not raw:
            return None
        try:
            size_value = int(raw)
        except (TypeError, ValueError):
            return None
        mapped_size = self._map_size_command_value(size_value)
        if mapped_size is None:
            return None
        content = text[:idx]
        return content, mapped_size

    def _map_size_command_value(self, size_value: int):
        if not self.window.font_sizes:
            return None
        min_size = min(self.window.font_sizes)
        max_size = max(self.window.font_sizes)
        if size_value < min_size or size_value > max_size:
            return None

        mapped = min_size
        for size in sorted(self.window.font_sizes):
            if size > size_value:
                break
            mapped = size
        return mapped

    def _parse_alpha_command(self, text: str):
        default_token = "/alpha/"
        if text.endswith(default_token):
            return text[:-len(default_token)], 255

        prefix = "/alpha "
        idx = text.rfind(prefix)
        if idx == -1 or not text.endswith("/"):
            return None
        raw = text[idx + len(prefix):-1].strip()
        if not raw:
            return None
        try:
            alpha_percent = int(raw)
        except (TypeError, ValueError):
            return None
        mapped_alpha = self._map_alpha_percent_to_value(alpha_percent)
        if mapped_alpha is None:
            return None
        content = text[:idx]
        return content, mapped_alpha

    def _map_alpha_percent_to_value(self, alpha_percent: int):
        if alpha_percent > 100:
            return None
        if not self.window.alpha_values:
            return None
        if alpha_percent < 27:
            alpha_percent = 27

        steps = sorted(self.window.alpha_values)
        mapped = steps[0]
        for value in steps:
            percent = int(round(value / 255.0 * 100.0))
            if percent > alpha_percent:
                break
            mapped = value
        return mapped

    @staticmethod
    def _parse_fill_command_count(text: str, token: str) -> int | None:
        stripped = text.strip()
        if stripped == token:
            return None
        prefix = token[:-1] + " "
        if not (stripped.startswith(prefix) and stripped.endswith("/")):
            return -1
        raw = stripped[len(prefix):-1].strip()
        if not raw:
            return -1
        try:
            value = int(raw)
        except (TypeError, ValueError):
            return -1
        if value <= 0:
            return -1
        return value

    @staticmethod
    def _parse_internal_clipboard_payload(
        payload: bytes | bytearray | memoryview,
    ) -> list[dict] | None:
        try:
            decoded = bytes(payload).decode("utf-8")
            data = json.loads(decoded)
        except (TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
            return None
        if not isinstance(data, dict):
            return None
        fragments = data.get("paragraphs", [])
        if not isinstance(fragments, list) or not fragments:
            return None
        return fragments

    @staticmethod
    def _build_external_clipboard_html_document(
        *,
        entries: list[dict],
        base_html: str,
        fallback_text: str,
    ) -> str | None:
        if not entries:
            return None
        if not base_html:
            lines = fallback_text.split("\n")
            escaped_lines = [html.escape(line) for line in lines]
            return f"<html><body>{'<br/>'.join(escaped_lines)}</body></html>"
        parts = re.split(r"(<p[^>]*>.*?</p>)", base_html, flags=re.S)
        entry_index = 0
        for idx, part in enumerate(parts):
            if entry_index >= len(entries):
                break
            if not part.startswith("<p"):
                continue
            prefix = entries[entry_index]["prefix"]
            if prefix:
                parts[idx] = re.sub(
                    r"(<p[^>]*>)",
                    r"\1<span style=\"font-size:12pt; color:#000000;\">"
                    + html.escape(prefix)
                    + r"</span>",
                    part,
                    count=1,
                    flags=re.S,
                )
            entry_index += 1
        return "".join(parts)
