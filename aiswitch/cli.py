import click
import sys
from pathlib import Path
from typing import Optional, List
import yaml

from .preset import PresetManager
from .config import PresetConfig


@click.group()
@click.version_option(version="0.1.0", prog_name="aiswitch")
def cli():
    """AISwitch - AI API环境切换工具

    快速切换不同AI API服务提供商的环境配置。
    """
    pass


@cli.command()
@click.argument('name')
@click.option('--key', required=True, help='API密钥')
@click.option('--url', required=True, help='API基础URL')
@click.option('--model', help='默认模型名称')
@click.option('--description', default="", help='预设描述')
@click.option('--tags', help='标签(逗号分隔)')
def add(name: str, key: str, url: str, model: Optional[str], description: str, tags: Optional[str]):
    """添加新的预设配置"""
    try:
        preset_manager = PresetManager()

        tag_list = []
        if tags:
            tag_list = [tag.strip() for tag in tags.split(',')]

        preset = preset_manager.add_preset(
            name=name,
            api_key=key,
            base_url=url,
            model=model,
            description=description,
            tags=tag_list
        )

        click.echo(f"✓ Preset '{name}' added successfully")
        if description:
            click.echo(f"  Description: {description}")
        if model:
            click.echo(f"  Model: {model}")
        if tag_list:
            click.echo(f"  Tags: {', '.join(tag_list)}")

    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('name')
@click.option('--force', is_flag=True, help='强制删除，即使是当前使用的预设')
def remove(name: str, force: bool):
    """删除指定预设"""
    try:
        preset_manager = PresetManager()

        current = preset_manager.get_current_preset()
        if current and current.name == name and not force:
            click.echo(f"Error: Cannot remove current preset '{name}'. Use --force to override.", err=True)
            sys.exit(1)

        if preset_manager.remove_preset(name):
            click.echo(f"✓ Preset '{name}' removed successfully")
        else:
            click.echo(f"Error: Preset '{name}' not found", err=True)
            sys.exit(1)

    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('name')
def use(name: str):
    """切换到指定预设"""
    try:
        preset_manager = PresetManager()
        preset, applied_vars = preset_manager.use_preset(name)

        click.echo(f"✓ Switched to preset '{name}'")

        for var, value in applied_vars.items():
            if 'KEY' in var:
                display_value = f"{value[:8]}..." if len(value) > 8 else "***"
            else:
                display_value = value
            click.echo(f"  {var}: {display_value}")

    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--verbose', is_flag=True, help='显示详细信息')
def list(verbose: bool):
    """列出所有可用预设"""
    try:
        preset_manager = PresetManager()
        presets = preset_manager.list_presets()

        if not presets:
            click.echo("No presets found. Use 'aiswitch add' to create one.")
            return

        current = preset_manager.get_current_preset()
        current_name = current.name if current else None

        click.echo("Available presets:")
        for name, preset in presets:
            marker = "* " if name == current_name else "  "
            if verbose:
                click.echo(f"{marker}{name:<15} - {preset.description}")
                if preset.tags:
                    click.echo(f"    Tags: {', '.join(preset.tags)}")
                click.echo(f"    Created: {preset.created_at[:10]}")
                click.echo(f"    Variables: {len(preset.variables)}")
                click.echo()
            else:
                desc = preset.description if preset.description else "No description"
                click.echo(f"{marker}{name:<15} - {desc}")

    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--verbose', is_flag=True, help='显示详细环境变量')
def current(verbose: bool):
    """显示当前使用的预设"""
    try:
        preset_manager = PresetManager()
        current_preset = preset_manager.get_current_preset()

        if not current_preset:
            click.echo("No current preset. Use 'aiswitch use <preset>' to set one.")
            return

        click.echo(f"Current preset: {current_preset.name}")
        if current_preset.description:
            click.echo(f"Description: {current_preset.description}")

        if verbose:
            click.echo("\nEnvironment variables:")
            for var, value in current_preset.variables.items():
                if 'KEY' in var:
                    display_value = f"{value[:8]}..." if len(value) > 8 else "***"
                else:
                    display_value = value
                click.echo(f"  {var}: {display_value}")
        else:
            for var, value in current_preset.variables.items():
                if 'KEY' in var:
                    display_value = f"{value[:8]}..." if len(value) > 8 else "***"
                else:
                    display_value = value
                click.echo(f"{var}: {display_value}")

    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        sys.exit(1)


@cli.command()
def clear():
    """清除当前环境变量设置"""
    try:
        preset_manager = PresetManager()
        cleared_vars = preset_manager.clear_current()

        if cleared_vars:
            click.echo(f"✓ Cleared environment variables: {', '.join(cleared_vars)}")
        else:
            click.echo("No environment variables to clear")

    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--preset', help='指定要保存的预设名称(默认使用当前预设)')
@click.option('--override', multiple=True, help='覆盖变量 格式: KEY=VALUE')
def save(preset: Optional[str], override: List[str]):
    """保存当前配置到项目目录"""
    try:
        preset_manager = PresetManager()

        overrides = {}
        for override_str in override:
            if '=' not in override_str:
                click.echo(f"Error: Invalid override format '{override_str}'. Use KEY=VALUE", err=True)
                sys.exit(1)
            key, value = override_str.split('=', 1)
            overrides[key.strip()] = value.strip()

        project_config = preset_manager.save_project_config(
            preset_name=preset,
            overrides=overrides if overrides else None
        )

        click.echo(f"✓ Project configuration saved to .aiswitch.yaml")
        click.echo(f"  Preset: {project_config.preset}")
        if project_config.overrides:
            click.echo(f"  Overrides: {len(project_config.overrides)} variables")

    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        sys.exit(1)


@cli.command()
def load():
    """从项目配置文件加载配置"""
    try:
        preset_manager = PresetManager()
        preset, applied_vars = preset_manager.load_project_config()

        click.echo(f"✓ Loaded project configuration")
        click.echo(f"  Preset: {preset.name}")

        for var, value in applied_vars.items():
            if 'KEY' in var:
                display_value = f"{value[:8]}..." if len(value) > 8 else "***"
            else:
                display_value = value
            click.echo(f"  {var}: {display_value}")

    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--verbose', is_flag=True, help='显示详细状态信息')
def status(verbose: bool):
    """显示当前状态信息"""
    try:
        preset_manager = PresetManager()
        status_info = preset_manager.get_status()

        click.echo("AISwitch Status:")
        click.echo(f"  Current preset: {status_info['current_preset'] or 'None'}")
        click.echo(f"  Total presets: {status_info['total_presets']}")

        if status_info['project_config']:
            click.echo(f"  Project config: Found (.aiswitch.yaml)")
            click.echo(f"    Preset: {status_info['project_config']['preset']}")
            if status_info['project_config']['overrides']:
                click.echo(f"    Overrides: {len(status_info['project_config']['overrides'])}")
        else:
            click.echo(f"  Project config: Not found")

        if verbose:
            click.echo(f"  Config directory: {status_info['config_directory']}")

            env_info = status_info['environment_variables']
            click.echo(f"  System: {env_info['system']}")
            click.echo(f"  Shell: {env_info['shell']}")

            if status_info['current_preset_details']:
                details = status_info['current_preset_details']
                click.echo(f"\nCurrent preset details:")
                click.echo(f"  Name: {details['name']}")
                click.echo(f"  Description: {details['description']}")
                click.echo(f"  Created: {details['created_at']}")
                click.echo(f"  Tags: {', '.join(details['tags']) if details['tags'] else 'None'}")
                click.echo(f"  Variables: {details['variables_count']}")

    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        sys.exit(1)


@cli.command()
def info():
    """显示配置文件路径信息"""
    try:
        preset_manager = PresetManager()

        click.echo("AISwitch Configuration:")
        click.echo(f"  Config directory: {preset_manager.config_manager.config_dir}")
        click.echo(f"  Presets directory: {preset_manager.config_manager.presets_dir}")
        click.echo(f"  Global config: {preset_manager.config_manager.global_config_path}")
        click.echo(f"  Current config: {preset_manager.config_manager.current_config_path}")

        project_config_path = Path.cwd() / ".aiswitch.yaml"
        click.echo(f"  Project config: {project_config_path}")
        click.echo(f"    Exists: {'Yes' if project_config_path.exists() else 'No'}")

    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        sys.exit(1)


def main():
    """主入口点"""
    try:
        cli()
    except KeyboardInterrupt:
        click.echo("\nOperation cancelled by user", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Fatal error: {e}", err=True)
        sys.exit(1)


if __name__ == '__main__':
    main()