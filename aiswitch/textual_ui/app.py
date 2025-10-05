"""Main AISwitch Textual application."""

from __future__ import annotations

import os
from pathlib import Path
from time import sleep
from typing import Dict, List, Any, Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.reactive import reactive
from textual.widgets import Header, Footer

from .components.multi_agent_container import MultiAgentContainer
from .commands import AddAgentProvider, AgentManagementProvider, PresetManagementProvider
from .events import (
    UserMessageSubmitted,
    AgentSelected,
    AgentResponseReceived,
    AgentStatusChanged,
    ExecutionModeChanged,
    PresetChanged,
    ChatCleared,
    SessionSaveRequested,
    SessionLoadRequested,
    CommandExecutionStarted,
    CommandExecutionCompleted,
    AgentError,
    AgentAddRequested
)


class AISwitch(App):
    """AISwitch main Textual application with multi-agent support."""

    CSS_PATH = Path(__file__).parent / "styles.tcss"

    TITLE = "AISwitch - Multi-Agent Terminal Interface"
    SUB_TITLE = "Seamlessly switch between AI agents"

    COMMANDS = {
        AddAgentProvider,
        AgentManagementProvider,
        PresetManagementProvider,
    }

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", priority=True),
        Binding("ctrl+l", "clear_chat", "Clear Chat"),
        Binding("ctrl+s", "save_session", "Save Session"),
        Binding("ctrl+o", "load_session", "Load Session"),
        Binding("f1", "show_help", "Help"),
        Binding("f2", "show_settings", "Settings"),
        # Agent switching keys with priority=True to work even when Input is focused
        Binding("ctrl+right", "next_agent", "Next Agent", priority=True),
        Binding("ctrl+left", "prev_agent", "Previous Agent", priority=True),
        Binding("ctrl+1", "set_sequential", "Sequential Mode"),
        Binding("ctrl+2", "set_parallel", "Parallel Mode"),
        Binding("ctrl+r", "refresh_agents", "Refresh Agents"),
    ]

    # Reactive state
    current_preset = reactive("", layout=False)
    available_agents = reactive([], layout=False)
    execution_mode = reactive("sequential", layout=False)
    app_status = reactive("initializing", layout=False)

    def __init__(self, preset: str = "default", **kwargs):
        super().__init__(**kwargs)
        self.current_preset = preset
        self.session_data = {}

    def compose(self) -> ComposeResult:
        """Compose the main application UI."""
        yield Header()

        # Create container with preset already set
        container = MultiAgentContainer(id="main_container")
        container.current_preset = self.current_preset
        yield container

        yield Footer()

    async def on_mount(self) -> None:
        """Initialize the application when mounted."""
        try:
            self.app_status = "loading"

            # Update title with preset info
            if self.current_preset:
                self.sub_title = f"Using preset: {self.current_preset}"

            # Container is already initialized with preset in compose()
            # Just update the title
            container = self.query_one("#main_container", MultiAgentContainer)

            self.app_status = "ready"

        except Exception as e:
            self.app_status = "error"
            import traceback
            error_info = traceback.format_exc()
            print(f"❌ Error during app initialization: {e}")
            print("Full traceback:")
            print(error_info)
            self.exit(1)

    # Event handlers for custom events
    async def on_user_message_submitted(self, event: UserMessageSubmitted) -> None:
        """Handle user message submission."""
        # The MultiAgentContainer handles this internally
        pass

    async def on_agent_selected(self, event: AgentSelected) -> None:
        """Handle agent selection."""
        container = self.query_one("#main_container", MultiAgentContainer)
        # Update app state
        self.available_agents = container.get_active_agents()

    async def on_agent_response_received(self, event: AgentResponseReceived) -> None:
        """Handle agent response."""
        # Update app statistics or logging
        pass

    async def on_agent_status_changed(self, event: AgentStatusChanged) -> None:
        """Handle agent status changes."""
        # Update global agent status tracking
        pass

    async def on_execution_mode_changed(self, event: ExecutionModeChanged) -> None:
        """Handle execution mode changes."""
        self.execution_mode = event.mode
        self.sub_title = f"Mode: {event.mode} | Preset: {self.current_preset}"

    async def on_preset_changed(self, event: PresetChanged) -> None:
        """Handle preset changes."""
        self.current_preset = event.preset
        self.sub_title = f"Mode: {self.execution_mode} | Preset: {event.preset}"

    async def on_chat_cleared(self, event: ChatCleared) -> None:
        """Handle chat clear events."""
        # Reset any global state if needed
        pass

    async def on_session_save_requested(self, event: SessionSaveRequested) -> None:
        """Handle session save requests."""
        # TODO: Implement session saving
        await self._save_session(event.session_name)

    async def on_session_load_requested(self, event: SessionLoadRequested) -> None:
        """Handle session load requests."""
        # TODO: Implement session loading
        await self._load_session(event.session_name)

    async def on_command_execution_started(self, event: CommandExecutionStarted) -> None:
        """Handle command execution start."""
        self.title = f"AISwitch - Executing on {', '.join(event.agents)}"

    async def on_command_execution_completed(self, event: CommandExecutionCompleted) -> None:
        """Handle command execution completion."""
        self.title = "AISwitch - Multi-Agent Terminal Interface"

    async def on_agent_error(self, event: AgentError) -> None:
        """Handle agent errors."""
        # Log error or show notification
        pass

    async def on_agent_add_requested(self, event: AgentAddRequested) -> None:
        """Handle agent add requests."""
        # The MultiAgentContainer handles the actual logic
        # Here we can update app-level state if needed
        pass

    # Action handlers for key bindings
    def action_clear_chat(self) -> None:
        """Clear chat history."""
        self.post_message(ChatCleared())

    async def action_save_session(self) -> None:
        """Save current session."""
        self.post_message(SessionSaveRequested())

    async def action_load_session(self) -> None:
        """Load a session."""
        # TODO: Show session selection dialog
        pass

    async def action_show_help(self) -> None:
        """Show help screen."""
        await self._show_help()

    async def action_show_settings(self) -> None:
        """Show settings screen."""
        # TODO: Implement settings screen
        pass

    def action_next_agent(self) -> None:
        """Switch to next available agent."""
        container = self.query_one("#main_container", MultiAgentContainer)
        agents = container.get_active_agents()
        current = container.get_current_agent()

        if not agents:
            return

        # Find current agent index
        current_idx = -1
        for i, agent in enumerate(agents):
            if agent.get("agent_id") == current:
                current_idx = i
                break

        # Move to next agent
        next_idx = (current_idx + 1) % len(agents)
        next_agent = agents[next_idx]["agent_id"]

        self.post_message(AgentSelected(next_agent))

    def action_prev_agent(self) -> None:
        """Switch to previous available agent."""
        container = self.query_one("#main_container", MultiAgentContainer)
        agents = container.get_active_agents()
        current = container.get_current_agent()

        if not agents:
            return

        # Find current agent index
        current_idx = -1
        for i, agent in enumerate(agents):
            if agent.get("agent_id") == current:
                current_idx = i
                break

        # Move to previous agent
        prev_idx = (current_idx - 1) % len(agents)
        prev_agent = agents[prev_idx]["agent_id"]

        self.post_message(AgentSelected(prev_agent))

    def action_set_sequential(self) -> None:
        """Set execution mode to sequential."""
        self.post_message(ExecutionModeChanged("sequential"))

    def action_set_parallel(self) -> None:
        """Set execution mode to parallel."""
        self.post_message(ExecutionModeChanged("parallel"))

    async def action_refresh_agents(self) -> None:
        """Refresh available agents."""
        container = self.query_one("#main_container", MultiAgentContainer)
        await container.refresh_state()


    # Helper methods
    async def _save_session(self, session_name: Optional[str] = None) -> None:
        """Save current session to file."""
        try:
            container = self.query_one("#main_container", MultiAgentContainer)
            chat_display = container.query_one("#chat_display")

            # Generate session name if not provided
            if not session_name:
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                session_name = f"session_{timestamp}"

            # Collect session data
            session_data = {
                "name": session_name,
                "preset": self.current_preset,
                "execution_mode": self.execution_mode,
                "chat_history": chat_display.export_chat_history(),
                "agents": container.get_active_agents(),
                "current_agent": container.get_current_agent(),
            }

            # Save to file (TODO: implement proper session storage)
            session_file = os.path.expanduser(f"~/.aiswitch/sessions/{session_name}.json")
            os.makedirs(os.path.dirname(session_file), exist_ok=True)

            import json
            with open(session_file, 'w') as f:
                json.dump(session_data, f, indent=2)

            # Show success message
            status_bar = container.query_one("#status_bar")
            status_bar.show_success(f"Session saved as '{session_name}'")

        except Exception as e:
            # Show error message
            container = self.query_one("#main_container", MultiAgentContainer)
            status_bar = container.query_one("#status_bar")
            status_bar.show_error(f"Failed to save session: {e}")

    async def _load_session(self, session_name: str) -> None:
        """Load session from file."""
        try:
            session_file = os.path.expanduser(f"~/.aiswitch/sessions/{session_name}.json")

            if not os.path.exists(session_file):
                raise FileNotFoundError(f"Session '{session_name}' not found")

            import json
            with open(session_file, 'r') as f:
                session_data = json.load(f)

            # Restore session state
            self.current_preset = session_data.get("preset", "")
            self.execution_mode = session_data.get("execution_mode", "sequential")

            # Apply to container
            container = self.query_one("#main_container", MultiAgentContainer)
            if session_data.get("preset"):
                await container.apply_preset(session_data["preset"])

            if session_data.get("execution_mode"):
                self.post_message(ExecutionModeChanged(session_data["execution_mode"]))

            # TODO: Restore chat history and agent selection

            # Show success message
            status_bar = container.query_one("#status_bar")
            status_bar.show_success(f"Session '{session_name}' loaded")

        except Exception as e:
            # Show error message
            container = self.query_one("#main_container", MultiAgentContainer)
            status_bar = container.query_one("#status_bar")
            status_bar.show_error(f"Failed to load session: {e}")

    async def _show_help(self) -> None:
        """Show help information."""
        help_text = """AISwitch Multi-Agent Interface Help

Key Bindings:
  Ctrl+Q        - Quit application
  Ctrl+P        - Open command palette (agent management)
  Ctrl+L        - Clear chat history
  Ctrl+S        - Save current session
  Ctrl+O        - Load saved session
  F1            - Show this help
  F2            - Show settings
  Ctrl+N        - Switch to next agent
  Ctrl+Shift+P  - Switch to previous agent
  Ctrl+1        - Set sequential execution mode
  Ctrl+2        - Set parallel execution mode
  Ctrl+R        - Refresh agent list

Commands:
  /clear        - Clear chat history
  /agent <name> - Switch to specific agent
  /mode <mode>  - Set execution mode (parallel/sequential)
  /preset <name>- Switch to preset
  /save         - Save current session
  /load <name>  - Load saved session
  /help         - Show command help

Command Palette (Ctrl+P):
  Add Agent     - Add new agents with preset selection
  Switch Agent  - Switch between available agents
  Remove Agent  - Remove agents
  Switch Preset - Change environment presets

Execution Modes:
  Sequential    - Execute commands one agent at a time
  Parallel      - Execute commands on all agents simultaneously

For more information, visit: https://github.com/your-repo/aiswitch"""

        # Send help as system message
        self.post_message(AgentResponseReceived("system", help_text, {"type": "help"}))

    def get_current_preset(self) -> str:
        """Get current preset."""
        return self.current_preset

    def get_execution_mode(self) -> str:
        """Get current execution mode."""
        return self.execution_mode

    def get_app_status(self) -> str:
        """Get current app status."""
        return self.app_status

    async def switch_preset(self, preset: str) -> None:
        """Switch to a different preset."""
        self.post_message(PresetChanged(preset))

    async def add_agent(self, agent_id: str, adapter_type: str, config: Dict[str, Any] = None) -> bool:
        """Add a new agent to the application."""
        container = self.query_one("#main_container", MultiAgentContainer)
        return await container.register_agent(agent_id, adapter_type, config or {})

    async def remove_agent(self, agent_id: str) -> bool:
        """Remove an agent from the application."""
        container = self.query_one("#main_container", MultiAgentContainer)
        return await container.unregister_agent(agent_id)


def run_aiswitch_app(preset: str = "default", **kwargs) -> None:
    """Run the AISwitch Textual application."""
    print(f"Starting AISwitch app with preset: {preset}")
    try:
        app = AISwitch(preset=preset, **kwargs)
        print("App instance created, starting run...")
        app.run()
        print("App run completed")
    except Exception as e:
        import traceback
        print(f"Error in run_aiswitch_app: {e}")
        traceback.print_exc()
        raise