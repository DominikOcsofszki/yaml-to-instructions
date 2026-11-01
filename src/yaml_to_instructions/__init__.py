"""Generate VS Code instructions and settings from YAML configuration."""

from .cli import main
from .instructions import (
    render_frontmatter,
    render_instruction,
    write_instructions,
    write_settings,
)
from .models import (
    DEFAULT_AGENTIC_RULES_DIR,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_RULES_DIR,
    DEFAULT_SETTINGS_DIR,
    DEFAULT_SETTINGS_OUTPUT,
    INSTRUCTION_SUFFIX,
    KNOWN_RULE_KEYS,
    SENTINEL_GLOB,
    Rule,
    RuleError,
    WriteReport,
)
from .rules import load_rules, parse_rule
from .settings import load_settings

# Backward-compatible name used by the original single-module API.
KNOWN_KEYS = KNOWN_RULE_KEYS

__all__ = [
    "DEFAULT_AGENTIC_RULES_DIR",
    "DEFAULT_OUTPUT_DIR",
    "DEFAULT_RULES_DIR",
    "DEFAULT_SETTINGS_DIR",
    "DEFAULT_SETTINGS_OUTPUT",
    "INSTRUCTION_SUFFIX",
    "KNOWN_RULE_KEYS",
    "KNOWN_KEYS",
    "SENTINEL_GLOB",
    "Rule",
    "RuleError",
    "WriteReport",
    "load_rules",
    "load_settings",
    "main",
    "parse_rule",
    "render_frontmatter",
    "render_instruction",
    "write_instructions",
    "write_settings",
]
