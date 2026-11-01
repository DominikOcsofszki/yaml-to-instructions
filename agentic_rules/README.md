# Agentic configuration

- Add Copilot instruction definitions as YAML under `rules/`.
- Add VS Code setting mappings as YAML under `settings/`.

Run the generator from the repository root. It writes instruction files to
`.github/instructions/rules/` and VS Code settings to `.vscode/settings.json`.
The generated files are outputs; edit their YAML sources instead.
