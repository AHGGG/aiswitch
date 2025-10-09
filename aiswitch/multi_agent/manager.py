"""Multi-agent manager for coordinating multiple AI agents."""

from __future__ import annotations

import asyncio
from typing import Dict, List, Any, TypedDict

from aiswitch.preset import PresetManager
from .adapters import BaseAdapter, ClaudeAdapter
from .types import Task, TaskResult, AgentStatus


class AgentInfo(TypedDict):
    agent_id: str
    agent_instance: BaseAdapter
    adapter_type: str
    status: AgentStatus
    config: Dict[str, Any]
    task_count: int
    metadata: Dict[str, Any]


class MultiAgentManager:
    """Multi-agent manager for coordinating AI agents."""

    def __init__(self):
        self.agents: Dict[str, AgentInfo] = {}
        self.adapters: Dict[str, type[BaseAdapter]] = {
            "claude": ClaudeAdapter,
        }

    async def register_agent(
        self, agent_id: str, adapter_type: str, config: Dict[str, Any] = None
    ) -> None:
        """Register a new agent."""
        if adapter_type not in self.adapters:
            raise ValueError(f"Unknown adapter type: {adapter_type}")

        if agent_id in self.agents:
            raise ValueError(f"Agent {agent_id} already registered")

        adapter_class = self.adapters[adapter_type]
        adapter_instance = adapter_class(config or {})

        try:
            await adapter_instance.initialize()

            self.agents[agent_id] = {
                "agent_id": agent_id,
                "agent_instance": adapter_instance,
                "adapter_type": adapter_type,
                "status": AgentStatus.IDLE,
                "config": config or {},  # config["preset"] = "xx"
                "task_count": 0,
                "metadata": {},
            }

        except Exception as e:
            raise RuntimeError(f"Failed to initialize agent {agent_id}: {e}")

    async def execute_task(
        self, agent_ids: List[str], task: Task, mode: str = "parallel"
    ) -> List[TaskResult]:
        """Execute task on specified agents."""
        if not agent_ids:
            raise ValueError("No agents specified")

        # Validate all agents exist
        for agent_id in agent_ids:
            if agent_id not in self.agents:
                raise ValueError(f"Agent {agent_id} not found")

        if mode == "parallel":
            return await self._execute_parallel(agent_ids, task)
        elif mode == "sequential":
            return await self._execute_sequential(agent_ids, task)
        else:
            raise ValueError(f"Unknown execution mode: {mode}")

    async def _execute_parallel(
        self, agent_ids: List[str], task: Task
    ) -> List[TaskResult]:
        """Execute task in parallel across agents."""
        tasks = []

        for agent_id in agent_ids:
            agent_info = self.agents[agent_id]
            agent_info["status"] = AgentStatus.BUSY

            # Create agent-specific task
            agent_task = Task(
                id=f"{agent_id}-{task.id}",
                prompt=task.prompt,
                agent_ids=[agent_id],
                metadata=task.metadata.copy(),
                system_prompt=task.system_prompt,
                max_tokens=task.max_tokens,
                temperature=task.temperature,
                timeout=task.timeout,
            )

            # Create execution coroutine
            coro = self._execute_on_agent(agent_id, agent_task)
            tasks.append(coro)

        # Execute all tasks in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results and update agent statuses
        processed_results = []
        for i, result in enumerate(results):
            agent_id = agent_ids[i]
            agent_info = self.agents[agent_id]

            if isinstance(result, Exception):
                # Handle exception
                processed_results.append(
                    TaskResult(
                        task_id=f"{agent_id}-{task.id}",
                        success=False,
                        error=str(result),
                    )
                )
                agent_info["status"] = AgentStatus.ERROR
            else:
                processed_results.append(result)
                agent_info["status"] = AgentStatus.IDLE
                agent_info["task_count"] += 1

        return processed_results

    async def _execute_sequential(
        self, agent_ids: List[str], task: Task
    ) -> List[TaskResult]:
        """Execute task sequentially across agents."""
        results = []

        for agent_id in agent_ids:
            agent_info = self.agents[agent_id]
            agent_info["status"] = AgentStatus.BUSY

            # Create agent-specific task
            agent_task = Task(
                id=f"{agent_id}-{task.id}",
                prompt=task.prompt,
                agent_ids=[agent_id],
                metadata=task.metadata.copy(),
                system_prompt=task.system_prompt,
                max_tokens=task.max_tokens,
                temperature=task.temperature,
                timeout=task.timeout,
            )

            try:
                result = await self._execute_on_agent(agent_id, agent_task)
                results.append(result)
                agent_info["status"] = AgentStatus.IDLE
                agent_info["task_count"] += 1

                # Stop on first failure if configured
                if not result.success and task.metadata.get("stop_on_error", False):
                    print(f"error: {result}")
                    break

            except Exception as e:
                result = TaskResult(
                    task_id=f"{agent_id}-{task.id}", success=False, error=str(e)
                )
                results.append(result)
                agent_info["status"] = AgentStatus.ERROR
                break

        return results

    async def _execute_on_agent(self, agent_id: str, task: Task) -> TaskResult:
        """Execute task on a specific agent."""
        agent_info = self.agents[agent_id]
        agent_instance = agent_info["agent_instance"]

        try:
            result = await agent_instance.execute_task(task, task.timeout)
            return result
        except Exception as e:
            return TaskResult(task_id=task.id, success=False, error=str(e))

    async def switch_agent_env(self, agent_id: str, preset: str):
        """Switch environment for a specific agent."""
        if agent_id not in self.agents:
            raise ValueError(f"Agent {agent_id} not found")

        agent_info = self.agents[agent_id]
        agent_instance = self.agents[agent_id]["agent_instance"]
        agent_instance.change_preset(preset)
        agent_info["metadata"]["current_preset"] = preset

    def get_agent_status(self, agent_id: str) -> Dict[str, Any]:
        """Get status of a specific agent."""
        if agent_id not in self.agents:
            return {"error": "Agent not found"}

        agent_info = self.agents[agent_id]

        # Extract name from config if available
        name = agent_info["config"].get("name", agent_id)

        return {
            "agent_id": agent_id,
            "name": name,  # Add name to top level for UI display
            "adapter_type": agent_info["adapter_type"],
            "status": agent_info["status"].value,
            "task_count": agent_info["task_count"],
            "metadata": agent_info["metadata"],
        }

    async def list_agents(self) -> List[Dict[str, Any]]:
        """List all registered agents."""
        agents_info = []

        for agent_id, agent_info in self.agents.items():
            status_info = self.get_agent_status(agent_id)
            agents_info.append(status_info)

        return agents_info

    async def terminate_agent(self, agent_id: str) -> None:
        """Terminate and remove an agent."""
        if agent_id not in self.agents:
            raise ValueError(f"Agent {agent_id} not found")

        agent_info = self.agents[agent_id]
        agent_instance = agent_info["agent_instance"]

        # Set status to stopping
        agent_info["status"] = AgentStatus.STOPPING

        try:
            # Clean up agent instance (this will close ClaudeSDKClient for Claude adapters)
            await agent_instance.close()
        finally:
            # Remove from agents dict
            del self.agents[agent_id]

    def get_available_adapters(self) -> List[str]:
        """Get list of available adapter types."""
        return list(self.adapters.keys())

    def register_adapter(
        self, adapter_type: str, adapter_class: type[BaseAdapter]
    ) -> None:
        """Register a new adapter type."""
        self.adapters[adapter_type] = adapter_class

    async def cleanup(self) -> None:
        """Clean up all agents and resources."""
        agent_ids = list(self.agents.keys())
        for agent_id in agent_ids:
            try:
                await self.terminate_agent(agent_id)
            except Exception:
                # Continue cleanup even if individual agents fail
                pass
