import click
import sys
from pathlib import Path
from typing import Optional, List, Dict
import yaml
import os
import subprocess
import json
import asyncio
from datetime import datetime

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
@click.option('--agents', help='指定代理列表，逗号分隔，例如: claude,gpt')
@click.option('--agent-presets', help='指定agent到preset的映射，格式: agent1:preset1,agent2:preset2')
@click.option('--agent-tasks', help='指定agent到task的映射，格式: agent1:"task1",agent2:"task2"')
@click.option('--parallel', is_flag=True, help='并行执行（默认串行）')
@click.option('--task', help='要执行的任务内容（未在agent-tasks中指定的agent使用此默认任务）')
@click.option('--timeout', type=float, default=30.0, help='命令超时时间（秒）')
@click.option('--stop-on-error', is_flag=True, help='遇到错误时停止执行（仅串行模式）')
def apply(name: str, export: bool, quiet: bool, agents: Optional[str], agent_presets: Optional[str], agent_tasks: Optional[str], parallel: bool, task: Optional[str], timeout: float, stop_on_error: bool):
    """应用指定预设（核心命令）

    \b
    交互模式: aiswitch apply <preset>
      切换到指定预设，在安装了 shell 集成后直接在当前终端生效。
      首次使用时若未安装集成，会提示一键安装。

    \b
    多代理模式: aiswitch apply <preset> --agents claude,gpt --task "任务内容"
      使用多个AI代理执行指定任务，支持并行或串行执行。
      默认所有代理使用同一个preset的环境变量。

    \b
    多预设模式: aiswitch apply <fallback-preset> --agents claude,codex --agent-presets claude:ds,codex:88codex --task "任务内容"
      为不同代理指定不同的预设环境变量。
      格式: --agent-presets agent1:preset1,agent2:preset2

    \b
    个性化任务模式: aiswitch apply <preset> --agents claude,codex --agent-tasks 'claude:"What is 2+2?",codex:"Write Python code"'
      为不同代理指定不同的任务内容。
      格式: --agent-tasks agent1:"task1",agent2:"task2"
      注意: 使用单引号包围整个参数以保护内部的双引号和逗号

    \b
    一次性运行模式: aiswitch apply <preset> -- <cmd> [args...]
      仅对子进程注入环境变量，不修改当前终端，不依赖 shell 集成。
      适合脚本、CI 环境和 Windows 系统。
      注意：使用双破折号 -- 来分隔预设名和命令。

    \b
    --export 选项仅供 shell 集成内部使用。
    """
    try:
        # 多代理模式：apply <preset> --agents <agents> --task <task>
        if agents:
            # 确保有默认任务或agent-tasks映射
            if not task and not agent_tasks:
                click.echo("❌ Error: Must provide either --task or --agent-tasks when using --agents")
                sys.exit(1)
            asyncio.run(_apply_with_agents(name, agents, agent_presets, agent_tasks, parallel, task, timeout, stop_on_error))
            return

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


# 全局管理器实例
_agent_manager: Optional['CLIAgentManager'] = None

async def get_agent_manager():
    """获取代理管理器实例"""
    global _agent_manager
    if _agent_manager is None:
        from .cli_wrapper.manager import CLIAgentManager
        _agent_manager = CLIAgentManager()
    return _agent_manager

async def _execute_ai_agent(agent_name: str, task: str, timeout: float, preset_name: str):
    """统一执行AI CLI agent"""
    import subprocess
    import os
    from datetime import datetime
    from .cli_wrapper.types import ParsedResult, CommandResult

    # AI agent命令模板配置
    agent_commands = {
        'claude': ['claude', '--print'],
        'codex': ['codex', 'exec'],  # codex exec接受prompt作为参数
        'gpt': ['gpt', '--query'],
        'gemini': ['gemini', '--ask'],
        'openai': ['openai', '--prompt'],
        'anthropic': ['anthropic', '--ask'],
        'chatgpt': ['chatgpt', '--prompt']
    }

    # 获取命令模板
    command_template = agent_commands.get(agent_name)
    if not command_template:
        # 如果没有预定义，尝试通用格式
        command_template = [agent_name, '--query']

    # 先应用预设获取环境变量
    from .preset import PresetManager
    preset_manager = PresetManager()
    try:
        preset, _, _ = preset_manager.use_preset(preset_name, apply_to_env=False)
        env = {**os.environ, **preset.variables}
    except Exception as e:
        env = dict(os.environ)

    # 构建完整命令
    full_command = command_template + [task]

    try:
        result = subprocess.run(
            full_command,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env
        )

        output = result.stdout.strip() if result.stdout else ""
        error = result.stderr.strip() if result.stderr else ""

        parsed_result = ParsedResult(
            output=output,
            error=error,
            metadata={"adapter": f"{agent_name}-subprocess", "return_code": result.returncode},
            success=result.returncode == 0
        )

        return CommandResult(
            agent_id=agent_name,
            session_id="subprocess",
            command=task,
            result=parsed_result,
            timestamp=datetime.now(),
            success=result.returncode == 0
        )

    except subprocess.TimeoutExpired:
        parsed_result = ParsedResult(
            output="",
            error="Command timed out",
            metadata={"adapter": f"{agent_name}-subprocess", "timeout": True},
            success=False
        )

        return CommandResult(
            agent_id=agent_name,
            session_id="subprocess",
            command=task,
            result=parsed_result,
            timestamp=datetime.now(),
            success=False
        )
    except Exception as e:
        parsed_result = ParsedResult(
            output="",
            error=str(e),
            metadata={"adapter": f"{agent_name}-subprocess", "error": True},
            success=False
        )

        return CommandResult(
            agent_id=agent_name,
            session_id="subprocess",
            command=task,
            result=parsed_result,
            timestamp=datetime.now(),
            success=False
        )

def _parse_agent_presets(agent_presets_str: Optional[str]) -> Dict[str, str]:
    """解析agent-presets映射字符串"""
    if not agent_presets_str:
        return {}

    mapping = {}
    for pair in agent_presets_str.split(','):
        if ':' not in pair:
            click.echo(f"⚠️  Invalid agent-preset mapping format: {pair} (expected agent:preset)")
            continue

        agent, preset = pair.split(':', 1)
        mapping[agent.strip()] = preset.strip()

    return mapping

def _parse_agent_tasks(agent_tasks_str: Optional[str]) -> Dict[str, str]:
    """解析agent-tasks映射字符串，支持带引号的任务内容"""
    if not agent_tasks_str:
        return {}

    mapping = {}
    # 使用简单的状态机解析，处理引号内的逗号
    current_pair = ""
    in_quotes = False
    quote_char = None

    for char in agent_tasks_str:
        if char in ['"', "'"] and not in_quotes:
            in_quotes = True
            quote_char = char
            current_pair += char
        elif char == quote_char and in_quotes:
            in_quotes = False
            quote_char = None
            current_pair += char
        elif char == ',' and not in_quotes:
            # 处理完整的pair
            if current_pair.strip():
                _parse_single_agent_task(current_pair.strip(), mapping)
            current_pair = ""
        else:
            current_pair += char

    # 处理最后一个pair
    if current_pair.strip():
        _parse_single_agent_task(current_pair.strip(), mapping)

    return mapping

def _parse_single_agent_task(pair: str, mapping: Dict[str, str]):
    """解析单个agent:task对"""
    if ':' not in pair:
        click.echo(f"⚠️  Invalid agent-task mapping format: {pair} (expected agent:\"task\")")
        return

    agent, task = pair.split(':', 1)
    agent = agent.strip()
    task = task.strip()

    # 移除任务内容的引号
    if (task.startswith('"') and task.endswith('"')) or \
       (task.startswith("'") and task.endswith("'")):
        task = task[1:-1]

    mapping[agent] = task

async def _apply_with_agents(name: str, agents: str, agent_presets: Optional[str], agent_tasks: Optional[str], parallel: bool, task: Optional[str], timeout: float, stop_on_error: bool):
    """统一的多代理执行逻辑"""
    import asyncio

    agent_list = [a.strip() for a in agents.split(',')]
    preset_mapping = _parse_agent_presets(agent_presets)
    task_mapping = _parse_agent_tasks(agent_tasks)

    # 为每个agent确定使用的preset和task
    agent_configs = []
    for agent in agent_list:
        preset = preset_mapping.get(agent, name)  # 如果没有映射，使用fallback preset
        agent_task = task_mapping.get(agent, task)  # 如果没有映射，使用默认task

        if agent_task is None:
            click.echo(f"❌ Error: No task specified for agent '{agent}' (use --task for default or --agent-tasks for specific)")
            sys.exit(1)

        agent_configs.append((agent, preset, agent_task))

    # 显示执行计划
    click.echo(f"\n{'Executing agents in parallel' if parallel else 'Executing agents sequentially'}:")
    for agent, preset, agent_task in agent_configs:
        preset_info = f"preset: {preset}" if preset != name else f"fallback preset: {preset}"
        task_info = f"task: \"{agent_task[:50]}{'...' if len(agent_task) > 50 else ''}\""
        click.echo(f"  - {agent} ({preset_info}, {task_info})")

    if parallel:
        # 并行执行所有代理
        tasks = [_execute_ai_agent(agent, agent_task, timeout, preset) for agent, preset, agent_task in agent_configs]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理异常结果
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                from .cli_wrapper.types import ParsedResult, CommandResult
                from datetime import datetime

                agent, preset, agent_task = agent_configs[i]
                error_result = CommandResult(
                    agent_id=agent,
                    session_id="subprocess",
                    command=agent_task,
                    result=ParsedResult(
                        output="",
                        error=str(result),
                        metadata={"adapter": f"{agent}-subprocess", "error": True},
                        success=False
                    ),
                    timestamp=datetime.now(),
                    success=False
                )
                final_results.append(error_result)
            else:
                final_results.append(result)
        results = final_results
    else:
        # 顺序执行代理
        results = []
        for agent, preset, agent_task in agent_configs:
            try:
                result = await _execute_ai_agent(agent, agent_task, timeout, preset)
                results.append(result)

                # 如果设置了stop_on_error且执行失败，停止执行
                if stop_on_error and not result.success:
                    click.echo(f"✗ Agent {agent} failed, stopping execution due to --stop-on-error")
                    break

            except Exception as e:
                from .cli_wrapper.types import ParsedResult, CommandResult
                from datetime import datetime

                error_result = CommandResult(
                    agent_id=agent,
                    session_id="subprocess",
                    command=agent_task,
                    result=ParsedResult(
                        output="",
                        error=str(e),
                        metadata={"adapter": f"{agent}-subprocess", "error": True},
                        success=False
                    ),
                    timestamp=datetime.now(),
                    success=False
                )
                results.append(error_result)

                if stop_on_error:
                    click.echo(f"✗ Agent {agent} failed with exception, stopping execution due to --stop-on-error")
                    break

    # 显示结果
    _display_results(results, parallel)


def _display_results(results: List, parallel: bool):
    """显示执行结果"""
    click.echo(f"\n{'='*60}")
    click.echo("EXECUTION RESULTS")
    click.echo(f"{'='*60}")

    for i, result in enumerate(results, 1):
        if isinstance(result, Exception):
            click.echo(f"\n[{i}] ✗ Error: {result}")
            continue

        status_icon = "✓" if result.success else "✗"
        click.echo(f"\n[{i}] {status_icon} Agent: {result.agent_id}")
        click.echo(f"    Command: {result.command}")
        click.echo(f"    Time: {result.timestamp.strftime('%H:%M:%S')}")

        if result.success:
            click.echo(f"    Output:\n{_indent_text(result.result.output)}")
            if result.result.metadata:
                click.echo(f"    Metadata: {result.result.metadata}")
        else:
            click.echo(f"    Error:\n{_indent_text(result.result.error)}")

def _indent_text(text: str, spaces: int = 8) -> str:
    """缩进文本"""
    indent = " " * spaces
    return "\n".join(indent + line for line in text.split("\n"))

# 新增agents命令组
@cli.group()
def agents():
    """管理CLI代理"""
    pass

@agents.command('list')
def agents_list():
    """列出所有代理和会话"""
    asyncio.run(_agents_list())

async def _agents_list():
    """列出代理实现"""
    manager = await get_agent_manager()
    agents_info = await manager.list_agents()

    if not agents_info:
        click.echo("No active agents found.")
        return

    click.echo("Active Agents:")
    click.echo("-" * 50)

    for agent_info in agents_info:
        click.echo(f"\n🤖 {agent_info['agent_id']} ({agent_info['adapter']})")
        if agent_info['sessions']:
            click.echo("   Sessions:")
            for session in agent_info['sessions']:
                status_icon = "🟢" if session['status']['status'] == 'running' else "🔴"
                click.echo(f"   {status_icon} {session['session_id'][:8]}... ({session['status']['status']})")
        else:
            click.echo("   No active sessions")

@agents.command('status')
@click.argument('agent_id')
def agents_status(agent_id):
    """查看指定代理的详细状态"""
    asyncio.run(_agents_status(agent_id))

async def _agents_status(agent_id: str):
    """查看代理状态实现"""
    manager = await get_agent_manager()

    if agent_id not in manager.agents:
        click.echo(f"Agent '{agent_id}' not found.")
        return

    agent = manager.agents[agent_id]
    sessions = await agent.list_sessions()

    click.echo(f"Agent: {agent_id}")
    click.echo(f"Adapter: {agent.adapter.name}")
    click.echo(f"Capabilities: {agent.capabilities}")
    click.echo(f"Sessions: {len(sessions)}")

    if sessions:
        click.echo("\nSession Details:")
        for session in sessions:
            click.echo(f"  ID: {session['session_id']}")
            click.echo(f"  Status: {session['status']['status']}")
            click.echo(f"  Created: {session['created_at']}")
            click.echo(f"  Commands: {session['status']['command_count']}")
            click.echo()

@agents.command('terminate')
@click.argument('agent_id')
@click.confirmation_option(prompt='Are you sure you want to terminate this agent?')
def agents_terminate(agent_id):
    """终止指定代理的所有会话"""
    asyncio.run(_agents_terminate(agent_id))

async def _agents_terminate(agent_id: str):
    """终止代理实现"""
    manager = await get_agent_manager()

    try:
        await manager.terminate_agent(agent_id)
        click.echo(f"✓ Agent '{agent_id}' terminated successfully.")
    except ValueError as e:
        click.echo(f"✗ Error: {e}")
    except Exception as e:
        click.echo(f"✗ Failed to terminate agent: {e}")

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
