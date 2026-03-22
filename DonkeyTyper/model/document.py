from __future__ import annotations

from dataclasses import dataclass, field

from .inline_run import InlineRun
from .paragraph import Paragraph


@dataclass(slots=True)
class Document:
    paragraphs: list[Paragraph] = field(default_factory=list)
    format_version: int = 2

    def __post_init__(self):
        if not self.paragraphs:
            self.paragraphs = [Paragraph()]

    def to_dict(self) -> dict:
        return {
            "format_version": self.format_version,
            "paragraphs": [paragraph.to_dict() for paragraph in self.paragraphs],
        }

    @classmethod
    def from_dict(cls, payload: dict | None) -> "Document":
        if not isinstance(payload, dict):
            payload = {}
        paragraphs_payload = payload.get("paragraphs", [])
        paragraphs = []
        if isinstance(paragraphs_payload, list):
            paragraphs = [Paragraph.from_dict(item) for item in paragraphs_payload]
        return cls(
            paragraphs=paragraphs,
            format_version=_coerce_int(payload.get("format_version"), default=2),
        )

    @classmethod
    def from_plain_text(cls, text: str, default_font_size: int = 16) -> "Document":
        normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n")
        parts = normalized.split("\n")
        paragraphs = []
        for part in parts:
            runs = []
            if part:
                runs.append(InlineRun(text=part))
            paragraphs.append(
                Paragraph(
                    runs=runs,
                    default_font_size=int(default_font_size),
                    alignment="left",
                )
            )
        return cls(paragraphs=paragraphs)


def _coerce_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
