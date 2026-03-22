from __future__ import annotations

import sys
from dataclasses import dataclass

from .document_file_format import load_dty_payload
from model import Document


@dataclass(slots=True)
class LoadedDocumentSession:
    path: str
    document: Document
    paragraph_type_definitions: list[dict]
    ui_state: dict | None
    active_slot: int | None
    slot_states: list[dict]
    loaded_from_model: bool


def load_document_session(
    path: str,
    *,
    fallback_ui_state: dict,
    slot_count: int,
    sanitize_ui_state,
    default_font_size: int,
) -> LoadedDocumentSession:
    if path.lower().endswith(".dty"):
        return _load_dty_session(
            path,
            fallback_ui_state=fallback_ui_state,
            slot_count=slot_count,
            sanitize_ui_state=sanitize_ui_state,
            default_font_size=default_font_size,
        )
    return _load_plain_text_session(
        path,
        fallback_ui_state=fallback_ui_state,
        slot_count=slot_count,
        sanitize_ui_state=sanitize_ui_state,
        default_font_size=default_font_size,
    )


def _load_dty_session(
    path: str,
    *,
    fallback_ui_state: dict,
    slot_count: int,
    sanitize_ui_state,
    default_font_size: int,
) -> LoadedDocumentSession:
    try:
        payload = load_dty_payload(path)
    except Exception:
        text = _read_text_with_fallback(path)
        return _build_plain_text_session(
            path,
            text=text,
            fallback_ui_state=fallback_ui_state,
            slot_count=slot_count,
            sanitize_ui_state=sanitize_ui_state,
            default_font_size=default_font_size,
        )

    if not isinstance(payload, dict):
        payload = {}
    document_payload = payload.get("document")
    if isinstance(document_payload, dict):
        document = Document.from_dict(document_payload)
        loaded_from_model = True
    elif isinstance(payload.get("paragraphs"), list):
        document = Document.from_dict(payload)
        loaded_from_model = True
    else:
        document = Document()
        loaded_from_model = False
    return LoadedDocumentSession(
        path=path,
        document=document,
        paragraph_type_definitions=_coerce_definition_list(
            payload.get("paragraph_type_definitions")
        ),
        ui_state=payload.get("ui_state"),
        active_slot=_parse_active_slot(payload.get("active_slot"), slot_count),
        slot_states=_restore_slot_states(
            payload.get("slot_states"),
            fallback_ui_state=fallback_ui_state,
            slot_count=slot_count,
            sanitize_ui_state=sanitize_ui_state,
        ),
        loaded_from_model=loaded_from_model,
    )


def _load_plain_text_session(
    path: str,
    *,
    fallback_ui_state: dict,
    slot_count: int,
    sanitize_ui_state,
    default_font_size: int,
) -> LoadedDocumentSession:
    text = _read_text_with_fallback(path)
    return _build_plain_text_session(
        path,
        text=text,
        fallback_ui_state=fallback_ui_state,
        slot_count=slot_count,
        sanitize_ui_state=sanitize_ui_state,
        default_font_size=default_font_size,
    )


def _build_plain_text_session(
    path: str,
    *,
    text: str,
    fallback_ui_state: dict,
    slot_count: int,
    sanitize_ui_state,
    default_font_size: int,
) -> LoadedDocumentSession:
    sanitized_fallback = sanitize_ui_state(fallback_ui_state)
    return LoadedDocumentSession(
        path=path,
        document=Document.from_plain_text(text, default_font_size=default_font_size),
        paragraph_type_definitions=[],
        ui_state=sanitized_fallback,
        active_slot=None,
        slot_states=[dict(sanitized_fallback) for _ in range(slot_count)],
        loaded_from_model=True,
    )


def _read_text_with_fallback(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        with open(path, "r", encoding=sys.getdefaultencoding(), errors="replace") as f:
            return f.read()


def _restore_slot_states(
    payload,
    *,
    fallback_ui_state: dict,
    slot_count: int,
    sanitize_ui_state,
) -> list[dict]:
    restored = [sanitize_ui_state(fallback_ui_state) for _ in range(slot_count)]
    if not isinstance(payload, list):
        return restored
    for index in range(min(len(restored), len(payload))):
        restored[index] = sanitize_ui_state(payload[index])
    return restored


def _parse_active_slot(value, slot_count: int) -> int | None:
    try:
        index = int(value)
    except (TypeError, ValueError):
        return None
    if 0 <= index < slot_count:
        return index
    return None


def _coerce_definition_list(value) -> list[dict]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]
