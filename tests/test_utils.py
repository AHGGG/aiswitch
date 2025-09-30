"""Tests for the utils.py module."""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from aiswitch.utils import (
    is_valid_preset_name,
    is_valid_url,
    normalize_url,
    mask_sensitive_value,
    get_system_info,
    ensure_directory_exists,
    safe_file_operation,
    format_table,
    find_project_root,
    truncate_string,
    parse_key_value_pairs,
    colorize,
    success_message,
    error_message,
    warning_message,
    info_message,
    validate_environment_variable_name,
    clean_environment_variable_value,
    get_file_permissions,
    create_backup_filename,
    is_writable_directory,
    human_readable_size
)


class TestPresetNameValidation:
    def test_valid_preset_names(self):
        """Test valid preset names."""
        valid_names = [
            "openai",
            "claude",
            "test123",
            "my-preset",
            "my_preset",
            "preset-1",
            "a",
            "A123",
            "test_test_test"
        ]
        for name in valid_names:
            assert is_valid_preset_name(name), f"'{name}' should be valid"

    def test_invalid_preset_names(self):
        """Test invalid preset names."""
        invalid_names = [
            "",
            "   ",
            None,
            "preset with spaces",
            "preset@invalid",
            "preset!",
            ".hidden",
            "-starting-dash",
            "a" * 51,  # Too long
            "preset/slash",
            "preset\\backslash",
            "preset=equals"
        ]
        for name in invalid_names:
            assert not is_valid_preset_name(name), f"'{name}' should be invalid"


class TestUrlValidation:
    def test_valid_urls(self):
        """Test valid URLs."""
        valid_urls = [
            "https://api.openai.com",
            "http://localhost:8080",
            "https://api.example.com/v1",
            "http://192.168.1.1:3000",
            "https://subdomain.example.com",
            "http://localhost",
            "https://api.anthropic.com/v1/messages"
        ]
        for url in valid_urls:
            assert is_valid_url(url), f"'{url}' should be valid"

    def test_invalid_urls(self):
        """Test invalid URLs."""
        invalid_urls = [
            "",
            "not-a-url",
            "ftp://example.com",
            "just-text",
            "http://",
            "https://",
            "://example.com"
        ]
        for url in invalid_urls:
            assert not is_valid_url(url), f"'{url}' should be invalid"

    def test_normalize_url(self):
        """Test URL normalization."""
        test_cases = [
            ("api.openai.com", "https://api.openai.com"),
            ("https://api.openai.com", "https://api.openai.com"),
            ("http://localhost:8080/", "http://localhost:8080"),
            ("https://example.com/", "https://example.com"),
            ("  api.example.com  ", "https://api.example.com"),
            ("api.example.com/path/", "https://api.example.com/path")
        ]
        for input_url, expected in test_cases:
            assert normalize_url(input_url) == expected


class TestSensitiveValueMasking:
    def test_mask_short_values(self):
        """Test masking of short values."""
        assert mask_sensitive_value("abc") == "***"
        assert mask_sensitive_value("12345678") == "********"

    def test_mask_long_values(self):
        """Test masking of long values."""
        assert mask_sensitive_value("sk-1234567890abcdef") == "sk-1***********cdef"
        assert mask_sensitive_value("very-long-secret-key-value") == "very******************alue"

    def test_mask_custom_char(self):
        """Test masking with custom character."""
        assert mask_sensitive_value("secret123", mask_char='#') == "secr#t123"


class TestSystemInfo:
    @patch('aiswitch.utils.platform.system')
    @patch('aiswitch.utils.platform.version')
    @patch('aiswitch.utils.platform.machine')
    @patch('aiswitch.utils.sys.version')
    @patch.dict(os.environ, {'SHELL': '/bin/bash'})
    def test_get_system_info(self, mock_version, mock_machine, mock_platform_version, mock_platform_system):
        """Test system info collection."""
        mock_platform_system.return_value = "Linux"
        mock_platform_version.return_value = "5.4.0"
        mock_machine.return_value = "x86_64"
        mock_version.split.return_value = ["3.9.0", "(default,", "Oct", "9", "2020,", "15:56:51)"]

        info = get_system_info()

        assert info['platform'] == "Linux"
        assert info['platform_version'] == "5.4.0"
        assert info['architecture'] == "x86_64"
        assert info['shell'] == "/bin/bash"
        assert '3.9.0' in info['python_version']


class TestDirectoryOperations:
    def test_ensure_directory_exists_new(self):
        """Test creating new directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            new_dir = Path(temp_dir) / "new" / "nested" / "dir"
            result = ensure_directory_exists(new_dir)

            assert result == new_dir
            assert new_dir.exists()
            assert new_dir.is_dir()

    def test_ensure_directory_exists_existing(self):
        """Test with existing directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            existing_dir = Path(temp_dir)
            result = ensure_directory_exists(existing_dir)

            assert result == existing_dir
            assert existing_dir.exists()

    def test_ensure_directory_exists_string_path(self):
        """Test with string path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            new_dir_str = str(Path(temp_dir) / "string_dir")
            result = ensure_directory_exists(new_dir_str)

            assert isinstance(result, Path)
            assert result.exists()


class TestSafeFileOperation:
    def test_safe_file_operation_success(self):
        """Test successful file operation."""
        def mock_operation(value):
            return value * 2

        result = safe_file_operation(mock_operation, 5)
        assert result == 10

    def test_safe_file_operation_permission_error(self):
        """Test file operation with permission error."""
        def mock_operation():
            raise PermissionError("Access denied")

        with pytest.raises(PermissionError) as exc_info:
            safe_file_operation(mock_operation)
        assert "Permission denied" in str(exc_info.value)

    def test_safe_file_operation_os_error(self):
        """Test file operation with OS error."""
        def mock_operation():
            raise OSError("File not found")

        with pytest.raises(OSError) as exc_info:
            safe_file_operation(mock_operation)
        assert "File operation failed" in str(exc_info.value)

    def test_safe_file_operation_unexpected_error(self):
        """Test file operation with unexpected error."""
        def mock_operation():
            raise ValueError("Some error")

        with pytest.raises(Exception) as exc_info:
            safe_file_operation(mock_operation)
        assert "Unexpected error during file operation" in str(exc_info.value)


class TestTableFormatting:
    def test_format_table_basic(self):
        """Test basic table formatting."""
        headers = ["Name", "Value"]
        rows = [["test", "123"], ["example", "456"]]

        result = format_table(headers, rows)

        assert "Name" in result
        assert "Value" in result
        assert "test" in result
        assert "123" in result
        assert "|" in result
        assert "-" in result

    def test_format_table_empty_rows(self):
        """Test table formatting with empty rows."""
        headers = ["Header1", "Header2"]
        rows = []

        result = format_table(headers, rows)
        assert result == ""

    def test_format_table_different_widths(self):
        """Test table with columns of different widths."""
        headers = ["Short", "Very Long Header"]
        rows = [["a", "b"], ["longer text", "c"]]

        result = format_table(headers, rows)

        lines = result.split('\n')
        assert len(lines) >= 3  # Header, separator, at least one row
        # Check that columns are properly aligned
        header_line = lines[0]
        assert "Short" in header_line
        assert "Very Long Header" in header_line

    def test_format_table_min_width(self):
        """Test table with minimum width setting."""
        headers = ["A", "B"]
        rows = [["x", "y"]]

        result = format_table(headers, rows, min_width=15)

        lines = result.split('\n')
        header_line = lines[0]
        # Each column should be at least 15 characters wide
        assert len(header_line) >= 15 * 2 + 3  # 2 columns + separators


class TestProjectRootFinding:
    def test_find_project_root_with_git(self):
        """Test finding project root with .git directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            git_dir = project_root / ".git"
            git_dir.mkdir()

            nested_dir = project_root / "src" / "deep" / "nested"
            nested_dir.mkdir(parents=True)

            result = find_project_root(nested_dir)
            assert result == project_root

    def test_find_project_root_with_pyproject(self):
        """Test finding project root with pyproject.toml."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            (project_root / "pyproject.toml").touch()

            nested_dir = project_root / "src"
            nested_dir.mkdir()

            result = find_project_root(nested_dir)
            assert result == project_root

    def test_find_project_root_not_found(self):
        """Test when no project root is found."""
        with tempfile.TemporaryDirectory() as temp_dir:
            deep_dir = Path(temp_dir) / "no" / "project" / "markers"
            deep_dir.mkdir(parents=True)

            result = find_project_root(deep_dir)
            assert result is None

    def test_find_project_root_current_dir(self):
        """Test finding project root from current directory."""
        with patch('pathlib.Path.cwd') as mock_cwd:
            mock_cwd.return_value = Path("/fake/current/dir")
            with patch('pathlib.Path.exists') as mock_exists:
                mock_exists.return_value = False
                result = find_project_root()
                assert result is None


class TestStringUtilities:
    def test_truncate_string_short(self):
        """Test truncating string shorter than max length."""
        result = truncate_string("short", 10)
        assert result == "short"

    def test_truncate_string_exact(self):
        """Test truncating string exactly at max length."""
        result = truncate_string("exactly10!", 10)
        assert result == "exactly10!"

    def test_truncate_string_long(self):
        """Test truncating long string."""
        result = truncate_string("this is a very long string", 10)
        assert result == "this is..."
        assert len(result) == 10

    def test_truncate_string_custom_suffix(self):
        """Test truncating with custom suffix."""
        result = truncate_string("long string", 8, suffix="[...]")
        assert result == "lon[...]"
        assert len(result) == 8


class TestKeyValueParsing:
    def test_parse_key_value_pairs_valid(self):
        """Test parsing valid key-value pairs."""
        pairs = ["API_KEY=secret", "URL=https://api.com", "PORT=8080"]
        result = parse_key_value_pairs(pairs)

        expected = {
            "API_KEY": "secret",
            "URL": "https://api.com",
            "PORT": "8080"
        }
        assert result == expected

    def test_parse_key_value_pairs_with_equals_in_value(self):
        """Test parsing when value contains equals sign."""
        pairs = ["KEY=value=with=equals"]
        result = parse_key_value_pairs(pairs)
        assert result == {"KEY": "value=with=equals"}

    def test_parse_key_value_pairs_with_spaces(self):
        """Test parsing with spaces around key and value."""
        pairs = ["  API_KEY  =  secret  "]
        result = parse_key_value_pairs(pairs)
        assert result == {"API_KEY": "secret"}

    def test_parse_key_value_pairs_empty_key(self):
        """Test parsing with empty key."""
        pairs = ["=value"]
        with pytest.raises(ValueError) as exc_info:
            parse_key_value_pairs(pairs)
        assert "Key cannot be empty" in str(exc_info.value)

    def test_parse_key_value_pairs_no_equals(self):
        """Test parsing without equals sign."""
        pairs = ["invalid_format"]
        with pytest.raises(ValueError) as exc_info:
            parse_key_value_pairs(pairs)
        assert "Invalid format" in str(exc_info.value)


class TestColorization:
    @patch('sys.stdout.isatty')
    def test_colorize_with_tty(self, mock_isatty):
        """Test colorization when stdout is a TTY."""
        mock_isatty.return_value = True

        result = colorize("test", "red")
        assert "\033[31m" in result  # Red color code
        assert "\033[0m" in result   # Reset code
        assert "test" in result

    @patch('sys.stdout.isatty')
    def test_colorize_without_tty(self, mock_isatty):
        """Test colorization when stdout is not a TTY."""
        mock_isatty.return_value = False

        result = colorize("test", "red")
        assert result == "test"
        assert "\033[" not in result

    @patch('sys.stdout.isatty')
    def test_colorize_invalid_color(self, mock_isatty):
        """Test colorization with invalid color."""
        mock_isatty.return_value = True

        result = colorize("test", "invalidcolor")
        assert result == "test"

    @patch('sys.stdout.isatty')
    def test_message_functions(self, mock_isatty):
        """Test message formatting functions."""
        mock_isatty.return_value = True

        success = success_message("Success")
        error = error_message("Error")
        warning = warning_message("Warning")
        info = info_message("Info")

        assert "✓" in success
        assert "✗" in error
        assert "⚠" in warning
        assert "ℹ" in info


class TestEnvironmentVariableValidation:
    def test_validate_environment_variable_name_valid(self):
        """Test valid environment variable names."""
        valid_names = [
            "API_KEY",
            "BASE_URL",
            "TEST_VAR",
            "A",
            "API_KEY_V2",
            "LONG_VARIABLE_NAME"
        ]
        for name in valid_names:
            assert validate_environment_variable_name(name), f"'{name}' should be valid"

    def test_validate_environment_variable_name_invalid(self):
        """Test invalid environment variable names."""
        invalid_names = [
            "",
            "api_key",  # lowercase
            "1API_KEY",  # starts with number
            "API-KEY",   # contains dash
            "API KEY",   # contains space
            "api",       # lowercase
            "_API_KEY"   # starts with underscore
        ]
        for name in invalid_names:
            assert not validate_environment_variable_name(name), f"'{name}' should be invalid"

    def test_clean_environment_variable_value(self):
        """Test cleaning environment variable values."""
        test_cases = [
            ('"quoted value"', 'quoted value'),
            ("'single quoted'", 'single quoted'),
            ('  spaced  ', 'spaced'),
            ('normal_value', 'normal_value'),
            ('"nested "quotes""', 'nested "quotes"'),
            ("'mixed \"quotes'", 'mixed "quotes'),
            ('', '')
        ]
        for input_val, expected in test_cases:
            assert clean_environment_variable_value(input_val) == expected


class TestFileUtilities:
    def test_get_file_permissions(self):
        """Test getting file permissions."""
        with tempfile.NamedTemporaryFile() as temp_file:
            temp_path = Path(temp_file.name)
            permissions = get_file_permissions(temp_path)
            assert len(permissions) == 3  # Should be 3 digits
            assert permissions.isdigit()

    def test_get_file_permissions_nonexistent(self):
        """Test getting permissions for nonexistent file."""
        nonexistent = Path("/nonexistent/file")
        permissions = get_file_permissions(nonexistent)
        assert permissions == "unknown"

    def test_create_backup_filename(self):
        """Test backup filename creation."""
        # Since datetime is imported inside the function, we can't easily mock it
        # Let's test the behavior without mocking the timestamp
        original = Path("/path/to/file.txt")
        backup = create_backup_filename(original)

        # Check that it follows the expected pattern
        assert backup.parent == original.parent
        assert backup.name.startswith("file.")
        assert backup.name.endswith(".bak")
        # The middle part should be a timestamp in format YYYYMMDD_HHMMSS
        parts = backup.stem.split(".")
        assert len(parts) == 2  # "file" and "20231201_123456"
        timestamp = parts[1]
        assert len(timestamp) == 15  # YYYYMMDD_HHMMSS format
        assert timestamp[8] == "_"  # Underscore separator

    def test_is_writable_directory_true(self):
        """Test writable directory check for writable directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            assert is_writable_directory(temp_path) is True

    def test_is_writable_directory_false(self):
        """Test writable directory check for nonexistent directory."""
        nonexistent = Path("/nonexistent/directory")
        assert is_writable_directory(nonexistent) is False

    @patch('pathlib.Path.touch')
    @patch('pathlib.Path.unlink')
    def test_is_writable_directory_permission_error(self, mock_unlink, mock_touch):
        """Test writable directory check with permission error."""
        mock_touch.side_effect = PermissionError("Access denied")

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            assert is_writable_directory(temp_path) is False


class TestHumanReadableSize:
    def test_human_readable_size_bytes(self):
        """Test size formatting for bytes."""
        assert human_readable_size(512) == "512.0 B"
        assert human_readable_size(1000) == "1000.0 B"

    def test_human_readable_size_kb(self):
        """Test size formatting for kilobytes."""
        assert human_readable_size(1024) == "1.0 KB"
        assert human_readable_size(1536) == "1.5 KB"

    def test_human_readable_size_mb(self):
        """Test size formatting for megabytes."""
        assert human_readable_size(1024 * 1024) == "1.0 MB"
        assert human_readable_size(1024 * 1024 * 1.5) == "1.5 MB"

    def test_human_readable_size_gb(self):
        """Test size formatting for gigabytes."""
        assert human_readable_size(1024 * 1024 * 1024) == "1.0 GB"

    def test_human_readable_size_tb(self):
        """Test size formatting for terabytes."""
        size_tb = 1024 * 1024 * 1024 * 1024
        assert human_readable_size(size_tb) == "1.0 TB"

    def test_human_readable_size_zero(self):
        """Test size formatting for zero."""
        assert human_readable_size(0) == "0.0 B"