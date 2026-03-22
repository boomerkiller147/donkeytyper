from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class InlineRun:
    text: str = ""
    font_size: int | None = None
    font_family: str | None = None
    bold: bool = False
    italic: bool = False
    color: str = "#000000"
    alpha: int = 255
    underline: bool = False

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "font_size": self.font_size,
            "font_family": self.font_family,
            "bold": self.bold,
            "italic": self.italic,
            "color": self.color,
            "alpha": self.alpha,
            "underline": self.underline,
        }

    @classmethod
    def from_dict(cls, payload: dict | None) -> "InlineRun":
        if not isinstance(payload, dict):
            payload = {}
        return cls(
            text=str(payload.get("text", "")),
            font_size=_coerce_optional_int(payload.get("font_size")),
            font_family=_coerce_optional_str(payload.get("font_family")),
            bold=bool(payload.get("bold", False)),
            italic=bool(payload.get("italic", False)),
            color=str(payload.get("color", "#000000")),
            alpha=_coerce_int(payload.get("alpha"), default=255),
            underline=bool(payload.get("underline", False)),
        )


def _coerce_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_optional_int(value) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_optional_str(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
