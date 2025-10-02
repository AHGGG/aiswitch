"""CLI适配器基类"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, TYPE_CHECKING
from ..types import RawCommandResult, ParsedResult

if TYPE_CHECKING:
    from ..stdio_controller import StdioController


class BaseCliAdapter(ABC):
    """CLI适配器基类，定义统一接口"""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    async def build_command(self, preset: str) -> List[str]:
        """构建启动CLI的命令"""
        pass

    @abstractmethod
    async def wait_for_ready(self, stdio_controller: "StdioController") -> None:
        """等待CLI初始化完成"""
        pass

    @abstractmethod
    async def format_command(self, command: str) -> str:
        """格式化要发送的命令"""
        pass

    @abstractmethod
    async def is_command_complete(self, stdout_lines: List[str], stderr_lines: List[str]) -> bool:
        """判断命令是否执行完成"""
        pass

    @abstractmethod
    async def parse_result(self, raw_result: RawCommandResult) -> ParsedResult:
        """解析命令执行结果"""
        pass

    async def get_capabilities(self) -> Dict[str, Any]:
        """返回适配器能力"""
        return {
            "name": self.name,
            "supports_interactive": True,
            "supports_files": True,
            "supports_streaming": True
        }