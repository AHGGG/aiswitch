"""通用CLI适配器"""

import re
from typing import List, Dict, Any
from .base_adapter import BaseCliAdapter
from ..types import RawCommandResult, ParsedResult


class GenericAdapter(BaseCliAdapter):
    """通用CLI适配器，适用于大多数CLI工具"""

    def __init__(self, name: str, command: List[str], prompt_pattern: str = None):
        super().__init__(name)
        self.command = command
        self.prompt_pattern = re.compile(prompt_pattern or r'.*[$#>]\s*$')

    async def build_command(self, preset: str) -> List[str]:
        """构建启动命令"""
        return self.command

    async def wait_for_ready(self, stdio_controller) -> None:
        """等待CLI准备就绪"""
        import asyncio
        # 对于cat这样的简单命令，我们只需要等待一下确保进程启动
        await asyncio.sleep(0.5)

    async def format_command(self, command: str) -> str:
        """格式化命令（默认不修改）"""
        # 对于claude代理，直接返回命令作为参数
        if self.name == 'claude':
            return command
        return command

    async def is_command_complete(self, stdout_lines: List[str], stderr_lines: List[str]) -> bool:
        """判断命令是否完成"""
        if not stdout_lines:
            return False

        # 对于一次性命令（如claude --print），只要有输出就认为完成
        if self.name == 'claude':
            return len(stdout_lines) > 0

        # 对于交互式代理，检查提示符
        last_line = stdout_lines[-1] if stdout_lines else ""
        has_prompt = self.prompt_pattern.match(last_line) is not None

        return has_prompt

    async def parse_result(self, raw_result: RawCommandResult) -> ParsedResult:
        """解析输出"""
        output_text = '\n'.join(raw_result.stdout)
        error_text = '\n'.join(raw_result.stderr)

        # 移除提示符行
        lines = output_text.split('\n')
        if lines and self.prompt_pattern.match(lines[-1]):
            lines = lines[:-1]
        cleaned_output = '\n'.join(lines)

        return ParsedResult(
            output=cleaned_output,
            error=error_text,
            metadata={
                "adapter": self.name,
                "raw_lines": len(raw_result.stdout)
            },
            success=len(error_text) == 0
        )