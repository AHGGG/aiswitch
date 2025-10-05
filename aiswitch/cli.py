import click
import sys
from pathlib import Path
from typing import Optional, List, Dict
import yaml
import os
import subprocess
import json
import asyncio
import platform
from datetime import datetime

from .preset import PresetManager
from .config import PresetConfig


# Windows GBK终端兼容性：安全输出Unicode字符
def safe_echo(message, **kwargs):
    """在Windows GBK终端下安全输出Unicode字符"""
    try:
        click.echo(message, **kwargs)
    except UnicodeEncodeError:
        # 替换Unicode符号为ASCII
        safe_message = message.replace('✓', '[OK]').replace('✗', '[X]').replace('❌', '[ERROR]').replace('⚠️', '[WARN]').replace('→', '->').replace('🤖', '[BOT]').replace('🟢', '[*]').replace('🔴', '[ ]')
        click.echo(safe_message, **kwargs)


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

        safe_echo(f"✓ Preset '{name}' added successfully")
        if description:
            safe_echo(f"  Description: {description}")
        if tag_list:
            safe_echo(f"  Tags: {', '.join(tag_list)}")

        safe_echo(f"  Environment variables:")
        for var_name, var_value in variables.items():
            if 'KEY' in var_name.upper():
                display_value = f"{var_value[:8]}..." if len(var_value) > 8 else "***"
            else:
                display_value = var_value
            safe_echo(f"    {var_name}: {display_value}")

    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('names', nargs=-1, required=True)
@click.option('--force', is_flag=True, help='强制删除，即使是当前使用的预设')
def remove(names: tuple, force: bool):
    """删除一个或多个预设

    使用方式:
      aiswitch remove <preset1>                    # 删除单个预设
      aiswitch remove <preset1> <preset2> ...      # 删除多个预设
      aiswitch remove <preset1> <preset2> --force  # 强制删除（包括当前预设）
    """
    try:
        preset_manager = PresetManager()
        current = preset_manager.get_current_preset()
        current_name = current.name if current else None

        removed = []
        skipped_current = []
        not_found = []

        for name in names:
            # 检查是否是当前预设且没有 --force
            if current_name and name == current_name and not force:
                skipped_current.append(name)
                continue

            # 尝试删除
            if preset_manager.remove_preset(name):
                removed.append(name)
            else:
                not_found.append(name)

        # 汇总报告
        if removed:
            safe_echo(f"✓ Removed {len(removed)} preset(s): {', '.join(removed)}")

        if skipped_current:
            click.echo(f"⚠️  Skipped current preset(s): {', '.join(skipped_current)} (use --force to override)", err=True)

        if not_found:
            click.echo(f"⚠️  Not found: {', '.join(not_found)}", err=True)

        # 如果什么都没删除成功，退出码为 1
        if not removed:
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
        # Windows环境特殊处理
        if platform.system() == 'Windows':
            safe_echo(f"✓ Preset '{name}' configured (session only)")
            safe_echo(f"\n  Note: On Windows, environment variables are only applied in subprocess mode.")
            safe_echo(f"  To run commands with this preset, use:")
            safe_echo(f"    aiswitch apply {name} -- <your-command>")
            safe_echo(f"\n  Example: aiswitch apply {name} -- python script.py")
            safe_echo(f"\n  Variables in preset '{name}':")
        else:
            safe_echo(f"✓ Switched to preset '{name}'")

        for var, value in applied_vars.items():
            if 'KEY' in var:
                display_value = f"{value[:8]}..." if len(value) > 8 else "***"
            else:
                display_value = value
            safe_echo(f"  {var}: {display_value}")


@cli.command()
@click.argument('name')
@click.option('--export', is_flag=True, help='输出环境变量export语句，用于shell集成自动应用')
@click.option('--quiet', '-q', is_flag=True, help='静默模式，不显示执行信息（仅用于一次性运行模式）')
@click.option('--interactive', is_flag=True, help='启动交互式多代理界面')
def apply(name: str, export: bool, quiet: bool, interactive: bool):
    """应用指定预设（核心命令）

    \b
    交互模式: aiswitch apply <preset>
      切换到指定预设，在安装了 shell 集成后直接在当前终端生效。
      首次使用时若未安装集成，会提示一键安装。

    \b
    交互式多代理模式: aiswitch apply <preset> --interactive
      启动多代理交互界面，支持多轮对话。
      输入'exit'、'quit'或按Ctrl+C退出会话。

    \b
    一次性运行模式: aiswitch apply <preset> -- <cmd> [args...]
      仅对子进程注入环境变量，不修改当前终端，不依赖 shell 集成。
      适合脚本、CI 环境和 Windows 系统。
      注意：使用双破折号 -- 来分隔预设名和命令。

    \b
    --export 选项仅供 shell 集成内部使用。
    """
    try:
        # 交互式多代理模式：apply <preset> --interactive
        if interactive:
            _execute_ai_agent_interactive(name)
            return

        # 交互模式：apply <preset>
        # 首次体验优化：若未安装集成且为交互式会话，询问是否安装
        # 注意：Windows环境下shell集成不可用，跳过检查
        if not export and platform.system() != 'Windows':
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
        # Windows环境不支持shell集成
        if platform.system() == 'Windows':
            click.echo("❌ Shell integration is not supported on Windows")
            click.echo("\n  On Windows, use the one-time execution mode:")
            click.echo("    aiswitch apply <preset> -- <command>")
            click.echo("\n  Example: aiswitch apply mypreset -- python script.py")
            sys.exit(1)

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


@cli.command()
@click.argument('preset_name', required=False)
@click.option('--output', '-o', type=click.Path(), help='输出文件路径')
@click.option('--all', 'export_all', is_flag=True, help='导出所有预设')
@click.option('--include-secrets', is_flag=True, help='包含敏感信息（慎用）')
def export(preset_name: Optional[str], output: Optional[str], export_all: bool, include_secrets: bool):
    """导出预设配置

    使用方式:
      aiswitch export <preset_name>           # 导出单个预设到stdout
      aiswitch export <preset_name> -o file   # 导出单个预设到文件
      aiswitch export --all                   # 导出所有预设到stdout
      aiswitch export --all -o file           # 导出所有预设到文件
    """
    try:
        preset_manager = PresetManager()

        if export_all:
            # 导出所有预设
            output_path = Path(output) if output else None
            export_data = preset_manager.export_all_presets(
                output_file=output_path,
                redact_secrets=not include_secrets
            )

            if not output:
                click.echo(json.dumps(export_data, indent=2, ensure_ascii=False))
            else:
                click.echo(f"✓ All presets exported to '{output}'")
                click.echo(f"  Exported {len(export_data['presets'])} presets")

        elif preset_name:
            # 导出单个预设
            if output:
                output_path = Path(output)
                preset_manager.export_preset_to_file(
                    preset_name,
                    output_path,
                    redact_secrets=not include_secrets
                )
                click.echo(f"✓ Preset '{preset_name}' exported to '{output}'")
            else:
                preset_data = preset_manager.export_preset(
                    preset_name,
                    redact_secrets=not include_secrets
                )
                export_data = {
                    "version": "1.0.0",
                    "export_time": datetime.now().isoformat(),
                    "preset": preset_data
                }
                click.echo(json.dumps(export_data, indent=2, ensure_ascii=False))
        else:
            click.echo("Error: Must specify either a preset name or --all flag", err=True)
            sys.exit(1)

        if include_secrets:
            click.echo("⚠️  Warning: Export includes sensitive information. Handle with care.", err=True)

    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        sys.exit(1)


@cli.command(name="import")
@click.argument('input_file', type=click.Path(exists=True))
@click.option('--force', is_flag=True, help='覆盖已存在的预设')
@click.option('--dry-run', is_flag=True, help='预览导入内容，不实际导入')
def import_cmd(input_file: str, force: bool, dry_run: bool):
    """从文件导入预设配置

    使用方式:
      aiswitch import config.json           # 导入配置文件
      aiswitch import config.json --force   # 强制覆盖已存在的预设
      aiswitch import config.json --dry-run # 预览导入内容
    """
    try:
        preset_manager = PresetManager()
        input_path = Path(input_file)

        if not input_path.exists():
            click.echo(f"Error: File '{input_file}' not found", err=True)
            sys.exit(1)

        # 读取文件进行预览
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            click.echo(f"Error: Invalid JSON format: {e}", err=True)
            sys.exit(1)

        # 分析导入内容
        presets_to_import = []
        if "preset" in data:
            presets_to_import = [data["preset"]]
        elif "presets" in data:
            presets_to_import = data["presets"]
        else:
            click.echo("Error: Invalid import file format. Expected 'preset' or 'presets' key.", err=True)
            sys.exit(1)

        # 显示预览信息
        click.echo(f"Import preview from '{input_file}':")
        click.echo(f"  File format version: {data.get('version', 'unknown')}")
        if 'export_time' in data:
            click.echo(f"  Export time: {data['export_time']}")
        click.echo(f"  Presets to import: {len(presets_to_import)}")

        conflicts = []
        for preset_data in presets_to_import:
            name = preset_data.get('name', 'unknown')
            exists = preset_manager.config_manager.preset_exists(name)
            status = "exists" if exists else "new"

            # 检查是否有编辑的密钥
            redacted_vars = []
            for key, value in preset_data.get('variables', {}).items():
                if value == "***REDACTED***":
                    redacted_vars.append(key)

            if exists:
                conflicts.append(name)

            click.echo(f"    - {name}: {status}")
            if redacted_vars:
                click.echo(f"      ⚠️  Contains redacted variables: {', '.join(redacted_vars)}")

        if conflicts and not force:
            click.echo(f"\n❌ Conflicts detected: {', '.join(conflicts)}")
            click.echo("Use --force to overwrite existing presets")

        if dry_run:
            click.echo("\n📋 Dry run completed. Use without --dry-run to actually import.")
            return

        if conflicts and not force:
            sys.exit(1)

        # 检查编辑的变量
        has_redacted = any(
            value == "***REDACTED***"
            for preset_data in presets_to_import
            for value in preset_data.get('variables', {}).values()
        )

        if has_redacted:
            click.echo("\n❌ Cannot import: File contains redacted secret values.")
            click.echo("Please edit the file and replace '***REDACTED***' with actual values.")
            sys.exit(1)

        # 执行导入
        click.echo(f"\n🔄 Importing presets...")
        imported_presets = preset_manager.import_from_file(input_path, allow_overwrite=force)

        click.echo(f"✓ Successfully imported {len(imported_presets)} presets:")
        for preset in imported_presets:
            click.echo(f"  - {preset.name}")

    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        sys.exit(1)


def _execute_ai_agent_interactive(preset_name: str):
    """交互式执行AI CLI agent，使用多代理界面"""
    try:
        from .textual_ui.app import run_aiswitch_app
        run_aiswitch_app(preset=preset_name)
    except ImportError:
        click.echo("❌ Error: Multi-agent interface not available. Install with: pip install textual", err=True)
        sys.exit(1)
    except KeyboardInterrupt:
        click.echo("\n👋 Interactive session ended")
    except Exception as e:
        click.echo(f"❌ Error starting interactive session: {e}", err=True)
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
            # 在Windows上，需要使用shell=True来正确解析.cmd/.bat文件
            # 在Unix上，为了安全性，只在有shell操作符时才使用shell=True
            use_shell = platform.system() == 'Windows' or any(op in cmd_str for op in ['|', '>', '<', '&&', '||', ';', '`', '$('])

            if use_shell:
                # 使用shell执行（Windows必需，或包含shell操作符）
                result = subprocess.run(cmd_str, shell=True, env=env, check=False)
            else:
                # 简单命令，直接执行（更安全，仅Unix）
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
