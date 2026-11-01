# yaml-to-instructions

Turn declarative **YAML rules** into **Copilot CLI instruction files**.

```
agentic_rules/rules/*.yaml      ──▶   .github/instructions/rules/*.instructions.md
agentic_rules/settings/*.yaml   ──▶   .vscode/settings.json
```

The YAML files are the source of truth. Generated instruction and settings
files should not be hand-edited.

## Install

```bash
cd yaml_to_instructions
uv sync            # creates .venv with pyyaml + pytest
```

## Usage

```bash
# from the repo root; defaults use agentic_rules/ and the generated output paths
npm run instructions
```

| Flag | Meaning |
|---|---|
| `--rules DIR` | directory holding instruction YAML files (default `agentic_rules/rules`) |
| `--out DIR` | directory to write instruction files to (default `.github/instructions/rules`) |
| `--settings DIR` | directory holding VS Code settings YAML files (default `agentic_rules/settings`) |
| `--settings-out FILE` | VS Code settings JSON output (default `.vscode/settings.json`) |
| `--prune` | delete instruction files that no rule produced |
| `--dry-run` | report what would happen without writing anything |
| `--check` | exit non-zero if any instruction file is out of date (CI) |
| `--list` | list the discovered rules and their `applyTo` globs |
| `--json` | emit the report as JSON |

Validate the generated agent sandbox and command approval policy with:

```bash
uv run yaml-to-instructions-check-settings
```

The checker validates `.vscode/settings.json`, relying on VS Code's default
read/write access to the agent's current working directory and rejecting
configured write paths outside the project root. Use `--settings FILE` and
`--project-root DIR` to check another settings file or project. It also checks
that `uv` and the configured read-only commands are auto-approved, while
destructive filesystem and Git commands remain set to `false` (manual approval
required).

## Rule format

One YAML file per instruction file. Rule files may be nested below
`agentic_rules/rules/`; the generator mirrors each subdirectory below
`.github/instructions/rules/`.
The filename is free-form; the `id` determines the output filename.

```yaml
id: instruction.sdk.index          # -> instruction.sdk.index.instructions.md
title: "`index.js` — plugin entry point"
apply_to:                          # glob list, relative to the repo root
  - index.js
body: |
  Markdown content injected into the model context.
```

### Keys

| Key | Required | Meaning |
|---|---|---|
| `id` | yes | Output filename stem. `[A-Za-z0-9._-]+` only. |
| `title` | yes | Rendered as the `# heading` of the instruction file. |
| `body` | yes | Markdown body. |
| `apply_to` | no | Glob list. Omit for an always-on file. |
| `always` | no | `true` → injected for every path. Mutually exclusive with `apply_to`. |
| `exclude_agent` | no | e.g. `["code-review"]` → emitted as `excludeAgent`. |
| `enabled` | no | `false` → rule is skipped (file not written). |
| `notes` | no | Free-form comment, not emitted. |

A file may also hold a **list** of rules instead of a single mapping.

## VS Code settings format

Put YAML mappings of VS Code setting names to values under
`agentic_rules/settings/`. Multiple files are merged; defining the same setting
in more than one file is allowed when both values are mappings. Nested mappings
merge recursively, so related entries under a setting can live in separate
files; defining the same leaf setting twice is an error.

```yaml
"chat.agent.sandbox.enabled": "on"
"chat.agent.sandbox.fileSystem.userConfiguredPaths":
  readwritePaths:
    - /absolute/path/to/your/project
```

The generator writes these values to `.vscode/settings.json`. `--check` checks
both generated instructions and settings, and `--dry-run` previews both.

## Instruction format notes

- `applyTo` is emitted as a string, as required by VS Code. Multiple globs
  from the YAML `apply_to` list are joined with commas.
- Omitting `apply_to` (or using `apply_to: ["**"]`) means "always included".
- Globs are matched relative to the repo root.
- Generated instruction filenames must end in `.instructions.md` and live
  under `.github/instructions/rules/`.

## Development

```bash
uv run pytest
```

The installed package also exposes the generation functions directly:

```python
from pathlib import Path

from yaml_to_instructions import (
    load_rules,
    load_settings,
    write_instructions,
    write_settings,
)

rules_dir = Path("agentic_rules/rules")
settings_dir = Path("agentic_rules/settings")
write_instructions(
    load_rules(rules_dir),
    Path(".github/instructions/rules"),
    rules_dir=rules_dir,
)
write_settings(load_settings(settings_dir), Path(".vscode/settings.json"))
```

### Migrating existing instruction files

`yaml-to-instructions-migrate` converts the instruction files back into YAML
rules under `agentic_rules/rules/`:

```bash
uv run yaml-to-instructions-migrate
```

Run it from the project root, or pass `--root PATH` to select a project.
