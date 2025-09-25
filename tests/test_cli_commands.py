import os
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
