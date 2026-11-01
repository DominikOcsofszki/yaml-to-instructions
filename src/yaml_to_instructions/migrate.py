"""Convert generated instruction files back into YAML rule files."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import yaml

FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
MARKER_RE = re.compile(r"^<!-- (.+?) -->\n", re.MULTILINE)
TITLE_RE = re.compile(r"^# (.+)$", re.MULTILINE)


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Split a leading YAML frontmatter block off ``text``."""
    match = FRONTMATTER_RE.match(text)
    if not match:
        raise ValueError("no frontmatter block found")
    data = yaml.safe_load(match.group(1)) or {}
    return data, text[match.end() :]


def parse_instruction(path: Path) -> dict[str, Any]:
    """Turn one instruction file into a rule mapping."""
    text = path.read_text(encoding="utf-8")
    front, rest = parse_frontmatter(text)

    marker = MARKER_RE.match(rest)
    if not marker:
        raise ValueError(f"{path.name}: missing <!-- filename --> marker")
    rest = rest[marker.end() :]

    title_match = TITLE_RE.search(rest)
    if not title_match:
        raise ValueError(f"{path.name}: missing '# title' heading")
    title = title_match.group(1).strip()
    body = rest[title_match.end() :].strip()
    rule_id = path.name[: -len(".instructions.md")]

    apply_to = front.get("applyTo")
    if apply_to is None:
        rule: dict[str, Any] = {
            "id": rule_id,
            "title": title,
            "always": True,
            "body": body,
        }
    elif apply_to == "**":
        rule = {
            "id": rule_id,
            "title": title,
            "apply_to": ["**"],
            "body": body,
        }
    else:
        if isinstance(apply_to, str):
            apply_to = [glob.strip() for glob in apply_to.split(",")]
        rule = {
            "id": rule_id,
            "title": title,
            "apply_to": list(apply_to),
            "body": body,
        }

    if front.get("excludeAgent"):
        rule["exclude_agent"] = (
            [front["excludeAgent"]]
            if isinstance(front["excludeAgent"], str)
            else list(front["excludeAgent"])
        )

    return rule


def dump_rule(rule: dict[str, Any]) -> str:
    """Serialise a rule mapping to a stable, hand-editable YAML layout."""
    lines: list[str] = []
    lines.append(f"id: {rule['id']}")
    lines.append(f"title: {_scalar(rule['title'])}")

    if rule.get("always"):
        lines.append("always: true")
    else:
        lines.append("apply_to:")
        lines.extend(f"  - {_scalar(glob)}" for glob in rule["apply_to"])

    if rule.get("exclude_agent"):
        lines.append("exclude_agent:")
        lines.extend(f"  - {_scalar(agent)}" for agent in rule["exclude_agent"])

    lines.append("body: |")
    body = rule["body"].rstrip("\n")
    for line in body.split("\n"):
        lines.append(f"  {line}" if line else "")

    return "\n".join(lines) + "\n"


def _scalar(value: str) -> str:
    """Quote a scalar only when YAML would otherwise mis-parse it."""
    if value and not re.search(r"[:#\[\]{}&*!|>'\"%@`,]|^\s|\s$", value):
        return value
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def main(argv: list[str] | None = None) -> int:
    """Convert instructions beneath the selected project root into YAML rules."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="project root containing .github/instructions/rules (default: current directory)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="print what would be written without touching disk",
    )
    args = parser.parse_args(argv)

    instructions_dir = args.root / ".github" / "instructions" / "rules"
    rules_dir = args.root / "agentic_rules" / "rules"
    if not instructions_dir.is_dir():
        print(f"error: {instructions_dir} not found", file=sys.stderr)
        return 2

    files = sorted(instructions_dir.rglob("*.instructions.md"))
    if not files:
        print(f"error: no instruction files in {instructions_dir}", file=sys.stderr)
        return 2

    for path in files:
        rule = parse_instruction(path)
        relative_dir = path.parent.relative_to(instructions_dir)
        target = rules_dir / relative_dir / f"{rule['id']}.yaml"
        content = dump_rule(rule)
        if args.check:
            print(f"would write {target}")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        print(f"write {target}")

    print(f"{len(files)} rule file(s) in {rules_dir}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
