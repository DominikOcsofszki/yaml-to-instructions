"""Rendering and writing generated instruction and settings files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from .models import INSTRUCTION_SUFFIX, Rule, RuleError, WriteReport


def _yaml_quote(value: str) -> str:
    """Quote a string for YAML frontmatter."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def render_frontmatter(rule: Rule) -> str:
    """Render the VS Code instruction frontmatter."""
    lines = ["---"]
    globs = rule.globs
    apply_to = "**" if rule.always or globs == ("**",) else ", ".join(globs)
    lines.append(f"applyTo: {_yaml_quote(apply_to)}")
    lines.extend(f"excludeAgent: {_yaml_quote(agent)}" for agent in rule.exclude_agent)
    lines.append("---")
    return "\n".join(lines)


def render_instruction(rule: Rule) -> str:
    """Render a complete instruction file."""
    parts = [
        render_frontmatter(rule),
        f"<!-- {rule.filename} -->",
        "",
        f"# {rule.title}",
        "",
        rule.body.rstrip(),
        "",
    ]
    return "\n".join(parts)


def write_instructions(
    rules: Iterable[Rule],
    output_dir: Path,
    *,
    rules_dir: Path | None = None,
    prune: bool = False,
    dry_run: bool = False,
) -> WriteReport:
    """Write instructions and optionally remove stale generated files."""
    report = WriteReport()
    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)

    expected: set[Path] = set()
    for rule in rules:
        relative_dir = Path()
        if rules_dir is not None and rule.source is not None:
            try:
                relative_dir = rule.source.resolve().parent.relative_to(
                    rules_dir.resolve()
                )
            except ValueError as exc:
                raise RuleError(
                    f"{rule.source}: rule file is outside rules directory {rules_dir}"
                ) from exc

        rule_output_dir = output_dir / relative_dir
        if not rule.enabled:
            report.skipped.append(rule_output_dir / rule.filename)
            continue

        path = rule_output_dir / rule.filename
        expected.add(path)
        content = render_instruction(rule)
        if path.is_file() and path.read_text(encoding="utf-8") == content:
            report.unchanged.append(path)
            continue

        if not dry_run:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        report.written.append(path)

    if prune:
        for path in sorted(output_dir.rglob(f"*{INSTRUCTION_SUFFIX}")):
            if path in expected:
                continue
            if not dry_run:
                path.unlink()
            report.removed.append(path)
    return report


def write_settings(
    settings: dict[str, Any],
    output_file: Path,
    *,
    dry_run: bool = False,
) -> WriteReport:
    """Write VS Code settings as formatted JSON."""
    report = WriteReport()
    content = json.dumps(settings, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    if output_file.is_file() and output_file.read_text(encoding="utf-8") == content:
        report.unchanged.append(output_file)
        return report

    if not dry_run:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(content, encoding="utf-8")
    report.written.append(output_file)
    return report
