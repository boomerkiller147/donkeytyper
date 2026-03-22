from __future__ import annotations

from dataclasses import dataclass, field

from model import Document, InlineRun, Paragraph, filter_display_style_changes
from paragraphs.registry import (
    display_prefix_requires_numbering,
    find_clean_transition_tag,
    find_tag_for_create_command,
    get_plain_display_prefix_text,
    get_create_command_name,
    get_default_paragraph_font_size,
    get_paragraph_type_spec,
    get_text_tag_for_font_size,
    uses_display_prefix,
)
from paragraphs.types import normalize_paragraph_tag


@dataclass(slots=True)
class CaretPosition:
    paragraph_index: int = 0
    run_index: int = 0
    offset: int = 0


@dataclass(slots=True)
class SelectionRange:
    start: CaretPosition
    end: CaretPosition

    def is_collapsed(self) -> bool:
        return self.start == self.end


@dataclass(slots=True)
class InputStyleState:
    size_index: int = 1
    alpha_index: int = 0
    color_index: int = 0
    bold: bool = False
    italic: bool = False

    def to_dict(self) -> dict:
        return {
            "size_index": self.size_index,
            "alpha_index": self.alpha_index,
            "color_index": self.color_index,
            "bold": self.bold,
            "italic": self.italic,
        }

    @classmethod
    def from_dict(cls, payload: dict | None) -> "InputStyleState":
        if not isinstance(payload, dict):
            payload = {}
        return cls(
            size_index=_coerce_int(payload.get("size_index"), 1),
            alpha_index=_coerce_int(payload.get("alpha_index"), 0),
            color_index=_coerce_int(payload.get("color_index"), 0),
            bold=bool(payload.get("bold", False)),
            italic=bool(payload.get("italic", False)),
        )


@dataclass(slots=True)
class TransactionSnapshot:
    document: dict
    caret: dict
    selection: dict | None


@dataclass(slots=True)
class TransactionRecord:
    kind: str
    before: TransactionSnapshot
    after: TransactionSnapshot
    merge_key: tuple | None = None
    metadata: dict = field(default_factory=dict)


class EditorController:
    def __init__(self, document: Document | None = None):
        self._document = document or Document()
        self._caret = CaretPosition()
        self._selection: SelectionRange | None = None
        self._input_style = InputStyleState()
        self._active_slot: int | None = None
        self._slot_states: list[InputStyleState] = [InputStyleState() for _ in range(3)]
        self._undo_stack: list[TransactionRecord] = []
        self._redo_stack: list[TransactionRecord] = []

    def get_document(self) -> Document:
        return self._document

    def set_document(self, document: Document, *, reset_history: bool = True):
        self._document = document
        self._caret = CaretPosition()
        self._selection = None
        if reset_history:
            self.clear_history()

    def clear_history(self):
        self._undo_stack.clear()
        self._redo_stack.clear()

    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    def can_redo(self) -> bool:
        return bool(self._redo_stack)

    def undo(self) -> bool:
        if not self._undo_stack:
            return False
        record = self._undo_stack.pop()
        self._restore_snapshot(record.before)
        self._redo_stack.append(record)
        return True

    def redo(self) -> bool:
        if not self._redo_stack:
            return False
        record = self._redo_stack.pop()
        self._restore_snapshot(record.after)
        self._undo_stack.append(record)
        return True

    def relabel_last_transaction(self, kind: str, *, metadata: dict | None = None) -> bool:
        if not self._undo_stack:
            return False
        self._undo_stack[-1].kind = kind
        if metadata:
            self._undo_stack[-1].metadata.update(metadata)
        return True

    def run_document_transaction(self, kind: str, callback, *, merge_key: tuple | None = None, metadata: dict | None = None):
        before = self._capture_snapshot()
        result = callback()
        after = self._capture_snapshot()
        if before != after:
            record = TransactionRecord(
                kind=kind,
                before=before,
                after=after,
                merge_key=merge_key,
                metadata=dict(metadata or {}),
            )
            if (
                merge_key is not None
                and self._undo_stack
                and self._undo_stack[-1].merge_key == merge_key
                and self._undo_stack[-1].after == before
            ):
                self._undo_stack[-1].after = after
                if metadata:
                    self._undo_stack[-1].metadata.update(metadata)
            else:
                self._undo_stack.append(record)
            self._redo_stack.clear()
        return result

    def get_caret(self) -> CaretPosition:
        return self._caret

    def set_caret(self, caret: CaretPosition):
        self._caret = caret
        self._selection = None

    def get_selection(self) -> SelectionRange | None:
        return self._selection

    def get_selection_paragraph_offsets(self) -> tuple[int, int, int, int] | None:
        if self._selection is None:
            return None
        start, end = _ordered_carets(self._selection.start, self._selection.end)
        start_paragraph = self._document.paragraphs[start.paragraph_index]
        end_paragraph = self._document.paragraphs[end.paragraph_index]
        return (
            start.paragraph_index,
            _paragraph_offset_from_caret(start_paragraph, start),
            end.paragraph_index,
            _paragraph_offset_from_caret(end_paragraph, end),
        )

    def set_selection(self, selection: SelectionRange | None):
        self._selection = selection

    def set_selection_from_paragraph_offsets(
        self,
        start_paragraph_index: int,
        start_offset: int,
        end_paragraph_index: int,
        end_offset: int,
    ):
        start = _caret_from_paragraph_offset(self._document, start_paragraph_index, start_offset)
        end = _caret_from_paragraph_offset(self._document, end_paragraph_index, end_offset)
        start, end = _ordered_carets(start, end)
        self._selection = SelectionRange(start=start, end=end)
        self._caret = end

    def clear_selection(self):
        self._selection = None

    def has_selection(self) -> bool:
        return self._selection is not None and not self._selection.is_collapsed()

    def get_input_style(self) -> InputStyleState:
        return self._input_style

    def set_input_style(self, style: InputStyleState):
        self._input_style = style

    def update_input_style(self, **changes) -> InputStyleState:
        state = self._input_style.to_dict()
        state.update(changes)
        self._input_style = InputStyleState.from_dict(state)
        return self._input_style

    def toggle_bold(self) -> InputStyleState:
        return self.update_input_style(bold=not self._input_style.bold)

    def toggle_italic(self) -> InputStyleState:
        return self.update_input_style(italic=not self._input_style.italic)

    def set_size_index(self, size_index: int) -> InputStyleState:
        return self.update_input_style(size_index=size_index)

    def set_alpha_index(self, alpha_index: int) -> InputStyleState:
        return self.update_input_style(alpha_index=alpha_index)

    def set_color_index(self, color_index: int) -> InputStyleState:
        return self.update_input_style(color_index=color_index)

    def get_active_slot(self) -> int | None:
        return self._active_slot

    def set_active_slot(self, slot_index: int | None):
        self._active_slot = slot_index

    def get_slot_states(self) -> list[InputStyleState]:
        return list(self._slot_states)

    def set_slot_state(self, slot_index: int, style: InputStyleState):
        if 0 <= slot_index < len(self._slot_states):
            self._slot_states[slot_index] = style

    def set_slot_states(self, slot_states: list[InputStyleState]):
        self._slot_states = list(slot_states)

    def clear_active_slot(self):
        self._active_slot = None

    def toggle_slot(self, slot_index: int) -> tuple[int | None, InputStyleState | None]:
        if not (0 <= slot_index < len(self._slot_states)):
            return self._active_slot, None
        if self._active_slot == slot_index:
            self._active_slot = None
            return None, None
        self._active_slot = slot_index
        self._input_style = self._slot_states[slot_index]
        return self._active_slot, self._input_style

    def set_caret_from_paragraph_offset(self, paragraph_index: int, paragraph_offset: int):
        paragraph_index = max(0, min(paragraph_index, len(self._document.paragraphs) - 1))
        paragraph = self._document.paragraphs[paragraph_index]
        run_index, run_offset = _resolve_run_position(paragraph, paragraph_offset)
        self._caret = CaretPosition(
            paragraph_index=paragraph_index,
            run_index=run_index,
            offset=run_offset,
        )
        self._selection = None

    def get_caret_paragraph_offset(self) -> int:
        paragraph = self._document.paragraphs[self._caret.paragraph_index]
        return _paragraph_offset_from_caret(paragraph, self._caret)

    def insert_text_at_caret(
        self,
        text: str,
        *,
        paragraph_font_size: int,
        bold: bool,
        italic: bool,
        color: str,
        alpha: int,
        underline: bool = False,
    ):
        if not text:
            return

        target_size = int(paragraph_font_size)
        paragraph = self._prepare_caret_paragraph_for_text_input(target_size)
        paragraph_offset = self.get_caret_paragraph_offset()
        _prepare_paragraph_for_text_edit(paragraph)
        if paragraph.is_empty and _is_size_rigid_text_paragraph(paragraph):
            paragraph.default_font_size = target_size

        insert_run = InlineRun(
            text=text,
            font_size=None,
            bold=bold,
            italic=italic,
            color=color,
            alpha=int(alpha),
            underline=underline,
        )
        paragraph.runs = _insert_run(paragraph.runs, paragraph_offset, insert_run)
        paragraph.normalize()
        _normalize_empty_paragraph_font_size(paragraph)
        _finalize_pending_special_paragraph_edit(paragraph)
        self.set_caret_from_paragraph_offset(self._caret.paragraph_index, paragraph_offset + len(text))

    def delete_selection(self) -> bool:
        if not self.has_selection():
            return False

        selection = self._selection
        assert selection is not None
        start, end = _ordered_carets(selection.start, selection.end)
        start_paragraph = self._document.paragraphs[start.paragraph_index]
        end_paragraph = self._document.paragraphs[end.paragraph_index]
        start_offset = _paragraph_offset_from_caret(start_paragraph, start)
        end_offset = _paragraph_offset_from_caret(end_paragraph, end)

        if start.paragraph_index == end.paragraph_index:
            start_paragraph.runs = _delete_range(start_paragraph.runs, start_offset, end_offset)
            _prepare_paragraph_for_text_edit(start_paragraph)
            start_paragraph.normalize()
            _normalize_empty_paragraph_font_size(start_paragraph)
            _normalize_pending_special_paragraph_state(start_paragraph)
        else:
            left_runs, _ = _split_runs(start_paragraph.runs, start_offset)
            _, right_runs = _split_runs(end_paragraph.runs, end_offset)
            left = Paragraph(
                runs=left_runs,
                tag=start_paragraph.tag,
                tag_data=dict(start_paragraph.tag_data),
                default_font_size=start_paragraph.default_font_size,
                alignment=start_paragraph.alignment,
            )
            right = Paragraph(
                runs=right_runs,
                tag=end_paragraph.tag,
                tag_data=dict(end_paragraph.tag_data),
                default_font_size=end_paragraph.default_font_size,
                alignment=end_paragraph.alignment,
            )
            left.normalize()
            right.normalize()
            _normalize_empty_paragraph_font_size(left)
            _normalize_empty_paragraph_font_size(right)
            _normalize_pending_special_paragraph_state(left)
            _normalize_pending_special_paragraph_state(right)

            if _can_merge_paragraphs_after_cross_delete(left, right):
                merged = Paragraph(
                    runs=_merge_adjacent_runs(left.runs + right.runs),
                    tag=left.tag,
                    tag_data=dict(left.tag_data),
                    default_font_size=left.default_font_size,
                    alignment=left.alignment,
                )
                merged.normalize()
                _normalize_empty_paragraph_font_size(merged)
                _normalize_pending_special_paragraph_state(merged)
                replacement = [merged]
            else:
                replacement: list[Paragraph] = []
                if left.plain_text():
                    replacement.append(left)
                if right.plain_text():
                    replacement.append(right)
                if not replacement:
                    replacement.append(Paragraph())

            self._document.paragraphs[start.paragraph_index:end.paragraph_index + 1] = replacement

        self.set_caret_from_paragraph_offset(start.paragraph_index, start_offset)
        self.clear_selection()
        return True

    def replace_selection_with_text(
        self,
        text: str,
        *,
        paragraph_font_size: int,
        bold: bool,
        italic: bool,
        color: str,
        alpha: int,
        underline: bool = False,
    ) -> bool:
        if not self.has_selection():
            return False
        self.delete_selection()
        if text:
            return self.paste_text_at_caret(
                text,
                paragraph_font_size=paragraph_font_size,
                bold=bold,
                italic=italic,
                color=color,
                alpha=alpha,
                underline=underline,
            )
        return True

    def export_selection_for_internal_clipboard(self) -> list[dict]:
        if not self.has_selection():
            return []

        selection = self._selection
        assert selection is not None
        start, end = _ordered_carets(selection.start, selection.end)
        exported: list[dict] = []

        for paragraph_index in range(start.paragraph_index, end.paragraph_index + 1):
            paragraph = self._document.paragraphs[paragraph_index]
            start_offset = 0
            end_offset = len(paragraph.plain_text())
            if paragraph_index == start.paragraph_index:
                start_offset = _paragraph_offset_from_caret(paragraph, start)
            if paragraph_index == end.paragraph_index:
                end_offset = _paragraph_offset_from_caret(paragraph, end)
            if end_offset < start_offset:
                start_offset, end_offset = end_offset, start_offset
            text = paragraph.plain_text()[start_offset:end_offset]
            exported.append(
                {
                    "text": text,
                    "tag": paragraph.tag,
                    "tag_data": dict(paragraph.tag_data),
                }
            )

        return exported

    def export_selection_for_external_copy_text(self) -> str:
        entries = self.export_selection_for_external_copy_entries()
        return "\n".join(
            f"{entry['prefix']}{entry['text']}" if entry["prefix"] else entry["text"]
            for entry in entries
        )

    def export_selection_for_external_copy_entries(self) -> list[dict]:
        if not self.has_selection():
            return []

        selection = self._selection
        assert selection is not None
        start, end = _ordered_carets(selection.start, selection.end)
        entries: list[dict] = []

        for paragraph_index in range(start.paragraph_index, end.paragraph_index + 1):
            paragraph = self._document.paragraphs[paragraph_index]
            start_offset = 0
            end_offset = len(paragraph.plain_text())
            if paragraph_index == start.paragraph_index:
                start_offset = _paragraph_offset_from_caret(paragraph, start)
            if paragraph_index == end.paragraph_index:
                end_offset = _paragraph_offset_from_caret(paragraph, end)
            if end_offset < start_offset:
                start_offset, end_offset = end_offset, start_offset
            text = paragraph.plain_text()[start_offset:end_offset]
            prefix = ""
            if uses_display_prefix(paragraph.tag):
                ordered_number = None
                if display_prefix_requires_numbering(paragraph.tag):
                    ordered_number = self._get_ordered_prefixed_render_number(paragraph_index)
                prefix = get_plain_display_prefix_text(paragraph.tag, ordered_number=ordered_number)
            entries.append({"text": text, "prefix": prefix})

        return entries

    def paste_internal_fragments_at_caret(
        self,
        fragments: list[dict],
        *,
        paragraph_font_size: int,
        bold: bool,
        italic: bool,
        color: str,
        alpha: int,
        underline: bool = False,
    ) -> bool:
        normalized_fragments: list[dict] = []
        for item in fragments:
            if not isinstance(item, dict):
                continue
            text = str(item.get("text", ""))
            tag = item.get("tag")
            if tag is not None:
                tag = str(tag).strip() or None
            tag_data = item.get("tag_data")
            if not isinstance(tag_data, dict):
                tag_data = {}
            if text == "" and tag is None:
                continue
            normalized_fragments.append(
                {
                    "text": text,
                    "tag": tag,
                    "tag_data": dict(tag_data),
                }
            )

        if not normalized_fragments:
            return False

        if self.has_selection():
            self.delete_selection()

        if len(normalized_fragments) == 1:
            fragment = normalized_fragments[0]
            paragraph = self._document.paragraphs[self._caret.paragraph_index]
            if _can_inline_merge_internal_fragment(
                paragraph,
                fragment,
                paragraph_font_size=int(paragraph_font_size),
            ):
                return self.paste_text_at_caret(
                    fragment["text"],
                    paragraph_font_size=paragraph_font_size,
                    bold=bold,
                    italic=italic,
                    color=color,
                    alpha=alpha,
                    underline=underline,
                )

        paragraph_index = self._caret.paragraph_index
        paragraph = self._document.paragraphs[paragraph_index]
        paragraph_offset = self.get_caret_paragraph_offset()
        left_runs, right_runs = _split_runs(paragraph.runs, paragraph_offset)
        right_text_length = len("".join(run.text for run in right_runs))

        left = Paragraph(
            runs=left_runs,
            tag=paragraph.tag,
            tag_data=dict(paragraph.tag_data),
            default_font_size=paragraph.default_font_size,
            alignment=paragraph.alignment,
        )
        right = Paragraph(
            runs=right_runs,
            tag=paragraph.tag,
            tag_data=dict(paragraph.tag_data),
            default_font_size=paragraph.default_font_size,
            alignment=paragraph.alignment,
        )
        left.normalize()
        right.normalize()
        _normalize_empty_paragraph_font_size(left)
        _normalize_empty_paragraph_font_size(right)
        _normalize_pending_special_paragraph_state(left)
        _normalize_pending_special_paragraph_state(right)

        inserted: list[Paragraph] = []
        for item in normalized_fragments:
            text = item["text"]
            tag = item["tag"]
            runs: list[InlineRun] = []
            if text:
                runs.append(
                    InlineRun(
                        text=text,
                        font_size=None,
                        bold=bold,
                        italic=italic,
                        color=color,
                        alpha=int(alpha),
                        underline=underline,
                    )
                )
            created = Paragraph(
                runs=runs,
                tag=tag,
                tag_data=dict(item["tag_data"]),
                default_font_size=int(paragraph_font_size),
                alignment="left",
            )
            _normalize_empty_paragraph_font_size(created)
            _normalize_pending_special_paragraph_state(created)
            _finalize_pending_special_paragraph_edit(created)
            inserted.append(created)

        replacement: list[Paragraph] = []
        if not left.is_empty or not _is_empty_tag(left.tag):
            replacement.append(left)
        replacement.extend(inserted)
        if not right.is_empty or not _is_empty_tag(right.tag):
            replacement.append(right)
        if not replacement:
            replacement.append(Paragraph())

        self._document.paragraphs[paragraph_index:paragraph_index + 1] = replacement

        inserted_index = 0
        if not left.is_empty or not _is_empty_tag(left.tag):
            inserted_index = 1
        target_index = paragraph_index + inserted_index + len(inserted) - 1
        target_paragraph = self._document.paragraphs[target_index]
        target_offset = len(target_paragraph.plain_text())
        self.set_caret_from_paragraph_offset(target_index, target_offset)
        if right_text_length > 0 and target_index == paragraph_index + len(replacement) - 1:
            self.set_caret_from_paragraph_offset(target_index, max(0, target_offset - right_text_length))
        return True

    def _get_ordered_prefixed_render_number(self, paragraph_index: int) -> int:
        number = 0
        for index, paragraph in enumerate(self._document.paragraphs):
            if _prefix_requires_numbering(paragraph.tag):
                number += 1
                if index == paragraph_index:
                    return number
            else:
                number = 0
        return 1

    def break_paragraph_at_caret(self):
        paragraph_index = self._caret.paragraph_index
        paragraph = self._document.paragraphs[paragraph_index]
        paragraph_offset = self.get_caret_paragraph_offset()
        left_runs, right_runs = _split_runs(paragraph.runs, paragraph_offset)

        left = Paragraph(
            runs=left_runs,
            tag=paragraph.tag,
            tag_data=dict(paragraph.tag_data),
            default_font_size=paragraph.default_font_size,
            alignment=paragraph.alignment,
        )
        right = Paragraph(
            runs=right_runs,
            default_font_size=paragraph.default_font_size,
            alignment="left",
        )
        _prepare_paragraph_for_text_edit(left)
        _prepare_paragraph_for_text_edit(right)
        left.normalize()
        _normalize_empty_paragraph_font_size(right)
        _normalize_pending_special_paragraph_state(left)

        self._document.paragraphs[paragraph_index] = left
        self._document.paragraphs.insert(paragraph_index + 1, right)
        self.set_caret_from_paragraph_offset(paragraph_index + 1, 0)

    def handle_enter_at_caret(self, command_executor=None) -> str | None:
        paragraph_index = self._caret.paragraph_index
        command_name = None
        if command_executor is not None:
            command_name = command_executor(paragraph_index)
        if command_name is not None:
            return command_name
        self.break_paragraph_at_caret()
        return self._continue_special_paragraph_after_break(paragraph_index)

    def _transition_caret_to_input_paragraph(self, paragraph_font_size: int):
        paragraph_index = self._caret.paragraph_index
        paragraph = self._document.paragraphs[paragraph_index]
        paragraph_offset = self.get_caret_paragraph_offset()

        if paragraph.is_empty:
            _normalize_empty_paragraph_font_size(paragraph)
            _prepare_paragraph_for_text_edit(paragraph)
            self.set_caret_from_paragraph_offset(paragraph_index, 0)
            return

        left_runs, right_runs = _split_runs(paragraph.runs, paragraph_offset)
        created: list[Paragraph] = []

        if left_runs:
            left = Paragraph(
                runs=_clear_run_font_sizes(left_runs),
                default_font_size=paragraph.default_font_size,
                alignment=paragraph.alignment,
            )
            _finalize_paragraph_after_text_edit(left)
            created.append(left)

        middle = Paragraph(
            runs=[],
            default_font_size=get_default_paragraph_font_size("empty"),
            alignment="left",
        )
        middle.normalize()
        _normalize_empty_paragraph_font_size(middle)
        created.append(middle)

        if right_runs:
            right = Paragraph(
                runs=_clear_run_font_sizes(right_runs),
                default_font_size=paragraph.default_font_size,
                alignment="left",
            )
            _finalize_paragraph_after_text_edit(right)
            created.append(right)

        self._document.paragraphs[paragraph_index:paragraph_index + 1] = created
        middle_index = paragraph_index + (1 if left_runs else 0)
        self.set_caret_from_paragraph_offset(middle_index, 0)

    def delete_backward_at_caret(self) -> bool:
        paragraph_index = self._caret.paragraph_index
        paragraph = self._document.paragraphs[paragraph_index]
        paragraph_offset = self.get_caret_paragraph_offset()
        if paragraph_offset > 0:
            return self._delete_backward_within_paragraph(paragraph_index, paragraph_offset)
        return self._handle_backward_paragraph_boundary(paragraph_index)

    def delete_forward_at_caret(self) -> bool:
        paragraph_index = self._caret.paragraph_index
        paragraph = self._document.paragraphs[paragraph_index]
        paragraph_offset = self.get_caret_paragraph_offset()
        if paragraph_offset < len(paragraph.plain_text()):
            return self._delete_forward_within_paragraph(paragraph_index, paragraph_offset)
        return self._handle_forward_paragraph_boundary(paragraph_index)

    def paste_text_at_caret(
        self,
        text: str,
        *,
        paragraph_font_size: int,
        bold: bool,
        italic: bool,
        color: str,
        alpha: int,
        underline: bool = False,
    ) -> bool:
        if text is None:
            return False
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        while normalized.endswith("\n"):
            normalized = normalized[:-1]
        if normalized == "":
            return False

        target_size = int(paragraph_font_size)
        paragraph_index = self._caret.paragraph_index
        paragraph = self._prepare_caret_paragraph_for_text_input(target_size)
        paragraph_index = self._caret.paragraph_index
        paragraph_offset = self.get_caret_paragraph_offset()
        base_size = _get_carried_paragraph_font_size(paragraph, fallback_font_size=paragraph_font_size)
        inherited_tag = paragraph.tag if _is_contagious_paragraph_tag(paragraph.tag) else None
        left_runs, right_runs = _split_runs(paragraph.runs, paragraph_offset)
        parts = normalized.split("\n")
        created_paragraphs: list[Paragraph] = []

        for index, part in enumerate(parts):
            runs = []
            if part:
                runs = [
                    InlineRun(
                        text=part,
                        font_size=None,
                        bold=bold,
                        italic=italic,
                        color=color,
                        alpha=int(alpha),
                        underline=underline,
                    )
                ]

            current = Paragraph(
                runs=runs,
                tag=inherited_tag,
                tag_data=(
                    {"pending": False}
                    if inherited_tag is not None and _uses_pending_cleanup_for_tag(inherited_tag)
                    else {}
                ),
                default_font_size=base_size,
                alignment=paragraph.alignment if index == 0 else "left",
            )
            _normalize_empty_paragraph_font_size(current)
            created_paragraphs.append(current)

        created_paragraphs[0].runs = _merge_adjacent_runs(left_runs + created_paragraphs[0].runs)
        _prepare_paragraph_for_text_edit(created_paragraphs[0])
        created_paragraphs[0].normalize()
        _normalize_empty_paragraph_font_size(created_paragraphs[0])
        _finalize_pending_special_paragraph_edit(created_paragraphs[0])
        last = created_paragraphs[-1]
        last.runs = _merge_adjacent_runs(last.runs + right_runs)
        _prepare_paragraph_for_text_edit(last)
        last.normalize()
        _normalize_empty_paragraph_font_size(last)
        _finalize_pending_special_paragraph_edit(last)

        self._document.paragraphs[paragraph_index:paragraph_index + 1] = created_paragraphs
        last_index = paragraph_index + len(created_paragraphs) - 1
        last_offset = len(created_paragraphs[-1].plain_text()) - len("".join(run.text for run in right_runs))
        self.set_caret_from_paragraph_offset(last_index, last_offset)
        return True

    def execute_center_command(self, paragraph_index: int) -> bool:
        if not (0 <= paragraph_index < len(self._document.paragraphs)):
            return False

        paragraph = self._document.paragraphs[paragraph_index]
        token = "/center/"
        text = paragraph.plain_text()
        if not text.endswith(token):
            return False

        content = text[:-len(token)]
        if token in content:
            return False

        paragraph.runs = _delete_range(paragraph.runs, len(content), len(text))
        paragraph.alignment = "center"
        paragraph.normalize()
        _normalize_empty_paragraph_font_size(paragraph)
        return True

    def execute_registered_create_command(self, paragraph_index: int, *, token: str) -> bool:
        return self._execute_registered_tag_command(paragraph_index, token=token)

    def execute_contagious_enter(self, paragraph_index: int) -> bool:
        if not (0 <= paragraph_index < len(self._document.paragraphs) - 1):
            return False

        paragraph = self._document.paragraphs[paragraph_index]
        if not _is_contagious_paragraph_tag(paragraph.tag):
            return False

        next_index = paragraph_index + 1
        next_paragraph = self._document.paragraphs[next_index]
        self._configure_contagious_next_paragraph(next_paragraph, source_tag=paragraph.tag)
        self.set_caret_from_paragraph_offset(next_index, 0)
        return True

    def _continue_special_paragraph_after_break(self, paragraph_index: int) -> str | None:
        if paragraph_index < 0:
            return None
        if self.is_prefixed_paragraph(paragraph_index):
            if self.execute_contagious_enter(paragraph_index):
                paragraph = self._document.paragraphs[paragraph_index]
                return get_create_command_name(paragraph.tag)
        return None

    def cleanup_pending_special_paragraphs(self, active_paragraph_index: int | None) -> bool:
        removed = False
        index = 0
        while index < len(self._document.paragraphs):
            paragraph = self._document.paragraphs[index]
            if (
                _uses_pending_cleanup_for_tag(paragraph.tag)
                and bool(paragraph.tag_data.get("pending"))
                and paragraph.plain_text() == ""
                and index != active_paragraph_index
            ):
                self.delete_paragraph(index)
                removed = True
                if active_paragraph_index is not None and index < active_paragraph_index:
                    active_paragraph_index -= 1
                continue
            index += 1
        return removed

    def _execute_registered_tag_command(self, paragraph_index: int, *, token: str) -> bool:
        if not (0 <= paragraph_index < len(self._document.paragraphs)):
            return False

        paragraph = self._document.paragraphs[paragraph_index]
        text = paragraph.plain_text().strip()
        if text != token:
            return False
        target_tag = find_tag_for_create_command(token, from_tag=paragraph.tag)
        if target_tag is None:
            return False

        paragraph.runs = []
        paragraph.alignment = "left"
        paragraph.tag = target_tag
        paragraph.tag_data = {"pending": True} if _uses_pending_cleanup_for_tag(target_tag) else {}
        paragraph.normalize()

        next_index = paragraph_index + 1
        if 0 <= next_index < len(self._document.paragraphs):
            next_paragraph = self._document.paragraphs[next_index]
            if next_paragraph.is_empty and is_empty_tag(next_paragraph.tag):
                self.delete_paragraph(next_index)

        self.set_caret_from_paragraph_offset(paragraph_index, 0)
        return True

    def execute_fill_command(
        self,
        paragraph_index: int,
        *,
        token: str,
        fill_char: str,
        count: int,
        paragraph_font_size: int,
        color: str,
        alpha: int,
    ) -> bool:
        if not (0 <= paragraph_index < len(self._document.paragraphs)):
            return False

        paragraph = self._document.paragraphs[paragraph_index]
        text = paragraph.plain_text().strip()
        if text != token:
            return False

        fill_text = fill_char * max(1, int(count))
        paragraph.runs = [
            InlineRun(
                text=fill_text,
                font_size=None,
                bold=False,
                italic=False,
                color=color,
                alpha=int(alpha),
                underline=False,
            )
        ]
        paragraph.default_font_size = int(paragraph_font_size)
        paragraph.normalize()
        _normalize_empty_paragraph_font_size(paragraph)
        _finalize_pending_special_paragraph_edit(paragraph)
        self.set_caret_from_paragraph_offset(paragraph_index, len(fill_text))
        return True

    def execute_size_command(self, paragraph_index: int, size_value: int, content_length: int, full_length: int) -> bool:
        if not (0 <= paragraph_index < len(self._document.paragraphs)):
            return False
        paragraph = self._document.paragraphs[paragraph_index]
        paragraph.runs = _delete_range(paragraph.runs, content_length, full_length)
        paragraph.default_font_size = int(size_value)
        for run in paragraph.runs:
            run.font_size = None
        paragraph.normalize()
        _normalize_empty_paragraph_font_size(paragraph)
        return True

    def set_paragraph_font_size(self, paragraph_index: int, size_value: int) -> bool:
        if not (0 <= paragraph_index < len(self._document.paragraphs)):
            return False
        paragraph = self._document.paragraphs[paragraph_index]
        target_size = int(size_value)
        if not _is_size_rigid_text_paragraph(paragraph):
            changed = False
            for run in paragraph.runs:
                if run.font_size is not None:
                    run.font_size = None
                    changed = True
            paragraph.normalize()
            _normalize_empty_paragraph_font_size(paragraph)
            return changed
        changed = _paragraph_font_size_differs(paragraph, target_size)
        paragraph.default_font_size = target_size
        target_tag = get_text_tag_for_font_size(target_size)
        if paragraph.tag != target_tag:
            paragraph.tag = target_tag
            changed = True
        for run in paragraph.runs:
            if run.font_size is not None:
                run.font_size = None
                changed = True
        paragraph.normalize()
        _normalize_empty_paragraph_font_size(paragraph)
        return changed

    def set_paragraph_display_style(self, paragraph_index: int, **changes) -> bool:
        if not (0 <= paragraph_index < len(self._document.paragraphs)):
            return False
        paragraph = self._document.paragraphs[paragraph_index]
        display_changes = filter_display_style_changes(changes)
        if not display_changes and not any(value is None for value in changes.values()):
            return False
        return paragraph.update_display_style(**display_changes)

    def apply_display_style_to_selection(self, **changes) -> bool:
        if not self.has_selection():
            return False

        selection = self._selection
        assert selection is not None
        start, end = _ordered_carets(selection.start, selection.end)
        if start.paragraph_index != end.paragraph_index:
            return False

        paragraph_index = start.paragraph_index
        paragraph = self._document.paragraphs[paragraph_index]
        start_offset = _paragraph_offset_from_caret(paragraph, start)
        end_offset = _paragraph_offset_from_caret(paragraph, end)
        full_length = len(paragraph.plain_text())
        if start_offset != 0 or end_offset != full_length:
            return False

        changed = self.set_paragraph_display_style(paragraph_index, **changes)
        if changed:
            self.set_selection_from_paragraph_offsets(paragraph_index, 0, paragraph_index, full_length)
        return changed

    def apply_font_size_to_selection(self, size_value: int) -> bool:
        if not self.has_selection():
            return False

        selection = self._selection
        assert selection is not None
        start, end = _ordered_carets(selection.start, selection.end)
        if start.paragraph_index != end.paragraph_index:
            return False

        paragraph_index = start.paragraph_index
        paragraph = self._document.paragraphs[paragraph_index]
        start_offset = _paragraph_offset_from_caret(paragraph, start)
        end_offset = _paragraph_offset_from_caret(paragraph, end)
        if start_offset == end_offset:
            return False

        full_length = len(paragraph.plain_text())
        target_size = int(size_value)
        if start_offset == 0 and end_offset == full_length:
            changed = self.set_paragraph_font_size(paragraph_index, target_size)
            self.set_selection_from_paragraph_offsets(paragraph_index, 0, paragraph_index, full_length)
            return changed

        if not _is_size_rigid_text_paragraph(paragraph):
            left_runs, remainder = _split_runs(paragraph.runs, start_offset)
            middle_runs, right_runs = _split_runs(remainder, end_offset - start_offset)
            updated_middle = _apply_changes_to_runs(middle_runs, font_size=None)
            if updated_middle == middle_runs:
                return False
            paragraph.runs = _merge_adjacent_runs(left_runs + updated_middle + right_runs)
            paragraph.normalize()
            _normalize_empty_paragraph_font_size(paragraph)
            self.set_selection_from_paragraph_offsets(paragraph_index, start_offset, paragraph_index, end_offset)
            return True

        original_size = _get_paragraph_font_size_value(paragraph)
        if original_size == target_size:
            return False

        left_runs, remainder = _split_runs(paragraph.runs, start_offset)
        middle_runs, right_runs = _split_runs(remainder, end_offset - start_offset)
        created: list[Paragraph] = []

        if left_runs:
            left = Paragraph(
                runs=_clear_run_font_sizes(left_runs),
                default_font_size=original_size,
                alignment=paragraph.alignment,
            )
            left.normalize()
            _normalize_empty_paragraph_font_size(left)
            created.append(left)

        middle = Paragraph(
            runs=_clear_run_font_sizes(middle_runs),
            default_font_size=target_size,
            alignment=paragraph.alignment,
        )
        middle.normalize()
        _normalize_empty_paragraph_font_size(middle)
        created.append(middle)

        if right_runs:
            right = Paragraph(
                runs=_clear_run_font_sizes(right_runs),
                default_font_size=original_size,
                alignment=paragraph.alignment,
            )
            right.normalize()
            _normalize_empty_paragraph_font_size(right)
            created.append(right)

        self._document.paragraphs[paragraph_index:paragraph_index + 1] = created
        middle_index = paragraph_index + (1 if left_runs else 0)
        middle_length = len(middle.plain_text())
        self.set_selection_from_paragraph_offsets(middle_index, 0, middle_index, middle_length)
        return True

    def apply_inline_style_to_selection(self, **changes) -> bool:
        if not self.has_selection():
            return False

        selection = self._selection
        assert selection is not None
        start, end = _ordered_carets(selection.start, selection.end)
        if _compare_carets(start, end) == 0:
            return False
        start_paragraph_index = start.paragraph_index
        end_paragraph_index = end.paragraph_index
        start_offset_value = _paragraph_offset_from_caret(
            self._document.paragraphs[start_paragraph_index], start
        )
        end_offset_value = _paragraph_offset_from_caret(
            self._document.paragraphs[end_paragraph_index], end
        )

        changed = False
        for paragraph_index in range(start.paragraph_index, end.paragraph_index + 1):
            paragraph = self._document.paragraphs[paragraph_index]
            paragraph_length = len(paragraph.plain_text())

            start_offset = 0
            end_offset = paragraph_length
            if paragraph_index == start.paragraph_index:
                start_offset = _paragraph_offset_from_caret(paragraph, start)
            if paragraph_index == end.paragraph_index:
                end_offset = _paragraph_offset_from_caret(paragraph, end)

            if start_offset >= end_offset:
                continue

            left_runs, remainder = _split_runs(paragraph.runs, start_offset)
            middle_runs, right_runs = _split_runs(remainder, end_offset - start_offset)
            styled_middle = _apply_changes_to_runs(middle_runs, **changes)
            if styled_middle != middle_runs:
                changed = True
            paragraph.runs = _merge_adjacent_runs(left_runs + styled_middle + right_runs)
            paragraph.normalize()
            _normalize_empty_paragraph_font_size(paragraph)

        if changed:
            self.set_selection_from_paragraph_offsets(
                start_paragraph_index,
                start_offset_value,
                end_paragraph_index,
                end_offset_value,
            )
        return changed

    def execute_alpha_command(self, paragraph_index: int, alpha_value: int, content_length: int, full_length: int) -> bool:
        if not (0 <= paragraph_index < len(self._document.paragraphs)):
            return False
        paragraph = self._document.paragraphs[paragraph_index]
        paragraph.runs = _delete_range(paragraph.runs, content_length, full_length)
        if not paragraph.runs:
            return False
        for run in paragraph.runs:
            run.alpha = int(alpha_value)
        paragraph.normalize()
        _normalize_empty_paragraph_font_size(paragraph)
        return True

    def execute_clean_command(self, paragraph_index: int) -> bool:
        if not (0 <= paragraph_index < len(self._document.paragraphs)):
            return False

        token = "/clean/"
        paragraph = self._document.paragraphs[paragraph_index]
        text = paragraph.plain_text()
        if not text.endswith(token):
            return False

        content = text[:-len(token)]
        clean_handlers = [
            lambda: self._clean_special_paragraph_result(paragraph_index, text),
            lambda: self._clean_center_result(paragraph_index, content, len(text)),
            lambda: self._clean_current_fill_result(paragraph_index, content),
            lambda: text.strip() == token and self._clean_previous_fill_result(paragraph_index),
        ]
        for handler in clean_handlers:
            if handler():
                return True
        return False

    def _clean_special_paragraph_result(self, paragraph_index: int, text: str) -> bool:
        if text.strip() != "/clean/":
            return False
        if not (0 <= paragraph_index < len(self._document.paragraphs)):
            return False
        paragraph = self._document.paragraphs[paragraph_index]
        target_tag = find_clean_transition_tag(paragraph.tag, "/clean/")
        if target_tag is None:
            return False
        paragraph.runs = []
        paragraph.alignment = "left"
        paragraph.tag = target_tag
        paragraph.tag_data = {}
        paragraph.normalize()
        next_index = paragraph_index + 1
        if 0 <= next_index < len(self._document.paragraphs):
            next_paragraph = self._document.paragraphs[next_index]
            if next_paragraph.is_empty and _is_empty_tag(next_paragraph.tag):
                self.delete_paragraph(next_index)
                self.set_caret_from_paragraph_offset(paragraph_index, 0)
                return True
        self.set_caret_from_paragraph_offset(paragraph_index, 0)
        return True

    def get_paragraph_text(self, paragraph_index: int) -> str:
        if not (0 <= paragraph_index < len(self._document.paragraphs)):
            return ""
        return self._document.paragraphs[paragraph_index].plain_text()

    def is_fill_paragraph(self, paragraph_index: int) -> bool:
        if not (0 <= paragraph_index < len(self._document.paragraphs)):
            return False
        paragraph = self._document.paragraphs[paragraph_index]
        return _is_fill_text(paragraph.plain_text())

    def is_prefixed_paragraph(self, paragraph_index: int) -> bool:
        if not (0 <= paragraph_index < len(self._document.paragraphs)):
            return False
        return _uses_prefix_decoration(self._document.paragraphs[paragraph_index].tag)

    def _prepare_caret_paragraph_for_text_input(self, target_size: int) -> Paragraph:
        paragraph = self._document.paragraphs[self._caret.paragraph_index]
        if _should_split_paragraph_for_style_input(paragraph, target_size):
            self._transition_caret_to_input_paragraph(target_size)
            paragraph = self._document.paragraphs[self._caret.paragraph_index]
        return paragraph

    def _delete_backward_within_paragraph(self, paragraph_index: int, paragraph_offset: int) -> bool:
        paragraph = self._document.paragraphs[paragraph_index]
        paragraph.runs = _delete_range(paragraph.runs, paragraph_offset - 1, paragraph_offset)
        _finalize_paragraph_after_text_edit(paragraph)
        self.set_caret_from_paragraph_offset(paragraph_index, paragraph_offset - 1)
        return True

    def _delete_forward_within_paragraph(self, paragraph_index: int, paragraph_offset: int) -> bool:
        paragraph = self._document.paragraphs[paragraph_index]
        paragraph.runs = _delete_range(paragraph.runs, paragraph_offset, paragraph_offset + 1)
        _finalize_paragraph_after_text_edit(paragraph)
        self.set_caret_from_paragraph_offset(paragraph_index, paragraph_offset)
        return True

    def _handle_backward_paragraph_boundary(self, paragraph_index: int) -> bool:
        if self._delete_pending_empty_special_paragraph_at_caret_boundary(paragraph_index):
            return True
        if paragraph_index == 0:
            return False
        previous = self._document.paragraphs[paragraph_index - 1]
        paragraph = self._document.paragraphs[paragraph_index]
        if paragraph.is_empty:
            del self._document.paragraphs[paragraph_index]
            self.set_caret_from_paragraph_offset(paragraph_index - 1, len(previous.plain_text()))
            return True
        return self._merge_paragraph_into_previous_at_boundary(paragraph_index)

    def _handle_forward_paragraph_boundary(self, paragraph_index: int) -> bool:
        return False

    def _configure_contagious_next_paragraph(self, paragraph: Paragraph, *, source_tag: str):
        paragraph.tag = source_tag
        paragraph.tag_data = {"pending": True} if _uses_pending_cleanup_for_tag(source_tag) else {}
        paragraph.alignment = "left"
        _finalize_paragraph_after_text_edit(paragraph)

    def _delete_pending_empty_special_paragraph_at_caret_boundary(self, paragraph_index: int) -> bool:
        if not (0 <= paragraph_index < len(self._document.paragraphs)):
            return False
        paragraph = self._document.paragraphs[paragraph_index]
        if not _is_pending_empty_special_paragraph(paragraph):
            return False
        if paragraph_index == 0:
            self.delete_paragraph(paragraph_index)
        else:
            previous = self._document.paragraphs[paragraph_index - 1]
            previous_offset = len(previous.plain_text())
            self.delete_paragraph(paragraph_index)
            self.set_caret_from_paragraph_offset(paragraph_index - 1, previous_offset)
        return True

    def _merge_paragraph_into_previous_at_boundary(self, paragraph_index: int) -> bool:
        if not (0 < paragraph_index < len(self._document.paragraphs)):
            return False
        previous = self._document.paragraphs[paragraph_index - 1]
        paragraph = self._document.paragraphs[paragraph_index]
        if not _can_merge_adjacent_paragraphs(previous, paragraph):
            return False
        previous_offset = len(previous.plain_text())
        previous.runs = _merge_adjacent_runs(previous.runs + [_clone_run(run) for run in paragraph.runs])
        _finalize_paragraph_after_text_edit(previous)
        del self._document.paragraphs[paragraph_index]
        self.set_caret_from_paragraph_offset(paragraph_index - 1, previous_offset)
        return True

    def is_pending_special_paragraph(self, paragraph_index: int) -> bool:
        if not (0 <= paragraph_index < len(self._document.paragraphs)):
            return False
        paragraph = self._document.paragraphs[paragraph_index]
        if not _uses_pending_cleanup_for_tag(paragraph.tag):
            return False
        return bool(paragraph.tag_data.get("pending"))

    def clear_paragraph(self, paragraph_index: int):
        if not (0 <= paragraph_index < len(self._document.paragraphs)):
            return
        paragraph = self._document.paragraphs[paragraph_index]
        paragraph.runs = []
        paragraph.alignment = "left"
        paragraph.normalize()
        _normalize_empty_paragraph_font_size(paragraph)

    def delete_paragraph(self, paragraph_index: int):
        if not (0 <= paragraph_index < len(self._document.paragraphs)):
            return
        removed = self._document.paragraphs[paragraph_index]
        del self._document.paragraphs[paragraph_index]
        if not self._document.paragraphs:
            restored = Paragraph(
                default_font_size=removed.default_font_size,
                alignment="left",
            )
            _normalize_empty_paragraph_font_size(restored)
            self._document.paragraphs.append(restored)
            self.set_caret_from_paragraph_offset(0, 0)
            return
        target_index = min(paragraph_index, len(self._document.paragraphs) - 1)
        self.set_caret_from_paragraph_offset(target_index, 0)

    def _clean_center_result(self, paragraph_index: int, content: str, full_length: int) -> bool:
        paragraph = self._document.paragraphs[paragraph_index]
        if paragraph.alignment != "center":
            return False

        paragraph.runs = _delete_range(paragraph.runs, len(content), full_length)
        paragraph.alignment = "left"
        paragraph.normalize()
        _normalize_empty_paragraph_font_size(paragraph)
        self.set_caret_from_paragraph_offset(paragraph_index, len(content))
        return True

    def _clean_current_fill_result(self, paragraph_index: int, content: str) -> bool:
        if not _is_fill_text(content):
            return False

        self.clear_paragraph(paragraph_index)
        if self._document.paragraphs[paragraph_index].is_empty:
            self.delete_paragraph(paragraph_index)
        else:
            self.set_caret_from_paragraph_offset(paragraph_index, 0)
        return True

    def _clean_previous_fill_result(self, paragraph_index: int) -> bool:
        previous_index = paragraph_index - 1
        if previous_index < 0 or not self.is_fill_paragraph(previous_index):
            return False

        self.delete_paragraph(previous_index)
        current_index = max(0, paragraph_index - 1)
        if not (0 <= current_index < len(self._document.paragraphs)):
            return False

        self.clear_paragraph(current_index)
        next_index = current_index + 1
        if 0 <= next_index < len(self._document.paragraphs):
            next_paragraph = self._document.paragraphs[next_index]
            if next_paragraph.is_empty:
                self.delete_paragraph(next_index)

        self.set_caret_from_paragraph_offset(current_index, 0)
        return True

    def _capture_snapshot(self) -> TransactionSnapshot:
        return TransactionSnapshot(
            document=self._document.to_dict(),
            caret=_caret_to_dict(self._caret),
            selection=_selection_to_dict(self._selection),
        )

    def _restore_snapshot(self, snapshot: TransactionSnapshot):
        self._document = Document.from_dict(snapshot.document)
        self._caret = _caret_from_dict(snapshot.caret)
        self._selection = _selection_from_dict(snapshot.selection)


def _coerce_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _is_empty_tag(tag: str | None) -> bool:
    return normalize_paragraph_tag(tag) == "empty"


def _get_prefix_kind(tag: str | None) -> str | None:
    return get_paragraph_type_spec(tag).decoration.prefix_kind


def _is_prefixed_paragraph_tag(tag: str | None) -> bool:
    return uses_display_prefix(tag)


def _prefix_requires_numbering(tag: str | None) -> bool:
    return display_prefix_requires_numbering(tag)


def _prefix_uses_bullet_glyph(tag: str | None) -> bool:
    return _get_prefix_kind(tag) == "unordered_list"


def _get_plain_prefix_text(tag: str | None, *, ordered_number: int | None = None) -> str:
    return get_plain_display_prefix_text(tag, ordered_number=ordered_number)


def _is_contagious_paragraph_tag(tag: str | None) -> bool:
    return bool(get_paragraph_type_spec(tag).contagious)


def _uses_pending_cleanup_for_tag(tag: str | None) -> bool:
    spec = get_paragraph_type_spec(tag)
    return bool(spec.commands.create_command) and not bool(spec.allows_empty_persistence)


def _caret_from_paragraph_offset(document: Document, paragraph_index: int, paragraph_offset: int) -> CaretPosition:
    paragraph_index = max(0, min(paragraph_index, len(document.paragraphs) - 1))
    paragraph = document.paragraphs[paragraph_index]
    run_index, run_offset = _resolve_run_position(paragraph, paragraph_offset)
    return CaretPosition(paragraph_index=paragraph_index, run_index=run_index, offset=run_offset)


def _caret_to_dict(caret: CaretPosition) -> dict:
    return {
        "paragraph_index": int(caret.paragraph_index),
        "run_index": int(caret.run_index),
        "offset": int(caret.offset),
    }


def _caret_from_dict(payload: dict | None) -> CaretPosition:
    if not isinstance(payload, dict):
        payload = {}
    return CaretPosition(
        paragraph_index=_coerce_int(payload.get("paragraph_index"), 0),
        run_index=_coerce_int(payload.get("run_index"), 0),
        offset=_coerce_int(payload.get("offset"), 0),
    )


def _selection_to_dict(selection: SelectionRange | None) -> dict | None:
    if selection is None:
        return None
    return {
        "start": _caret_to_dict(selection.start),
        "end": _caret_to_dict(selection.end),
    }


def _selection_from_dict(payload: dict | None) -> SelectionRange | None:
    if not isinstance(payload, dict):
        return None
    return SelectionRange(
        start=_caret_from_dict(payload.get("start")),
        end=_caret_from_dict(payload.get("end")),
    )


def _ordered_carets(left: CaretPosition, right: CaretPosition) -> tuple[CaretPosition, CaretPosition]:
    if _compare_carets(left, right) <= 0:
        return left, right
    return right, left


def _compare_carets(left: CaretPosition, right: CaretPosition) -> int:
    left_key = (left.paragraph_index, left.run_index, left.offset)
    right_key = (right.paragraph_index, right.run_index, right.offset)
    if left_key < right_key:
        return -1
    if left_key > right_key:
        return 1
    return 0


def _paragraph_offset_from_caret(paragraph: Paragraph, caret: CaretPosition) -> int:
    offset = 0
    for index, run in enumerate(paragraph.runs):
        if index == caret.run_index:
            return offset + min(max(caret.offset, 0), len(run.text))
        offset += len(run.text)
    return offset


def _resolve_run_position(paragraph: Paragraph, paragraph_offset: int) -> tuple[int, int]:
    paragraph_offset = max(0, min(paragraph_offset, len(paragraph.plain_text())))
    consumed = 0
    for index, run in enumerate(paragraph.runs):
        next_consumed = consumed + len(run.text)
        if paragraph_offset <= next_consumed:
            return index, paragraph_offset - consumed
        consumed = next_consumed
    return 0, 0


def _insert_run(runs: list[InlineRun], paragraph_offset: int, insert_run: InlineRun) -> list[InlineRun]:
    left_runs, right_runs = _split_runs(runs, paragraph_offset)
    merged = left_runs + [insert_run] + right_runs
    return _merge_adjacent_runs(merged)


def _delete_range(runs: list[InlineRun], start_offset: int, end_offset: int) -> list[InlineRun]:
    left_runs, middle_runs = _split_runs(runs, start_offset)
    _, right_runs = _split_runs(middle_runs, max(0, end_offset - start_offset))
    return _merge_adjacent_runs(left_runs + right_runs)


def _split_runs(runs: list[InlineRun], paragraph_offset: int) -> tuple[list[InlineRun], list[InlineRun]]:
    paragraph_offset = max(0, paragraph_offset)
    consumed = 0
    left: list[InlineRun] = []
    right: list[InlineRun] = []
    split_done = False

    for run in runs:
        text_length = len(run.text)
        if split_done:
            right.append(_clone_run(run))
            consumed += text_length
            continue

        if paragraph_offset <= consumed:
            right.append(_clone_run(run))
        elif paragraph_offset >= consumed + text_length:
            left.append(_clone_run(run))
        else:
            cut = paragraph_offset - consumed
            if cut > 0:
                left.append(_clone_run(run, run.text[:cut]))
            if cut < text_length:
                right.append(_clone_run(run, run.text[cut:]))
            split_done = True
        consumed += text_length

    return _merge_adjacent_runs(left), _merge_adjacent_runs(right)


def _merge_adjacent_runs(runs: list[InlineRun]) -> list[InlineRun]:
    merged: list[InlineRun] = []
    for run in runs:
        if not run.text:
            continue
        if merged and _same_inline_style(merged[-1], run):
            merged[-1].text += run.text
        else:
            merged.append(_clone_run(run))
    return merged


def _same_inline_style(left: InlineRun, right: InlineRun) -> bool:
    return (
        left.font_size == right.font_size
        and left.font_family == right.font_family
        and left.bold == right.bold
        and left.italic == right.italic
        and left.color == right.color
        and left.alpha == right.alpha
        and left.underline == right.underline
    )


def _clone_run(run: InlineRun, text: str | None = None) -> InlineRun:
    return InlineRun(
        text=run.text if text is None else text,
        font_size=run.font_size,
        font_family=run.font_family,
        bold=run.bold,
        italic=run.italic,
        color=run.color,
        alpha=run.alpha,
        underline=run.underline,
    )


def _clear_run_font_sizes(runs: list[InlineRun]) -> list[InlineRun]:
    cleared: list[InlineRun] = []
    for run in runs:
        clone = _clone_run(run)
        clone.font_size = None
        cleared.append(clone)
    return _merge_adjacent_runs(cleared)


def _normalize_empty_paragraph_font_size(paragraph: Paragraph):
    if paragraph.plain_text() == "":
        paragraph.default_font_size = get_default_paragraph_font_size("empty")


def _finalize_paragraph_after_text_edit(paragraph: Paragraph):
    _prepare_paragraph_for_text_edit(paragraph)
    paragraph.normalize()
    _normalize_empty_paragraph_font_size(paragraph)
    _normalize_pending_special_paragraph_state(paragraph)


def _prepare_paragraph_for_text_edit(paragraph: Paragraph):
    return


def _uses_prefix_decoration(tag: str | None) -> bool:
    return _is_prefixed_paragraph_tag(tag)


def _finalize_pending_special_paragraph_edit(paragraph: Paragraph):
    if not _uses_pending_cleanup_for_tag(paragraph.tag):
        return
    if paragraph.plain_text():
        paragraph.tag_data = {
            **paragraph.tag_data,
            "pending": False,
        }


def _normalize_pending_special_paragraph_state(paragraph: Paragraph):
    if not _uses_pending_cleanup_for_tag(paragraph.tag):
        return
    paragraph.tag_data = {
        **paragraph.tag_data,
        "pending": paragraph.plain_text() == "",
    }


def _is_pending_empty_special_paragraph(paragraph: Paragraph) -> bool:
    return (
        _uses_pending_cleanup_for_tag(paragraph.tag)
        and bool(paragraph.tag_data.get("pending"))
        and paragraph.plain_text() == ""
    )


def _can_merge_paragraphs_after_cross_delete(left: Paragraph, right: Paragraph) -> bool:
    return _can_merge_adjacent_paragraphs(left, right)


def _can_merge_adjacent_paragraphs(left: Paragraph, right: Paragraph) -> bool:
    return (
        left.default_font_size == right.default_font_size
        and left.alignment == right.alignment
        and left.tag == right.tag
    )


def _can_inline_merge_internal_fragment(
    paragraph: Paragraph,
    fragment: dict,
    *,
    paragraph_font_size: int,
) -> bool:
    text = str(fragment.get("text", ""))
    if text == "":
        return False
    fragment_tag = normalize_paragraph_tag(fragment.get("tag"))
    if paragraph.tag != fragment_tag:
        return False
    fragment_tag_data = fragment.get("tag_data")
    if not isinstance(fragment_tag_data, dict):
        fragment_tag_data = {}
    if dict(paragraph.tag_data) != dict(fragment_tag_data):
        return False
    return _get_paragraph_font_size_value(paragraph) == int(paragraph_font_size)


def _get_carried_paragraph_font_size(paragraph: Paragraph, *, fallback_font_size: int) -> int:
    if paragraph.is_empty:
        return int(fallback_font_size)
    return _get_paragraph_font_size_value(paragraph)


def _get_paragraph_font_size_value(paragraph: Paragraph) -> int:
    return int(paragraph.default_font_size)


def _paragraph_font_size_differs(paragraph: Paragraph, target_size: int) -> bool:
    return _get_paragraph_font_size_value(paragraph) != int(target_size)


def _is_size_rigid_text_paragraph(paragraph: Paragraph) -> bool:
    spec = get_paragraph_type_spec(paragraph.tag)
    return (
        spec.uses_runs
        and spec.allows_text_input
        and spec.commands.create_command is None
    )


def _should_split_paragraph_for_style_input(paragraph: Paragraph, target_size: int) -> bool:
    if paragraph.is_empty:
        return False
    if not _is_size_rigid_text_paragraph(paragraph):
        return False
    return _paragraph_font_size_differs(paragraph, target_size)


def _apply_changes_to_runs(runs: list[InlineRun], **changes) -> list[InlineRun]:
    updated: list[InlineRun] = []
    for run in runs:
        clone = _clone_run(run)
        for key, value in changes.items():
            setattr(clone, key, value)
        updated.append(clone)
    return _merge_adjacent_runs(updated)


def _is_fill_text(text: str) -> bool:
    if not text:
        return False
    stripped = text.strip()
    if not stripped:
        return False
    return all(ch in ("█", "━") for ch in stripped)
