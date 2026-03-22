from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QTextBlockFormat, QTextCharFormat, QTextCursor, QTextFormat

from model import Document
from paragraphs.registry import get_paragraph_type_spec
from .layout_policy import (
    build_block_layout_spec,
    build_list_prefix_layout_spec,
    compute_list_text_start_from_spec,
)


_ALIGNMENT_MAP = {
    "left": Qt.AlignLeft,
    "center": Qt.AlignHCenter,
    "right": Qt.AlignRight,
}

_BLOCK_TAG_PROPERTY = int(QTextFormat.Property.UserProperty) + 1

_EMPTY_PARAGRAPH_PLACEHOLDER = "\u200b"


@dataclass(slots=True)
class ParagraphDisplayStyle:
    font_size: int
    color: str | None = None
    bold: bool | None = None
    italic: bool | None = None
    font_family: str | None = None


def render_document_to_editor(editor, document: Document):
    editor.blockSignals(True)
    try:
        editor.document().setDocumentMargin(0)
        editor.clear()
        cursor = editor.textCursor()
        cursor.movePosition(QTextCursor.Start)

        for index, paragraph in enumerate(document.paragraphs):
            if index > 0:
                cursor.insertBlock()

            layout_spec = build_block_layout_spec(document, index)
            rendered_font_size = layout_spec.rendered_font_size
            prefix_layout_spec = build_list_prefix_layout_spec(document, index)
            cursor.setBlockFormat(
                _build_block_format(
                    editor,
                    cursor.blockFormat(),
                    paragraph,
                    layout_spec,
                    prefix_layout_spec=prefix_layout_spec,
                )
            )
            block_format = cursor.blockFormat()
            block_format.setProperty(_BLOCK_TAG_PROPERTY, paragraph.tag)
            cursor.setBlockFormat(block_format)
            cursor.setCharFormat(_build_paragraph_char_format(rendered_font_size))
            if paragraph.runs:
                display_style = _resolve_paragraph_display_style(paragraph, rendered_font_size)
                for run in paragraph.runs:
                    cursor.insertText(
                        run.text,
                        _build_char_format(
                            run,
                            display_style,
                        ),
                    )
            else:
                cursor.insertText(
                    _EMPTY_PARAGRAPH_PLACEHOLDER,
                    _build_paragraph_char_format(rendered_font_size, alpha=0),
                )

        cursor.movePosition(QTextCursor.Start)
        editor.setTextCursor(cursor)
    finally:
        editor.blockSignals(False)


def _build_block_format(
    editor,
    block_format: QTextBlockFormat,
    paragraph,
    layout_spec,
    *,
    prefix_layout_spec,
) -> QTextBlockFormat:
    block_format.setAlignment(_ALIGNMENT_MAP.get(paragraph.alignment, Qt.AlignLeft))
    left_margin = float(layout_spec.left_margin)
    if prefix_layout_spec is not None and prefix_layout_spec.expands_text_start:
        font = QFont(editor.font().family(), int(layout_spec.rendered_font_size))
        metrics = QFontMetricsF(font)
        left_margin = compute_list_text_start_from_spec(
            left_margin,
            metrics,
            prefix_layout_spec,
        )
    block_format.setLeftMargin(left_margin)
    block_format.setTextIndent(float(layout_spec.text_indent))
    block_format.setTopMargin(float(layout_spec.top_margin))
    block_format.setBottomMargin(float(layout_spec.bottom_margin))
    height_type = QTextBlockFormat.LineHeightTypes.MinimumHeight
    block_format.setLineHeight(float(layout_spec.line_height), int(height_type.value))
    return block_format


def _build_char_format(run, display_style: ParagraphDisplayStyle) -> QTextCharFormat:
    char_format = QTextCharFormat()
    char_format.setFontPointSize(display_style.font_size)
    resolved_family = display_style.font_family or run.font_family
    if resolved_family:
        font = char_format.font()
        font.setFamily(resolved_family)
        char_format.setFont(font)
    resolved_bold = display_style.bold if display_style.bold is not None else run.bold
    resolved_italic = display_style.italic if display_style.italic is not None else run.italic
    char_format.setFontWeight(700 if resolved_bold else 400)
    char_format.setFontItalic(bool(resolved_italic))
    char_format.setFontUnderline(run.underline)

    resolved_color = display_style.color or run.color
    color = QColor(resolved_color)
    if not color.isValid():
        color = QColor("#000000")
    color.setAlpha(max(0, min(int(run.alpha), 255)))
    char_format.setForeground(color)
    return char_format


def _build_paragraph_char_format(default_font_size: int, *, alpha: int = 255) -> QTextCharFormat:
    char_format = QTextCharFormat()
    char_format.setFontPointSize(default_font_size)
    color = QColor("#000000")
    color.setAlpha(max(0, min(int(alpha), 255)))
    char_format.setForeground(color)
    return char_format


def _resolve_paragraph_display_style(paragraph, default_font_size: int) -> ParagraphDisplayStyle:
    paragraph_spec = get_paragraph_type_spec(paragraph.tag)
    definition_style = _resolve_definition_display_style(paragraph_spec, default_font_size)
    paragraph_style = _get_paragraph_display_truth(paragraph)
    return ParagraphDisplayStyle(
        font_size=definition_style.font_size,
        color=paragraph_style.get("color") or definition_style.color,
        bold=_resolve_optional_bool(paragraph_style, "bold", definition_style.bold),
        italic=_resolve_optional_bool(paragraph_style, "italic", definition_style.italic),
        font_family=paragraph_style.get("font_family") or definition_style.font_family,
    )


def _resolve_definition_display_style(paragraph_spec, default_font_size: int) -> ParagraphDisplayStyle:
    return ParagraphDisplayStyle(
        font_size=int(default_font_size),
        color=paragraph_spec.text_style.color,
        bold=paragraph_spec.text_style.bold,
        italic=paragraph_spec.text_style.italic,
        font_family=paragraph_spec.text_style.font_family,
    )


def _get_paragraph_display_truth(paragraph) -> dict:
    return paragraph.get_display_style()


def _resolve_optional_bool(display_overrides: dict, key: str, paragraph_default):
    if key in display_overrides:
        return display_overrides[key]
    return paragraph_default
