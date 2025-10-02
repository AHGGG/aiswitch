"""CLI代理包装器模块

提供管理和协调多个AI CLI工具的系统，支持模拟用户输入、捕获CLI输出、
并提供统一的接口来控制多个CLI工具。
"""

from .manager import CLIAgentManager
from .agent_wrapper import CLIAgentWrapper
from .types import CommandResult, SessionStatus, AgentConfig

__all__ = [
    'CLIAgentManager',
    'CLIAgentWrapper',
    'CommandResult',
    'SessionStatus',
    'AgentConfig'
]