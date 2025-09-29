import os
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner
from click.testing import make_input_stream as original_make_input_stream

from aiswitch.cli import cli
import aiswitch.cli as cli_module


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
def test_apply_one_time_mode_does_not_update_current(temp_config_dir, monkeypatch):
    r = CliRunner()

    # Prepare two presets
    assert r.invoke(cli, ["add", "a", "API_KEY", "1", "API_BASE_URL", "https://x", "API_MODEL", "m"]).exit_code == 0
    assert r.invoke(cli, ["add", "b", "API_KEY", "2", "API_BASE_URL", "https://y", "API_MODEL", "n"]).exit_code == 0

    # Set current to 'a'
    assert r.invoke(cli, ["apply", "a"]).exit_code == 0

    # Mock the one-time mode handler to test behavior
    called = {}

    class DummyCompletedProcess:
        def __init__(self, returncode: int = 0):
            self.returncode = returncode

    def fake_run(command, env=None, shell=None, check=None):  # type: ignore[override]
        called["command"] = command
        called["env"] = env
        called["shell"] = shell
        return DummyCompletedProcess(0)

    monkeypatch.setattr(cli_module.subprocess, "run", fake_run)

    # Test the one-time mode through apply command with -- separator
    # Since CliRunner doesn't handle the -- separator well, we'll test the handler directly
    import sys
    original_argv = sys.argv
    try:
        sys.argv = ["aiswitch", "apply", "b", "--", "echo", "ok"]

        # Test that handle_apply_one_time_mode would process this correctly
        assert cli_module.handle_apply_one_time_mode() is not False

        # Verify the call would have the right environment
        assert called.get("env", {}).get("API_KEY") == "2"

    except SystemExit:
        # Expected when subprocess.run is mocked and sys.exit is called
        pass
    finally:
        sys.argv = original_argv

    # Current should still be 'a' (one-time mode doesn't change current preset)
    status_out = r.invoke(cli, ["status"]).output
    assert "Current preset: a" in status_out


@pytest.mark.skipif(sys.platform.startswith("win"), reason="Unix-like shells expected")
def test_apply_first_run_offers_install(temp_config_dir, monkeypatch):
    # Monkeypatch ShellIntegration to pretend not installed and to succeed on install
    from aiswitch import shell_integration as si

    install_called = {"value": False}

    class DummyIntegration(si.ShellIntegration):
        def is_installed(self) -> bool:  # type: ignore[override]
            return False

        def install(self) -> bool:  # type: ignore[override]
            install_called["value"] = True
            return True

        def get_shell_config_path(self):  # type: ignore[override]
            return Path(temp_config_dir) / ".bashrc"

    monkeypatch.setattr(si, "ShellIntegration", DummyIntegration)
    r = CliRunner()
    # Add preset
    assert r.invoke(cli, ["add", "x", "API_KEY", "k", "API_BASE_URL", "https://z", "API_MODEL", "m"]).exit_code == 0

    # Simulate TTY and answer yes
    # click's CliRunner doesn't set isatty; we monkeypatch sys.stdin.isatty
    def fake_make_input_stream(*args, **kwargs):
        stream = original_make_input_stream(*args, **kwargs)
        setattr(stream, "isatty", lambda: True)
        return stream

    monkeypatch.setattr("click.testing.make_input_stream", fake_make_input_stream)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True, raising=False)
    monkeypatch.setattr("aiswitch.cli.click.confirm", lambda *a, **k: True)
    res = r.invoke(cli, ["apply", "x"], input="y\n")
    assert res.exit_code == 0
    assert "Shell 集成已安装" in res.output
    assert install_called["value"] is True
