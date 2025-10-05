"""Multi-agent system for AISwitch."""

from .manager import MultiAgentManager
from .types import Task, TaskResult, AgentStatus

__all__ = [
    "MultiAgentManager",
    "Task",
    "TaskResult",
    "AgentStatus",
]
