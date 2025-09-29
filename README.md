# AISwitch

AISwitch is a lightweight command-line helper for managing environment variables when switching between different AI API providers. It lets you store multiple presets, apply them to your shell, and persist them across sessions with one command.

## Requirements

- Python 3.12 or newer
- macOS, Linux, or Windows (shell integration currently targets bash/zsh/fish on Unix-like systems)

## Installation

### Install from PyPI (recommended)

```bash
pip install aiswitch
```

### Install from source

```bash
git clone https://github.com/your-org/aiswitch.git
cd aiswitch
python -m venv .venv
source .venv/bin/activate  # Windows use .venv\Scripts\activate
uv tool install --editable .
```

If you prefer [uv](https://github.com/astral-sh/uv), run `uv sync` in the project root and use `uv run aiswitch ...` for commands.

## Quick Start

```bash
# 1) Create a preset (example: OpenAI public cloud)
aiswitch add openai \
  API_KEY sk-your-key \
  API_BASE_URL https://api.openai.com/v1 \
  API_MODEL gpt-4o

# 2) Switch to this preset (takes effect in current terminal)
# First time will automatically guide shell integration installation
aiswitch apply openai

# 3) Optional: Persist current preset to shell config (auto-load in new terminals)
aiswitch save

# 4) View all presets
aiswitch list
```

## Everyday Commands

| Action | Command |
| --- | --- |
| Create a preset | `aiswitch add <name> KEY value ...` |
| Apply preset to current terminal | `aiswitch apply <name>` |
| Persist current preset into shell profile | `aiswitch save` |
| Clear current session and persistent vars | `aiswitch clear` |
| Inspect available presets | `aiswitch list` (add `--verbose`) |
| Show the active preset | `aiswitch current` (add `--verbose`) |
| Remove a preset | `aiswitch remove <name>` (add `--force`) |
| Run one command with a preset (no pollution) | `aiswitch apply <name> -- <cmd>` |
| Open a subshell with a preset (temporary) | `aiswitch shell <name>` |
| Export preset configurations | `aiswitch export <name>` or `aiswitch export --all` |
| Import preset configurations | `aiswitch import <file>` |
| Show runtime/config paths | `aiswitch status`, `aiswitch info` |

## Shell Integration

On first `aiswitch apply <name>`, AISwitch detects whether shell integration is installed. If not, it offers to install a tiny function into your shell profile so `apply` directly updates the current terminal without extra steps. After installation, reload your shell (`source ~/.bashrc`, `source ~/.zshrc`, or restart the terminal) once.

Useful maintenance commands:

```bash
# Manually install/reinstall integration (optional)
aiswitch install [--force]

# Persist current preset variables to shell config file
aiswitch save

# Clear persisted variables and current session variables
aiswitch clear

# Uninstall shell integration
aiswitch uninstall
```

## Configuration Files

AISwitch keeps its data under `~/.config/aiswitch/` by default (falling back to `~/.aiswitch/` or a per-user temp folder if needed):

- `config.yaml`: global settings and the name of the current preset
- `presets/<name>.yaml`: individual preset definitions
- `current.yaml`: snapshot of the preset currently applied to your shell

You can also create a project-scoped configuration in the repository root:

```yaml
# .aiswitch.yaml
preset: openai
overrides:
  API_MODEL: gpt-4o-mini
```

Project configs let you pin a preset and override individual variables when you run AISwitch from that directory. `aiswitch status` reports whether a `.aiswitch.yaml` file is detected.

## Export and Import

You can export and import preset configurations for backup, sharing, or migration:

```bash
# Export a single preset
aiswitch export openai

# Export a single preset to file
aiswitch export openai -o openai-preset.json

# Export all presets to file
aiswitch export --all -o all-presets.json

# Include secrets in export (by default, sensitive values are redacted)
aiswitch export --all --include-secrets -o config-with-secrets.json

# Import presets from file
aiswitch import config.json

# Force overwrite existing presets during import
aiswitch import config.json --force
```

**Security Note**: By default, export redacts sensitive values (containing "KEY", "SECRET", or "TOKEN") with `***REDACTED***`. Use `--include-secrets` to export actual values when needed.

## Development Setup

These steps assume you are working inside a clone of this repository:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows use .venv\Scripts\activate
pip install -e .
```

Useful commands while developing:

```bash
# View CLI help
python -m aiswitch --help

# Run commands locally (automatically points to current source code)
aiswitch status

# Run with uv (if you use uv to manage environment)
uv run aiswitch list

# Run test suite (recommended using uv for isolated environment)
uv run python -m pytest

# Run tests and view coverage
uv run python -m pytest --cov=aiswitch --cov-report=term-missing

# Generate HTML coverage report (visual view)
uv run python -m pytest --cov=aiswitch --cov-report=html
# Then open htmlcov/index.html to view detailed report

# If you use virtual environment with pytest installed, you can also run directly
python -m pytest
```

When you change CLI behaviour, update `pyproject.toml` version metadata as needed and run your preferred testing or linting workflow before publishing.
