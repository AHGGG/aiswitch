import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def restore_environ():
    """Keep global environment stable across CLI invocations."""
    original = os.environ.copy()
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(original)


@pytest.fixture()
def temp_config_dir(tmp_path, monkeypatch):
    """Put AISwitch config and home directories in a temp location."""
    home_dir = tmp_path / "home"
    config_root = tmp_path / "xdg"
    home_dir.mkdir(parents=True, exist_ok=True)
    config_root.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_root))

    return config_root
