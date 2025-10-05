"""CLI代理包装器"""

import uuid
from datetime import datetime
from typing import Dict, Optional, Any, List, TYPE_CHECKING
from .process_session import CLIProcessSession
from .types import CommandResult

if TYPE_CHECKING:
    from .adapters.base_adapter import BaseCliAdapter


class CLIAgentWrapper:
    """CLI代理包装器，管理单个CLI工具的多个会话"""

    def __init__(self, agent_id: str, adapter: "BaseCliAdapter"):
        self.agent_id = agent_id
        self.adapter = adapter
        self.sessions: Dict[str, CLIProcessSession] = {}
        self.capabilities: Optional[Dict[str, Any]] = None

    async def initialize(self) -> Dict[str, Any]:
        """初始化代理，返回能力信息"""
        self.capabilities = await self.adapter.get_capabilities()
        return {
            "agent_id": self.agent_id,
            "capabilities": self.capabilities,
            "status": "initialized",
            "initialized_at": datetime.now().isoformat()
        }

    async def new_session(
        self,
        preset: str,
        cwd: str = None,
        env: Dict[str, str] = None
    ) -> str:
        """创建新会话"""
        session_id = str(uuid.uuid4())

        session = CLIProcessSession(
            session_id=session_id,
            agent_id=self.agent_id,
            adapter=self.adapter,
            preset=preset,
            cwd=cwd,
            env=env or {}
        )

        await session.start()
        self.sessions[session_id] = session

        return session_id

    async def execute_command(
        self,
        session_id: str,
        command: str,
        timeout: float = 30.0
    ) -> CommandResult:
        """在指定会话中执行命令"""
        if session_id not in self.sessions:
            raise ValueError(f"Session {session_id} not found")

        session = self.sessions[session_id]
        return await session.execute_command(command, timeout)

    async def terminate_session(self, session_id: str) -> None:
        """终止指定会话"""
        if session_id in self.sessions:
            await self.sessions[session_id].terminate()
            del self.sessions[session_id]

    async def get_session_status(self, session_id: str) -> Dict[str, Any]:
        """获取会话状态"""
        if session_id not in self.sessions:
            return {"error": "Session not found"}

        session = self.sessions[session_id]
        return await session.get_status()

    async def list_sessions(self) -> List[Dict[str, Any]]:
        """列出所有会话"""
        sessions_info = []
        for session_id, session in self.sessions.items():
            status = await session.get_status()
            sessions_info.append({
                "session_id": session_id,
                "status": status,
                "created_at": session.created_at.isoformat()
            })
        return sessions_info