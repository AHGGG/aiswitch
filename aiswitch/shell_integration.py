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

    if test "$cmd" = "use"
        eval (command aiswitch use $argv --export | string replace "export " "set -gx " | string replace "=" " ")
    else
        command aiswitch $cmd $argv
    end
end'''
        else:
            # bash/zsh
            return '''# AISwitch shell integration
aiswitch() {
    local cmd="$1"
    shift

    if [ "$cmd" = "use" ]; then
        eval $(command aiswitch use "$@" --export)
    else
        command aiswitch "$cmd" "$@"
    fi
}'''

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

            # 准备要添加的内容
            integration_code = self.get_integration_code()
            content_to_add = f'''
{self.marker_start}
{integration_code}
{self.marker_end}
'''

            # 读取现有内容
            existing_content = ""
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    existing_content = f.read()

            # 写入新内容
            with open(config_path, 'w', encoding='utf-8') as f:
                f.write(existing_content + content_to_add)

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

            # 移除整个标记块（包括前后的换行符）
            end_idx += len(self.marker_end)

            # 查找前面的换行符
            if start_idx > 0 and content[start_idx - 1] == '\n':
                start_idx -= 1

            # 查找后面的换行符
            if end_idx < len(content) and content[end_idx] == '\n':
                end_idx += 1

            new_content = content[:start_idx] + content[end_idx:]

            # 写回文件
            with open(config_path, 'w', encoding='utf-8') as f:
                f.write(new_content)

            return True

        except Exception as e:
            print(f"卸载失败: {e}")
            return False

    def get_install_command(self) -> str:
        """获取手动安装的命令"""
        return f'eval $(aiswitch use <preset> --export)'