from __future__ import annotations

from dataclasses import dataclass
import re

from model import Document, InlineRun, Paragraph
from paragraphs.registry import (
    get_markdown_prefix,
    get_markdown_role,
    get_markdown_suffix,
    get_paragraph_type_spec,
)
from paragraphs.types import normalize_paragraph_tag

ORDERED_FILL_DEFAULT_COUNT = 63
BLOCK_FILL_DEFAULT_COUNT = 54
FILL_LENGTH_TOLERANCE = 1.2
@dataclass(slots=True)
class _RenderedParagraph:
    text: str


@dataclass(slots=True)
class _MarkdownInlineStyle:
    bold: bool | None = None
    italic: bool | None = None


def render_document_to_markdown(document: Document) -> str:
    rendered: list[_RenderedParagraph] = []
    ordered_index = 0

    for paragraph in document.paragraphs:
        if _markdown_prefix_requires_numbering(paragraph.tag):
            ordered_index += 1
        else:
            ordered_index = 0

        rendered.append(_render_paragraph(paragraph, ordered_index))

    return "\n".join(current.text for current in rendered)


def _render_paragraph(paragraph: Paragraph, ordered_index: int) -> _RenderedParagraph:
    if _is_empty_tag(paragraph.tag):
        return _RenderedParagraph(text="")
    if _is_markdown_divider(paragraph):
        return _RenderedParagraph(text="---")

    inline_text = _render_inline_runs(paragraph)
    custom_prefix = get_markdown_prefix(paragraph.tag)
    custom_suffix = get_markdown_suffix(paragraph.tag)
    if custom_prefix is not None or custom_suffix is not None:
        return _RenderedParagraph(
            text=f"{custom_prefix or ''}{inline_text}{custom_suffix or ''}"
        )

    markdown_prefix = _get_markdown_prefix_text(paragraph.tag, ordered_number=ordered_index)
    if _has_markdown_prefix(paragraph.tag):
        return _RenderedParagraph(text=f"{markdown_prefix}{inline_text}")

    heading_level = _get_heading_level(paragraph.tag)
    if heading_level is not None:
        prefix = "#" * heading_level
        return _RenderedParagraph(text=f"{prefix} {inline_text}".rstrip())

    body_text = inline_text
    if _is_body_markdown_tag(paragraph.tag):
        body_text = _escape_plain_paragraph_prefix(paragraph.plain_text(), body_text)
    return _RenderedParagraph(text=body_text)


def _render_inline_runs(paragraph: Paragraph) -> str:
    paragraph_style = _resolve_markdown_inline_style(paragraph)
    return "".join(_render_inline_run(run, paragraph_style) for run in paragraph.runs)


def _render_inline_run(run: InlineRun, paragraph_style: _MarkdownInlineStyle) -> str:
    if not run.text:
        return ""
    text = _escape_inline_text(run.text)
    resolved_bold = paragraph_style.bold if paragraph_style.bold is not None else run.bold
    resolved_italic = paragraph_style.italic if paragraph_style.italic is not None else run.italic
    if resolved_bold and resolved_italic:
        return f"***{text}***"
    if resolved_bold:
        return f"**{text}**"
    if resolved_italic:
        return f"*{text}*"
    return text


def _resolve_markdown_inline_style(paragraph: Paragraph) -> _MarkdownInlineStyle:
    paragraph_spec = get_paragraph_type_spec(paragraph.tag)
    paragraph_style = paragraph.get_display_style()
    return _MarkdownInlineStyle(
        bold=_resolve_optional_bool(paragraph_style, "bold", paragraph_spec.text_style.bold),
        italic=_resolve_optional_bool(paragraph_style, "italic", paragraph_spec.text_style.italic),
    )


def _resolve_optional_bool(display_overrides: dict, key: str, paragraph_default):
    if key in display_overrides:
        return display_overrides[key]
    return paragraph_default


def _escape_inline_text(text: str) -> str:
    replacements = {
        "\\": "\\\\",
        "`": "\\`",
        "*": "\\*",
        "_": "\\_",
        "[": "\\[",
        "]": "\\]",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return text


def _escape_plain_paragraph_prefix(raw_text: str, rendered_text: str) -> str:
    if not raw_text:
        return rendered_text
    if re.match(r"^\d+\.\s", raw_text):
        return "\\" + rendered_text
    if raw_text[0] in {"#", ">", "-", "+", "*"}:
        return "\\" + rendered_text
    return rendered_text


def _is_markdown_divider(paragraph: Paragraph) -> bool:
    if not _is_body_markdown_tag(paragraph.tag):
        return False

    stripped = paragraph.plain_text().strip()
    if len(stripped) < 3:
        return False
    if set(stripped) == {"-"}:
        return True
    if set(stripped) == {"━"}:
        return len(stripped) <= int(ORDERED_FILL_DEFAULT_COUNT * FILL_LENGTH_TOLERANCE)
    if set(stripped) == {"█"}:
        return len(stripped) <= int(BLOCK_FILL_DEFAULT_COUNT * FILL_LENGTH_TOLERANCE)
    return False

def _is_empty_tag(tag: str | None) -> bool:
    return normalize_paragraph_tag(tag) == "empty"


def _is_body_markdown_tag(tag: str | None) -> bool:
    return get_markdown_role(tag) == "body"


def _markdown_prefix_requires_numbering(tag: str | None) -> bool:
    return get_markdown_role(tag) == "ordered_item"


def _has_markdown_prefix(tag: str | None) -> bool:
    return get_markdown_role(tag) in {"ordered_item", "unordered_item"}


def _get_markdown_prefix_text(tag: str | None, *, ordered_number: int | None = None) -> str:
    if _markdown_prefix_requires_numbering(tag):
        number = 1 if ordered_number is None else int(ordered_number)
        return f"{number}. "
    if _has_markdown_prefix(tag):
        return "- "
    return ""


def _get_heading_level(tag: str | None) -> int | None:
    markdown_role = get_markdown_role(tag)
    if not markdown_role.startswith("heading_"):
        return None
    try:
        return int(markdown_role.rsplit("_", 1)[-1])
    except (TypeError, ValueError):
        return None
