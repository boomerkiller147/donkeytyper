from __future__ import annotations

from dataclasses import dataclass, field

from paragraphs.registry import (
    get_paragraph_type_spec,
    get_text_tag_for_font_size,
)
from paragraphs.types import normalize_paragraph_tag

from .inline_run import InlineRun


_DISPLAY_STYLE_KEYS = ("color", "bold", "italic", "font_family")


@dataclass(slots=True, init=False)
class Paragraph:
    runs: list[InlineRun] = field(default_factory=list)
    tag: str = "empty"
    tag_data: dict = field(default_factory=dict)
    default_font_size: int = 16
    alignment: str = "left"
    is_empty: bool = True

    def __init__(
        self,
        runs: list[InlineRun] | None = None,
        *,
        tag: str = "empty",
        tag_data: dict | None = None,
        default_font_size: int = 16,
        alignment: str = "left",
        is_empty: bool = True,
    ):
        self.runs = list(runs or [])
        self.tag = _coerce_tag(tag)
        self.tag_data = _coerce_dict(tag_data)
        self.default_font_size = _coerce_int(default_font_size, default=16)
        self.alignment = str(alignment)
        self.is_empty = bool(is_empty)
        self.normalize()

    def __post_init__(self):
        self.normalize()

    def normalize(self):
        self.runs = [run for run in self.runs if run.text != ""]
        if self.runs:
            self.is_empty = False
            if _is_empty_tag(self.tag):
                self.tag = get_text_tag_for_font_size(self.default_font_size)
        else:
            self.is_empty = True
            spec = get_paragraph_type_spec(self.tag)
            should_fall_back_to_empty = (
                (
                    spec.uses_runs
                    and spec.allows_text_input
                    and spec.commands.create_command is None
                    and not _is_empty_tag(self.tag)
                )
                or (
                    not spec.allows_empty_persistence
                    and not bool(self.tag_data.get("pending"))
                )
            )
            if should_fall_back_to_empty:
                self.tag = "empty"
                self.tag_data = {}

    def plain_text(self) -> str:
        return "".join(run.text for run in self.runs)

    def get_display_style(self) -> dict:
        return _normalize_display_style_payload(self.tag_data.get("display_style"))

    def set_display_style(self, style: dict | None):
        normalized = _normalize_display_style_payload(style)
        if normalized:
            self.tag_data = {
                **self.tag_data,
                "display_style": normalized,
            }
            return
        if "display_style" not in self.tag_data:
            return
        updated = dict(self.tag_data)
        updated.pop("display_style", None)
        self.tag_data = updated

    def update_display_style(self, **changes) -> bool:
        current_style = self.get_display_style()
        next_style = dict(current_style)
        for key, value in changes.items():
            if value is None:
                next_style.pop(key, None)
            else:
                next_style[key] = value
        self.set_display_style(next_style)
        return self.get_display_style() != current_style

    def to_dict(self) -> dict:
        self.normalize()
        return {
            "runs": [run.to_dict() for run in self.runs],
            "tag": self.tag,
            "tag_data": dict(self.tag_data),
            "default_font_size": self.default_font_size,
            "alignment": self.alignment,
            "is_empty": self.is_empty,
        }

    @classmethod
    def from_dict(cls, payload: dict | None) -> "Paragraph":
        if not isinstance(payload, dict):
            payload = {}
        runs_payload = payload.get("runs", [])
        runs = []
        if isinstance(runs_payload, list):
            runs = [InlineRun.from_dict(item) for item in runs_payload]
        paragraph = cls(
            runs=runs,
            tag=_coerce_tag(payload.get("tag")),
            tag_data=_coerce_dict(payload.get("tag_data")),
            default_font_size=_coerce_int(payload.get("default_font_size"), default=16),
            alignment=str(payload.get("alignment", "left")),
            is_empty=bool(payload.get("is_empty", False)),
        )
        paragraph.normalize()
        return paragraph


def _coerce_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_optional_str(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _coerce_tag(value) -> str:
    tag = _coerce_optional_str(value)
    return normalize_paragraph_tag(tag)


def _is_empty_tag(tag: str | None) -> bool:
    return normalize_paragraph_tag(tag) == "empty"


def _coerce_dict(value) -> dict:
    if not isinstance(value, dict):
        return {}
    return dict(value)


def list_display_style_keys() -> tuple[str, ...]:
    return _DISPLAY_STYLE_KEYS


def is_display_style_key(key: str) -> bool:
    return key in _DISPLAY_STYLE_KEYS


def filter_display_style_changes(changes: dict | None) -> dict:
    if not isinstance(changes, dict):
        return {}
    return {
        key: value
        for key, value in changes.items()
        if is_display_style_key(key)
    }


def _normalize_display_style_payload(value) -> dict:
    value = filter_display_style_changes(value)
    normalized: dict = {}
    color = value.get("color")
    if color is not None:
        normalized["color"] = str(color)
    font_family = value.get("font_family")
    if font_family is not None:
        text = str(font_family).strip()
        if text:
            normalized["font_family"] = text
    for key in ("bold", "italic"):
        if key in value:
            normalized[key] = bool(value.get(key))
    return normalized
