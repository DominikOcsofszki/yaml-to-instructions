"""Shared data types and defaults for YAML-to-instructions."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

INSTRUCTION_SUFFIX = ".instructions.md"
DEFAULT_OUTPUT_DIR = Path(".github/instructions/rules")
DEFAULT_AGENTIC_RULES_DIR = Path("agentic_rules")
DEFAULT_RULES_DIR = DEFAULT_AGENTIC_RULES_DIR / "rules"
DEFAULT_SETTINGS_DIR = DEFAULT_AGENTIC_RULES_DIR / "settings"
DEFAULT_SETTINGS_OUTPUT = Path(".vscode/settings.json")
SENTINEL_GLOB = "on-demand/**"

KNOWN_RULE_KEYS = {
    "id",
    "title",
    "apply_to",
    "always",
    "body",
    "exclude_agent",
    "enabled",
    "notes",
}


class RuleError(ValueError):
    """Raised when an instruction rule or settings file is malformed."""


@dataclass(frozen=True)
class Rule:
    """One instruction file, described declaratively."""

    id: str
    title: str
    body: str
    apply_to: tuple[str, ...] = ()
    always: bool = False
    exclude_agent: tuple[str, ...] = ()
    enabled: bool = True
    notes: str = ""
    source: Path | None = None

    @property
    def filename(self) -> str:
        """Instruction filename, e.g. ``coding.instructions.md``."""
        return f"{self.id}{INSTRUCTION_SUFFIX}"

    @property
    def globs(self) -> tuple[str, ...]:
        """Globs to emit as ``applyTo``."""
        if self.always:
            return ()
        return self.apply_to or (SENTINEL_GLOB,)


@dataclass
class WriteReport:
    """Files written, unchanged, skipped, or removed by a generation run."""

    written: list[Path] = field(default_factory=list)
    skipped: list[Path] = field(default_factory=list)
    removed: list[Path] = field(default_factory=list)
    unchanged: list[Path] = field(default_factory=list)

    def summary(self) -> str:
        """Return a short count summary."""
        return (
            f"{len(self.written)} written, {len(self.unchanged)} unchanged, "
            f"{len(self.skipped)} skipped, {len(self.removed)} removed"
        )
