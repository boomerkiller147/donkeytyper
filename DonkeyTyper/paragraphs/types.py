from __future__ import annotations

from dataclasses import asdict, dataclass, field


TEXT_CONTENT_KIND = "inline_text"
BLOCK_CONTENT_KIND = "block_data"

RENDER_TEXT = "text"
RENDER_DECORATED_TEXT = "decorated_text"
RENDER_CUSTOM_BLOCK = "custom_block"


@dataclass(slots=True)
class LayoutSpec:
    rendered_font_size: int | None = None
    line_height: float | None = None
    top_margin: float | None = None
    bottom_margin: float | None = None
    left_margin: float | None = None
    text_indent: float | None = None
    prefixed_item_gap: float | None = None
    prefix_gap: float | None = None
    ordered_prefix_min_digits: int | None = None
    expand_text_start: bool = False


@dataclass(slots=True)
class DecorationSpec:
    prefix_kind: str | None = None
    prefix_text: str | None = None
    suffix_kind: str | None = None
    has_border: bool = False
    has_background: bool = False
    custom_renderer: str | None = None


@dataclass(slots=True)
class TextStyleOverrideSpec:
    color: str | None = None
    bold: bool | None = None
    italic: bool | None = None
    font_family: str | None = None


@dataclass(slots=True)
class CommandTransitionSpec:
    create_command: str | None = None
    create_from_tag: str = "*"
    clean_command: str | None = "/clean/"
    clean_to_tag: str | None = None


@dataclass(slots=True)
class ExportSpec:
    markdown_role: str = "paragraph"
    markdown_prefix: str | None = None
    markdown_suffix: str | None = None


@dataclass(slots=True)
class ParagraphTypeSpec:
    tag: str
    display_name: str
    content_kind: str = TEXT_CONTENT_KIND
    render_kind: str = RENDER_TEXT
    uses_runs: bool = True
    allows_text_input: bool = True
    contagious: bool = False
    allows_empty_persistence: bool = True
    layout: LayoutSpec = field(default_factory=LayoutSpec)
    text_style: TextStyleOverrideSpec = field(default_factory=TextStyleOverrideSpec)
    decoration: DecorationSpec = field(default_factory=DecorationSpec)
    commands: CommandTransitionSpec = field(default_factory=CommandTransitionSpec)
    export: ExportSpec = field(default_factory=ExportSpec)


def normalize_paragraph_tag(tag: str | None) -> str:
    if tag is None:
        return "empty"
    normalized = str(tag).strip()
    return normalized or "empty"


def paragraph_type_spec_to_dict(spec: ParagraphTypeSpec) -> dict:
    payload = asdict(spec)
    payload["tag"] = normalize_paragraph_tag(spec.tag)
    payload["display_name"] = str(spec.display_name)
    return payload


def paragraph_type_spec_from_dict(payload: dict | None) -> ParagraphTypeSpec:
    if not isinstance(payload, dict):
        payload = {}
    layout = payload.get("layout")
    text_style = payload.get("text_style")
    decoration = payload.get("decoration")
    commands = payload.get("commands")
    export = payload.get("export")
    normalized_tag = normalize_paragraph_tag(payload.get("tag"))
    return ParagraphTypeSpec(
        tag=normalized_tag,
        display_name=str(payload.get("display_name") or normalized_tag.replace("_", " ").title()),
        content_kind=str(payload.get("content_kind") or TEXT_CONTENT_KIND),
        render_kind=str(payload.get("render_kind") or RENDER_TEXT),
        uses_runs=bool(payload.get("uses_runs", True)),
        allows_text_input=bool(payload.get("allows_text_input", True)),
        contagious=bool(payload.get("contagious", False)),
        allows_empty_persistence=bool(payload.get("allows_empty_persistence", True)),
        layout=LayoutSpec(**_filter_dict_for_dataclass(layout, LayoutSpec)),
        text_style=TextStyleOverrideSpec(**_filter_dict_for_dataclass(text_style, TextStyleOverrideSpec)),
        decoration=DecorationSpec(**_filter_dict_for_dataclass(decoration, DecorationSpec)),
        commands=CommandTransitionSpec(**_filter_dict_for_dataclass(commands, CommandTransitionSpec)),
        export=ExportSpec(**_filter_dict_for_dataclass(export, ExportSpec)),
    )


def clone_paragraph_type_spec(spec: ParagraphTypeSpec) -> ParagraphTypeSpec:
    return paragraph_type_spec_from_dict(paragraph_type_spec_to_dict(spec))


def _filter_dict_for_dataclass(payload, cls) -> dict:
    if not isinstance(payload, dict):
        return {}
    allowed = getattr(cls, "__dataclass_fields__", {})
    return {
        key: value
        for key, value in payload.items()
        if key in allowed
    }
