"""Tests for the yaml-to-instructions pipeline."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from yaml_to_instructions import (
    INSTRUCTION_SUFFIX,
    SENTINEL_GLOB,
    Rule,
    RuleError,
    load_rules,
    load_settings,
    main,
    parse_rule,
    render_frontmatter,
    render_instruction,
    write_instructions,
    write_settings,
)
from yaml_to_instructions.check_settings import (
    MANUAL_APPROVAL_COMMANDS,
    SAFE_AUTO_APPROVE_COMMANDS,
    SettingsPolicyError,
    main as check_settings_main,
    validate_settings,
)
from yaml_to_instructions.migrate import parse_instruction


def write_rule(path: Path, text: str) -> Path:
    path.write_text(textwrap.dedent(text).lstrip(), encoding="utf-8")
    return path


# ------------------------------------------------------------------ parsing


def test_parse_rule_minimal():
    rule = parse_rule(
        {"id": "demo", "title": "Demo", "body": "Hello."}, Path("demo.yaml")
    )
    assert rule.id == "demo"
    assert rule.title == "Demo"
    assert rule.body == "Hello.\n"
    assert rule.always is False
    # No apply_to -> sentinel glob, so the file is discoverable but never injected.
    assert rule.globs == (SENTINEL_GLOB,)
    assert rule.filename == f"demo{INSTRUCTION_SUFFIX}"


def test_parse_rule_rejects_unknown_key():
    with pytest.raises(RuleError, match="unknown key"):
        parse_rule(
            {"id": "demo", "title": "D", "body": "b", "colour": "red"},
            Path("demo.yaml"),
        )


def test_parse_rule_rejects_bad_id():
    with pytest.raises(RuleError, match="may only contain"):
        parse_rule({"id": "bad id!", "title": "D", "body": "b"}, Path("d.yaml"))


def test_parse_rule_requires_title_and_body():
    with pytest.raises(RuleError, match="'title' is required"):
        parse_rule({"id": "d", "body": "b"}, Path("d.yaml"))
    with pytest.raises(RuleError, match="'body' is required"):
        parse_rule({"id": "d", "title": "T"}, Path("d.yaml"))


def test_parse_rule_always_and_apply_to_are_exclusive():
    with pytest.raises(RuleError, match="mutually exclusive"):
        parse_rule(
            {"id": "d", "title": "T", "body": "b", "always": True, "apply_to": ["a.js"]},
            Path("d.yaml"),
        )


def test_parse_rule_rejects_negation_glob():
    with pytest.raises(RuleError, match="negation globs"):
        parse_rule(
            {"id": "d", "title": "T", "body": "b", "apply_to": ["**", "!node_modules/**"]},
            Path("d.yaml"),
        )


def test_parse_rule_accepts_scalar_apply_to():
    rule = parse_rule(
        {"id": "d", "title": "T", "body": "b", "apply_to": "index.js"}, Path("d.yaml")
    )
    assert rule.globs == ("index.js",)


def test_parse_rule_rejects_non_string_glob():
    with pytest.raises(RuleError, match="only strings"):
        parse_rule(
            {"id": "d", "title": "T", "body": "b", "apply_to": ["a.js", 5]}, Path("d.yaml")
        )


# ------------------------------------------------------------------ loading


def test_load_rules_single_and_list(tmp_path):
    write_rule(
        tmp_path / "a.yaml",
        """
        id: a
        title: A
        apply_to: ["a.js"]
        body: |
          Body A
        """,
    )
    write_rule(
        tmp_path / "b.yaml",
        """
        - id: b
          title: B
          body: |
            Body B
        - id: c
          title: C
          body: |
            Body C
        """,
    )
    rules = load_rules(tmp_path)
    assert {r.id for r in rules} == {"a", "b", "c"}


def test_nested_rules_generate_nested_instructions_and_prune_recursively(tmp_path):
    rules_dir = tmp_path / "rules"
    nested_rules = rules_dir / "sdk" / "api"
    nested_rules.mkdir(parents=True)
    write_rule(
        nested_rules / "plugin.yaml",
        """
        id: plugin
        title: Plugin API
        apply_to: ["App.tsx"]
        body: |
          Body
        """,
    )
    out_dir = tmp_path / "instructions"
    stale = out_dir / "old" / f"stale{INSTRUCTION_SUFFIX}"
    stale.parent.mkdir(parents=True)
    stale.write_text("stale", encoding="utf-8")

    rules = load_rules(rules_dir)
    report = write_instructions(rules, out_dir, rules_dir=rules_dir, prune=True)

    generated = out_dir / "sdk" / "api" / f"plugin{INSTRUCTION_SUFFIX}"
    assert generated.is_file()
    assert report.removed == [stale]
    assert not stale.exists()


def test_load_rules_detects_duplicate_ids(tmp_path):
    write_rule(tmp_path / "a.yaml", "id: dup\ntitle: A\nbody: |\n  x\n")
    write_rule(tmp_path / "b.yaml", "id: dup\ntitle: B\nbody: |\n  y\n")
    with pytest.raises(RuleError, match="duplicate id"):
        load_rules(tmp_path)


def test_load_rules_missing_dir(tmp_path):
    with pytest.raises(RuleError, match="not found"):
        load_rules(tmp_path / "nope")


def test_load_rules_allows_empty_directory(tmp_path):
    assert load_rules(tmp_path) == []


def test_load_rules_invalid_yaml(tmp_path):
    (tmp_path / "a.yaml").write_text("id: [unclosed\n", encoding="utf-8")
    with pytest.raises(RuleError, match="invalid YAML"):
        load_rules(tmp_path)


def test_load_settings_merges_yaml_files(tmp_path):
    write_rule(
        tmp_path / "approvals.yaml",
        """
        "chat.tools.terminal.autoApprove":
          uv: true
          rm: false
        """,
    )
    write_rule(
        tmp_path / "sandbox.yaml",
        """
        "chat.agent.sandbox.enabled": "on"
        "chat.tools.terminal.autoApprove":
          git: true
        """,
    )

    assert load_settings(tmp_path) == {
        "chat.agent.sandbox.enabled": "on",
        "chat.tools.terminal.autoApprove": {"uv": True, "rm": False, "git": True},
    }


def test_load_settings_rejects_duplicate_setting_names(tmp_path):
    write_rule(
        tmp_path / "a.yaml",
        '"chat.tools.terminal.autoApprove":\n  uv: true\n',
    )
    write_rule(
        tmp_path / "b.yaml",
        '"chat.tools.terminal.autoApprove":\n  uv: false\n',
    )

    with pytest.raises(RuleError, match="duplicate setting 'chat.tools.terminal.autoApprove.uv'"):
        load_settings(tmp_path)


def test_load_settings_rejects_non_mapping(tmp_path):
    write_rule(tmp_path / "settings.yaml", "- not-a-setting\n")

    with pytest.raises(RuleError, match="must be a mapping"):
        load_settings(tmp_path)


def test_migration_parses_comma_separated_apply_to(tmp_path):
    instruction = tmp_path / "example.instructions.md"
    instruction.write_text(
        '---\napplyTo: "**/*.py, **/*.md"\n---\n'
        "<!-- example.instructions.md -->\n\n"
        "# Example\n\n"
        "Instruction body.\n",
        encoding="utf-8",
    )

    assert parse_instruction(instruction)["apply_to"] == ["**/*.py", "**/*.md"]


def valid_agent_settings(project_root: Path) -> dict:
    return {
        "chat.agent.sandbox.enabled": "on",
        "chat.agent.sandbox.allowUnsandboxedCommands": False,
        "chat.agent.sandbox.fileSystem.userConfiguredPaths": {
            "readwritePaths": []
        },
        "chat.tools.terminal.autoApprove": {
            **dict.fromkeys(SAFE_AUTO_APPROVE_COMMANDS, True),
            **dict.fromkeys(MANUAL_APPROVAL_COMMANDS, False),
        },
    }


def test_validate_settings_accepts_expected_policy(tmp_path):
    settings = valid_agent_settings(tmp_path)

    validated = validate_settings(settings, tmp_path)

    assert validated.sandbox_enabled == "on"


def test_validate_settings_rejects_readwrite_parent_directory(tmp_path):
    settings = valid_agent_settings(tmp_path)
    settings["chat.agent.sandbox.fileSystem.userConfiguredPaths"]["readwritePaths"] = [
        str(tmp_path.parent)
    ]

    with pytest.raises(SettingsPolicyError, match="broader path"):
        validate_settings(settings, tmp_path)


def test_validate_settings_rejects_broader_write_scope(tmp_path):
    settings = valid_agent_settings(tmp_path)
    settings["chat.agent.sandbox.fileSystem.userConfiguredPaths"]["readwritePaths"].append(
        str(tmp_path.parent)
    )

    with pytest.raises(SettingsPolicyError, match="broader path"):
        validate_settings(settings, tmp_path)


def test_validate_settings_rejects_unsandboxed_commands(tmp_path):
    settings = valid_agent_settings(tmp_path)
    settings["chat.agent.sandbox.allowUnsandboxedCommands"] = True

    with pytest.raises(SettingsPolicyError, match="allowUnsandboxedCommands must be false"):
        validate_settings(settings, tmp_path)


def test_validate_settings_requires_manual_approval_for_destructive_commands(tmp_path):
    settings = valid_agent_settings(tmp_path)
    settings["chat.tools.terminal.autoApprove"]["rm"] = True

    with pytest.raises(SettingsPolicyError, match="require manual approval"):
        validate_settings(settings, tmp_path)


def test_check_settings_cli_validates_json_file(tmp_path, capsys):
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(
        json.dumps(valid_agent_settings(tmp_path)),
        encoding="utf-8",
    )

    assert check_settings_main(
        ["--settings", str(settings_file), "--project-root", str(tmp_path)]
    ) == 0
    assert "settings policy valid" in capsys.readouterr().out


# ---------------------------------------------------------------- rendering


def test_render_frontmatter_uses_comma_separated_string_for_multiple_globs():
    rule = Rule(id="d", title="T", body="b", apply_to=("a.js", "b.tsx"))
    fm = render_frontmatter(rule)
    assert fm == '---\napplyTo: "a.js, b.tsx"\n---'


def test_render_frontmatter_uses_string_form_for_always():
    rule = Rule(id="d", title="T", body="b", always=True)
    assert render_frontmatter(rule) == '---\napplyTo: "**"\n---'


def test_render_frontmatter_escapes_quotes():
    rule = Rule(id="d", title="T", body="b", apply_to=('a"b.js',))
    assert 'applyTo: "a\\"b.js"' in render_frontmatter(rule)


def test_render_instruction_layout():
    rule = Rule(id="demo", title="Demo title", body="Body text.", apply_to=("a.js",))
    out = render_instruction(rule)
    assert out.startswith('---\napplyTo: "a.js"\n---\n')
    assert "<!-- demo.instructions.md -->" in out
    assert "# Demo title" in out
    assert "Body text." in out
    assert out.endswith("\n")


def test_render_instruction_includes_exclude_agent():
    rule = Rule(
        id="d", title="T", body="b", apply_to=("a.js",), exclude_agent=("code-review",)
    )
    assert 'excludeAgent: "code-review"' in render_frontmatter(rule)


# ------------------------------------------------------------------ writing


def test_write_instructions_creates_files(tmp_path):
    rules = [Rule(id="demo", title="T", body="Body.", apply_to=("a.js",))]
    out = tmp_path / "out"
    report = write_instructions(rules, out)
    assert len(report.written) == 1
    assert (out / f"demo{INSTRUCTION_SUFFIX}").exists()


def test_write_instructions_is_idempotent(tmp_path):
    rules = [Rule(id="demo", title="T", body="Body.", apply_to=("a.js",))]
    out = tmp_path / "out"
    write_instructions(rules, out)
    report = write_instructions(rules, out)
    assert report.written == []
    assert len(report.unchanged) == 1


def test_write_instructions_prune_removes_orphans(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    orphan = out / f"orphan{INSTRUCTION_SUFFIX}"
    orphan.write_text("stale", encoding="utf-8")

    rules = [Rule(id="demo", title="T", body="Body.", apply_to=("a.js",))]
    report = write_instructions(rules, out, prune=True)
    assert report.removed == [orphan]
    assert not orphan.exists()


def test_write_instructions_dry_run_touches_nothing(tmp_path):
    out = tmp_path / "out"
    rules = [Rule(id="demo", title="T", body="Body.", apply_to=("a.js",))]
    report = write_instructions(rules, out, dry_run=True)
    assert len(report.written) == 1
    assert not (out / f"demo{INSTRUCTION_SUFFIX}").exists()
    # The output directory itself must not be created either.
    assert not out.exists()


def test_write_instructions_skips_disabled_rules(tmp_path):
    out = tmp_path / "out"
    rules = [Rule(id="demo", title="T", body="Body.", apply_to=("a.js",), enabled=False)]
    report = write_instructions(rules, out)
    assert len(report.skipped) == 1
    assert not (out / f"demo{INSTRUCTION_SUFFIX}").exists()


def test_write_settings_creates_and_checks_file(tmp_path):
    output = tmp_path / ".vscode" / "settings.json"
    settings = {"editor.tabSize": 2}

    report = write_settings(settings, output)
    assert report.written == [output]
    assert output.read_text(encoding="utf-8") == '{\n  "editor.tabSize": 2\n}\n'

    report = write_settings(settings, output)
    assert report.unchanged == [output]


def test_write_settings_dry_run_touches_nothing(tmp_path):
    output = tmp_path / ".vscode" / "settings.json"

    report = write_settings({"editor.tabSize": 2}, output, dry_run=True)

    assert report.written == [output]
    assert not output.exists()


# ---------------------------------------------------------------------- cli


def test_cli_list(tmp_path, capsys):
    write_rule(
        tmp_path / "a.yaml",
        """
        id: a
        title: A
        apply_to: ["a.js"]
        body: |
          Body
        """,
    )
    assert main(["--rules", str(tmp_path), "--list"]) == 0
    out = capsys.readouterr().out
    assert "a.instructions.md" in out
    assert "a.js" in out


def test_cli_defaults_use_repository_root_paths(tmp_path, monkeypatch):
    rules_dir = tmp_path / "agentic_rules" / "rules"
    rules_dir.mkdir()
    write_rule(
        rules_dir / "a.yaml",
        """
        id: a
        title: A
        apply_to: ["a.js"]
        body: |
          Body
        """,
    )
    settings_dir = tmp_path / "agentic_rules" / "settings"
    settings_dir.mkdir()
    write_rule(settings_dir / "vscode.yaml", '"editor.tabSize": 2\n')
    monkeypatch.chdir(tmp_path)

    assert main([]) == 0
    generated = tmp_path / ".github" / "instructions" / "rules" / "a.instructions.md"
    assert generated.is_file()
    settings_output = tmp_path / ".vscode" / "settings.json"
    assert settings_output.is_file()
    assert '"editor.tabSize": 2' in settings_output.read_text(encoding="utf-8")
    assert main(["--check"]) == 0


def test_cli_check_reports_outdated(tmp_path):
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    write_rule(
        rules_dir / "a.yaml",
        """
        id: a
        title: A
        apply_to: ["a.js"]
        body: |
          Body
        """,
    )
    settings_dir = tmp_path / "settings"
    settings_dir.mkdir()
    write_rule(settings_dir / "vscode.yaml", '"editor.tabSize": 2\n')
    out_dir = tmp_path / "out"
    settings_out = tmp_path / "settings.json"
    options = [
        "--rules",
        str(rules_dir),
        "--out",
        str(out_dir),
        "--settings",
        str(settings_dir),
        "--settings-out",
        str(settings_out),
    ]
    # Nothing written yet -> check must fail.
    assert main([*options, "--check"]) == 1
    # After writing -> check passes.
    assert main(options) == 0
    assert main([*options, "--check"]) == 0
    write_rule(settings_dir / "vscode.yaml", '"editor.tabSize": 4\n')
    assert main([*options, "--check"]) == 1


def test_cli_reports_invalid_rules(tmp_path, capsys):
    write_rule(tmp_path / "a.yaml", "id: a\ntitle: A\nbody: |\n  x\nbogus: 1\n")
    assert main(["--rules", str(tmp_path)]) == 2
    assert "unknown key" in capsys.readouterr().err
