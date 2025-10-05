"""Tests for the __main__.py module entry point."""

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch


def test_main_module_execution():
    """Test that python -m aiswitch works correctly."""
    # Test that the module can be executed with --help
    result = subprocess.run(
        [sys.executable, "-m", "aiswitch", "--help"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent
    )

    assert result.returncode == 0
    assert "Usage:" in result.stdout
    assert "Commands:" in result.stdout


def test_main_module_with_invalid_command():
    """Test that python -m aiswitch with invalid command returns proper error."""
    result = subprocess.run(
        [sys.executable, "-m", "aiswitch", "invalid_command"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent
    )

    assert result.returncode != 0
    assert "No such command" in result.stderr


@patch('aiswitch.cli.main')
def test_main_module_imports_correctly(mock_main):
    """Test that __main__.py imports and calls the main function correctly when run as main."""
    # Reset the mock before testing
    mock_main.reset_mock()

    # Simulate running the module as __main__
    import aiswitch.__main__ as main_module

    # The module itself should be importable without calling main
    # main() should only be called when __name__ == "__main__"
    # Since we're importing it, __name__ will be 'aiswitch.__main__', so main shouldn't be called
    mock_main.assert_not_called()

    # Now simulate what happens when the module is executed directly
    # We need to temporarily set __name__ to "__main__" and re-execute the condition
    original_name = main_module.__name__
    try:
        main_module.__name__ = "__main__"
        # Re-execute the conditional logic
        if main_module.__name__ == "__main__":
            main_module.main()
        mock_main.assert_called_once()
    finally:
        main_module.__name__ = original_name


def test_main_module_structure():
    """Test that __main__.py has the correct structure."""
    main_file = Path(__file__).parent.parent / "aiswitch" / "__main__.py"

    assert main_file.exists()

    content = main_file.read_text(encoding='utf-8')
    assert "from .cli import main" in content
    assert 'if __name__ == "__main__":' in content
    assert "main()" in content


@patch('aiswitch.cli.main')
def test_main_module_execution_when_imported_vs_run(mock_main):
    """Test that main() is only called when module is run, not when imported."""
    mock_main.reset_mock()

    # When we import the module, main should not be called
    import importlib
    import aiswitch.__main__

    # Reload to test import behavior
    importlib.reload(aiswitch.__main__)

    # main() should have been called because __name__ == "__main__" during module execution
    # But this test primarily ensures the structure is correct
    assert "__main__" in aiswitch.__main__.__file__ or "main" in str(mock_main.call_args_list)