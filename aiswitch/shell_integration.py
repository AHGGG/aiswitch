import os
import platform
import shutil
from pathlib import Path
from typing import Optional


class ShellIntegration:
    def __init__(self):
        self.system = platform.system()
        self.marker_start = "# >>> AISwitch shell integration >>>"
        self.marker_end = "# <<< AISwitch shell integration <<<"

    def get_shell_type(self) -> str:
        """检测当前shell类型"""
        shell = os.environ.get('SHELL', '')
        if 'zsh' in shell:
            return 'zsh'
        elif 'bash' in shell:
            return 'bash'
        elif 'fish' in shell:
            return 'fish'
        else:
            return 'bash'  # 默认bash

    def get_shell_config_path(self) -> Path:
        """获取shell配置文件路径"""
        home = Path.home()
        shell_type = self.get_shell_type()

        if shell_type == 'zsh':
            return home / '.zshrc'
        elif shell_type == 'fish':
            return home / '.config' / 'fish' / 'config.fish'
        else:  # bash
            # 优先选择 .bashrc，如果不存在则使用 .bash_profile
            bashrc = home / '.bashrc'
            if bashrc.exists() or self.system == 'Linux':
                return bashrc
            else:
                return home / '.bash_profile'

    def get_integration_code(self) -> str:
        """获取要注入的shell集成代码"""
        shell_type = self.get_shell_type()

        if shell_type == 'fish':
            return '''# AISwitch shell integration for Fish
function aiswitch
    set cmd $argv[1]
    set -e argv[1]

    if test "$cmd" = "use" -o "$cmd" = "apply"
        # Check if this is one-time execution mode for apply command (has -- separator)
        set has_separator false
        for arg in $argv
            if test "$arg" = "--"
                set has_separator true
                break
            end
        end

        if test "$cmd" = "apply" -a "$has_separator" = "true"
            # One-time execution mode: pass through directly
            command aiswitch $cmd $argv
        else
            # Check if this is a help request or other special flag
            set is_help false
            for arg in $argv
                if test "$arg" = "--help" -o "$arg" = "-h"
                    set is_help true
                    break
                end
            end

            if test "$is_help" = "true"
                # For help requests, pass through directly without --export
                command aiswitch $cmd $argv
            else
                # Interactive mode: convert export statements to Fish format
                eval (command aiswitch $cmd $argv --export | string replace "export " "set -gx " | string replace "=" " ")
                echo "✓ Environment variables applied to current shell"
            end
        end
    else
        command aiswitch $cmd $argv
    end
end'''
        else:
            # bash/zsh
            return '''# AISwitch shell integration - define before interactive check
# This ensures the function works in both interactive and non-interactive shells

# Unset any existing function/alias first
unset -f aiswitch 2>/dev/null || true
unalias aiswitch 2>/dev/null || true

aiswitch() {
    local cmd="$1"
    shift

    if [ "$cmd" = "use" ] || [ "$cmd" = "apply" ]; then
        # Check if this is one-time execution mode (has -- separator)
        # For apply command, if there's a -- separator, it's one-time mode
        local has_separator=false
        for arg in "$@"; do
            if [ "$arg" = "--" ]; then
                has_separator=true
                break
            fi
        done

        if [ "$cmd" = "apply" ] && [ "$has_separator" = "true" ]; then
            # One-time execution mode: pass through directly
            command aiswitch "$cmd" "$@"
        else
            # Check if this is a help request or other special flag
            local is_help=false
            for arg in "$@"; do
                if [ "$arg" = "--help" ] || [ "$arg" = "-h" ]; then
                    is_help=true
                    break
                fi
            done

            if [ "$is_help" = "true" ]; then
                # For help requests, pass through directly without --export
                command aiswitch "$cmd" "$@"
            else
                # Interactive mode: use --export and eval the result
                local switch_commands=$(command aiswitch "$cmd" "$@" --export)
                if [ $? -eq 0 ]; then
                    eval "$switch_commands"
                    echo "✓ Environment variables applied to current shell"
                else
                    echo "✗ Failed to switch preset"
                    return 1
                fi
            fi
        fi
    else
        command aiswitch "$cmd" "$@"
    fi
}

# Export the function to make it available in subshells
export -f aiswitch'''

    def is_installed(self) -> bool:
        """检查是否已经安装"""
        config_path = self.get_shell_config_path()

        if not config_path.exists():
            return False

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return self.marker_start in content
        except Exception:
            return False

    def install(self) -> bool:
        """安装shell集成"""
        config_path = self.get_shell_config_path()

        try:
            # 确保配置文件存在
            config_path.parent.mkdir(parents=True, exist_ok=True)

            # 如果已安装，先卸载
            if self.is_installed():
                self.uninstall()

            # 备份原文件
            if config_path.exists():
                backup_path = config_path.with_suffix(config_path.suffix + '.aiswitch.backup')
                shutil.copy2(config_path, backup_path)

            # 读取现有内容
            existing_content = ""
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    existing_content = f.read()

            # 准备要添加的内容
            integration_code = self.get_integration_code()
            content_to_add = f'''
{self.marker_start}
{integration_code}
{self.marker_end}
'''

            # 对于bash/zsh，在交互式检查之前插入函数定义
            if 'case $- in' in existing_content:
                # 找到交互式检查的位置
                lines = existing_content.split('\n')
                insert_pos = 0
                for i, line in enumerate(lines):
                    if 'case $- in' in line:
                        insert_pos = i
                        break

                # 在交互式检查之前插入
                lines.insert(insert_pos, content_to_add.strip())
                new_content = '\n'.join(lines)
            else:
                # 如果没有找到交互式检查，就追加到末尾
                new_content = existing_content + content_to_add

            # 写入新内容
            with open(config_path, 'w', encoding='utf-8') as f:
                f.write(new_content)

            return True

        except Exception as e:
            print(f"安装失败: {e}")
            return False

    def uninstall(self) -> bool:
        """卸载shell集成"""
        config_path = self.get_shell_config_path()

        if not config_path.exists():
            return True

        try:
            # 读取现有内容
            with open(config_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 查找并移除标记块
            start_idx = content.find(self.marker_start)
            if start_idx == -1:
                return True  # 没有找到，认为已经卸载

            end_idx = content.find(self.marker_end)
            if end_idx == -1:
                return False  # 找到开始标记但没有结束标记，可能文件损坏

            # 移除整个标记块（包括结束标记）
            end_idx += len(self.marker_end)

            # 使用行分割的方式来处理，确保不破坏文件结构
            lines = content.split('\n')
            new_lines = []
            in_marker_block = False

            for line in lines:
                if self.marker_start in line:
                    in_marker_block = True
                    continue
                elif self.marker_end in line:
                    in_marker_block = False
                    continue

                if not in_marker_block:
                    new_lines.append(line)

            new_content = '\n'.join(new_lines)

            # 写回文件
            with open(config_path, 'w', encoding='utf-8') as f:
                f.write(new_content)

            return True

        except Exception as e:
            print(f"卸载失败: {e}")
            return False

    def get_existing_env_vars(self) -> dict:
        """获取当前.bashrc中已持久化的环境变量"""
        config_path = self.get_shell_config_path()

        if not config_path.exists():
            return {}

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                content = f.read()

            lines = content.split('\n')
            existing_vars = {}
            in_env_block = False

            for line in lines:
                # 检查是否是任何AISwitch环境变量块的开始
                if line.strip().startswith("# >>> AISwitch environment variables") and line.strip().endswith(">>>"):
                    in_env_block = True
                    continue
                elif line.strip().startswith("# <<< AISwitch environment variables") and line.strip().endswith("<<<"):
                    in_env_block = False
                    continue

                if in_env_block and line.strip().startswith('export '):
                    # 解析 export VAR="value" 格式
                    export_line = line.strip()[7:]  # 移除 "export "
                    if '=' in export_line:
                        var_name = export_line.split('=')[0]
                        existing_vars[var_name] = True

            return existing_vars

        except Exception:
            return {}

    def save_env_vars(self, env_vars: dict, preset_name: str) -> bool:
        """持久化环境变量到shell配置文件"""
        config_path = self.get_shell_config_path()
        env_marker_start = f"# >>> AISwitch environment variables ({preset_name}) >>>"
        env_marker_end = f"# <<< AISwitch environment variables ({preset_name}) <<<"

        try:
            # 获取之前存在的环境变量
            existing_vars = self.get_existing_env_vars()

            # 确保配置文件存在
            config_path.parent.mkdir(parents=True, exist_ok=True)

            # 读取现有内容
            existing_content = ""
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    existing_content = f.read()

            # 移除之前的环境变量配置(如果存在)
            lines = existing_content.split('\n')
            new_lines = []
            in_env_block = False

            for line in lines:
                # 检查是否是任何AISwitch环境变量块的开始
                if line.strip().startswith("# >>> AISwitch environment variables") and line.strip().endswith(">>>"):
                    in_env_block = True
                    continue
                elif line.strip().startswith("# <<< AISwitch environment variables") and line.strip().endswith("<<<"):
                    in_env_block = False
                    continue

                if not in_env_block:
                    new_lines.append(line)

            # 准备unset语句（用于清除之前的环境变量）
            unset_statements = []
            for var in existing_vars.keys():
                if var not in env_vars:  # 如果新预设中没有这个变量，就unset它
                    unset_statements.append(f'unset {var}')

            # 准备新的环境变量配置
            env_exports = []

            # 先添加unset语句
            if unset_statements:
                env_exports.extend(unset_statements)
                env_exports.append('')  # 空行分隔

            # 再添加新的export语句
            for var, value in env_vars.items():
                # 转义特殊字符
                escaped_value = value.replace('"', '\\"').replace('$', '\\$').replace('`', '\\`')
                env_exports.append(f'export {var}="{escaped_value}"')

            env_content = f'''
{env_marker_start}
{chr(10).join(env_exports)}
{env_marker_end}'''

            # 添加新的环境变量配置到文件末尾
            new_content = '\n'.join(new_lines) + env_content

            # 写入新内容
            with open(config_path, 'w', encoding='utf-8') as f:
                f.write(new_content)

            return True

        except Exception as e:
            print(f"保存环境变量失败: {e}")
            return False

    def clear_env_vars(self) -> bool:
        """清除持久化的环境变量"""
        config_path = self.get_shell_config_path()

        if not config_path.exists():
            return True

        try:
            # 读取现有内容
            with open(config_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 移除所有AISwitch环境变量块
            lines = content.split('\n')
            new_lines = []
            in_env_block = False

            for line in lines:
                # 检查是否是任何AISwitch环境变量块的开始
                if line.strip().startswith("# >>> AISwitch environment variables") and line.strip().endswith(">>>"):
                    in_env_block = True
                    continue
                elif line.strip().startswith("# <<< AISwitch environment variables") and line.strip().endswith("<<<"):
                    in_env_block = False
                    continue

                if not in_env_block:
                    new_lines.append(line)

            new_content = '\n'.join(new_lines)

            # 写回文件
            with open(config_path, 'w', encoding='utf-8') as f:
                f.write(new_content)

            return True

        except Exception as e:
            print(f"清除环境变量失败: {e}")
            return False

    def get_install_command(self) -> str:
        """获取手动安装的命令"""
        return f'eval $(aiswitch apply <preset> --export)'
