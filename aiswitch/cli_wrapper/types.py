"""CLI代理包装器类型定义"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum


class SessionStatus(Enum):
    """会话状态枚举"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class RawCommandResult:
    """原始命令执行结果"""
    stdout: List[str]
    stderr: List[str]
    command: str
    completed: bool


@dataclass
class ParsedResult:
    """解析后的结果"""
    output: str
    error: str
    metadata: Dict[str, Any]
    success: bool


@dataclass
class CommandResult:
    """完整的命令执行结果"""
    session_id: str
    agent_id: str
    command: str
    result: ParsedResult
    timestamp: datetime
    success: bool


@dataclass
class AgentConfig:
    """代理配置"""
    command: List[str]
    prompt_pattern: Optional[str] = None
    env: Optional[Dict[str, str]] = None
    cwd: Optional[str] = None


@dataclass
class BackgroundProcess:
    """后台进程信息"""
    process_id: str
    status: str
    started_at: datetime
    last_output: Optional[str] = None