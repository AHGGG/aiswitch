"""Multi-agent manager for coordinating multiple AI agents."""

from __future__ import annotations

import asyncio
from typing import Dict, List, Any, Optional

from .adapters import BaseAdapter, ClaudeAdapter
from .types import Task, TaskResult, AgentStatus, AgentInfo, AgentConfig


class MultiAgentManager:
    """Multi-agent manager for coordinating AI agents."""

    def __init__(self):
        self.agents: Dict[str, Dict[str, Any]] = {}
        self.adapters: Dict[str, type[BaseAdapter]] = {
            'claude': ClaudeAdapter,
        }

    async def register_agent(
        self,
        agent_id: str,
        adapter_type: str,
        config: Dict[str, Any] = None
    ) -> None:
        """Register a new agent."""
        if adapter_type not in self.adapters:
            raise ValueError(f"Unknown adapter type: {adapter_type}")

        if agent_id in self.agents:
            raise ValueError(f"Agent {agent_id} already registered")

        adapter_class = self.adapters[adapter_type]
        adapter = adapter_class(config or {})

        try:
            await adapter.initialize()

            self.agents[agent_id] = {
                "agent_id": agent_id,
                "adapter": adapter,
                "adapter_type": adapter_type,
                "status": AgentStatus.IDLE,
                "config": config or {},
                "task_count": 0,
                "metadata": {}
            }

        except Exception as e:
            raise RuntimeError(f"Failed to initialize agent {agent_id}: {e}")

    async def execute_task(
        self,
        agent_ids: List[str],
        task: Task,
        mode: str = "parallel"
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

    async def _execute_parallel(self, agent_ids: List[str], task: Task) -> List[TaskResult]:
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
                timeout=task.timeout
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
                processed_results.append(TaskResult(
                    task_id=f"{agent_id}-{task.id}",
                    success=False,
                    error=str(result)
                ))
                agent_info["status"] = AgentStatus.ERROR
            else:
                processed_results.append(result)
                agent_info["status"] = AgentStatus.IDLE
                agent_info["task_count"] += 1

        return processed_results

    async def _execute_sequential(self, agent_ids: List[str], task: Task) -> List[TaskResult]:
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
                timeout=task.timeout
            )

            try:
                result = await self._execute_on_agent(agent_id, agent_task)
                results.append(result)
                agent_info["status"] = AgentStatus.IDLE
                agent_info["task_count"] += 1

                # Stop on first failure if configured
                if not result.success and task.metadata.get("stop_on_error", False):
                    break

            except Exception as e:
                result = TaskResult(
                    task_id=f"{agent_id}-{task.id}",
                    success=False,
                    error=str(e)
                )
                results.append(result)
                agent_info["status"] = AgentStatus.ERROR
                break

        return results

    async def _execute_on_agent(self, agent_id: str, task: Task) -> TaskResult:
        """Execute task on a specific agent."""
        agent_info = self.agents[agent_id]
        adapter = agent_info["adapter"]

        try:
            result = await adapter.execute_task(task, task.timeout)
            return result
        except Exception as e:
            return TaskResult(
                task_id=task.id,
                success=False,
                error=str(e)
            )

    async def switch_agent_env(self, agent_id: str, preset: str) -> bool:
        """Switch environment for a specific agent."""
        if agent_id not in self.agents:
            raise ValueError(f"Agent {agent_id} not found")

        agent_info = self.agents[agent_id]
        adapter = agent_info["adapter"]

        # Load environment variables for preset
        env_vars = self._get_preset_env_vars(preset)

        try:
            success = await adapter.switch_environment(preset, env_vars)
            if success:
                agent_info["metadata"]["current_preset"] = preset
            return success
        except Exception:
            return False

    def _get_preset_env_vars(self, preset: str) -> Dict[str, str]:
        """Get environment variables for a preset."""
        # TODO: Implement proper preset loading
        # For now, return current environment
        import os
        return dict(os.environ)

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
            "capabilities": agent_info["adapter"].get_capabilities()
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
        adapter = agent_info["adapter"]

        # Set status to stopping
        agent_info["status"] = AgentStatus.STOPPING

        try:
            # Clean up adapter
            if hasattr(adapter, 'close'):
                await adapter.close()
        finally:
            # Remove from agents dict
            del self.agents[agent_id]

    def get_available_adapters(self) -> List[str]:
        """Get list of available adapter types."""
        return list(self.adapters.keys())

    def register_adapter(self, adapter_type: str, adapter_class: type[BaseAdapter]) -> None:
        """Register a new adapter type."""
        self.adapters[adapter_type] = adapter_class

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on all agents."""
        health_info = {
            "total_agents": len(self.agents),
            "healthy_agents": 0,
            "error_agents": 0,
            "agents": {}
        }

        for agent_id, agent_info in self.agents.items():
            status = agent_info["status"]
            health_info["agents"][agent_id] = {
                "status": status.value,
                "healthy": status not in [AgentStatus.ERROR, AgentStatus.STOPPING]
            }

            if health_info["agents"][agent_id]["healthy"]:
                health_info["healthy_agents"] += 1
            else:
                health_info["error_agents"] += 1

        return health_info

    async def cleanup(self) -> None:
        """Clean up all agents and resources."""
        agent_ids = list(self.agents.keys())
        for agent_id in agent_ids:
            try:
                await self.terminate_agent(agent_id)
            except Exception:
                # Continue cleanup even if individual agents fail
                pass