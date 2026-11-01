---
applyTo: "agentic_rules/settings/sandbox.yaml"
---
<!-- agentic-settings.sandbox.instructions.md -->

# Updating the agent sandbox settings

When changing the agent sandbox configuration:

- Edit `agentic_rules/settings/sandbox.yaml`, the source of truth. Do not edit
  the generated `.vscode/settings.json` directly.
- Keep sandboxing enabled and unsandboxed command execution disabled unless
  the user explicitly requests a different security policy.
- Keep filesystem permissions scoped to the project paths the user requested;
  do not broaden access to parent directories or the home directory.
- Regenerate settings by running `uv run yaml-to-instructions`, then verify
  that `uv run yaml-to-instructions --check` passes.
- Review the generated `.vscode/settings.json` to confirm it reflects the
  YAML source and preserves unrelated settings.
