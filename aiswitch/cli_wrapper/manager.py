"""CLI代理管理器"""

import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional
from .agent_wrapper import CLIAgentWrapper
from .adapters import GenericAdapter
from .types import CommandResult, AgentConfig, ParsedResult


class CLIAgentManager:
    """CLI代理管理器，统一管理多个代理"""

    def __init__(self):
        self.agents: Dict[str, CLIAgentWrapper] = {}
        self.adapters: Dict[str, Any] = {
            'generic': GenericAdapter
        }

    async def register_agent(
        self,
        agent_id: str,
        adapter_name: str,
        config: AgentConfig = None
    ) -> None:
        """注册新代理"""
        if adapter_name not in self.adapters:
            raise ValueError(f"Unknown adapter: {adapter_name}")

        adapter_class = self.adapters[adapter_name]
        if adapter_name == 'generic' and config:
            # 为通用适配器创建实例
            adapter = GenericAdapter(
                name=agent_id,
                command=config.command,
                prompt_pattern=config.prompt_pattern
            )
        else:
            # 为其他适配器创建默认实例
            adapter = adapter_class(agent_id)

        agent = CLIAgentWrapper(agent_id, adapter)
        await agent.initialize()
        self.agents[agent_id] = agent

    async def create_session(self, agent_id: str, preset: str, **kwargs) -> str:
        """为指定代理创建会话"""
        if agent_id not in self.agents:
            raise ValueError(f"Agent {agent_id} not found")

        return await self.agents[agent_id].new_session(preset, **kwargs)

    async def execute_command(
        self,
        agent_id: str,
        session_id: str,
        command: str,
        **kwargs
    ) -> CommandResult:
        """在指定代理的会话中执行命令"""
        if agent_id not in self.agents:
            raise ValueError(f"Agent {agent_id} not found")

        return await self.agents[agent_id].execute_command(session_id, command, **kwargs)

    async def execute_parallel(self, commands: List[Dict[str, Any]]) -> List[CommandResult]:
        """并行执行多个命令"""
        tasks = []

        for cmd_info in commands:
            agent_id = cmd_info['agent_id']
            session_id = cmd_info['session_id']
            command = cmd_info['command']

            if agent_id in self.agents:
                task = self.agents[agent_id].execute_command(session_id, command)
                tasks.append(task)

        return await asyncio.gather(*tasks, return_exceptions=True)

    async def execute_sequential(self, commands: List[Dict[str, Any]]) -> List[CommandResult]:
        """串行执行多个命令"""
        results = []

        for cmd_info in commands:
            agent_id = cmd_info['agent_id']
            session_id = cmd_info['session_id']
            command = cmd_info['command']

            if agent_id in self.agents:
                try:
                    result = await self.agents[agent_id].execute_command(session_id, command)
                    results.append(result)

                    # 如果命令失败且设置了stop_on_error，则停止执行
                    if not result.success and cmd_info.get('stop_on_error', False):
                        break

                except Exception as e:
                    error_result = CommandResult(
                        session_id=session_id,
                        agent_id=agent_id,
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
                    results.append(error_result)
                    if cmd_info.get('stop_on_error', False):
                        break

        return results

    async def list_agents(self) -> List[Dict[str, Any]]:
        """列出所有代理"""
        agents_info = []
        for agent_id, agent in self.agents.items():
            sessions = await agent.list_sessions()
            agents_info.append({
                "agent_id": agent_id,
                "adapter": agent.adapter.name,
                "capabilities": agent.capabilities,
                "sessions": sessions
            })
        return agents_info

    async def terminate_agent(self, agent_id: str) -> None:
        """终止指定代理的所有会话"""
        if agent_id in self.agents:
            agent = self.agents[agent_id]
            for session_id in list(agent.sessions.keys()):
                await agent.terminate_session(session_id)
            del self.agents[agent_id]