"""Loading and merging VS Code settings YAML files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from .models import RuleError


def _merge_mapping(
    target: dict[str, Any],
    incoming: dict[Any, Any],
    source: Path,
    sources: dict[str, Path],
    key_path: tuple[str, ...] = (),
) -> None:
    """Recursively merge mappings, rejecting duplicate leaf settings."""
    for key, value in incoming.items():
        if not isinstance(key, str) or not key.strip():
            raise RuleError(f"{source}: setting names must be non-empty strings")

        full_path = (*key_path, key)
        setting_name = ".".join(full_path)
        if key not in target:
            sources[setting_name] = source
            if isinstance(value, dict):
                target[key] = {}
                _merge_mapping(target[key], value, source, sources, full_path)
            else:
                target[key] = value
            continue

        existing = target[key]
        if isinstance(existing, dict) and isinstance(value, dict):
            _merge_mapping(existing, value, source, sources, full_path)
            continue

        raise RuleError(
            f"{source}: duplicate setting {setting_name!r} "
            f"(already defined in {sources[setting_name]})"
        )


def load_settings(settings_dir: Path) -> dict[str, Any]:
    """Load and recursively merge VS Code settings mappings."""
    if not settings_dir.is_dir():
        raise RuleError(f"settings directory not found: {settings_dir}")

    settings: dict[str, Any] = {}
    sources: dict[str, Path] = {}
    for path in sorted(settings_dir.rglob("*.y*ml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise RuleError(f"{path}: invalid YAML — {exc}") from exc

        if data is None:
            continue
        if not isinstance(data, dict):
            raise RuleError(f"{path}: settings document must be a mapping")
        _merge_mapping(settings, data, path, sources)

    try:
        json.dumps(settings, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise RuleError(
            f"{settings_dir}: settings must contain JSON-compatible values: {exc}"
        ) from exc
    return settings
