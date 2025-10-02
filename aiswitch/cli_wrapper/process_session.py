"""CLI进程会话管理"""

import os
import subprocess
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any, TYPE_CHECKING
from .stdio_controller import StdioController
from .types import CommandResult, SessionStatus, ParsedResult

if TYPE_CHECKING:
    from .adapters.base_adapter import BaseCliAdapter


class CLIProcessSession:
    """CLI进程会话，管理单个CLI工具实例"""

    def __init__(
        self,
        session_id: str,
        agent_id: str,
        adapter: "BaseCliAdapter",
        preset: str,
        cwd: str = None,
        env: Dict[str, str] = None
    ):
        self.session_id = session_id
        self.agent_id = agent_id
        self.adapter = adapter
        self.preset = preset
        self.cwd = cwd
        self.env = env or {}
        self.created_at = datetime.now()

        # 进程相关
        self.process: Optional[subprocess.Popen] = None
        self.stdio_controller: Optional[StdioController] = None
        self.status = SessionStatus.STOPPED
        self.cancelled = False

        # 状态跟踪
        self.command_count = 0
        self.last_activity = datetime.now()

    async def start(self) -> None:
        """启动CLI进程"""
        try:
            # 构建命令和环境
            command = await self.adapter.build_command(self.preset)
            full_env = {**os.environ, **self.env}

            # 启动进程
            self.process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=0,
                cwd=self.cwd,
                env=full_env
            )

            # 创建stdio控制器
            self.stdio_controller = StdioController(self.process, self.adapter)
            await self.stdio_controller.start()

            # 等待初始化完成
            await self.adapter.wait_for_ready(self.stdio_controller)

            self.status = SessionStatus.RUNNING
            self.last_activity = datetime.now()

        except Exception as e:
            self.status = SessionStatus.ERROR
            raise RuntimeError(f"Failed to start session: {e}")

    async def execute_command(self, command: str, timeout: float = 30.0) -> CommandResult:
        """执行命令并返回结果"""
        if self.status != SessionStatus.RUNNING:
            raise RuntimeError(f"Session not running, status: {self.status}")

        self.command_count += 1
        self.last_activity = datetime.now()

        try:
            # 格式化命令
            formatted_command = await self.adapter.format_command(command)

            # 发送命令并等待响应
            result = await self.stdio_controller.execute_command(formatted_command, timeout)

            # 解析结果
            parsed_result = await self.adapter.parse_result(result)

            return CommandResult(
                session_id=self.session_id,
                agent_id=self.agent_id,
                command=command,
                result=parsed_result,
                timestamp=datetime.now(),
                success=True
            )

        except asyncio.TimeoutError:
            return CommandResult(
                session_id=self.session_id,
                agent_id=self.agent_id,
                command=command,
                result=ParsedResult(
                    output="",
                    error="Command timeout",
                    metadata={},
                    success=False
                ),
                timestamp=datetime.now(),
                success=False
            )
        except Exception as e:
            return CommandResult(
                session_id=self.session_id,
                agent_id=self.agent_id,
                command=command,
                result=ParsedResult(
                    output="",
                    error=str(e),
                    metadata={},
                    success=False
                ),
                timestamp=datetime.now(),
                success=False
            )

    async def terminate(self) -> None:
        """优雅终止进程"""
        self.cancelled = True
        self.status = SessionStatus.STOPPING

        if self.stdio_controller:
            await self.stdio_controller.stop()

        if self.process:
            try:
                # 尝试优雅关闭
                self.process.terminate()
                await asyncio.wait_for(asyncio.to_thread(self.process.wait), timeout=5.0)
            except asyncio.TimeoutError:
                # 强制关闭
                self.process.kill()
                await asyncio.to_thread(self.process.wait)

        self.status = SessionStatus.STOPPED

    async def get_status(self) -> Dict[str, Any]:
        """获取会话状态"""
        return {
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "command_count": self.command_count,
            "cancelled": self.cancelled,
            "process_id": self.process.pid if self.process else None
        }