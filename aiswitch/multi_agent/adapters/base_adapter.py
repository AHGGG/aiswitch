"""Base adapter for multi-agent system."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..types import Task, TaskResult


class BaseAdapter(ABC):
    """Base class for agent adapters."""

    def __init__(self, adapter_type: str):
        self.adapter_type = adapter_type
        self._initialized = False

    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the adapter."""
        pass

    @abstractmethod
    async def execute_task(self, task: Task, timeout: float = 30.0) -> TaskResult:
        """Execute a task and return the result."""
        pass

    async def close(self) -> None:
        """Clean up adapter resources."""
        self._initialized = False

    def is_initialized(self) -> bool:
        """Check if adapter is initialized."""
        return self._initialized

    @abstractmethod
    def change_preset(self, preset):
        pass


DEFAULT_PRESET = "ds"
