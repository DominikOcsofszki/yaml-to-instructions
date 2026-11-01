"""Command-line interface for generating instruction and settings files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from .instructions import write_instructions, write_settings
from .models import (
    DEFAULT_OUTPUT_DIR,
    DEFAULT_RULES_DIR,
    DEFAULT_SETTINGS_DIR,
    DEFAULT_SETTINGS_OUTPUT,
    Rule,
    RuleError,
    WriteReport,
)
from .rules import load_rules
from .settings import load_settings


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="yaml-to-instructions",
        description="Generate VS Code instructions and settings from YAML.",
    )
    parser.add_argument(
        "--rules",
        type=Path,
        default=DEFAULT_RULES_DIR,
        help=f"instruction YAML directory (default: {DEFAULT_RULES_DIR})",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"instruction output directory (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--settings",
        type=Path,
        default=DEFAULT_SETTINGS_DIR,
        help=f"settings YAML directory (default: {DEFAULT_SETTINGS_DIR})",
    )
    parser.add_argument(
        "--settings-out",
        type=Path,
        default=DEFAULT_SETTINGS_OUTPUT,
        help=f"settings JSON output (default: {DEFAULT_SETTINGS_OUTPUT})",
    )
    parser.add_argument("--prune", action="store_true", help="remove stale instruction files")
    parser.add_argument("--dry-run", action="store_true", help="report changes without writing")
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit non-zero if generated files are out of date",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="list discovered rules and their applyTo globs",
    )
    parser.add_argument("--json", action="store_true", help="emit reports as JSON")
    return parser


def _list_rules(rules: list[Rule], as_json: bool) -> int:
    payload = [
        {
            "id": rule.id,
            "file": rule.filename,
            "title": rule.title,
            "applyTo": None if rule.always else list(rule.globs),
            "enabled": rule.enabled,
        }
        for rule in rules
    ]
    if as_json:
        print(json.dumps(payload, indent=2))
    else:
        for item in payload:
            scope = "ALWAYS" if item["applyTo"] is None else ", ".join(item["applyTo"])
            print(f"{item['file']:52s} {scope}")
    return 0


def _write_report(report: WriteReport, as_json: bool) -> None:
    if as_json:
        print(
            json.dumps(
                {
                    "written": [str(path) for path in report.written],
                    "unchanged": [str(path) for path in report.unchanged],
                    "skipped": [str(path) for path in report.skipped],
                    "removed": [str(path) for path in report.removed],
                },
                indent=2,
            )
        )
        return

    for label, paths in (
        ("write", report.written),
        ("same", report.unchanged),
        ("skip", report.skipped),
        ("remove", report.removed),
    ):
        for path in paths:
            print(f"{label:7s} {path}")
    print(report.summary())


def main(argv: Sequence[str] | None = None) -> int:
    """Run the generator CLI."""
    args = _build_parser().parse_args(argv)
    try:
        rules = load_rules(args.rules)
        if args.list:
            return _list_rules(rules, args.json)

        settings = load_settings(args.settings)
        report = write_instructions(
            rules,
            args.out,
            rules_dir=args.rules,
            prune=args.prune,
            dry_run=args.dry_run,
        )
        settings_report = write_settings(settings, args.settings_out, dry_run=args.dry_run)
    except RuleError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    report.written.extend(settings_report.written)
    report.unchanged.extend(settings_report.unchanged)
    _write_report(report, args.json)
    return 1 if args.check and (report.written or report.removed) else 0
