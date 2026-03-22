from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor, QTextFormat

from model import Document, InlineRun, Paragraph
from paragraphs.registry import get_paragraph_type_spec

_BLOCK_TAG_PROPERTY = int(QTextFormat.Property.UserProperty) + 1

_EMPTY_PARAGRAPH_PLACEHOLDER = "\u200b"


def extract_document_from_editor(editor) -> Document:
    qt_document = editor.document()
    paragraphs: list[Paragraph] = []

    block = qt_document.firstBlock()
    while block.isValid():
        paragraphs.append(_extract_paragraph(block))
        block = block.next()

    return Document(paragraphs=paragraphs)


def _extract_paragraph(block) -> Paragraph:
    runs: list[InlineRun] = []
    iterator = block.begin()
    default_font_size = 16

    while not iterator.atEnd():
        fragment = iterator.fragment()
        if fragment.isValid() and fragment.length() > 0:
            text = fragment.text()
            if text == _EMPTY_PARAGRAPH_PLACEHOLDER:
                iterator += 1
                continue
            char_format = fragment.charFormat()
            color = char_format.foreground().color()
            font_size = char_format.fontPointSize()
            if font_size <= 0:
                font_size = char_format.font().pointSizeF()
            if font_size <= 0:
                font_size = default_font_size
            else:
                font_size = int(round(font_size))
                if not runs:
                    default_font_size = font_size

            runs.append(
                InlineRun(
                    text=text,
                    font_size=font_size,
                    font_family=char_format.font().family() or None,
                    bold=char_format.fontWeight() >= 700,
                    italic=char_format.fontItalic(),
                    color=color.name() if color.isValid() else "#000000",
                    alpha=color.alpha() if color.isValid() else 255,
                    underline=char_format.fontUnderline(),
                )
            )
        iterator += 1

    alignment = _extract_alignment(block)
    block_format = QTextCursor(block).blockFormat()
    tag = block_format.stringProperty(_BLOCK_TAG_PROPERTY)
    tag_data = {}
    if _uses_pending_cleanup(tag) and not runs:
        tag_data = {"pending": True}
    paragraph = Paragraph(
        runs=runs,
        tag=tag,
        tag_data=tag_data,
        default_font_size=default_font_size,
        alignment=alignment,
        is_empty=(not runs),
    )
    paragraph.normalize()
    if not runs:
        paragraph.is_empty = True
    if _uses_pending_cleanup(paragraph.tag):
        paragraph.tag_data = {"pending": paragraph.plain_text() == ""}
    return paragraph


def _extract_alignment(block) -> str:
    alignment = QTextCursor(block).blockFormat().alignment()
    if alignment & Qt.AlignHCenter:
        return "center"
    if alignment & Qt.AlignRight:
        return "right"
    return "left"


def _uses_pending_cleanup(tag: str | None) -> bool:
    spec = get_paragraph_type_spec(tag)
    return bool(spec.commands.create_command) and not bool(spec.allows_empty_persistence)
