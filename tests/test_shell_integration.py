"""Tests for the shell_integration.py module."""

import os
import platform
import tempfile
from pathlib import Path
from unittest.mock import patch, mock_open
import pytest

from aiswitch.shell_integration import ShellIntegration


class TestShellIntegration:
    def setup_method(self):
        self.integration = ShellIntegration()

    def test_init(self):
        """Test ShellIntegration initialization."""
        assert self.integration.system == platform.system()
        assert self.integration.marker_start == "# >>> AISwitch shell integration >>>"
        assert self.integration.marker_end == "# <<< AISwitch shell integration <<<"

    @patch.dict(os.environ, {'SHELL': '/bin/zsh'})
    def test_get_shell_type_zsh(self):
        """Test shell type detection for zsh."""
        assert self.integration.get_shell_type() == 'zsh'

    @patch.dict(os.environ, {'SHELL': '/bin/bash'})
    def test_get_shell_type_bash(self):
        """Test shell type detection for bash."""
        assert self.integration.get_shell_type() == 'bash'

    @patch.dict(os.environ, {'SHELL': '/usr/bin/fish'})
    def test_get_shell_type_fish(self):
        """Test shell type detection for fish."""
        assert self.integration.get_shell_type() == 'fish'

    @patch.dict(os.environ, {'SHELL': '/bin/unknown'})
    def test_get_shell_type_default(self):
        """Test shell type detection defaults to bash for unknown shells."""
        assert self.integration.get_shell_type() == 'bash'

    @patch.dict(os.environ, {}, clear=True)
    def test_get_shell_type_no_shell_env(self):
        """Test shell type detection when SHELL env var is not set."""
        assert self.integration.get_shell_type() == 'bash'

    @patch('aiswitch.shell_integration.Path.home')
    @patch.object(ShellIntegration, 'get_shell_type')
    def test_get_shell_config_path_zsh(self, mock_shell_type, mock_home):
        """Test shell config path for zsh."""
        mock_home.return_value = Path('/home/user')
        mock_shell_type.return_value = 'zsh'

        result = self.integration.get_shell_config_path()
        assert result == Path('/home/user/.zshrc')

    @patch('aiswitch.shell_integration.Path.home')
    @patch.object(ShellIntegration, 'get_shell_type')
    def test_get_shell_config_path_fish(self, mock_shell_type, mock_home):
        """Test shell config path for fish."""
        mock_home.return_value = Path('/home/user')
        mock_shell_type.return_value = 'fish'

        result = self.integration.get_shell_config_path()
        assert result == Path('/home/user/.config/fish/config.fish')

    @patch('aiswitch.shell_integration.Path.home')
    @patch.object(ShellIntegration, 'get_shell_type')
    @patch('aiswitch.shell_integration.platform.system')
    def test_get_shell_config_path_bash_linux(self, mock_system, mock_shell_type, mock_home):
        """Test shell config path for bash on Linux."""
        mock_home.return_value = Path('/home/user')
        mock_shell_type.return_value = 'bash'
        mock_system.return_value = 'Linux'
        # Mock the instance's system attribute
        self.integration.system = 'Linux'

        result = self.integration.get_shell_config_path()
        assert result == Path('/home/user/.bashrc')

    @patch('aiswitch.shell_integration.Path.home')
    @patch.object(ShellIntegration, 'get_shell_type')
    @patch('aiswitch.shell_integration.platform.system')
    def test_get_shell_config_path_bash_macos_no_bashrc(self, mock_system, mock_shell_type, mock_home):
        """Test shell config path for bash on macOS when .bashrc doesn't exist."""
        mock_home.return_value = Path('/home/user')
        mock_shell_type.return_value = 'bash'
        mock_system.return_value = 'Darwin'

        # Mock the system attribute on the instance to ensure it uses Darwin
        self.integration.system = 'Darwin'

        with patch('pathlib.Path.exists', return_value=False):
            result = self.integration.get_shell_config_path()
            assert result == Path('/home/user/.bash_profile')

    @patch('aiswitch.shell_integration.Path.home')
    @patch.object(ShellIntegration, 'get_shell_type')
    @patch('aiswitch.shell_integration.platform.system')
    def test_get_shell_config_path_bash_macos_with_bashrc(self, mock_system, mock_shell_type, mock_home):
        """Test shell config path for bash on macOS when .bashrc exists."""
        mock_home.return_value = Path('/home/user')
        mock_shell_type.return_value = 'bash'
        mock_system.return_value = 'Darwin'

        with patch('pathlib.Path.exists', return_value=True):
            result = self.integration.get_shell_config_path()
            assert result == Path('/home/user/.bashrc')

    @patch.object(ShellIntegration, 'get_shell_type')
    def test_get_integration_code_fish(self, mock_shell_type):
        """Test integration code generation for fish shell."""
        mock_shell_type.return_value = 'fish'

        code = self.integration.get_integration_code()
        assert 'function aiswitch' in code
        assert 'set cmd $argv[1]' in code
        assert 'command aiswitch' in code

    @patch.object(ShellIntegration, 'get_shell_type')
    def test_get_integration_code_bash(self, mock_shell_type):
        """Test integration code generation for bash shell."""
        mock_shell_type.return_value = 'bash'

        code = self.integration.get_integration_code()
        assert 'aiswitch() {' in code
        assert 'local cmd="$1"' in code
        assert 'command aiswitch' in code
        assert 'export -f aiswitch' in code

    def test_is_installed_file_not_exists(self):
        """Test is_installed when config file doesn't exist."""
        with patch.object(self.integration, 'get_shell_config_path') as mock_path:
            mock_path.return_value = Path('/nonexistent/file')
            assert self.integration.is_installed() is False

    def test_is_installed_no_marker(self):
        """Test is_installed when config file exists but no marker."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("some shell config\nexport PATH=$PATH\n")
            temp_path = Path(f.name)

        try:
            with patch.object(self.integration, 'get_shell_config_path') as mock_path:
                mock_path.return_value = temp_path
                assert self.integration.is_installed() is False
        finally:
            temp_path.unlink()

    def test_is_installed_with_marker(self):
        """Test is_installed when marker is present."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write(f"some config\n{self.integration.marker_start}\ncode\n{self.integration.marker_end}\n")
            temp_path = Path(f.name)

        try:
            with patch.object(self.integration, 'get_shell_config_path') as mock_path:
                mock_path.return_value = temp_path
                assert self.integration.is_installed() is True
        finally:
            temp_path.unlink()

    def test_is_installed_read_error(self):
        """Test is_installed when file read fails."""
        with patch.object(self.integration, 'get_shell_config_path') as mock_path:
            mock_path.return_value = Path('/etc/passwd')  # Should cause permission error
            with patch('builtins.open', side_effect=PermissionError()):
                assert self.integration.is_installed() is False

    @patch('aiswitch.shell_integration.shutil.copy2')
    @patch('pathlib.Path.mkdir')
    def test_install_success_new_file(self, mock_mkdir, mock_copy):
        """Test successful installation on new file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / '.bashrc'

            with patch.object(self.integration, 'get_shell_config_path') as mock_path:
                mock_path.return_value = config_path
                with patch.object(self.integration, 'is_installed', return_value=False):
                    with patch.object(self.integration, 'get_integration_code', return_value='mock code'):
                        result = self.integration.install()

            assert result is True
            assert config_path.exists()
            content = config_path.read_text()
            assert self.integration.marker_start in content
            assert self.integration.marker_end in content

    @patch('aiswitch.shell_integration.shutil.copy2')
    def test_install_with_existing_content(self, mock_copy):
        """Test installation with existing file content."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("existing content\n")
            temp_path = Path(f.name)

        try:
            with patch.object(self.integration, 'get_shell_config_path') as mock_path:
                mock_path.return_value = temp_path
                with patch.object(self.integration, 'is_installed', return_value=False):
                    with patch.object(self.integration, 'get_integration_code', return_value='mock code'):
                        result = self.integration.install()

            assert result is True
            content = temp_path.read_text()
            assert "existing content" in content
            assert self.integration.marker_start in content
        finally:
            temp_path.unlink()

    def test_install_already_installed(self):
        """Test installation when already installed (should uninstall first)."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write(f"content\n{self.integration.marker_start}\nold code\n{self.integration.marker_end}\n")
            temp_path = Path(f.name)

        try:
            with patch.object(self.integration, 'get_shell_config_path') as mock_path:
                mock_path.return_value = temp_path
                with patch.object(self.integration, 'get_integration_code', return_value='new code'):
                    result = self.integration.install()

            assert result is True
            content = temp_path.read_text()
            assert "new code" in content
            assert "old code" not in content
        finally:
            temp_path.unlink()

    def test_install_with_interactive_check(self):
        """Test installation with existing interactive check in bashrc."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("some content\ncase $- in\n*i*) echo interactive ;;\nesac\nmore content\n")
            temp_path = Path(f.name)

        try:
            with patch.object(self.integration, 'get_shell_config_path') as mock_path:
                mock_path.return_value = temp_path
                with patch.object(self.integration, 'is_installed', return_value=False):
                    with patch.object(self.integration, 'get_integration_code', return_value='mock code'):
                        result = self.integration.install()

            assert result is True
            content = temp_path.read_text()
            lines = content.split('\n')
            case_index = next(i for i, line in enumerate(lines) if 'case $- in' in line)
            marker_index = next(i for i, line in enumerate(lines) if self.integration.marker_start in line)
            assert marker_index < case_index  # Integration should be before interactive check
        finally:
            temp_path.unlink()

    def test_install_permission_error(self):
        """Test installation with permission error."""
        with patch.object(self.integration, 'get_shell_config_path') as mock_path:
            mock_path.return_value = Path('/root/.bashrc')  # Should cause permission error
            with patch('builtins.open', side_effect=PermissionError("Permission denied")):
                result = self.integration.install()

            assert result is False

    def test_uninstall_file_not_exists(self):
        """Test uninstall when config file doesn't exist."""
        with patch.object(self.integration, 'get_shell_config_path') as mock_path:
            mock_path.return_value = Path('/nonexistent/file')
            assert self.integration.uninstall() is True

    def test_uninstall_no_marker(self):
        """Test uninstall when no marker is present."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("some content\n")
            temp_path = Path(f.name)

        try:
            with patch.object(self.integration, 'get_shell_config_path') as mock_path:
                mock_path.return_value = temp_path
                result = self.integration.uninstall()

            assert result is True
        finally:
            temp_path.unlink()

    def test_uninstall_success(self):
        """Test successful uninstall."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write(f"before\n{self.integration.marker_start}\ncode to remove\n{self.integration.marker_end}\nafter\n")
            temp_path = Path(f.name)

        try:
            with patch.object(self.integration, 'get_shell_config_path') as mock_path:
                mock_path.return_value = temp_path
                result = self.integration.uninstall()

            assert result is True
            content = temp_path.read_text()
            assert "before" in content
            assert "after" in content
            assert self.integration.marker_start not in content
            assert self.integration.marker_end not in content
            assert "code to remove" not in content
        finally:
            temp_path.unlink()

    def test_uninstall_incomplete_markers(self):
        """Test uninstall with incomplete markers."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write(f"before\n{self.integration.marker_start}\ncode\n")  # Missing end marker
            temp_path = Path(f.name)

        try:
            with patch.object(self.integration, 'get_shell_config_path') as mock_path:
                mock_path.return_value = temp_path
                result = self.integration.uninstall()

            assert result is False  # Should fail with incomplete markers
        finally:
            temp_path.unlink()

    def test_get_existing_env_vars_file_not_exists(self):
        """Test getting existing env vars when file doesn't exist."""
        with patch.object(self.integration, 'get_shell_config_path') as mock_path:
            mock_path.return_value = Path('/nonexistent/file')
            result = self.integration.get_existing_env_vars()
            assert result == {}

    def test_get_existing_env_vars_no_env_block(self):
        """Test getting existing env vars when no env block exists."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("some content\nexport NORMAL_VAR=value\n")
            temp_path = Path(f.name)

        try:
            with patch.object(self.integration, 'get_shell_config_path') as mock_path:
                mock_path.return_value = temp_path
                result = self.integration.get_existing_env_vars()
                assert result == {}
        finally:
            temp_path.unlink()

    def test_get_existing_env_vars_with_env_block(self):
        """Test getting existing env vars with env block."""
        content = """
# >>> AISwitch environment variables (test) >>>
export API_KEY="value1"
export API_URL="value2"
# <<< AISwitch environment variables (test) <<<
"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write(content)
            temp_path = Path(f.name)

        try:
            with patch.object(self.integration, 'get_shell_config_path') as mock_path:
                mock_path.return_value = temp_path
                result = self.integration.get_existing_env_vars()
                assert result == {"API_KEY": True, "API_URL": True}
        finally:
            temp_path.unlink()

    def test_save_env_vars_new_file(self):
        """Test saving env vars to new file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / '.bashrc'

            with patch.object(self.integration, 'get_shell_config_path') as mock_path:
                mock_path.return_value = config_path
                with patch.object(self.integration, 'get_existing_env_vars', return_value={}):
                    result = self.integration.save_env_vars({"API_KEY": "test"}, "mypreset")

            assert result is True
            assert config_path.exists()
            content = config_path.read_text()
            assert "export API_KEY=\"test\"" in content
            assert "AISwitch environment variables (mypreset)" in content

    def test_save_env_vars_with_unset(self):
        """Test saving env vars with variables to unset."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / '.bashrc'

            with patch.object(self.integration, 'get_shell_config_path') as mock_path:
                mock_path.return_value = config_path
                with patch.object(self.integration, 'get_existing_env_vars', return_value={"OLD_VAR": True}):
                    result = self.integration.save_env_vars({"API_KEY": "test"}, "mypreset")

            assert result is True
            content = config_path.read_text()
            assert "unset OLD_VAR" in content
            assert "export API_KEY=\"test\"" in content

    def test_save_env_vars_escaping(self):
        """Test saving env vars with special characters that need escaping."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / '.bashrc'

            with patch.object(self.integration, 'get_shell_config_path') as mock_path:
                mock_path.return_value = config_path
                with patch.object(self.integration, 'get_existing_env_vars', return_value={}):
                    result = self.integration.save_env_vars({"API_KEY": 'test"value$with`quotes'}, "mypreset")

            assert result is True
            content = config_path.read_text()
            assert 'export API_KEY="test\\"value\\$with\\`quotes"' in content

    def test_clear_env_vars_file_not_exists(self):
        """Test clearing env vars when file doesn't exist."""
        with patch.object(self.integration, 'get_shell_config_path') as mock_path:
            mock_path.return_value = Path('/nonexistent/file')
            assert self.integration.clear_env_vars() is True

    def test_clear_env_vars_success(self):
        """Test successful clearing of env vars."""
        content = """
before content
# >>> AISwitch environment variables (test1) >>>
export API_KEY="value1"
# <<< AISwitch environment variables (test1) <<<
middle content
# >>> AISwitch environment variables (test2) >>>
export API_URL="value2"
# <<< AISwitch environment variables (test2) <<<
after content
"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write(content)
            temp_path = Path(f.name)

        try:
            with patch.object(self.integration, 'get_shell_config_path') as mock_path:
                mock_path.return_value = temp_path
                result = self.integration.clear_env_vars()

            assert result is True
            content = temp_path.read_text()
            assert "before content" in content
            assert "middle content" in content
            assert "after content" in content
            assert "AISwitch environment variables" not in content
            assert "export API_KEY" not in content
            assert "export API_URL" not in content
        finally:
            temp_path.unlink()

    def test_get_install_command(self):
        """Test getting install command."""
        command = self.integration.get_install_command()
        assert command == 'eval $(aiswitch apply <preset> --export)'

    def test_save_env_vars_permission_error(self):
        """Test save env vars with permission error."""
        with patch.object(self.integration, 'get_shell_config_path') as mock_path:
            mock_path.return_value = Path('/root/.bashrc')
            with patch('builtins.open', side_effect=PermissionError("Permission denied")):
                result = self.integration.save_env_vars({"API_KEY": "test"}, "preset")
                assert result is False

    def test_clear_env_vars_permission_error(self):
        """Test clear env vars with permission error."""
        with patch.object(self.integration, 'get_shell_config_path') as mock_path:
            mock_path.return_value = Path('/root/.bashrc')
            with patch('pathlib.Path.exists', return_value=True):
                with patch('builtins.open', side_effect=PermissionError("Permission denied")):
                    result = self.integration.clear_env_vars()
                    assert result is False