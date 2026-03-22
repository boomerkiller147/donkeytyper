from __future__ import annotations

import json


CURRENT_DTY_FORMAT_VERSION = 3


def load_dty_payload(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        return {}
    return payload


def save_dty_payload(path: str, payload: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def build_dty_payload(
    *,
    document: dict,
    paragraph_type_definitions: list[dict],
    ui_state: dict,
    active_slot,
    slot_states: list[dict],
) -> dict:
    return {
        "format_version": CURRENT_DTY_FORMAT_VERSION,
        "document": document,
        "paragraph_type_definitions": list(paragraph_type_definitions),
        "ui_state": dict(ui_state),
        "active_slot": active_slot,
        "slot_states": [dict(state) for state in slot_states],
    }
