from __future__ import annotations

import logging

from paragraphs.builtins import build_builtin_paragraph_type_specs
from paragraphs.types import (
    BLOCK_CONTENT_KIND,
    RENDER_CUSTOM_BLOCK,
    RENDER_DECORATED_TEXT,
    RENDER_TEXT,
    ParagraphTypeSpec,
    clone_paragraph_type_spec,
    normalize_paragraph_tag,
    paragraph_type_spec_from_dict,
    paragraph_type_spec_to_dict,
)


_BUILTIN_PARAGRAPH_TYPE_SPECS = build_builtin_paragraph_type_specs()
_PARAGRAPH_TYPE_REGISTRY: dict[str, ParagraphTypeSpec] = {}
_LOGGER = logging.getLogger(__name__)


def get_registered_paragraph_type_spec(tag: str | None) -> ParagraphTypeSpec | None:
    return _PARAGRAPH_TYPE_REGISTRY.get(normalize_paragraph_tag(tag))


def get_paragraph_type_spec(tag: str | None) -> ParagraphTypeSpec:
    spec = get_registered_paragraph_type_spec(tag)
    if spec is None:
        return _PARAGRAPH_TYPE_REGISTRY["body"]
    return spec


def list_registered_paragraph_tags() -> list[str]:
    return sorted(_PARAGRAPH_TYPE_REGISTRY.keys())


def list_builtin_paragraph_tags() -> list[str]:
    return sorted(_BUILTIN_PARAGRAPH_TYPE_SPECS.keys())


def register_paragraph_type(spec: ParagraphTypeSpec):
    _PARAGRAPH_TYPE_REGISTRY[normalize_paragraph_tag(spec.tag)] = spec


def reset_runtime_paragraph_type_registry():
    _PARAGRAPH_TYPE_REGISTRY.clear()
    for tag, spec in _BUILTIN_PARAGRAPH_TYPE_SPECS.items():
        _PARAGRAPH_TYPE_REGISTRY[tag] = clone_paragraph_type_spec(spec)


def configure_runtime_paragraph_type_registry(
    *,
    user_definitions: list[dict] | None = None,
    document_definitions: list[dict] | None = None,
):
    reset_runtime_paragraph_type_registry()
    apply_paragraph_type_definitions(
        user_definitions,
        source_name="user",
        allow_builtin_override=False,
    )
    apply_paragraph_type_definitions(
        document_definitions,
        source_name="document",
        allow_builtin_override=True,
    )


def apply_paragraph_type_definitions(
    definitions: list[dict] | None,
    *,
    source_name: str = "runtime",
    allow_builtin_override: bool = True,
):
    if not isinstance(definitions, list):
        return
    seen_tags: set[str] = set()
    for index, payload in enumerate(definitions):
        spec = _build_validated_spec_from_payload(
            payload,
            index=index,
            source_name=source_name,
            allow_builtin_override=allow_builtin_override,
            seen_tags=seen_tags,
        )
        if spec is None:
            continue
        register_paragraph_type(spec)
        seen_tags.add(normalize_paragraph_tag(spec.tag))


def export_runtime_paragraph_type_definitions(*, include_builtins: bool = False) -> list[dict]:
    exported: list[dict] = []
    for tag in list_registered_paragraph_tags():
        spec = get_registered_paragraph_type_spec(tag)
        if spec is None:
            continue
        payload = paragraph_type_spec_to_dict(spec)
        builtin = _BUILTIN_PARAGRAPH_TYPE_SPECS.get(tag)
        if not include_builtins and builtin is not None:
            if paragraph_type_spec_to_dict(builtin) == payload:
                continue
        exported.append(payload)
    return exported


def list_registered_create_commands() -> list[str]:
    commands = {
        str(spec.commands.create_command).strip()
        for spec in _PARAGRAPH_TYPE_REGISTRY.values()
        if spec.commands.create_command is not None and str(spec.commands.create_command).strip()
    }
    return sorted(commands)


def list_registered_clean_commands() -> list[str]:
    commands = {
        str(spec.commands.clean_command).strip()
        for spec in _PARAGRAPH_TYPE_REGISTRY.values()
        if spec.commands.clean_command is not None and str(spec.commands.clean_command).strip()
    }
    return sorted(commands)


def find_tag_for_create_command(command: str | None, *, from_tag: str | None = None) -> str | None:
    normalized_command = str(command or "").strip()
    normalized_from_tag = normalize_paragraph_tag(from_tag) if from_tag is not None else None
    for spec in _PARAGRAPH_TYPE_REGISTRY.values():
        create_from_tag = str(spec.commands.create_from_tag or "").strip() or "*"
        if (
            spec.commands.create_command == normalized_command
            and (
                create_from_tag == "*"
                or (
                    normalized_from_tag is not None
                    and normalize_paragraph_tag(create_from_tag) == normalized_from_tag
                )
            )
        ):
            return spec.tag
    return None


def find_clean_transition_tag(tag: str | None, command: str | None = "/clean/") -> str | None:
    spec = get_paragraph_type_spec(tag)
    normalized_command = str(command or "").strip()
    if spec.commands.clean_command != normalized_command:
        return None
    if spec.commands.clean_to_tag is None:
        return None
    target = normalize_paragraph_tag(spec.commands.clean_to_tag)
    if target == normalize_paragraph_tag(spec.tag):
        return None
    return target


def get_command_token(command: str | None) -> str | None:
    if command is None:
        return None
    normalized = str(command).strip()
    return normalized or None


def get_command_name(command: str | None) -> str | None:
    normalized = get_command_token(command)
    if normalized is None:
        return None
    if normalized.startswith("/") and normalized.endswith("/") and len(normalized) >= 3:
        return normalized[1:-1].strip() or None
    return normalized.strip() or None


def get_create_command(tag: str | None) -> str | None:
    command = get_paragraph_type_spec(tag).commands.create_command
    return get_command_token(command)


def get_create_command_name(tag: str | None) -> str | None:
    return get_command_name(get_create_command(tag))


def get_clean_command(tag: str | None) -> str | None:
    command = get_paragraph_type_spec(tag).commands.clean_command
    return get_command_token(command)


def get_markdown_role(tag: str | None) -> str:
    return get_paragraph_type_spec(tag).export.markdown_role


def get_markdown_prefix(tag: str | None) -> str | None:
    return get_paragraph_type_spec(tag).export.markdown_prefix


def get_markdown_suffix(tag: str | None) -> str | None:
    return get_paragraph_type_spec(tag).export.markdown_suffix


def get_prefix_kind(tag: str | None) -> str | None:
    return get_paragraph_type_spec(tag).decoration.prefix_kind


def get_prefix_text(tag: str | None) -> str | None:
    return get_paragraph_type_spec(tag).decoration.prefix_text


def uses_display_prefix(tag: str | None) -> bool:
    prefix_kind = get_prefix_kind(tag)
    if prefix_kind in {"ordered_list", "unordered_list"}:
        return True
    prefix_text = get_prefix_text(tag)
    return prefix_text is not None and str(prefix_text).strip() != ""


def display_prefix_requires_numbering(tag: str | None) -> bool:
    return get_prefix_kind(tag) == "ordered_list"


def display_prefix_uses_bullet_glyph(tag: str | None) -> bool:
    return get_prefix_kind(tag) == "unordered_list"


def get_plain_display_prefix_text(tag: str | None, *, ordered_number: int | None = None) -> str:
    prefix_text = get_prefix_text(tag)
    if prefix_text is not None and str(prefix_text).strip():
        return str(prefix_text)
    if display_prefix_requires_numbering(tag):
        number = 1 if ordered_number is None else int(ordered_number)
        return f"{number}. "
    if display_prefix_uses_bullet_glyph(tag):
        return "- "
    return ""


def get_default_paragraph_font_size(tag: str | None = "body") -> int:
    spec = get_paragraph_type_spec(tag)
    if spec.layout.rendered_font_size is not None:
        return int(spec.layout.rendered_font_size)
    body_spec = get_paragraph_type_spec("body")
    if body_spec.layout.rendered_font_size is not None:
        return int(body_spec.layout.rendered_font_size)
    return 16


def get_prefixed_item_gap(tag: str | None, *, default: float = 4.0) -> float:
    spec = get_registered_paragraph_type_spec(tag)
    if spec is None or spec.layout.prefixed_item_gap is None:
        return float(default)
    return float(spec.layout.prefixed_item_gap)


def get_prefix_gap(tag: str | None, *, default: float = 6.0) -> float:
    spec = get_registered_paragraph_type_spec(tag)
    if spec is None or spec.layout.prefix_gap is None:
        return float(default)
    return float(spec.layout.prefix_gap)


def get_ordered_prefix_min_digits(tag: str | None, *, default: int = 3) -> int:
    spec = get_registered_paragraph_type_spec(tag)
    if spec is None or spec.layout.ordered_prefix_min_digits is None:
        return int(default)
    return int(spec.layout.ordered_prefix_min_digits)


def get_text_tag_for_font_size(font_size: int | None) -> str:
    normalized_size = _coerce_int(font_size, default=get_default_paragraph_font_size("body"))
    mapping = _font_size_to_text_tag_mapping()
    if normalized_size in mapping:
        return mapping[normalized_size]
    closest_size = min(mapping, key=lambda size: abs(size - normalized_size))
    return mapping[closest_size]


def get_exact_text_tag_for_font_size(font_size: int | None) -> str | None:
    normalized_size = _coerce_int(font_size, default=get_default_paragraph_font_size("body"))
    return _font_size_to_text_tag_mapping().get(normalized_size)


def _font_size_to_text_tag_mapping() -> dict[int, str]:
    return {
        14: "body_small",
        16: "body",
        18: "heading_5",
        20: "heading_4",
        24: "heading_3",
        28: "heading_2",
        32: "heading_1",
    }


def _coerce_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


reset_runtime_paragraph_type_registry()


def _build_validated_spec_from_payload(
    payload,
    *,
    index: int,
    source_name: str,
    allow_builtin_override: bool,
    seen_tags: set[str],
) -> ParagraphTypeSpec | None:
    if not isinstance(payload, dict):
        _warn_skip("<invalid>", source_name, "definition is not an object", index=index)
        return None

    raw_tag = payload.get("tag")
    if not isinstance(raw_tag, str) or not raw_tag.strip():
        _warn_skip("<missing>", source_name, "missing or invalid tag", index=index)
        return None
    normalized_tag = normalize_paragraph_tag(raw_tag)

    if normalized_tag in seen_tags:
        _warn_skip(normalized_tag, source_name, "duplicate tag in same source", index=index)
        return None

    if not allow_builtin_override and normalized_tag in _BUILTIN_PARAGRAPH_TYPE_SPECS:
        _warn_skip(normalized_tag, source_name, "conflicts with builtin tag", index=index)
        return None

    if not _is_valid_definition_payload(payload):
        _warn_skip(normalized_tag, source_name, "invalid field structure", index=index)
        return None

    return paragraph_type_spec_from_dict(payload)


def _is_valid_definition_payload(payload: dict) -> bool:
    if "display_name" in payload and not isinstance(payload.get("display_name"), str):
        return False
    if "content_kind" in payload and payload.get("content_kind") not in {"inline_text", BLOCK_CONTENT_KIND}:
        return False
    if "render_kind" in payload and payload.get("render_kind") not in {
        RENDER_TEXT,
        RENDER_DECORATED_TEXT,
        RENDER_CUSTOM_BLOCK,
    }:
        return False
    for key in ("uses_runs", "allows_text_input", "contagious", "allows_empty_persistence"):
        if key in payload and not isinstance(payload.get(key), bool):
            return False
    if not _is_valid_layout_payload(payload.get("layout")):
        return False
    if not _is_valid_text_style_payload(payload.get("text_style")):
        return False
    if not _is_valid_decoration_payload(payload.get("decoration")):
        return False
    if not _is_valid_commands_payload(payload.get("commands")):
        return False
    if not _is_valid_export_payload(payload.get("export")):
        return False
    return True


def _is_valid_layout_payload(payload) -> bool:
    if payload is None:
        return True
    if not isinstance(payload, dict):
        return False
    int_fields = {"rendered_font_size", "ordered_prefix_min_digits"}
    float_fields = {
        "line_height",
        "top_margin",
        "bottom_margin",
        "left_margin",
        "text_indent",
        "prefixed_item_gap",
        "prefix_gap",
    }
    bool_fields = {"expand_text_start"}
    for key, value in payload.items():
        if key in int_fields and not isinstance(value, int):
            return False
        if key in float_fields and not isinstance(value, (int, float)):
            return False
        if key in bool_fields and not isinstance(value, bool):
            return False
    return True


def _is_valid_text_style_payload(payload) -> bool:
    if payload is None:
        return True
    if not isinstance(payload, dict):
        return False
    for key in ("color", "font_family"):
        if key in payload and payload.get(key) is not None and not isinstance(payload.get(key), str):
            return False
    for key in ("bold", "italic"):
        if key in payload and payload.get(key) is not None and not isinstance(payload.get(key), bool):
            return False
    return True


def _is_valid_decoration_payload(payload) -> bool:
    if payload is None:
        return True
    if not isinstance(payload, dict):
        return False
    if "prefix_kind" in payload and payload.get("prefix_kind") is not None and not isinstance(payload.get("prefix_kind"), str):
        return False
    if "prefix_text" in payload and payload.get("prefix_text") is not None and not isinstance(payload.get("prefix_text"), str):
        return False
    if "suffix_kind" in payload and payload.get("suffix_kind") is not None and not isinstance(payload.get("suffix_kind"), str):
        return False
    if "custom_renderer" in payload and payload.get("custom_renderer") is not None and not isinstance(payload.get("custom_renderer"), str):
        return False
    for key in ("has_border", "has_background"):
        if key in payload and not isinstance(payload.get(key), bool):
            return False
    return True


def _is_valid_commands_payload(payload) -> bool:
    if payload is None:
        return True
    if not isinstance(payload, dict):
        return False
    for key in ("create_command", "create_from_tag", "clean_command", "clean_to_tag"):
        if key in payload and payload.get(key) is not None and not isinstance(payload.get(key), str):
            return False
    return True


def _is_valid_export_payload(payload) -> bool:
    if payload is None:
        return True
    if not isinstance(payload, dict):
        return False
    for key in ("markdown_role", "markdown_prefix", "markdown_suffix"):
        if key in payload and payload.get(key) is not None and not isinstance(payload.get(key), str):
            return False
    return True


def _warn_skip(tag: str, source_name: str, reason: str, *, index: int):
    _LOGGER.warning(
        "Skipping paragraph type definition tag=%s source=%s index=%s: %s",
        tag,
        source_name,
        index,
        reason,
    )
