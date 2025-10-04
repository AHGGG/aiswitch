"""Textual UI components for AISwitch."""

from .app import AISwitch
from .events import (
    UserMessageSubmitted,
    AgentSelected,
    AgentResponseReceived,
    ExecutionModeChanged,
    PresetChanged,
)

__all__ = [
    "AISwitch",
    "UserMessageSubmitted",
    "AgentSelected",
    "AgentResponseReceived",
    "ExecutionModeChanged",
    "PresetChanged",
]