import click
import sys
from pathlib import Path
from typing import Optional, List
import yaml
import os
import subprocess

from .preset import PresetManager
from .config import PresetConfig


@click.group()
@click.version_option(version="0.1.0", prog_name="aiswitch")
def cli():
    """AISwitch - AI API环境切换工具

    极简工作流: add → apply → save/clear

    核心命令:
      - add: 添加新的预设配置
      - apply: 应用预设（交互模式 或 apply <preset> <cmd> 一次性运行）
      - list: 列出所有预设
      - save/clear: 持久化或清理环境变量
    """
    pass


@cli.command()
@click.argument('name')
@click.argument('env_pairs', nargs=-1, required=True)
@click.option('--description', default="", help='预设描述')
@click.option('--tags', help='标签(逗号分隔)')
def add(name: str, env_pairs: tuple, description: str, tags: Optional[str]):
    """添加新的预设配置

    使用方式: aiswitch add <config-name> <env_name> <env_value> [<env_name2> <env_value2> ...]

    示例: aiswitch add openai API_KEY your-key API_BASE_URL https://api.openai.com/v1 API_MODEL gpt-4
    """
    try:
        # 验证参数数量是否为偶数
        if len(env_pairs) == 0:
            click.echo("Error: At least one environment variable pair (name value) is required", err=True)
            sys.exit(1)

        if len(env_pairs) % 2 != 0:
            click.echo("Error: Environment variable arguments must come in pairs (name value)", err=True)
            sys.exit(1)

        # 解析环境变量对
        variables = {}
        for i in range(0, len(env_pairs), 2):
            env_name = env_pairs[i]
            env_value = env_pairs[i + 1]
            variables[env_name] = env_value

        preset_manager = PresetManager()

        tag_list = []
        if tags:
            tag_list = [tag.strip() for tag in tags.split(',')]

        preset = preset_manager.add_preset_flexible(
            name=name,
            variables=variables,
            description=description,
            tags=tag_list
        )

        click.echo(f"✓ Preset '{name}' added successfully")
        if description:
            click.echo(f"  Description: {description}")
        if tag_list:
            click.echo(f"  Tags: {', '.join(tag_list)}")

        click.echo(f"  Environment variables:")
        for var_name, var_value in variables.items():
            if 'KEY' in var_name.upper():
                display_value = f"{var_value[:8]}..." if len(var_value) > 8 else "***"
            else:
                display_value = var_value
            click.echo(f"    {var_name}: {display_value}")

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


def _apply_impl(name: str, export: bool):
    preset_manager = PresetManager()
    preset, applied_vars, cleared_vars = preset_manager.use_preset(name)

    if export:
        # 先输出unset语句清除旧变量
        for var in cleared_vars:
            click.echo(f'unset {var}')
        # 再输出export语句设置新变量
        for var, value in applied_vars.items():
            click.echo(f'export {var}="{value}"')
        return
    else:
        click.echo(f"✓ Switched to preset '{name}'")

        for var, value in applied_vars.items():
            if 'KEY' in var:
                display_value = f"{value[:8]}..." if len(value) > 8 else "***"
            else:
                display_value = value
            click.echo(f"  {var}: {display_value}")


@cli.command()
@click.argument('name')
@click.option('--export', is_flag=True, help='输出环境变量export语句，用于shell集成自动应用')
@click.option('--quiet', '-q', is_flag=True, help='静默模式，不显示执行信息（仅用于一次性运行模式）')
def apply(name: str, export: bool, quiet: bool):
    """应用指定预设（核心命令）

    \b
    交互模式: aiswitch apply <preset>
      切换到指定预设，在安装了 shell 集成后直接在当前终端生效。
      首次使用时若未安装集成，会提示一键安装。

    \b
    一次性运行模式: aiswitch apply <preset> -- <cmd> [args...]
      仅对子进程注入环境变量，不修改当前终端，不依赖 shell 集成。
      适合脚本、CI 环境和 Windows 系统。
      注意：使用双破折号 -- 来分隔预设名和命令。

    \b
    --export 选项仅供 shell 集成内部使用。
    """
    try:
        # 交互模式：apply <preset>
        # 首次体验优化：若未安装集成且为交互式会话，询问是否安装
        if not export:
            try:
                from .shell_integration import ShellIntegration
                integration = ShellIntegration()
                if not integration.is_installed() and sys.stdin.isatty():
                    if click.confirm("检测到未安装 shell 集成。现在安装以便 'apply' 直接在当前终端生效吗？", default=True):
                        success = integration.install()
                        if success:
                            click.echo("✓ Shell 集成已安装")
                            click.echo(f"  已修改: {integration.get_shell_config_path()}")
                            click.echo("  请运行: source 上述文件 或重启终端以生效")
                        else:
                            click.echo("❌ Shell 集成安装失败，可稍后重试: aiswitch install", err=True)
            except Exception:
                pass

        _apply_impl(name, export)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        sys.exit(1)


@cli.command(hidden=True)
@click.argument('name')
@click.option('--export', is_flag=True, help='输出环境变量export语句，用于eval（兼容模式）')
def use(name: str, export: bool):
    """[兼容别名] 等同于 apply（将逐步被替代）

    推荐使用: aiswitch apply <preset>
    """
    try:
        _apply_impl(name, export)
        if not export:
            click.echo("\n⚠️  注意: 'use' 将在未来版本中被 'apply' 取代，建议使用 'aiswitch apply'。")
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        sys.exit(1)


@cli.command(name="shell", hidden=True)
@click.argument('name')
def shell_cmd(name: str):
    """[兼容别名] 启动带有指定预设环境变量的子shell

    推荐使用: aiswitch apply <preset> -- $SHELL -l
    """
    try:
        click.echo("⚠️  注意: 'shell' 命令将在未来版本中移除，推荐使用: aiswitch apply <preset> -- $SHELL -l")

        preset_manager = PresetManager()
        # 仅为子shell准备环境，不修改当前指针与磁盘状态
        preset = preset_manager.config_manager.get_preset(name)
        if not preset:
            from .preset import PresetConfig  # type: ignore
            raise ValueError(f"Preset '{name}' not found. Use 'aiswitch list' to see available presets.")

        shell_path = os.environ.get('SHELL') or '/bin/bash'

        click.echo(f"→ Spawning subshell '{os.path.basename(shell_path)}' with preset '{preset.name}' (temporary)")
        click.echo("  Type 'exit' to return to your original shell.")

        # 使用 exec 替换为交互式子shell，传入合并后的环境
        try:
            child_env = os.environ.copy()
            child_env.update(preset.variables)
            os.execvpe(shell_path, [shell_path, '-i'], child_env)
        except FileNotFoundError:
            # 回退到subprocess以避免因shell不可用而失败
            child_env = os.environ.copy()
            child_env.update(preset.variables)
            subprocess.call([shell_path, '-i'], env=child_env)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        sys.exit(1)


@cli.command(name="exec", hidden=True)
@click.argument('name')
@click.argument('cmd', nargs=-1, required=True)
def exec_cmd(name: str, cmd: tuple):
    """[兼容别名] 在指定预设下执行命令

    推荐使用: aiswitch apply <preset> -- <command> [args...]
    """
    try:
        click.echo("⚠️  注意: 'exec' 命令将在未来版本中移除，推荐使用: aiswitch apply <preset> -- <command>")

        preset_manager = PresetManager()
        # 仅为子进程准备环境，不修改当前指针与磁盘状态
        preset = preset_manager.config_manager.get_preset(name)
        if not preset:
            raise ValueError(f"Preset '{name}' not found. Use 'aiswitch list' to see available presets.")

        env = os.environ.copy()
        env.update(preset.variables)

        result = subprocess.call(list(cmd), env=env)
        sys.exit(result)
    except FileNotFoundError:
        click.echo("Error: Command not found. Ensure the command exists in PATH.", err=True)
        sys.exit(127)
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
            click.echo("No current preset. Use 'aiswitch apply <preset>' to set one.")
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
    """清除当前环境变量设置和持久化配置"""
    try:
        preset_manager = PresetManager()
        cleared_vars = preset_manager.clear_current()

        # 同时清除持久化的环境变量
        from .shell_integration import ShellIntegration
        integration = ShellIntegration()
        integration.clear_env_vars()

        if cleared_vars:
            click.echo(f"✓ Cleared current session variables: {', '.join(cleared_vars)}")
        else:
            click.echo("No current session variables to clear")

        click.echo("✓ Cleared persistent environment variables from shell config")

    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        sys.exit(1)


@cli.command()
def save():
    """将当前预设的环境变量持久化到shell配置文件"""
    try:
        preset_manager = PresetManager()
        current_preset = preset_manager.get_current_preset()

        if not current_preset:
            click.echo("Error: No current preset. Use 'aiswitch apply <preset>' first.", err=True)
            sys.exit(1)

        from .shell_integration import ShellIntegration
        integration = ShellIntegration()

        success = integration.save_env_vars(current_preset.variables, current_preset.name)

        if success:
            click.echo(f"✓ Environment variables from preset '{current_preset.name}' saved to shell config")
            click.echo(f"  Variables saved: {', '.join(current_preset.variables.keys())}")
            click.echo("  These will be automatically loaded in new terminal sessions")
        else:
            click.echo("❌ Failed to save environment variables", err=True)
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


@cli.command()
@click.option('--force', is_flag=True, help='强制重新安装，即使已经安装')
def install(force: bool):
    """安装 shell 集成，使 apply 自动在当前终端应用环境变量"""
    try:
        from .shell_integration import ShellIntegration

        integration = ShellIntegration()

        if integration.is_installed() and not force:
            click.echo("✓ AISwitch shell集成已经安装")
            click.echo("使用 --force 选项可以重新安装")
            return

        success = integration.install()

        if success:
            click.echo("✓ AISwitch shell集成安装成功!")
            click.echo(f"已修改: {integration.get_shell_config_path()}")
            click.echo("\n请运行以下命令之一来激活集成:")
            click.echo(f"  source {integration.get_shell_config_path()}")
            click.echo("  或者重新启动终端")
            click.echo("\n安装后，你可以直接使用:")
            click.echo("  aiswitch apply <preset>  # 环境变量将自动应用到当前shell")
        else:
            click.echo("❌ Shell集成安装失败", err=True)
            sys.exit(1)

    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        sys.exit(1)


@cli.command()
def uninstall():
    """卸载shell集成"""
    try:
        from .shell_integration import ShellIntegration

        integration = ShellIntegration()

        if not integration.is_installed():
            click.echo("AISwitch shell集成未安装")
            return

        success = integration.uninstall()

        if success:
            click.echo("✓ AISwitch shell集成卸载成功!")
            click.echo("请重新启动终端或重新加载shell配置文件")
        else:
            click.echo("❌ Shell集成卸载失败", err=True)
            sys.exit(1)

    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        sys.exit(1)


def handle_apply_one_time_mode():
    """处理一次性运行模式，绕过Click的参数解析问题"""
    if len(sys.argv) < 3 or sys.argv[1] != 'apply':
        return False

    # 检查是否包含 -- 分隔符
    try:
        separator_index = sys.argv.index('--')
    except ValueError:
        return False

    # 解析参数
    args_before_separator = sys.argv[2:separator_index]
    cmd_args = sys.argv[separator_index + 1:]

    if not cmd_args:
        return False

    # 解析选项和预设名
    export = False
    quiet = False
    name = None

    for arg in args_before_separator:
        if arg == '--export':
            export = True
        elif arg == '--quiet' or arg == '-q':
            quiet = True
        elif not arg.startswith('-'):
            name = arg
            break

    if not name:
        click.echo("Error: Missing preset name", err=True)
        sys.exit(1)

    try:
        # 加载预设
        preset_manager = PresetManager()
        preset = preset_manager.config_manager.get_preset(name)
        if not preset:
            click.echo(f"Error: Preset '{name}' not found. Use 'aiswitch list' to see available presets.", err=True)
            sys.exit(1)

        # 准备环境变量
        env = os.environ.copy()
        env.update(preset.variables)

        # 显示正在执行的命令信息（除非开启静默模式）
        cmd_str = ' '.join(cmd_args)
        if not quiet:
            click.echo(f"→ Running with preset '{name}': {cmd_str}", err=True)

        # 执行命令
        try:
            # 支持shell特性（管道、重定向等）的智能检测
            if any(op in cmd_str for op in ['|', '>', '<', '&&', '||', ';', '`', '$(']):
                # 包含shell操作符，使用shell执行
                result = subprocess.run(cmd_str, shell=True, env=env, check=False)
            else:
                # 简单命令，直接执行（更安全）
                result = subprocess.run(cmd_args, env=env, check=False)

            sys.exit(result.returncode)
        except FileNotFoundError:
            click.echo(f"Error: Command '{cmd_args[0]}' not found. Ensure the command exists in PATH.", err=True)
            sys.exit(127)
        except PermissionError:
            click.echo(f"Error: Permission denied executing '{cmd_args[0]}'", err=True)
            sys.exit(126)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


def main():
    """主入口点"""
    try:
        # 在Click处理之前检查一次性运行模式
        handle_apply_one_time_mode()

        # 如果不是一次性运行模式，继续正常的Click处理
        cli()
    except KeyboardInterrupt:
        click.echo("\nOperation cancelled by user", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Fatal error: {e}", err=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
