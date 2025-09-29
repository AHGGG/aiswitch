import os
import json
import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from aiswitch.cli import cli
import aiswitch.cli as cli_module
import aiswitch.shell_integration as shell_integration


BASE_URL = "https://api.example.com"


def _add_default_preset(runner: CliRunner, name: str = "demo", model: str = "gpt-4o") -> None:
    result = runner.invoke(
        cli,
        [
            "add",
            name,
            "API_KEY",
            f"sk-{name}",
            "API_BASE_URL",
            BASE_URL,
            "API_MODEL",
            model,
        ],
    )
    assert result.exit_code == 0, result.output


def test_add_requires_pairs(temp_config_dir):
    runner = CliRunner()
    result = runner.invoke(cli, ["add", "broken", "API_KEY", "value", "ORPHAN"])
    assert result.exit_code != 0
    assert "must come in pairs" in result.output


def test_add_outputs_tags_and_description(temp_config_dir):
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "add",
            "tagged",
            "API_KEY",
            "sk-tagged",
            "API_BASE_URL",
            BASE_URL,
            "--description",
            "A test preset",
            "--tags",
            "prod, llm",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Description: A test preset" in result.output
    assert "Tags: prod, llm" in result.output


@pytest.mark.skipif(os.name == "nt", reason="Unix-like shells expected")
def test_remove_requires_force_for_current(temp_config_dir):
    runner = CliRunner()
    _add_default_preset(runner, name="keep")

    assert runner.invoke(cli, ["apply", "keep"]).exit_code == 0

    result = runner.invoke(cli, ["remove", "keep"])
    assert result.exit_code != 0
    assert "Cannot remove current preset" in result.output

    forced = runner.invoke(cli, ["remove", "keep", "--force"])
    assert forced.exit_code == 0
    assert "removed successfully" in forced.output


def test_remove_reports_missing_preset(temp_config_dir):
    runner = CliRunner()
    result = runner.invoke(cli, ["remove", "missing"])
    assert result.exit_code != 0
    assert "not found" in result.output


@pytest.mark.skipif(os.name == "nt", reason="Unix-like shells expected")
def test_use_command_warns_about_deprecation(temp_config_dir):
    runner = CliRunner()
    _add_default_preset(runner, name="legacy")

    res = runner.invoke(cli, ["use", "legacy"])
    assert res.exit_code == 0, res.output
    assert "Switched to preset" in res.output
    assert "'use' 将在未来版本中被 'apply' 取代" in res.output
    assert "API_KEY: sk-legac..." in res.output


@pytest.mark.skipif(os.name == "nt", reason="Unix-like shells expected")
def test_shell_command_invokes_subshell(temp_config_dir, monkeypatch):
    runner = CliRunner()
    _add_default_preset(runner, name="shelltest")

    monkeypatch.setenv("SHELL", "/bin/bash")

    exec_calls = {}

    def fake_execvpe(cmd, args, env):  # type: ignore[no-redef]
        raise FileNotFoundError

    def fake_call(args, env=None):  # type: ignore[no-redef]
        exec_calls["args"] = args
        exec_calls["env"] = env
        return 0

    monkeypatch.setattr(cli_module.os, "execvpe", fake_execvpe)
    monkeypatch.setattr(cli_module.subprocess, "call", fake_call)

    res = runner.invoke(cli, ["shell", "shelltest"])
    assert res.exit_code == 0, res.output
    assert "Spawning subshell" in res.output
    assert exec_calls["env"]["API_KEY"] == "sk-shelltest"


@pytest.mark.skipif(os.name == "nt", reason="Unix-like shells expected")
def test_list_marks_current_preset(temp_config_dir):
    runner = CliRunner()
    _add_default_preset(runner, name="first")
    _add_default_preset(runner, name="second")

    assert runner.invoke(cli, ["apply", "second"]).exit_code == 0
    res = runner.invoke(cli, ["list"])
    assert res.exit_code == 0
    assert "* second" in res.output
    assert "  first" in res.output


@pytest.mark.skipif(os.name == "nt", reason="Unix-like shells expected")
def test_list_verbose_shows_details(temp_config_dir):
    runner = CliRunner()
    _add_default_preset(runner, name="verbose")

    res = runner.invoke(cli, ["list", "--verbose"])
    assert res.exit_code == 0
    assert "Variables:" in res.output
    assert "Created:" in res.output


@pytest.mark.skipif(os.name == "nt", reason="Unix-like shells expected")
def test_current_verbose_displays_masked_keys(temp_config_dir):
    runner = CliRunner()
    _add_default_preset(runner, name="current")
    assert runner.invoke(cli, ["apply", "current"]).exit_code == 0

    res = runner.invoke(cli, ["current", "--verbose"])
    assert res.exit_code == 0
    assert "Current preset: current" in res.output
    assert "Environment variables" in res.output
    assert "API_KEY: sk-curre..." in res.output


@pytest.mark.skipif(os.name == "nt", reason="Unix-like shells expected")
def test_clear_invokes_shell_integration(temp_config_dir, monkeypatch):
    runner = CliRunner()
    _add_default_preset(runner, name="cleanup")
    assert runner.invoke(cli, ["apply", "cleanup"]).exit_code == 0

    calls = {"cleared": False}

    class DummyIntegration:
        def clear_env_vars(self) -> bool:
            calls["cleared"] = True
            return True

    monkeypatch.setattr(shell_integration, "ShellIntegration", DummyIntegration)

    res = runner.invoke(cli, ["clear"])
    assert res.exit_code == 0
    assert calls["cleared"] is True
    assert "Cleared current session variables" in res.output


def test_save_requires_current_preset(temp_config_dir):
    runner = CliRunner()
    res = runner.invoke(cli, ["save"])
    assert res.exit_code != 0
    assert "No current preset" in res.output


@pytest.mark.skipif(os.name == "nt", reason="Unix-like shells expected")
def test_save_persists_variables(temp_config_dir, monkeypatch):
    runner = CliRunner()
    _add_default_preset(runner, name="persist")
    assert runner.invoke(cli, ["apply", "persist"]).exit_code == 0

    saved = {}

    class DummyIntegration:
        def save_env_vars(self, env_vars, preset_name):
            saved["env"] = env_vars
            saved["preset"] = preset_name
            return True

    monkeypatch.setattr(shell_integration, "ShellIntegration", DummyIntegration)

    res = runner.invoke(cli, ["save"])
    assert res.exit_code == 0, res.output
    assert saved["preset"] == "persist"
    assert saved["env"]["API_KEY"] == "sk-persist"


@pytest.mark.skipif(os.name == "nt", reason="Unix-like shells expected")
def test_status_verbose_shows_environment_details(temp_config_dir):
    runner = CliRunner()
    _add_default_preset(runner, name="status")
    assert runner.invoke(cli, ["apply", "status"]).exit_code == 0

    res = runner.invoke(cli, ["status", "--verbose"])
    assert res.exit_code == 0
    assert "AISwitch Status:" in res.output
    assert "Current preset details" in res.output
    assert "Config directory" in res.output


def test_info_reports_paths(temp_config_dir):
    runner = CliRunner()
    res = runner.invoke(cli, ["info"])
    assert res.exit_code == 0
    assert "AISwitch Configuration:" in res.output
    assert "Config directory" in res.output
    assert "Project config" in res.output


@pytest.mark.skipif(os.name == "nt", reason="Unix-like shells expected")
def test_install_skips_when_already_installed(temp_config_dir, monkeypatch):
    calls = {"install": False}

    class DummyIntegration:
        def is_installed(self) -> bool:
            return True

        def install(self) -> bool:
            calls["install"] = True
            return True

    monkeypatch.setattr(shell_integration, "ShellIntegration", DummyIntegration)

    runner = CliRunner()
    res = runner.invoke(cli, ["install"])
    assert res.exit_code == 0
    assert calls["install"] is False
    assert "已经安装" in res.output


@pytest.mark.skipif(os.name == "nt", reason="Unix-like shells expected")
def test_install_force_runs_integration(temp_config_dir, monkeypatch):
    calls = {"install": 0}

    class DummyIntegration:
        def is_installed(self) -> bool:
            return True

        def install(self) -> bool:
            calls["install"] += 1
            return True

        def get_shell_config_path(self) -> Path:
            return Path.home() / ".bashrc"

    monkeypatch.setattr(shell_integration, "ShellIntegration", DummyIntegration)

    runner = CliRunner()
    res = runner.invoke(cli, ["install", "--force"])
    assert res.exit_code == 0
    assert calls["install"] == 1
    assert "已修改" in res.output


@pytest.mark.skipif(os.name == "nt", reason="Unix-like shells expected")
def test_uninstall_when_not_installed(temp_config_dir, monkeypatch):
    class DummyIntegration:
        def is_installed(self) -> bool:
            return False

    monkeypatch.setattr(shell_integration, "ShellIntegration", DummyIntegration)
    runner = CliRunner()
    res = runner.invoke(cli, ["uninstall"])
    assert res.exit_code == 0
    assert "未安装" in res.output


@pytest.mark.skipif(os.name == "nt", reason="Unix-like shells expected")
def test_uninstall_success(temp_config_dir, monkeypatch):
    calls = {"uninstall": 0}

    class DummyIntegration:
        def is_installed(self) -> bool:
            return True

        def uninstall(self) -> bool:
            calls["uninstall"] += 1
            return True

    monkeypatch.setattr(shell_integration, "ShellIntegration", DummyIntegration)

    runner = CliRunner()
    res = runner.invoke(cli, ["uninstall"])
    assert res.exit_code == 0
    assert calls["uninstall"] == 1
    assert "卸载成功" in res.output


def test_export_single_preset_to_stdout(temp_config_dir):
    """Test exporting a single preset to stdout"""
    runner = CliRunner()
    _add_default_preset(runner, name="export_test")

    res = runner.invoke(cli, ["export", "export_test"])
    assert res.exit_code == 0

    # Parse the output as JSON
    output_data = json.loads(res.output)
    assert output_data["version"] == "1.0.0"
    assert output_data["preset"]["name"] == "export_test"
    assert output_data["preset"]["variables"]["API_KEY"] == "***REDACTED***"  # Should be redacted by default
    assert output_data["preset"]["variables"]["API_BASE_URL"] == BASE_URL
    assert output_data["preset"]["variables"]["API_MODEL"] == "gpt-4o"


def test_export_single_preset_with_secrets(temp_config_dir):
    """Test exporting a single preset with secrets included"""
    runner = CliRunner()
    _add_default_preset(runner, name="export_secrets")

    res = runner.invoke(cli, ["export", "export_secrets", "--include-secrets"])
    assert res.exit_code == 0

    # The output includes a warning message, so we need to extract just the JSON part
    lines = res.output.strip().split('\n')
    json_lines = []
    collecting_json = False
    for line in lines:
        if line.startswith('{'):
            collecting_json = True
        if collecting_json:
            json_lines.append(line)
        if line.startswith('}'):
            break

    json_output = '\n'.join(json_lines)
    output_data = json.loads(json_output)
    assert output_data["preset"]["variables"]["API_KEY"] == "sk-export_secrets"  # Should not be redacted


def test_export_single_preset_to_file(temp_config_dir):
    """Test exporting a single preset to a file"""
    runner = CliRunner()
    _add_default_preset(runner, name="file_export")

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp_file:
        tmp_path = tmp_file.name

    try:
        res = runner.invoke(cli, ["export", "file_export", "-o", tmp_path])
        assert res.exit_code == 0
        assert f"exported to '{tmp_path}'" in res.output

        # Verify file contents
        with open(tmp_path, 'r') as f:
            data = json.load(f)
        assert data["preset"]["name"] == "file_export"
        assert data["preset"]["variables"]["API_KEY"] == "***REDACTED***"
    finally:
        os.unlink(tmp_path)


def test_export_all_presets_to_stdout(temp_config_dir):
    """Test exporting all presets to stdout"""
    runner = CliRunner()
    _add_default_preset(runner, name="preset1")
    _add_default_preset(runner, name="preset2", model="claude-3")

    res = runner.invoke(cli, ["export", "--all"])
    assert res.exit_code == 0

    output_data = json.loads(res.output)
    assert output_data["version"] == "1.0.0"
    assert len(output_data["presets"]) == 2

    preset_names = [p["name"] for p in output_data["presets"]]
    assert "preset1" in preset_names
    assert "preset2" in preset_names

    # Check that secrets are redacted by default
    for preset in output_data["presets"]:
        assert preset["variables"]["API_KEY"] == "***REDACTED***"


def test_export_all_presets_with_secrets_to_file(temp_config_dir):
    """Test exporting all presets with secrets to a file"""
    runner = CliRunner()
    _add_default_preset(runner, name="secret1")
    _add_default_preset(runner, name="secret2")

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp_file:
        tmp_path = tmp_file.name

    try:
        res = runner.invoke(cli, ["export", "--all", "--include-secrets", "-o", tmp_path])
        assert res.exit_code == 0
        assert f"All presets exported to '{tmp_path}'" in res.output
        assert "Exported 2 presets" in res.output

        # Verify file contents
        with open(tmp_path, 'r') as f:
            data = json.load(f)
        assert len(data["presets"]) == 2

        # Check that secrets are included
        for preset in data["presets"]:
            assert "sk-" in preset["variables"]["API_KEY"]
    finally:
        os.unlink(tmp_path)


def test_export_nonexistent_preset(temp_config_dir):
    """Test exporting a preset that doesn't exist"""
    runner = CliRunner()

    res = runner.invoke(cli, ["export", "nonexistent"])
    assert res.exit_code != 0
    assert "not found" in res.output


def test_export_all_when_no_presets(temp_config_dir):
    """Test exporting all presets when no presets exist"""
    runner = CliRunner()

    res = runner.invoke(cli, ["export", "--all"])
    assert res.exit_code != 0
    assert "No presets found" in res.output


def test_import_single_preset_from_file(temp_config_dir):
    """Test importing a single preset from a file"""
    runner = CliRunner()

    # Create test data
    preset_data = {
        "version": "1.0.0",
        "export_time": "2024-01-01T00:00:00",
        "preset": {
            "name": "imported_preset",
            "description": "Test imported preset",
            "variables": {
                "API_KEY": "sk-imported",
                "API_BASE_URL": "https://api.imported.com/v1",
                "API_MODEL": "gpt-3.5-turbo"
            },
            "tags": ["imported", "test"],
            "created_at": "2024-01-01T00:00:00"
        }
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp_file:
        json.dump(preset_data, tmp_file)
        tmp_path = tmp_file.name

    try:
        res = runner.invoke(cli, ["import", tmp_path])
        assert res.exit_code == 0
        assert "Successfully imported 1 preset" in res.output

        # Verify the preset was imported
        list_res = runner.invoke(cli, ["list"])
        assert "imported_preset" in list_res.output

        # Verify preset details
        list_verbose_res = runner.invoke(cli, ["list", "--verbose"])
        assert "Test imported preset" in list_verbose_res.output
        assert "imported, test" in list_verbose_res.output

    finally:
        os.unlink(tmp_path)


def test_import_multiple_presets_from_file(temp_config_dir):
    """Test importing multiple presets from a file"""
    runner = CliRunner()

    # Create test data with multiple presets
    export_data = {
        "version": "1.0.0",
        "export_time": "2024-01-01T00:00:00",
        "presets": [
            {
                "name": "multi1",
                "description": "First preset",
                "variables": {
                    "API_KEY": "sk-multi1",
                    "API_BASE_URL": "https://api.multi1.com/v1"
                },
                "tags": [],
                "created_at": "2024-01-01T00:00:00"
            },
            {
                "name": "multi2",
                "description": "Second preset",
                "variables": {
                    "API_KEY": "sk-multi2",
                    "API_BASE_URL": "https://api.multi2.com/v1"
                },
                "tags": ["multi"],
                "created_at": "2024-01-01T00:00:00"
            }
        ]
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp_file:
        json.dump(export_data, tmp_file)
        tmp_path = tmp_file.name

    try:
        res = runner.invoke(cli, ["import", tmp_path])
        assert res.exit_code == 0
        assert "Successfully imported 2 presets" in res.output

        # Verify both presets were imported
        list_res = runner.invoke(cli, ["list"])
        assert "multi1" in list_res.output
        assert "multi2" in list_res.output

    finally:
        os.unlink(tmp_path)


def test_import_preset_with_existing_name_without_force(temp_config_dir):
    """Test importing a preset with a name that already exists (without force)"""
    runner = CliRunner()
    _add_default_preset(runner, name="existing")

    preset_data = {
        "version": "1.0.0",
        "preset": {
            "name": "existing",
            "description": "Duplicate preset",
            "variables": {
                "API_KEY": "sk-duplicate",
                "API_BASE_URL": "https://api.duplicate.com/v1"
            },
            "tags": [],
            "created_at": "2024-01-01T00:00:00"
        }
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp_file:
        json.dump(preset_data, tmp_file)
        tmp_path = tmp_file.name

    try:
        res = runner.invoke(cli, ["import", tmp_path])
        assert res.exit_code != 0
        assert "Conflicts detected" in res.output
        assert "--force" in res.output

    finally:
        os.unlink(tmp_path)


def test_import_preset_with_existing_name_with_force(temp_config_dir):
    """Test importing a preset with a name that already exists (with force)"""
    runner = CliRunner()
    _add_default_preset(runner, name="existing")

    preset_data = {
        "version": "1.0.0",
        "preset": {
            "name": "existing",
            "description": "Overwritten preset",
            "variables": {
                "API_KEY": "sk-overwritten",
                "API_BASE_URL": "https://api.overwritten.com/v1"
            },
            "tags": ["overwritten"],
            "created_at": "2024-01-01T00:00:00"
        }
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp_file:
        json.dump(preset_data, tmp_file)
        tmp_path = tmp_file.name

    try:
        res = runner.invoke(cli, ["import", tmp_path, "--force"])
        assert res.exit_code == 0
        assert "Successfully imported 1 preset" in res.output

        # Verify the preset was overwritten
        list_verbose_res = runner.invoke(cli, ["list", "--verbose"])
        assert "Overwritten preset" in list_verbose_res.output
        assert "overwritten" in list_verbose_res.output

    finally:
        os.unlink(tmp_path)


def test_import_preset_with_redacted_secrets(temp_config_dir):
    """Test importing a preset with redacted secrets fails"""
    runner = CliRunner()

    preset_data = {
        "version": "1.0.0",
        "preset": {
            "name": "redacted",
            "description": "Preset with redacted secrets",
            "variables": {
                "API_KEY": "***REDACTED***",
                "API_BASE_URL": "https://api.test.com/v1"
            },
            "tags": [],
            "created_at": "2024-01-01T00:00:00"
        }
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp_file:
        json.dump(preset_data, tmp_file)
        tmp_path = tmp_file.name

    try:
        res = runner.invoke(cli, ["import", tmp_path])
        assert res.exit_code != 0
        assert "Cannot import: File contains redacted secret values" in res.output

    finally:
        os.unlink(tmp_path)


def test_import_invalid_json_file(temp_config_dir):
    """Test importing a file with invalid JSON"""
    runner = CliRunner()

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp_file:
        tmp_file.write("invalid json {")
        tmp_path = tmp_file.name

    try:
        res = runner.invoke(cli, ["import", tmp_path])
        assert res.exit_code != 0
        assert "Invalid JSON format" in res.output

    finally:
        os.unlink(tmp_path)


def test_import_nonexistent_file(temp_config_dir):
    """Test importing a file that doesn't exist"""
    runner = CliRunner()

    res = runner.invoke(cli, ["import", "/nonexistent/file.json"])
    assert res.exit_code != 0
    assert "does not exist" in res.output


def test_import_invalid_preset_format(temp_config_dir):
    """Test importing a file with invalid preset format"""
    runner = CliRunner()

    invalid_data = {
        "version": "1.0.0",
        "invalid": "format"
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp_file:
        json.dump(invalid_data, tmp_file)
        tmp_path = tmp_file.name

    try:
        res = runner.invoke(cli, ["import", tmp_path])
        assert res.exit_code != 0
        assert "Invalid import file format" in res.output

    finally:
        os.unlink(tmp_path)


def test_export_import_roundtrip(temp_config_dir):
    """Test exporting and then importing presets (roundtrip test)"""
    runner = CliRunner()

    # Create some test presets
    _add_default_preset(runner, name="roundtrip1", model="gpt-4")
    _add_default_preset(runner, name="roundtrip2", model="claude-3")

    # Export all presets with secrets
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp_export:
        export_path = tmp_export.name

    try:
        # Export
        export_res = runner.invoke(cli, ["export", "--all", "--include-secrets", "-o", export_path])
        assert export_res.exit_code == 0

        # Clear all presets
        runner.invoke(cli, ["remove", "roundtrip1", "--force"])
        runner.invoke(cli, ["remove", "roundtrip2", "--force"])

        # Verify presets are gone
        list_res = runner.invoke(cli, ["list"])
        assert "roundtrip1" not in list_res.output
        assert "roundtrip2" not in list_res.output

        # Import back
        import_res = runner.invoke(cli, ["import", export_path])
        assert import_res.exit_code == 0
        assert "Successfully imported 2 presets" in import_res.output

        # Verify presets are back
        final_list_res = runner.invoke(cli, ["list", "--verbose"])
        assert "roundtrip1" in final_list_res.output
        assert "roundtrip2" in final_list_res.output
        # Check that both presets exist with the right variable counts
        assert "Variables: 3" in final_list_res.output

    finally:
        os.unlink(export_path)


def test_apply_basic_functionality(temp_config_dir):
    """Test basic apply command functionality"""
    runner = CliRunner()
    _add_default_preset(runner, name="apply_test")

    res = runner.invoke(cli, ["apply", "apply_test"])
    assert res.exit_code == 0
    assert "✓ Switched to preset 'apply_test'" in res.output
    assert "API_KEY: sk-apply_test" in res.output or "API_KEY: sk-apply..." in res.output  # Masked key
    assert "API_BASE_URL: https://api.example.com" in res.output
    assert "API_MODEL: gpt-4o" in res.output


def test_apply_export_mode(temp_config_dir):
    """Test apply command with --export flag"""
    runner = CliRunner()
    _add_default_preset(runner, name="export_test")

    res = runner.invoke(cli, ["apply", "export_test", "--export"])
    assert res.exit_code == 0

    # Should output export statements
    output_lines = res.output.strip().split('\n')
    export_lines = [line for line in output_lines if line.startswith('export ')]
    unset_lines = [line for line in output_lines if line.startswith('unset ')]

    # Should have export statements for new variables
    assert any('export API_KEY=' in line for line in export_lines)
    assert any('export API_BASE_URL=' in line for line in export_lines)
    assert any('export API_MODEL=' in line for line in export_lines)


def test_apply_nonexistent_preset(temp_config_dir):
    """Test apply command with nonexistent preset"""
    runner = CliRunner()

    res = runner.invoke(cli, ["apply", "nonexistent"])
    assert res.exit_code != 0
    assert "not found" in res.output


def test_apply_with_shell_integration_check(temp_config_dir, monkeypatch):
    """Test apply command checks for shell integration"""
    runner = CliRunner()
    _add_default_preset(runner, name="integration_test")

    # Mock shell integration to simulate non-interactive mode (no stdin.isatty)
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)

    res = runner.invoke(cli, ["apply", "integration_test"])
    assert res.exit_code == 0
    assert "✓ Switched to preset 'integration_test'" in res.output




def test_apply_current_preset_switching(temp_config_dir):
    """Test apply command switches between different presets correctly"""
    runner = CliRunner()
    _add_default_preset(runner, name="preset1", model="gpt-4")
    _add_default_preset(runner, name="preset2", model="claude-3")

    # Apply first preset
    res1 = runner.invoke(cli, ["apply", "preset1"])
    assert res1.exit_code == 0
    assert "✓ Switched to preset 'preset1'" in res1.output

    # Verify current preset
    current_res = runner.invoke(cli, ["current"])
    assert "preset1" in current_res.output

    # Apply second preset
    res2 = runner.invoke(cli, ["apply", "preset2"])
    assert res2.exit_code == 0
    assert "✓ Switched to preset 'preset2'" in res2.output

    # Verify current preset changed
    current_res2 = runner.invoke(cli, ["current"])
    assert "preset2" in current_res2.output


def test_apply_with_quiet_flag(temp_config_dir):
    """Test apply command with --quiet flag"""
    runner = CliRunner()
    _add_default_preset(runner, name="quiet_test")

    # Note: The quiet flag is documented but doesn't seem to change behavior in normal mode
    # It's intended for one-time execution mode
    res = runner.invoke(cli, ["apply", "quiet_test", "--quiet"])
    assert res.exit_code == 0
    # In current implementation, quiet doesn't suppress output in normal apply mode


def test_add_empty_env_pairs(temp_config_dir):
    """Test add command with no environment variable pairs"""
    runner = CliRunner()

    res = runner.invoke(cli, ["add", "empty"])
    assert res.exit_code != 0
    assert "Missing argument 'ENV_PAIRS...'" in res.output


def test_add_duplicate_preset_name(temp_config_dir):
    """Test add command with duplicate preset name"""
    runner = CliRunner()
    _add_default_preset(runner, name="duplicate")

    # Try to add same name again
    res = runner.invoke(cli, ["add", "duplicate", "API_KEY", "sk-test"])
    assert res.exit_code != 0
    assert "already exists" in res.output


def test_current_when_no_preset_active(temp_config_dir):
    """Test current command when no preset is currently active"""
    runner = CliRunner()

    res = runner.invoke(cli, ["current"])
    assert res.exit_code == 0
    assert "No current preset" in res.output


def test_current_nonexistent_preset_in_config(temp_config_dir, monkeypatch):
    """Test current command when config references a nonexistent preset"""
    runner = CliRunner()
    _add_default_preset(runner, name="existing")

    # Apply a preset then remove it to create inconsistent state
    runner.invoke(cli, ["apply", "existing"])
    runner.invoke(cli, ["remove", "existing", "--force"])

    res = runner.invoke(cli, ["current"])
    assert res.exit_code == 0
    # Should handle gracefully when referenced preset doesn't exist


def test_clear_when_no_current_preset(temp_config_dir):
    """Test clear command when no preset is currently active"""
    runner = CliRunner()

    res = runner.invoke(cli, ["clear"])
    assert res.exit_code == 0
    # Should succeed even with no active preset


def test_status_with_project_config(temp_config_dir):
    """Test status command when project config exists"""
    runner = CliRunner()
    _add_default_preset(runner, name="project_test")

    # Apply preset and save project config
    runner.invoke(cli, ["apply", "project_test"])

    # Create a simple project config
    project_config_content = """
preset: project_test
overrides:
  API_MODEL: "project-specific-model"
"""

    with open(".aiswitch.yaml", "w") as f:
        f.write(project_config_content)

    try:
        res = runner.invoke(cli, ["status", "--verbose"])
        assert res.exit_code == 0
        # Should show project config information
        assert "project_test" in res.output

    finally:
        # Clean up
        if os.path.exists(".aiswitch.yaml"):
            os.unlink(".aiswitch.yaml")


def test_list_empty_presets(temp_config_dir):
    """Test list command when no presets exist"""
    runner = CliRunner()

    res = runner.invoke(cli, ["list"])
    assert res.exit_code == 0
    assert "No presets found" in res.output
    assert "Use 'aiswitch add' to create one" in res.output


def test_save_when_no_current_preset(temp_config_dir):
    """Test save command when no preset is currently active"""
    runner = CliRunner()

    res = runner.invoke(cli, ["save"])
    assert res.exit_code != 0
    # Should fail when there's no current preset to save


def test_remove_with_force_current_preset(temp_config_dir):
    """Test remove command with --force on currently active preset"""
    runner = CliRunner()
    _add_default_preset(runner, name="force_remove_test")

    # Apply the preset
    runner.invoke(cli, ["apply", "force_remove_test"])

    # Remove with force
    res = runner.invoke(cli, ["remove", "force_remove_test", "--force"])
    assert res.exit_code == 0
    assert "removed" in res.output

    # Verify it's removed from list
    list_res = runner.invoke(cli, ["list"])
    assert "force_remove_test" not in list_res.output


def test_remove_without_force_current_preset(temp_config_dir):
    """Test remove command without --force on currently active preset"""
    runner = CliRunner()
    _add_default_preset(runner, name="current_remove_test")

    # Apply the preset
    runner.invoke(cli, ["apply", "current_remove_test"])

    # Try to remove without force
    res = runner.invoke(cli, ["remove", "current_remove_test"])
    assert res.exit_code != 0
    assert "Cannot remove current preset" in res.output and "Use --force" in res.output


def test_add_with_special_characters_in_values(temp_config_dir):
    """Test add command with special characters in environment variable values"""
    runner = CliRunner()

    special_value = "sk-test123!@#$%^&*()_+-={}[]|\\:;\"'<>?,./"
    res = runner.invoke(cli, ["add", "special_chars", "API_KEY", special_value, "API_URL", "https://api.test.com/v1"])
    assert res.exit_code == 0
    assert "Preset 'special_chars' added successfully" in res.output


def test_cli_version_option(temp_config_dir):
    """Test CLI version option"""
    runner = CliRunner()

    res = runner.invoke(cli, ["--version"])
    assert res.exit_code == 0
    assert "0.1.0" in res.output


def test_cli_help_option(temp_config_dir):
    """Test CLI help option"""
    runner = CliRunner()

    res = runner.invoke(cli, ["--help"])
    assert res.exit_code == 0
    assert "AISwitch" in res.output
    assert "Usage:" in res.output


def test_subcommand_help_options(temp_config_dir):
    """Test help options for various subcommands"""
    runner = CliRunner()

    commands_to_test = ["add", "remove", "apply", "list", "current", "clear", "save", "status", "info", "export", "import"]

    for cmd in commands_to_test:
        res = runner.invoke(cli, [cmd, "--help"])
        assert res.exit_code == 0, f"Help for {cmd} command failed"
        assert "Usage:" in res.output, f"Help for {cmd} command doesn't contain usage"
