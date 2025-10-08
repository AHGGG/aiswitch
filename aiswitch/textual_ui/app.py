"""Main AISwitch Textual application."""

from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.reactive import reactive
from textual.widgets import Header, Footer

from aiswitch.textual_ui.commands import (
    AddAgentProvider,
    AgentManagementProvider,
    PresetManagementProvider,
)
from aiswitch.textual_ui.components.multi_agent_container import MultiAgentContainer
from aiswitch.textual_ui.events import (
    AgentSelected,
    ExecutionModeChanged,
    PresetChanged,
    CommandExecutionStarted,
    CommandExecutionCompleted,
)


class AISwitch(App):
    """AISwitch main Textual application with multi-agent support."""

    CSS_PATH = Path(__file__).parent / "styles.tcss"

    TITLE = "AISwitch - Multi-Agent Terminal Interface"

    COMMANDS = {
        AddAgentProvider,
        AgentManagementProvider,
        PresetManagementProvider,
    }

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", priority=True),
        # Agent switching keys with priority=True to work even when Input is focused
        Binding("ctrl+right", "next_agent", "Next Agent", priority=True),
        Binding("ctrl+left", "prev_agent", "Previous Agent", priority=True),
    ]

    # Reactive state
    current_preset = reactive("", layout=False)
    execution_mode = reactive("sequential", layout=False)

    def __init__(self, preset: str = "ds", **kwargs):
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
            # Container is already initialized with preset in compose()
            self.query_one("#main_container", MultiAgentContainer)

        except Exception as e:
            import traceback

            error_info = traceback.format_exc()
            print(f"❌ Error during app initialization: {e}")
            print("Full traceback:")
            print(error_info)
            self.exit(1)

    # Event handlers for custom events

    async def on_execution_mode_changed(self, event: ExecutionModeChanged) -> None:
        """Handle execution mode changes."""
        self.execution_mode = event.mode

    async def on_preset_changed(self, event: PresetChanged) -> None:
        """Handle preset changes."""
        self.current_preset = event.preset

    async def on_command_execution_started(
        self, event: CommandExecutionStarted
    ) -> None:
        """Handle command execution start."""
        self.title = f"AISwitch - Executing on {', '.join(event.agents)}"

    async def on_command_execution_completed(
        self, event: CommandExecutionCompleted
    ) -> None:
        """Handle command execution completion."""
        self.title = "AISwitch - Multi-Agent Terminal Interface"

    # Action handlers for key bindings
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

        # Post to container, not app
        container.post_message(AgentSelected(next_agent))

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

        # Post to container, not app
        container.post_message(AgentSelected(prev_agent))


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


if __name__ == "__main__":
    app = AISwitch()
    app.run()
