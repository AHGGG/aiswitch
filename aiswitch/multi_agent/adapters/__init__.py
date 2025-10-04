"""Agent adapters for the multi-agent system."""

from .base_adapter import BaseAdapter
from .claude_adapter import ClaudeAdapter

__all__ = [
    "BaseAdapter",
    "ClaudeAdapter",
]