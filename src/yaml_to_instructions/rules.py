"""Loading and validation for instruction rule YAML files."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from .models import KNOWN_RULE_KEYS, Rule, RuleError, SENTINEL_GLOB


def _as_str_list(value: Any, field_name: str, source: Path) -> tuple[str, ...]:
    """Normalize a scalar or sequence into a tuple of strings."""
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (list, tuple)):
        out: list[str] = []
        for item in value:
            if not isinstance(item, str):
                raise RuleError(
                    f"{source}: '{field_name}' must contain only strings, "
                    f"got {type(item).__name__}"
                )
            out.append(item)
        return tuple(out)
    raise RuleError(
        f"{source}: '{field_name}' must be a string or a list of strings, "
        f"got {type(value).__name__}"
    )


def parse_rule(data: Any, source: Path) -> Rule:
    """Validate a parsed YAML document and create a :class:`Rule`."""
    if not isinstance(data, dict):
        raise RuleError(f"{source}: top level must be a mapping")

    unknown = set(data) - KNOWN_RULE_KEYS
    if unknown:
        raise RuleError(
            f"{source}: unknown key(s): {', '.join(sorted(unknown))}. "
            f"Allowed: {', '.join(sorted(KNOWN_RULE_KEYS))}"
        )

    rule_id = data.get("id")
    if not isinstance(rule_id, str) or not rule_id.strip():
        raise RuleError(f"{source}: 'id' is required and must be a non-empty string")
    rule_id = rule_id.strip()
    if not re.fullmatch(r"[A-Za-z0-9._-]+", rule_id):
        raise RuleError(
            f"{source}: 'id' may only contain letters, digits, '.', '_' and '-', "
            f"got {rule_id!r}"
        )

    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        raise RuleError(f"{source}: 'title' is required and must be a non-empty string")

    body = data.get("body")
    if not isinstance(body, str) or not body.strip():
        raise RuleError(f"{source}: 'body' is required and must be a non-empty string")

    always = bool(data.get("always", False))
    apply_to = _as_str_list(data.get("apply_to"), "apply_to", source)
    if always and apply_to:
        raise RuleError(
            f"{source}: 'always: true' and 'apply_to' are mutually exclusive — "
            "an always-on file is injected for every path"
        )
    if not always and not apply_to:
        apply_to = (SENTINEL_GLOB,)

    for glob in apply_to:
        if glob.startswith("!"):
            raise RuleError(
                f"{source}: negation globs ('!{glob[1:]}') are unreliable — "
                "list positive globs instead"
            )

    enabled = data.get("enabled", True)
    if not isinstance(enabled, bool):
        raise RuleError(f"{source}: 'enabled' must be a boolean")

    return Rule(
        id=rule_id,
        title=title.strip(),
        body=body.strip() + "\n",
        apply_to=apply_to,
        always=always,
        exclude_agent=_as_str_list(data.get("exclude_agent"), "exclude_agent", source),
        enabled=enabled,
        notes=str(data.get("notes", "") or ""),
        source=source,
    )


def load_rules(rules_dir: Path) -> list[Rule]:
    """Recursively load every YAML rule file under ``rules_dir``."""
    if not rules_dir.is_dir():
        raise RuleError(f"rules directory not found: {rules_dir}")

    rules: list[Rule] = []
    seen: dict[str, Path] = {}
    for path in sorted(rules_dir.rglob("*.y*ml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise RuleError(f"{path}: invalid YAML — {exc}") from exc

        if data is None:
            continue
        documents = data if isinstance(data, list) else [data]
        for document in documents:
            rule = parse_rule(document, path)
            if rule.id in seen:
                raise RuleError(
                    f"{path}: duplicate id {rule.id!r} "
                    f"(already defined in {seen[rule.id]})"
                )
            seen[rule.id] = path
            rules.append(rule)
    return rules
