from __future__ import annotations

import json
import logging
import os


DEFAULT_CONFIG_FILENAME = "paragraph_types.json"
CONFIG_DEFINITIONS_KEY = "definitions"
CONFIG_PATH_ENV = "DONKEYTYPER_PARAGRAPH_TYPES"


_LOGGER = logging.getLogger(__name__)


def get_default_paragraph_type_config_path() -> str:
    package_dir = os.path.dirname(os.path.abspath(__file__))
    donkeytyper_dir = os.path.dirname(package_dir)
    app_root = os.path.dirname(donkeytyper_dir)
    return os.path.join(app_root, "paragraph_types", DEFAULT_CONFIG_FILENAME)


def resolve_paragraph_type_config_path(explicit_path: str | None = None) -> str:
    if explicit_path:
        return explicit_path
    env_path = os.environ.get(CONFIG_PATH_ENV, "").strip()
    if env_path:
        return env_path
    return get_default_paragraph_type_config_path()


def load_paragraph_type_definitions_from_file(path: str) -> list[dict]:
    if not path or not os.path.isfile(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except (OSError, ValueError, json.JSONDecodeError):
        _LOGGER.warning("Failed to load paragraph type config from %s; using builtins only", path)
        return []
    return _extract_definition_list(payload)


def load_user_paragraph_type_definitions(explicit_path: str | None = None) -> list[dict]:
    return load_paragraph_type_definitions_from_file(
        resolve_paragraph_type_config_path(explicit_path)
    )


def _extract_definition_list(payload) -> list[dict]:
    if not isinstance(payload, dict):
        _LOGGER.warning("Ignoring paragraph type config because top-level JSON value is not an object")
        return []
    definitions = payload.get(CONFIG_DEFINITIONS_KEY, [])
    if definitions is None:
        return []
    if not isinstance(definitions, list):
        _LOGGER.warning("Ignoring paragraph type config because 'definitions' is not a list")
        return []
    return [item for item in definitions if isinstance(item, dict)]
