"""Custom events for AISwitch Textual UI."""

from __future__ import annotations

from typing import Dict, Any, Optional
from textual.message import Message


class UserMessageSubmitted(Message):
    """Event fired when user submits a message."""

    def __init__(self, message: str, agent: str) -> None:
        super().__init__()
        self.message = message
        self.agent = agent


class AgentSelected(Message):
    """Event fired when an agent is selected."""

    def __init__(self, agent_id: str) -> None:
        super().__init__()
        self.agent_id = agent_id


class AgentResponseReceived(Message):
    """Event fired when agent response is received."""

    def __init__(self, agent: str, response: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        super().__init__()
        self.agent = agent
        self.response = response
        self.metadata = metadata or {}


class AgentStatusChanged(Message):
    """Event fired when agent status changes."""

    def __init__(self, agent_id: str, status: str, details: Optional[str] = None) -> None:
        super().__init__()
        self.agent_id = agent_id
        self.status = status
        self.details = details


class ExecutionModeChanged(Message):
    """Event fired when execution mode changes."""

    def __init__(self, mode: str) -> None:
        super().__init__()
        self.mode = mode


class PresetChanged(Message):
    """Event fired when preset changes."""

    def __init__(self, preset: str) -> None:
        super().__init__()
        self.preset = preset


class ChatCleared(Message):
    """Event fired when chat is cleared."""

    def __init__(self) -> None:
        super().__init__()


class SessionSaveRequested(Message):
    """Event fired when session save is requested."""

    def __init__(self, session_name: Optional[str] = None) -> None:
        super().__init__()
        self.session_name = session_name


class SessionLoadRequested(Message):
    """Event fired when session load is requested."""

    def __init__(self, session_name: str) -> None:
        super().__init__()
        self.session_name = session_name


class AgentError(Message):
    """Event fired when agent encounters an error."""

    def __init__(self, agent: str, error: str, details: Optional[str] = None) -> None:
        super().__init__()
        self.agent = agent
        self.error = error
        self.details = details


class CommandExecutionStarted(Message):
    """Event fired when command execution starts."""

    def __init__(self, command: str, agents: list[str], mode: str) -> None:
        super().__init__()
        self.command = command
        self.agents = agents
        self.mode = mode


class CommandExecutionCompleted(Message):
    """Event fired when command execution completes."""

    def __init__(self, command: str, agents: list[str], results: list[Any]) -> None:
        super().__init__()
        self.command = command
        self.agents = agents
        self.results = results


class AgentAddRequested(Message):
    """Event fired when adding a new agent is requested."""

    def __init__(self, agent_name: str, adapter_type: str, preset: Optional[str] = None) -> None:
        super().__init__()
        self.agent_name = agent_name
        self.adapter_type = adapter_type
        self.preset = preset