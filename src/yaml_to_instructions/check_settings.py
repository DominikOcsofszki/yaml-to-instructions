"""Validate generated VS Code agent settings against the project policy."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, ValidationError


SAFE_AUTO_APPROVE_COMMANDS = (
    "pwd",
    "ls",
    "find",
    "rg",
    "grep",
    "cat",
    "head",
    "tail",
    "wc",
    "file",
    "stat",
    "uv",
    "/^git (status|diff|log|show)\\b.*$/",
)

MANUAL_APPROVAL_COMMANDS = (
    "rm",
    "rmdir",
    "mv",
    "cp",
    "mkdir",
    "touch",
    "chmod",
    "chown",
    "tee",
    "dd",
    "truncate",
    "install",
    "/^git (add|commit|checkout|clean|reset|restore|apply|push|pull|merge|rebase|switch)\\b.*$/",
)


class SandboxPaths(BaseModel):
    """Filesystem path permissions configured for sandboxed terminal tools."""

    model_config = ConfigDict(extra="allow")

    readwrite_paths: list[Path] = Field(alias="readwritePaths")


class AgentSettings(BaseModel):
    """Required shape and values for the generated VS Code agent settings."""

    model_config = ConfigDict(extra="allow")

    sandbox_enabled: Literal["on"] = Field(alias="chat.agent.sandbox.enabled")
    allow_unsandboxed_commands: StrictBool = Field(
        alias="chat.agent.sandbox.allowUnsandboxedCommands"
    )
    sandbox_paths: SandboxPaths = Field(
        alias="chat.agent.sandbox.fileSystem.userConfiguredPaths"
    )
    terminal_auto_approve: dict[str, StrictBool] = Field(
        alias="chat.tools.terminal.autoApprove"
    )


class SettingsPolicyError(ValueError):
    """Raised when generated settings violate the expected agent policy."""


def validate_settings(data: object, project_root: Path) -> AgentSettings:
    """Validate JSON settings and their filesystem/command approval policy."""
    try:
        settings = AgentSettings.model_validate(data)
    except ValidationError as exc:
        raise SettingsPolicyError(f"settings schema validation failed:\n{exc}") from exc

    if settings.allow_unsandboxed_commands:
        raise SettingsPolicyError(
            "chat.agent.sandbox.allowUnsandboxedCommands must be false"
        )

    root = project_root.expanduser().resolve()
    write_paths = [path.expanduser().resolve() for path in settings.sandbox_paths.readwrite_paths]
    broader_paths = [path for path in write_paths if not path.is_relative_to(root)]
    if broader_paths:
        formatted = ", ".join(repr(str(path)) for path in broader_paths)
        raise SettingsPolicyError(
            f"readwritePaths must stay within the project root; broader path(s): {formatted}"
        )

    approvals = settings.terminal_auto_approve
    missing_auto = [name for name in SAFE_AUTO_APPROVE_COMMANDS if approvals.get(name) is not True]
    if missing_auto:
        raise SettingsPolicyError(
            "these read-only commands must be auto-approved: " + ", ".join(missing_auto)
        )

    incorrectly_approved = [
        name for name in MANUAL_APPROVAL_COMMANDS if approvals.get(name) is not False
    ]
    if incorrectly_approved:
        raise SettingsPolicyError(
            "these commands must require manual approval (set to false): "
            + ", ".join(incorrectly_approved)
        )

    return settings


def validate_settings_file(settings_file: Path, project_root: Path) -> AgentSettings:
    """Read and validate a generated settings JSON file."""
    try:
        data = json.loads(settings_file.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SettingsPolicyError(f"cannot read {settings_file}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise SettingsPolicyError(
            f"{settings_file}: invalid JSON at line {exc.lineno}, column {exc.colno}: "
            f"{exc.msg}"
        ) from exc

    try:
        return validate_settings(data, project_root)
    except SettingsPolicyError as exc:
        raise SettingsPolicyError(f"{settings_file}: {exc}") from exc


def main(argv: list[str] | None = None) -> int:
    """Run the generated settings policy checker."""
    parser = argparse.ArgumentParser(
        prog="yaml-to-instructions-check-settings",
        description="Validate generated VS Code agent settings and approval rules.",
    )
    parser.add_argument(
        "--settings",
        type=Path,
        default=Path(".vscode/settings.json"),
        help="generated VS Code settings JSON (default: .vscode/settings.json)",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="project root that should have read/write access (default: current directory)",
    )
    args = parser.parse_args(argv)

    try:
        validate_settings_file(args.settings, args.project_root)
    except SettingsPolicyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"settings policy valid: {args.settings}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
