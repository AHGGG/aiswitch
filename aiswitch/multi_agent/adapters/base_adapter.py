"""Base adapter for multi-agent system."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Any

from ..types import Task, TaskResult


class BaseAdapter(ABC):
    """Base class for agent adapters."""

    def __init__(self, adapter_type: str):
        self.adapter_type = adapter_type
        self.config: Dict[str, Any] = {}
        self._initialized = False

    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the adapter."""
        pass

    @abstractmethod
    async def execute_task(self, task: Task, timeout: float = 30.0) -> TaskResult:
        """Execute a task and return the result."""
        pass

    @abstractmethod
    async def switch_environment(self, preset: str, env_vars: Dict[str, str]) -> bool:
        """Switch environment variables."""
        pass

    async def close(self) -> None:
        """Clean up adapter resources."""
        self._initialized = False

    def is_initialized(self) -> bool:
        """Check if adapter is initialized."""
        return self._initialized

    def get_capabilities(self) -> Dict[str, Any]:
        """Get adapter capabilities."""
        return {
            "adapter_type": self.adapter_type,
            "supports_streaming": False,
            "supports_tools": False,
            "supports_files": False,
        }