"""Type definitions for the multi-agent system."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class AgentStatus(Enum):
    """Agent status enumeration."""

    STOPPED = "stopped"
    STARTING = "starting"
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    STOPPING = "stopping"


@dataclass
class Task:
    """Represents a task to be executed by agents."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    prompt: str = ""
    agent_ids: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    # Optional task parameters
    system_prompt: Optional[str] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    timeout: float = 60.0


@dataclass
class TaskResult:
    """Represents the result of a task execution."""

    task_id: str
    success: bool
    result: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    duration: Optional[float] = None
    completed_at: datetime = field(default_factory=datetime.now)


@dataclass
class AgentConfig:
    """Configuration for an agent."""

    name: str = ""
    adapter_type: str = ""
    config: Dict[str, Any] = field(default_factory=dict)
    env_vars: Dict[str, str] = field(default_factory=dict)
    enabled: bool = True


@dataclass
class AgentInfo:
    """Information about an agent."""

    agent_id: str
    name: str
    adapter_type: str
    status: AgentStatus
    capabilities: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: Optional[datetime] = None
    task_count: int = 0
