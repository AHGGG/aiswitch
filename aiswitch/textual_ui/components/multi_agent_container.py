"""Multi-agent container component for AISwitch."""

from __future__ import annotations

import asyncio
from typing import Dict, List, Any, Optional

from textual import on
from textual.reactive import reactive
from textual.containers import Container
from textual.css.query import NoMatches

from .chat_display import ChatDisplay
from .input_panel import InputPanel
from .status_bar import StatusBar
from ..events import (
    UserMessageSubmitted,
    AgentSelected,
    AgentResponseReceived,
    AgentStatusChanged,
    ExecutionModeChanged,
    PresetChanged,
    ChatCleared,
    CommandExecutionStarted,
    CommandExecutionCompleted,
    AgentError
)


class MultiAgentContainer(Container):
    """Container that manages multiple AI agents and their interactions."""

    # Reactive attributes
    active_agents = reactive([], layout=False)
    current_agent = reactive("", layout=False)
    execution_mode = reactive("sequential", layout=False)
    current_preset = reactive("", layout=False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.agent_manager = None
        self._execution_lock = asyncio.Lock()

    def compose(self):
        """Compose the multi-agent container UI."""
        from textual.app import ComposeResult
        yield ChatDisplay(id="chat_display")
        yield InputPanel(id="input_panel")
        yield StatusBar(id="status_bar")

    async def on_mount(self) -> None:
        """Initialize the container when mounted."""
        # Initialize agent manager
        await self._initialize_agent_manager()

        # Sync reactive attributes with components
        self._sync_component_states()

        # Force update status bar with current state
        try:
            status_bar = self.query_one("#status_bar", StatusBar)
            if self.current_preset:
                status_bar.set_preset(self.current_preset)
            if self.active_agents:
                status_bar.set_agents(self.active_agents)
            if self.current_agent:
                status_bar.set_current_agent(self.current_agent)
        except NoMatches:
            pass

    def watch_active_agents(self, agents: List[Dict[str, Any]]) -> None:
        """Update UI when active agents change."""
        try:
            if self.is_mounted:
                # Update status bar
                status_bar = self.query_one("#status_bar", StatusBar)
                status_bar.set_agents(agents)
                if agents:
                    status_bar.set_connection_status("connected")
                else:
                    status_bar.set_connection_status("disconnected")
        except NoMatches:
            # Components not yet mounted, will be updated in _sync_component_states
            pass

    def watch_current_agent(self, agent: str) -> None:
        """Update UI when current agent changes."""
        # Only update if agent is not empty
        if not agent:
            return

        try:
            if self.is_mounted:
                # Update all components
                status_bar = self.query_one("#status_bar", StatusBar)
                status_bar.set_current_agent(agent)

                chat_display = self.query_one("#chat_display", ChatDisplay)
                chat_display.switch_agent(agent)

                input_panel = self.query_one("#input_panel", InputPanel)
                input_panel.set_agent(agent)
        except NoMatches:
            # Components not yet mounted, will be updated in _sync_component_states
            pass

    def watch_execution_mode(self, mode: str) -> None:
        """Update UI when execution mode changes."""
        try:
            if self.is_mounted:
                status_bar = self.query_one("#status_bar", StatusBar)
                status_bar.set_execution_mode(mode)

                chat_display = self.query_one("#chat_display", ChatDisplay)
                chat_display.add_system_message(f"Execution mode set to: {mode}")
        except NoMatches:
            # Components not yet mounted, will be updated in _sync_component_states
            pass

    def watch_current_preset(self, preset: str) -> None:
        """Update UI when preset changes."""
        # Only update UI if the container is mounted and has child components
        try:
            if self.is_mounted:
                status_bar = self.query_one("#status_bar", StatusBar)
                status_bar.set_preset(preset)
        except NoMatches:
            # Components not yet mounted, will be updated in _sync_component_states
            pass

    async def _initialize_agent_manager(self) -> None:
        """Initialize the agent manager."""
        try:
            # Import here to avoid circular imports
            from ...multi_agent import MultiAgentManager
            self.agent_manager = MultiAgentManager()

            # Apply current preset to environment before registering agents
            if hasattr(self, 'current_preset') and self.current_preset:
                await self._apply_preset_to_environment(self.current_preset)

            # Register default agents
            await self._register_default_agents()

            # Load initial agent list
            await self._refresh_agent_list()

            # Ensure status bar is updated after agent initialization
            self.call_after_refresh(self._update_status_bar_after_init)

        except Exception as e:
            chat_display = self.query_one("#chat_display", ChatDisplay)
            chat_display.add_error_message(f"Failed to initialize agent manager: {e}")

    async def _apply_preset_to_environment(self, preset: str) -> None:
        """Apply preset environment variables to current process."""
        try:
            from ...preset import PresetManager
            import os

            preset_manager = PresetManager()
            preset_config, _, _ = preset_manager.use_preset(preset, apply_to_env=False)

            # Apply preset variables to current environment
            for key, value in preset_config.variables.items():
                os.environ[key] = value

        except Exception as e:
            chat_display = self.query_one("#chat_display", ChatDisplay)
            chat_display.add_system_message(f"Warning: Failed to apply preset environment: {e}", "warning")

    async def _register_default_agents(self) -> None:
        """Register default agents."""
        try:
            # Check if Claude SDK is available
            try:
                from claude_agent_sdk import query
                claude_available = True
            except ImportError:
                claude_available = False

            if claude_available:
                await self.agent_manager.register_agent("claude", "claude", {})

            # TODO: Add other agents as they become available

        except Exception as e:
            chat_display = self.query_one("#chat_display", ChatDisplay)
            chat_display.add_system_message(f"Warning: Some agents could not be registered: {e}", "warning")

    async def _refresh_agent_list(self) -> None:
        """Refresh the list of available agents."""
        if not self.agent_manager:
            return

        try:
            agents_info = await self.agent_manager.list_agents()
            self.active_agents = agents_info

            # Set default agent if none selected
            if agents_info and not self.current_agent:
                self.current_agent = agents_info[0]["agent_id"]

        except Exception as e:
            chat_display = self.query_one("#chat_display", ChatDisplay)
            chat_display.add_error_message(f"Failed to load agents: {e}")

    def _sync_component_states(self) -> None:
        """Sync reactive attributes with component states."""
        # This ensures all components reflect the current state
        self.watch_active_agents(self.active_agents)
        self.watch_current_agent(self.current_agent)
        self.watch_execution_mode(self.execution_mode)
        self.watch_current_preset(self.current_preset)

    # Event handlers
    @on(UserMessageSubmitted)
    async def handle_user_message(self, event: UserMessageSubmitted) -> None:
        """Handle user message submission."""
        chat_display = self.query_one("#chat_display", ChatDisplay)
        status_bar = self.query_one("#status_bar", StatusBar)

        # Display user message
        chat_display.add_user_message(event.message)
        status_bar.increment_message_count()

        # Execute command
        await self.execute_command(event.message)

    @on(AgentSelected)
    async def handle_agent_selected(self, event: AgentSelected) -> None:
        """Handle agent selection."""
        if event.agent_id != self.current_agent:
            old_agent = self.current_agent
            self.current_agent = event.agent_id

            chat_display = self.query_one("#chat_display", ChatDisplay)
            chat_display.add_system_message(f"Switched from {old_agent} to {event.agent_id}")

    @on(ExecutionModeChanged)
    async def handle_execution_mode_changed(self, event: ExecutionModeChanged) -> None:
        """Handle execution mode change."""
        if event.mode in ["parallel", "sequential"]:
            self.execution_mode = event.mode

    @on(PresetChanged)
    async def handle_preset_changed(self, event: PresetChanged) -> None:
        """Handle preset change."""
        await self.apply_preset(event.preset)

    @on(ChatCleared)
    async def handle_chat_cleared(self, event: ChatCleared) -> None:
        """Handle chat clear request."""
        chat_display = self.query_one("#chat_display", ChatDisplay)
        status_bar = self.query_one("#status_bar", StatusBar)

        chat_display.clear_history()
        status_bar.set_message_count(0)

    async def execute_command(self, command: str) -> None:
        """Execute a command using current agent(s)."""
        if not self.agent_manager:
            chat_display = self.query_one("#chat_display", ChatDisplay)
            chat_display.add_error_message("Agent manager not initialized")
            return

        async with self._execution_lock:
            try:
                # Determine which agents to use
                if self.execution_mode == "parallel":
                    agents_to_use = [agent["agent_id"] for agent in self.active_agents]
                else:
                    agents_to_use = [self.current_agent] if self.current_agent else []

                if not agents_to_use:
                    chat_display = self.query_one("#chat_display", ChatDisplay)
                    chat_display.add_error_message("No agents available for execution")
                    return

                # Notify execution start
                self.post_message(CommandExecutionStarted(command, agents_to_use, self.execution_mode))

                chat_display = self.query_one("#chat_display", ChatDisplay)
                status_bar = self.query_one("#status_bar", StatusBar)

                chat_display.add_execution_status(
                    f"Executing command: {command}",
                    agents_to_use,
                    self.execution_mode
                )

                status_bar.update_execution_info(agents_to_use, self.execution_mode, "started")

                # Execute the command
                results = []

                if self.execution_mode == "parallel":
                    results = await self._execute_parallel(command, agents_to_use)
                else:
                    results = await self._execute_sequential(command, agents_to_use)

                # Display results
                for result in results:
                    if result.success:
                        chat_display.add_agent_message(
                            result.task_id.split("-")[0],  # Extract agent name
                            result.result,
                            result.metadata
                        )
                    else:
                        chat_display.add_error_message(
                            result.error or "Unknown error",
                            result.task_id.split("-")[0]
                        )

                # Notify execution completion
                self.post_message(CommandExecutionCompleted(command, agents_to_use, results))
                status_bar.update_execution_info(agents_to_use, self.execution_mode, "completed")

            except Exception as e:
                chat_display = self.query_one("#chat_display", ChatDisplay)
                status_bar = self.query_one("#status_bar", StatusBar)

                chat_display.add_error_message(f"Execution failed: {e}")
                status_bar.update_execution_info([], self.execution_mode, "failed")

                self.post_message(AgentError("system", str(e)))

    async def _execute_parallel(self, command: str, agents: List[str]) -> List[Any]:
        """Execute command in parallel across multiple agents."""
        from ...multi_agent.types import Task
        import uuid

        task = Task(
            id=str(uuid.uuid4()),
            prompt=command,
            agent_ids=agents
        )

        return await self.agent_manager.execute_task(agents, task, mode="parallel")

    async def _execute_sequential(self, command: str, agents: List[str]) -> List[Any]:
        """Execute command sequentially across agents."""
        from ...multi_agent.types import Task
        import uuid

        task = Task(
            id=str(uuid.uuid4()),
            prompt=command,
            agent_ids=agents
        )

        return await self.agent_manager.execute_task(agents, task, mode="sequential")

    async def apply_preset(self, preset: str) -> None:
        """Apply an environment preset to all agents."""
        if not self.agent_manager:
            return

        try:
            chat_display = self.query_one("#chat_display", ChatDisplay)
            status_bar = self.query_one("#status_bar", StatusBar)

            chat_display.add_system_message(f"Applying preset: {preset}")

            # Apply preset to all agents
            success_count = 0
            for agent_info in self.active_agents:
                agent_id = agent_info["agent_id"]
                try:
                    success = await self.agent_manager.switch_agent_env(agent_id, preset)
                    if success:
                        success_count += 1
                except Exception as e:
                    chat_display.add_error_message(f"Failed to apply preset to {agent_id}: {e}")

            if success_count > 0:
                self.current_preset = preset
                status_bar.show_success(f"Preset applied to {success_count} agent(s)")
            else:
                status_bar.show_error("Failed to apply preset to any agents")

        except Exception as e:
            status_bar = self.query_one("#status_bar", StatusBar)
            status_bar.show_error(f"Failed to apply preset: {e}")

    async def register_agent(self, agent_id: str, adapter_type: str, config: Dict[str, Any] = None) -> bool:
        """Register a new agent."""
        if not self.agent_manager:
            return False

        try:
            await self.agent_manager.register_agent(agent_id, adapter_type, config or {})
            await self._refresh_agent_list()

            chat_display = self.query_one("#chat_display", ChatDisplay)
            chat_display.add_system_message(f"Agent '{agent_id}' registered successfully", "success")

            return True

        except Exception as e:
            chat_display = self.query_one("#chat_display", ChatDisplay)
            chat_display.add_error_message(f"Failed to register agent '{agent_id}': {e}")
            return False

    async def unregister_agent(self, agent_id: str) -> bool:
        """Unregister an agent."""
        if not self.agent_manager:
            return False

        try:
            await self.agent_manager.terminate_agent(agent_id)
            await self._refresh_agent_list()

            chat_display = self.query_one("#chat_display", ChatDisplay)
            chat_display.add_system_message(f"Agent '{agent_id}' unregistered", "info")

            return True

        except Exception as e:
            chat_display = self.query_one("#chat_display", ChatDisplay)
            chat_display.add_error_message(f"Failed to unregister agent '{agent_id}': {e}")
            return False

    def get_current_agent(self) -> str:
        """Get the current active agent."""
        return self.current_agent

    def get_execution_mode(self) -> str:
        """Get the current execution mode."""
        return self.execution_mode

    def get_current_preset(self) -> str:
        """Get the current preset."""
        return self.current_preset

    def get_active_agents(self) -> List[Dict[str, Any]]:
        """Get list of active agents."""
        return list(self.active_agents)

    def refresh(self, *, repaint: bool = True, layout: bool = False, recompose: bool = False) -> None:
        """Refresh the widget."""
        super().refresh(repaint=repaint, layout=layout, recompose=recompose)

    def _update_status_bar_after_init(self) -> None:
        """Update status bar after initialization is complete."""
        try:
            status_bar = self.query_one("#status_bar", StatusBar)

            # Force update all status bar fields
            if self.current_preset:
                status_bar.set_preset(self.current_preset)

            if self.active_agents:
                status_bar.set_agents(self.active_agents)

            if self.current_agent:
                status_bar.set_current_agent(self.current_agent)

        except NoMatches:
            # Try again after a short delay
            self.set_timer(0.1, self._update_status_bar_after_init)

    async def refresh_state(self) -> None:
        """Refresh the container state."""
        await self._refresh_agent_list()
        self._sync_component_states()