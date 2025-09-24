import os
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from aiswitch.cli import cli


@pytest.fixture()
def temp_config_dir(tmp_path, monkeypatch):
    # Use XDG_CONFIG_HOME for isolation
    cfg_home = tmp_path / "xdg"
    (cfg_home).mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(cfg_home))
    return cfg_home


@pytest.mark.skipif(sys.platform.startswith("win"), reason="Unix-like shells expected")
def test_apply_export_outputs_exports(temp_config_dir):
    r = CliRunner()

    # Add a preset
    add = r.invoke(
        cli,
        [
            "add",
            "openai",
            "API_KEY",
            "sk-test",
            "API_BASE_URL",
            "https://api.openai.com/v1",
            "API_MODEL",
            "gpt-4o",
        ],
    )
    assert add.exit_code == 0, add.output

    # Apply with --export should print unset/export lines
    out = r.invoke(cli, ["apply", "openai", "--export"]).output
    assert "export API_KEY=\"sk-test\"" in out
    assert "export API_BASE_URL=\"https://api.openai.com/v1\"" in out
    assert "export API_MODEL=\"gpt-4o\"" in out


@pytest.mark.skipif(sys.platform.startswith("win"), reason="Unix-like shells expected")
def test_exec_does_not_update_current(temp_config_dir, monkeypatch):
    r = CliRunner()

    # Prepare two presets
    assert r.invoke(cli, ["add", "a", "API_KEY", "1", "API_BASE_URL", "https://x", "API_MODEL", "m"]).exit_code == 0
    assert r.invoke(cli, ["add", "b", "API_KEY", "2", "API_BASE_URL", "https://y", "API_MODEL", "n"]).exit_code == 0

    # Set current to 'a'
    assert r.invoke(cli, ["apply", "a"]).exit_code == 0

    # Run a one-off command under preset 'b'
    # Use a very portable command
    code = r.invoke(cli, ["exec", "b", "bash", "-lc", "echo ok"]).exit_code
    assert code == 0

    # Current should still be 'a'
    status_out = r.invoke(cli, ["status"]).output
    assert "Current preset: a" in status_out


@pytest.mark.skipif(sys.platform.startswith("win"), reason="Unix-like shells expected")
def test_apply_first_run_offers_install(temp_config_dir, monkeypatch):
    # Monkeypatch ShellIntegration to pretend not installed and to succeed on install
    from aiswitch import shell_integration as si

    class DummyIntegration(si.ShellIntegration):
        def is_installed(self) -> bool:  # type: ignore[override]
            return False

        def install(self) -> bool:  # type: ignore[override]
            return True

        def get_shell_config_path(self):  # type: ignore[override]
            return Path(temp_config_dir) / ".bashrc"

    monkeypatch.setattr(si, "ShellIntegration", DummyIntegration)

    r = CliRunner()
    # Add preset
    assert r.invoke(cli, ["add", "x", "API_KEY", "k", "API_BASE_URL", "https://z", "API_MODEL", "m"]).exit_code == 0

    # Simulate TTY and answer yes
    # click's CliRunner doesn't set isatty; we monkeypatch sys.stdin.isatty
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    res = r.invoke(cli, ["apply", "x"], input="y\n")
    assert res.exit_code == 0
    assert "Shell 集成已安装" in res.output

