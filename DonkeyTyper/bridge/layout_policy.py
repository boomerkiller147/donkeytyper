from __future__ import annotations

from dataclasses import dataclass

from model import Document, Paragraph
from paragraphs.registry import (
    display_prefix_requires_numbering,
    display_prefix_uses_bullet_glyph,
    get_default_paragraph_font_size,
    get_ordered_prefix_min_digits,
    get_plain_display_prefix_text,
    get_prefixed_item_gap,
    get_prefix_gap,
    get_registered_paragraph_type_spec,
    uses_display_prefix,
)


FONT_SIZE_STEPS = [14, 16, 18, 20, 24, 28, 32]
LINE_HEIGHT_MAP = {
    14: 20.0,
    16: 24.0,
    18: 26.0,
    20: 28.0,
    24: 32.0,
    28: 36.0,
    32: 40.0,
}
BODY_BOTTOM_MARGIN = 8.0
LIST_BLOCK_TOP_MARGIN = 8.0
LIST_BLOCK_BOTTOM_MARGIN = 8.0
DOCUMENT_TOP_PADDING = 12.0
READING_COLUMN_MAX_WIDTH = 960
READING_COLUMN_MIN_PADDING = 24


@dataclass(slots=True)
class BlockLayoutSpec:
    rendered_font_size: int
    line_height: float
    top_margin: float
    bottom_margin: float
    left_margin: float
    text_indent: float


@dataclass(slots=True)
class ListPrefixLayoutSpec:
    prefix_text: str
    reserve_text: str
    prefix_gap: float
    render_as_bullet: bool
    expands_text_start: bool


def build_block_layout_spec(document: Document, paragraph_index: int) -> BlockLayoutSpec:
    paragraph = document.paragraphs[paragraph_index]
    previous = document.paragraphs[paragraph_index - 1] if paragraph_index > 0 else None
    next_paragraph = (
        document.paragraphs[paragraph_index + 1]
        if paragraph_index + 1 < len(document.paragraphs)
        else None
    )
    return build_paragraph_layout_spec(
        paragraph,
        is_first_block=paragraph_index == 0,
        previous=previous,
        next_paragraph=next_paragraph,
    )


def build_paragraph_layout_spec(
    paragraph: Paragraph,
    *,
    is_first_block: bool,
    previous: Paragraph | None = None,
    next_paragraph: Paragraph | None = None,
) -> BlockLayoutSpec:
    spec = get_registered_paragraph_type_spec(paragraph.tag)
    previous_bottom_margin = _get_raw_bottom_margin(previous, next_paragraph=paragraph)
    raw_top_margin = _get_raw_top_margin(paragraph, previous=previous)

    rendered_font_size = _resolve_rendered_font_size(spec)
    line_height = _resolve_line_height(spec, rendered_font_size)

    top_margin = 0.0 if is_first_block else (previous_bottom_margin + raw_top_margin)
    bottom_margin = 0.0
    left_margin = _resolve_layout_float(spec, "left_margin", 0.0)
    text_indent = _resolve_layout_float(spec, "text_indent", 0.0)

    return BlockLayoutSpec(
        rendered_font_size=rendered_font_size,
        line_height=line_height,
        top_margin=top_margin,
        bottom_margin=bottom_margin,
        left_margin=left_margin,
        text_indent=text_indent,
    )


def build_list_prefix_text(document: Document, paragraph_index: int) -> str | None:
    layout_spec = build_list_prefix_layout_spec(document, paragraph_index)
    if layout_spec is None:
        return None
    return layout_spec.prefix_text


def build_list_prefix_layout_spec(document: Document, paragraph_index: int) -> ListPrefixLayoutSpec | None:
    paragraph = document.paragraphs[paragraph_index]
    if display_prefix_uses_bullet_glyph(paragraph.tag):
        return ListPrefixLayoutSpec(
            prefix_text="\u2022",
            reserve_text="\u2022",
            prefix_gap=get_prefix_gap(paragraph.tag),
            render_as_bullet=True,
            expands_text_start=False,
        )
    if display_prefix_requires_numbering(paragraph.tag):
        number = 1
        scan_index = paragraph_index - 1
        while scan_index >= 0 and display_prefix_requires_numbering(document.paragraphs[scan_index].tag):
            number += 1
            scan_index -= 1
        prefix_text = get_plain_display_prefix_text(paragraph.tag, ordered_number=number).rstrip()
        return ListPrefixLayoutSpec(
            prefix_text=prefix_text,
            reserve_text=build_ordered_prefix_reserve_text(
                prefix_text,
                min_digits=get_ordered_prefix_min_digits(paragraph.tag),
            ),
            prefix_gap=get_prefix_gap(paragraph.tag),
            render_as_bullet=False,
            expands_text_start=True,
        )
    if not uses_display_prefix(paragraph.tag):
        return None
    return ListPrefixLayoutSpec(
        prefix_text=get_plain_display_prefix_text(paragraph.tag),
        reserve_text=get_plain_display_prefix_text(paragraph.tag),
        prefix_gap=get_prefix_gap(paragraph.tag),
        render_as_bullet=False,
        expands_text_start=True,
    )


def get_rendered_paragraph_font_size(paragraph: Paragraph) -> int:
    return _resolve_rendered_font_size(get_registered_paragraph_type_spec(paragraph.tag))


def get_line_height_for_font_size(font_size: int) -> float:
    normalized = _normalize_font_size(font_size)
    return LINE_HEIGHT_MAP.get(normalized, 24.0)


def compute_content_side_margin(available_width: int) -> int:
    usable_width = max(0, int(available_width))
    extra_width = max(0, usable_width - READING_COLUMN_MAX_WIDTH)
    return max(READING_COLUMN_MIN_PADDING, extra_width // 2)


def build_ordered_prefix_reserve_text(prefix: str, *, min_digits: int) -> str:
    digits = max(_extract_ordered_prefix_digits(prefix), int(min_digits))
    return ("8" * digits) + "."


def compute_ordered_list_text_start(base_left_margin: float, reserved_width: float, *, prefix_gap: float) -> float:
    return float(base_left_margin) + float(reserved_width) + float(prefix_gap)


def compute_list_prefix_reserved_width(metrics, prefix_layout_spec: ListPrefixLayoutSpec) -> float:
    return float(metrics.horizontalAdvance(prefix_layout_spec.reserve_text))


def compute_list_text_start_from_spec(base_left_margin: float, metrics, prefix_layout_spec: ListPrefixLayoutSpec) -> float:
    if not prefix_layout_spec.expands_text_start:
        return float(base_left_margin)
    reserved_width = compute_list_prefix_reserved_width(metrics, prefix_layout_spec)
    return compute_ordered_list_text_start(
        base_left_margin,
        reserved_width,
        prefix_gap=prefix_layout_spec.prefix_gap,
    )


def compute_list_prefix_x(
    left_margin: float,
    prefix_width: float,
    *,
    prefix_gap: float,
    reserved_width: float | None = None,
) -> float:
    if reserved_width is None:
        reserved_width = prefix_width
    return float(left_margin) - float(reserved_width) - float(prefix_gap)


def compute_list_prefix_x_from_spec(left_margin: float, metrics, prefix_layout_spec: ListPrefixLayoutSpec) -> float:
    prefix_width = float(metrics.horizontalAdvance(prefix_layout_spec.prefix_text))
    reserved_width = compute_list_prefix_reserved_width(metrics, prefix_layout_spec)
    return compute_list_prefix_x(
        left_margin,
        prefix_width,
        prefix_gap=prefix_layout_spec.prefix_gap,
        reserved_width=reserved_width,
    )


def is_list_semantic(tag: str | None) -> bool:
    return _is_prefixed_tag(tag)


def _get_prefix_kind(tag: str | None) -> str | None:
    spec = get_registered_paragraph_type_spec(tag)
    if spec is None:
        return None
    return spec.decoration.prefix_kind


def _is_prefixed_tag(tag: str | None) -> bool:
    return _get_prefix_kind(tag) in {"ordered_list", "unordered_list"}


def _prefix_requires_numbering(tag: str | None) -> bool:
    return display_prefix_requires_numbering(tag)


def _prefix_uses_bullet_glyph(tag: str | None) -> bool:
    return display_prefix_uses_bullet_glyph(tag)


def _normalize_font_size(font_size: int | float | None) -> int:
    try:
        value = int(font_size)
    except (TypeError, ValueError):
        value = get_default_paragraph_font_size("body")
    if value in FONT_SIZE_STEPS:
        return value
    closest = FONT_SIZE_STEPS[0]
    closest_distance = abs(closest - value)
    for step in FONT_SIZE_STEPS[1:]:
        distance = abs(step - value)
        if distance < closest_distance:
            closest = step
            closest_distance = distance
    return closest


def _get_tag(paragraph: Paragraph | None) -> str | None:
    if paragraph is None:
        return None
    return paragraph.tag


def _get_raw_top_margin(paragraph: Paragraph, *, previous: Paragraph | None) -> float:
    spec = get_registered_paragraph_type_spec(paragraph.tag)
    if is_list_semantic(paragraph.tag):
        base_top_margin = _resolve_layout_float(spec, "top_margin", LIST_BLOCK_TOP_MARGIN)
        return base_top_margin if not is_list_semantic(_get_tag(previous)) else 0.0
    return _resolve_layout_float(spec, "top_margin", 0.0)


def _get_raw_bottom_margin(paragraph: Paragraph | None, *, next_paragraph: Paragraph | None) -> float:
    if paragraph is None:
        return 0.0
    spec = get_registered_paragraph_type_spec(paragraph.tag)
    if is_list_semantic(paragraph.tag):
        base_bottom_margin = _resolve_layout_float(spec, "bottom_margin", LIST_BLOCK_BOTTOM_MARGIN)
        return (
            get_prefixed_item_gap(paragraph.tag)
            if is_list_semantic(_get_tag(next_paragraph))
            else base_bottom_margin
        )
    return _resolve_layout_float(spec, "bottom_margin", BODY_BOTTOM_MARGIN)


def _resolve_rendered_font_size(spec) -> int:
    if spec is not None and spec.layout.rendered_font_size is not None:
        return int(spec.layout.rendered_font_size)
    return get_default_paragraph_font_size("body")


def _resolve_line_height(spec, rendered_font_size: int) -> float:
    if spec is not None and spec.layout.line_height is not None:
        return float(spec.layout.line_height)
    return get_line_height_for_font_size(rendered_font_size)


def _resolve_layout_float(spec, field_name: str, default: float) -> float:
    if spec is None:
        return float(default)
    value = getattr(spec.layout, field_name)
    if value is None:
        return float(default)
    return float(value)


def _extract_ordered_prefix_digits(prefix: str) -> int:
    return sum(1 for ch in prefix if ch.isdigit())
