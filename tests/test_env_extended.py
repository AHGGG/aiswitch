"""Extended tests for env.py module to improve coverage."""

import os
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from aiswitch.env import EnvManager
from aiswitch.config import PresetConfig


class TestEnvManagerExtended:
    def setup_method(self):
        self.env_manager = EnvManager()

    def test_init(self):
        """Test EnvManager initialization."""
        assert self.env_manager.default_variables == ["API_KEY", "API_BASE_URL", "API_MODEL"]
        assert hasattr(self.env_manager, 'system')

    def test_apply_preset_with_current_preset(self):
        """Test applying preset when there's a current preset."""
        # Set up current environment with old preset
        old_preset = PresetConfig(
            name="old",
            variables={"API_KEY": "old-key", "API_BASE_URL": "old-url", "OLD_VAR": "old-value"},
            description="",
            tags=[]
        )

        new_preset = PresetConfig(
            name="new",
            variables={"API_KEY": "new-key", "API_BASE_URL": "new-url", "NEW_VAR": "new-value"},
            description="",
            tags=[]
        )

        # Set environment variables for old preset
        for key, value in old_preset.variables.items():
            os.environ[key] = value

        applied_vars, cleared_vars = self.env_manager.apply_preset(
            new_preset,
            current_preset=old_preset
        )

        # Check that old variables were cleared
        assert "OLD_VAR" not in os.environ
        assert set(cleared_vars) == {"API_KEY", "API_BASE_URL", "OLD_VAR"}

        # Check that new variables were applied
        assert os.environ["API_KEY"] == "new-key"
        assert os.environ["API_BASE_URL"] == "new-url"
        assert os.environ["NEW_VAR"] == "new-value"

        assert applied_vars == new_preset.variables

    def test_apply_preset_without_current_preset(self):
        """Test applying preset when there's no current preset."""
        # Set up some existing environment variables
        os.environ["ANTHROPIC_API_KEY"] = "old-anthropic-key"
        os.environ["API_MODEL"] = "old-model"
        os.environ["UNRELATED_VAR"] = "should-remain"

        new_preset = PresetConfig(
            name="new",
            variables={"API_KEY": "new-key", "API_BASE_URL": "new-url"},
            description="",
            tags=[]
        )

        applied_vars, cleared_vars = self.env_manager.apply_preset(new_preset, current_preset=None)

        # Check that old AISwitch variables were cleared (except those in new preset)
        assert "ANTHROPIC_API_KEY" not in os.environ
        assert "API_MODEL" not in os.environ  # Not in new preset, so cleared
        assert os.environ["UNRELATED_VAR"] == "should-remain"  # Not an AISwitch var

        # Check that new variables were applied
        assert os.environ["API_KEY"] == "new-key"
        assert os.environ["API_BASE_URL"] == "new-url"

        assert "ANTHROPIC_API_KEY" in cleared_vars
        assert "API_MODEL" in cleared_vars

    def test_apply_preset_without_clearing(self):
        """Test applying preset without clearing previous variables."""
        os.environ["EXISTING_VAR"] = "existing-value"

        preset = PresetConfig(
            name="test",
            variables={"API_KEY": "test-key"},
            description="",
            tags=[]
        )

        applied_vars, cleared_vars = self.env_manager.apply_preset(
            preset,
            clear_previous=False
        )

        # Check that existing variables remain
        assert os.environ["EXISTING_VAR"] == "existing-value"
        assert os.environ["API_KEY"] == "test-key"

        assert applied_vars == {"API_KEY": "test-key"}
        assert cleared_vars == []

    def test_clear_variables_default(self):
        """Test clearing default variables."""
        # Set up environment
        os.environ["API_KEY"] = "key"
        os.environ["API_BASE_URL"] = "url"
        os.environ["API_MODEL"] = "model"
        os.environ["OTHER_VAR"] = "other"

        cleared_vars = self.env_manager.clear_variables()

        # Check that default variables were cleared
        assert "API_KEY" not in os.environ
        assert "API_BASE_URL" not in os.environ
        assert "API_MODEL" not in os.environ
        assert os.environ["OTHER_VAR"] == "other"  # Should remain

        assert set(cleared_vars) == {"API_KEY", "API_BASE_URL", "API_MODEL"}

    def test_clear_variables_custom_list(self):
        """Test clearing custom list of variables."""
        os.environ["VAR1"] = "value1"
        os.environ["VAR2"] = "value2"
        os.environ["VAR3"] = "value3"

        cleared_vars = self.env_manager.clear_variables(["VAR1", "VAR3"])

        assert "VAR1" not in os.environ
        assert os.environ["VAR2"] == "value2"  # Should remain
        assert "VAR3" not in os.environ

        assert set(cleared_vars) == {"VAR1", "VAR3"}

    def test_clear_variables_nonexistent(self):
        """Test clearing variables that don't exist."""
        cleared_vars = self.env_manager.clear_variables(["NONEXISTENT1", "NONEXISTENT2"])
        assert cleared_vars == []

    def test_get_current_env_default(self):
        """Test getting current environment with default variables."""
        os.environ["API_KEY"] = "key"
        os.environ["API_MODEL"] = "model"
        # API_BASE_URL not set

        current_env = self.env_manager.get_current_env()

        expected = {
            "API_KEY": "key",
            "API_BASE_URL": "",  # Should be empty string for missing vars
            "API_MODEL": "model"
        }
        assert current_env == expected

    def test_get_current_env_custom_variables(self):
        """Test getting current environment with custom variables."""
        os.environ["CUSTOM1"] = "value1"
        os.environ["CUSTOM2"] = "value2"

        current_env = self.env_manager.get_current_env(["CUSTOM1", "CUSTOM2", "MISSING"])

        expected = {
            "CUSTOM1": "value1",
            "CUSTOM2": "value2",
            "MISSING": ""
        }
        assert current_env == expected

    def test_has_env_variables_true(self):
        """Test has_env_variables when variables exist."""
        os.environ["API_KEY"] = "key"
        assert self.env_manager.has_env_variables() is True

    def test_has_env_variables_false_empty(self):
        """Test has_env_variables when variables are empty."""
        os.environ["API_KEY"] = ""
        os.environ["API_BASE_URL"] = ""
        os.environ["API_MODEL"] = ""

        assert self.env_manager.has_env_variables() is False

    def test_has_env_variables_false_missing(self):
        """Test has_env_variables when variables are missing."""
        # Ensure default variables are not set
        for var in self.env_manager.default_variables:
            os.environ.pop(var, None)

        assert self.env_manager.has_env_variables() is False

    def test_has_env_variables_custom_list(self):
        """Test has_env_variables with custom variable list."""
        os.environ["CUSTOM_VAR"] = "value"

        assert self.env_manager.has_env_variables(["CUSTOM_VAR"]) is True
        assert self.env_manager.has_env_variables(["MISSING_VAR"]) is False

    def test_validate_env_variables_success(self):
        """Test successful validation of environment variables."""
        variables = {
            "API_KEY": "sk-test123",
            "API_BASE_URL": "https://api.example.com",
            "API_MODEL": "gpt-4"
        }

        validated = self.env_manager.validate_env_variables(variables)
        assert validated == variables

    def test_validate_env_variables_url_normalization(self):
        """Test URL normalization during validation."""
        variables = {
            "API_BASE_URL": "https://api.example.com/"  # Trailing slash
        }

        validated = self.env_manager.validate_env_variables(variables)
        assert validated["API_BASE_URL"] == "https://api.example.com"

    def test_validate_env_variables_empty_value(self):
        """Test validation with empty values."""
        variables = {
            "API_KEY": "",
            "API_BASE_URL": "   "  # Only whitespace
        }

        with pytest.raises(ValueError) as exc_info:
            self.env_manager.validate_env_variables(variables)

        error_msg = str(exc_info.value)
        assert "API_KEY" in error_msg
        assert "API_BASE_URL" in error_msg
        assert "cannot be empty" in error_msg

    def test_validate_env_variables_invalid_url(self):
        """Test validation with invalid URL."""
        variables = {
            "API_BASE_URL": "invalid-url"
        }

        with pytest.raises(ValueError) as exc_info:
            self.env_manager.validate_env_variables(variables)

        error_msg = str(exc_info.value)
        assert "must start with http://" in error_msg

    def test_validate_env_variables_mixed_errors(self):
        """Test validation with multiple types of errors."""
        variables = {
            "API_KEY": "",
            "API_BASE_URL": "invalid-url",
            "VALID_VAR": "valid-value"
        }

        with pytest.raises(ValueError) as exc_info:
            self.env_manager.validate_env_variables(variables)

        error_msg = str(exc_info.value)
        assert "API_KEY" in error_msg
        assert "API_BASE_URL" in error_msg

    def test_export_to_shell_windows(self):
        """Test exporting to shell on Windows."""
        # Temporarily set the system to Windows
        original_system = self.env_manager.system
        self.env_manager.system = "Windows"

        try:
            with patch.object(self.env_manager, '_export_to_windows_env', return_value=True) as mock_export:
                variables = {"API_KEY": "test"}
                result = self.env_manager.export_to_shell(variables)

                assert result is True
                mock_export.assert_called_once_with(variables)
        finally:
            self.env_manager.system = original_system

    def test_export_to_shell_unix(self):
        """Test exporting to shell on Unix."""
        # Temporarily set the system to Linux
        original_system = self.env_manager.system
        self.env_manager.system = "Linux"

        try:
            with patch.object(self.env_manager, '_export_to_unix_shell', return_value=True) as mock_export:
                variables = {"API_KEY": "test"}
                shell_file = Path("/tmp/.bashrc")

                result = self.env_manager.export_to_shell(variables, shell_file)

                assert result is True
                mock_export.assert_called_once_with(variables, shell_file)
        finally:
            self.env_manager.system = original_system

    def test_export_to_unix_shell_success(self):
        """Test successful export to Unix shell."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.bashrc') as f:
            shell_file = Path(f.name)

        try:
            variables = {"API_KEY": "test-key", "API_URL": "test-url"}
            result = self.env_manager._export_to_unix_shell(variables, shell_file)

            assert result is True

            content = shell_file.read_text()
            assert "# AISwitch environment variables" in content
            assert 'export API_KEY="test-key"' in content
            assert 'export API_URL="test-url"' in content
        finally:
            shell_file.unlink()

    def test_export_to_unix_shell_no_file(self):
        """Test export to Unix shell when file doesn't exist."""
        nonexistent_file = Path("/nonexistent/directory/.bashrc")
        result = self.env_manager._export_to_unix_shell({}, nonexistent_file)

        assert result is False

    def test_export_to_unix_shell_no_shell_file_provided(self):
        """Test export to Unix shell with no shell file provided."""
        with patch.object(self.env_manager, '_detect_shell_config', return_value=None):
            result = self.env_manager._export_to_unix_shell({"API_KEY": "test"})
            assert result is False

    def test_export_to_unix_shell_detect_config(self):
        """Test export to Unix shell with shell config detection."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.bashrc') as f:
            shell_file = Path(f.name)

        try:
            with patch.object(self.env_manager, '_detect_shell_config', return_value=shell_file):
                result = self.env_manager._export_to_unix_shell({"API_KEY": "test"})
                assert result is True
        finally:
            shell_file.unlink()

    def test_export_to_unix_shell_write_error(self):
        """Test export to Unix shell with write error."""
        with patch('builtins.open', side_effect=PermissionError("Access denied")):
            with tempfile.NamedTemporaryFile() as f:
                shell_file = Path(f.name)
                result = self.env_manager._export_to_unix_shell({"API_KEY": "test"}, shell_file)
                assert result is False

    @patch('aiswitch.env.subprocess.run')
    def test_export_to_windows_env_success(self, mock_run):
        """Test successful export to Windows environment."""
        mock_run.return_value = MagicMock()

        variables = {"API_KEY": "test-key", "API_URL": "test-url"}
        result = self.env_manager._export_to_windows_env(variables)

        assert result is True
        assert mock_run.call_count == 2  # Two variables

        # Check that setx was called for each variable
        calls = mock_run.call_args_list
        assert ['setx', 'API_KEY', 'test-key'] in [call[0][0] for call in calls]
        assert ['setx', 'API_URL', 'test-url'] in [call[0][0] for call in calls]

    @patch('aiswitch.env.subprocess.run')
    def test_export_to_windows_env_failure(self, mock_run):
        """Test export to Windows environment with failure."""
        mock_run.side_effect = subprocess.CalledProcessError(1, 'setx')

        result = self.env_manager._export_to_windows_env({"API_KEY": "test"})
        assert result is False

    @patch.dict(os.environ, {'SHELL': '/bin/zsh'})
    @patch('aiswitch.env.Path.home')
    def test_detect_shell_config_zsh(self, mock_home):
        """Test shell config detection for zsh."""
        mock_home.return_value = Path("/home/user")

        with patch('pathlib.Path.exists') as mock_exists:
            # .zshrc exists
            mock_exists.side_effect = lambda: True

            result = self.env_manager._detect_shell_config()
            assert result == Path("/home/user/.zshrc")

    @patch.dict(os.environ, {'SHELL': '/bin/bash'})
    def test_detect_shell_config_bash(self):
        """Test shell config detection for bash."""
        # Create a temporary directory structure
        with tempfile.TemporaryDirectory() as temp_dir:
            home_path = Path(temp_dir)
            bashrc_path = home_path / ".bashrc"

            # Create the .bashrc file
            bashrc_path.touch()

            with patch('aiswitch.env.Path.home', return_value=home_path):
                result = self.env_manager._detect_shell_config()
                assert result == bashrc_path

    @patch.dict(os.environ, {'SHELL': '/bin/unknown'})
    def test_detect_shell_config_fallback(self):
        """Test shell config detection fallback."""
        # Create a temporary directory structure
        with tempfile.TemporaryDirectory() as temp_dir:
            home_path = Path(temp_dir)
            profile_path = home_path / ".profile"

            # Create the .profile file (but not the shell-specific ones)
            profile_path.touch()

            with patch('aiswitch.env.Path.home', return_value=home_path):
                result = self.env_manager._detect_shell_config()
                assert result == profile_path

    @patch('aiswitch.env.Path.home')
    def test_detect_shell_config_none_exist(self, mock_home):
        """Test shell config detection when no config files exist."""
        mock_home.return_value = Path("/home/user")

        with patch('pathlib.Path.exists', return_value=False):
            result = self.env_manager._detect_shell_config()
            # Should return first option (.bashrc) as default
            assert result == Path("/home/user/.bashrc")

    def test_get_env_info_unix(self):
        """Test getting environment info on Unix."""
        # Mock the system attribute directly on the instance
        original_system = self.env_manager.system
        self.env_manager.system = "Linux"

        try:
            with patch.dict(os.environ, {'SHELL': '/bin/bash'}):
                with patch.object(self.env_manager, '_detect_shell_config') as mock_detect:
                    mock_detect.return_value = Path("/home/user/.bashrc")

                    # Set some environment variables
                    os.environ["API_KEY"] = "secret-key"
                    os.environ["API_BASE_URL"] = "https://api.example.com"

                    info = self.env_manager.get_env_info()

                    assert info["system"] == "Linux"
                    assert info["shell"] == "/bin/bash"
                    assert str(info["config_detected"]) == str(Path("/home/user/.bashrc"))
                    assert info["current_API_KEY"] == "***"  # Should be masked
                    assert info["current_API_BASE_URL"] == "https://api.example.com"
        finally:
            # Restore original system
            self.env_manager.system = original_system

    def test_get_env_info_windows(self):
        """Test getting environment info on Windows."""
        # Temporarily set the system to Windows
        original_system = self.env_manager.system
        self.env_manager.system = "Windows"

        try:
            info = self.env_manager.get_env_info()

            assert info["system"] == "Windows"
            assert info["config_detected"] == "Windows Registry"
        finally:
            self.env_manager.system = original_system

    def test_get_env_info_with_empty_vars(self):
        """Test getting environment info with empty variables."""
        # Ensure no environment variables are set
        for var in self.env_manager.default_variables:
            os.environ.pop(var, None)

        info = self.env_manager.get_env_info()

        # Should not contain current_* keys for empty variables
        for var in self.env_manager.default_variables:
            assert f"current_{var}" not in info

    @patch.dict(os.environ, {}, clear=True)
    def test_get_env_info_no_shell(self):
        """Test getting environment info when no SHELL env var."""
        info = self.env_manager.get_env_info()
        assert info["shell"] == "unknown"