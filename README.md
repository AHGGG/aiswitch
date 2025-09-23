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
source .venv/bin/activate  # Windows 使用 .venv\Scripts\activate
uv tool install --editable .
```

If you prefer [uv](https://github.com/astral-sh/uv), run `uv sync` in the project root and use `uv run aiswitch ...` for commands.

## Quick Start

```bash
# 1. 创建一个预设 (示例: OpenAI 公共云)
aiswitch add openai \
  API_KEY sk-your-key \
  API_BASE_URL https://api.openai.com/v1 \
  API_MODEL gpt-4o

# 2. 切换到该预设
aiswitch use openai

# 3. 将环境变量注入当前 shell
eval $(aiswitch use openai --export)

# 4. 查看所有预设
aiswitch list
```

## Everyday Commands

| Action | Command |
| --- | --- |
| Create or update environment presets | `aiswitch add <name> KEY value ...` |
| Switch presets and print masked variables | `aiswitch use <name>` |
| Apply variables directly to current shell | `eval $(aiswitch use <name> --export)` |
| Inspect available presets | `aiswitch list` (append `--verbose` for details) |
| Show the active preset | `aiswitch current` (append `--verbose` for env values) |
| Remove a preset | `aiswitch remove <name>` (add `--force` to delete the active one) |
| Clear in-memory variables and shell config | `aiswitch clear` |
| Persist current preset into shell profile | `aiswitch save` |
| Show runtime/config paths | `aiswitch status`, `aiswitch info` |

## Shell Integration

`aiswitch use <name> --export` works in any shell via `eval`, but you can install a helper function that runs automatically:

```bash
# 安装集成 (会在 ~/.bashrc 或 ~/.zshrc 中注入函数)
aiswitch install

# 将当前预设的变量持久化到 shell 配置文件中
aiswitch save

# 清除已持久化的变量和当前会话变量
aiswitch clear

# 卸载 shell 集成
aiswitch uninstall
```

After `aiswitch install`, subsequent `aiswitch use <name>` calls update your current shell without `eval`. Reload your shell (`source ~/.bashrc`, `source ~/.zshrc`, or restart the terminal) to activate the integration.

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

## Development Setup

These steps assume you are working inside a clone of this repository:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows 使用 .venv\Scripts\activate
pip install -e .
```

Useful commands while developing:

```bash
# 查看 CLI 帮助
python -m aiswitch --help

# 在本地运行命令 (自动指向当前源码)
aiswitch status

# 使用 uv 运行 (如果你使用 uv 管理环境)
uv run aiswitch list
```

When you change CLI behaviour, update `pyproject.toml` version metadata as needed and run your preferred testing or linting workflow before publishing.
