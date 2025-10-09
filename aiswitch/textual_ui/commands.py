"""Custom commands for AISwitch Textual UI."""

from __future__ import annotations

from typing import Any

from functools import partial
from textual.app import ComposeResult
from textual.command import DiscoveryHit, Hit, Hits, Provider
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Select, Static

from .components import MultiAgentContainer
from .events import AgentAddRequested


class AddAgentScreen(ModalScreen[tuple[str, str] | None]):
    """Modal screen for adding a new agent."""

    def __init__(self, preset_options: list[tuple[str, str]] = None, **kwargs):
        super().__init__(**kwargs)
        self.preset_options = preset_options or self._get_default_presets()

    DEFAULT_CSS = """
    AddAgentScreen {
        align: center middle;
    }

    #add_agent_dialog {
        width: 60;
        height: auto;
        max-height: 80%;
        border: thick $background 80%;
        background: $surface;
        padding: 1;
        layout: vertical;
    }

    #add_agent_dialog Label {
        width: 100%;
        text-align: center;
        margin: 1 0;
        height: auto;
    }

    #add_agent_dialog Select {
        width: 100%;
        margin: 1 0;
        height: 5;
    }

    #add_agent_dialog #buttons {
        align: center middle;
        width: 100%;
        height: 4;
        margin-top: 1;
        layout: horizontal;
    }

    #add_agent_dialog Button {
        margin: 0 1;
    }

    #add_agent_dialog Select.error {
        border: solid red;
        background: $error-lighten-3;
    }

    #add_agent_dialog #status_message {
        width: 100%;
        text-align: center;
        margin: 1 0;
        height: 1;
    }

    #add_agent_dialog #status_message.error {
        color: red;
        text-style: bold;
    }
    """

    def compose(self) -> ComposeResult:
        """Compose the add agent dialog."""
        with Vertical(id="add_agent_dialog"):
            yield Label("Add New Agent", id="title")
            yield Label("Select agent type:")
            yield Select(
                options=[
                    ("Claude", "claude"),
                    ("OpenAI GPT", "openai"),
                    ("Generic", "generic"),
                ],
                prompt="Choose agent type",
                id="agent_type_select",
            )
            yield Label("Select preset:")
            yield Select(
                options=self.preset_options,
                prompt="Choose preset",
                id="preset_select",
                allow_blank=False,
            )
            yield Static("", id="status_message")  # For error messages
            with Horizontal(id="buttons"):
                yield Button("Add Agent", variant="primary", id="add_btn")
                yield Button("Cancel", variant="default", id="cancel_btn")

    def _get_default_presets(self) -> list[tuple[str, str]]:
        """Get default preset fallback."""
        return [
            ("ds", "ds"),
            ("88cc", "88cc"),
            ("ar", "ar"),
        ]

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "add_btn":
            agent_type_select = self.query_one("#agent_type_select", Select)
            preset_select = self.query_one("#preset_select", Select)

            if (
                agent_type_select.value is not Select.BLANK
                and preset_select.value is not Select.BLANK
            ):
                agent_type = str(agent_type_select.value)
                preset = str(preset_select.value)
                self.dismiss((agent_type, preset))
            else:
                # Show visual feedback for required fields
                status_msg = self.query_one("#status_message", Static)
                missing_fields = []

                if agent_type_select.value is Select.BLANK:
                    agent_type_select.add_class("error")
                    missing_fields.append("Agent Type")
                else:
                    agent_type_select.remove_class("error")

                if preset_select.value is Select.BLANK:
                    preset_select.add_class("error")
                    missing_fields.append("Preset")
                else:
                    preset_select.remove_class("error")

                if missing_fields:
                    status_msg.update(f"Please select: {', '.join(missing_fields)}")
                    status_msg.add_class("error")
        else:  # cancel
            self.dismiss(None)

    def on_select_changed(self, event) -> None:
        """Clear error state when user makes a selection."""
        if hasattr(event.select, "remove_class"):
            event.select.remove_class("error")

        # Clear status message
        try:
            status_msg = self.query_one("#status_message", Static)
            status_msg.update("")
            status_msg.remove_class("error")
        except Exception:
            pass

    def on_key(self, event) -> None:
        """Handle key press."""
        if event.key == "escape":
            self.dismiss(None)


def show_add_agent_dialog(app: Any) -> None:
    """Show the add agent dialog."""
    # Get preset options before creating the dialog
    preset_options = get_preset_options()

    def handle_result(result: tuple[str, str] | None) -> None:
        if result is not None:
            agent_type, preset = result

            # Generate a unique agent name
            existing_agents = []
            container = None
            try:
                container = app.query_one("#main_container", MultiAgentContainer)
                existing_agents = [
                    a.get("agent_id", "") for a in container.get_active_agents()
                ]
            except Exception:
                pass

            # Generate name like claude1, claude2, etc.
            base_name = agent_type
            counter = 1
            while f"{base_name}{counter}" in existing_agents:
                counter += 1
            agent_name = f"{base_name}{counter}"

            # Post the add agent event directly to container (not app)
            # Events bubble up, so posting to app won't reach the container
            if container:
                container.post_message(AgentAddRequested(agent_name, agent_type, preset))

    # Show the modal dialog with preset options
    app.push_screen(AddAgentScreen(preset_options=preset_options), handle_result)


def get_preset_options() -> list[tuple[str, str]]:
    """Get available preset options."""
    try:
        from aiswitch.preset import PresetManager

        preset_manager = PresetManager()
        presets = preset_manager.list_presets()
        # Return list of (display_name, value) tuples
        return [(name, name) for name, _ in presets]
    except Exception:
        # Fallback
        return [
            ("ds", "ds"),
            ("88cc", "88cc"),
            ("ar", "ar"),
        ]


class AddAgentProvider(Provider):
    """Provider for add agent commands."""

    async def search(self, query: str) -> Hits:
        """Search for add agent commands."""
        matcher = self.matcher(query)

        # Single command that opens the modal dialog
        title = "Add Agent"
        match = matcher.match(title)
        if match > 0:
            yield Hit(
                match,
                matcher.highlight(title),
                partial(show_add_agent_dialog, self.app),
                help="Add a new agent with preset selection",
            )

    async def discover(self) -> Hits:
        """Default add agent suggestion when palette opens."""
        yield DiscoveryHit(
            "Add Agent",
            partial(show_add_agent_dialog, self.app),
            text="Add Agent",
            help="Add a new agent with preset selection",
        )


class AgentManagementProvider(Provider):
    """Provider for agent management commands."""

    async def search(self, query: str) -> Hits:
        """Search for agent management commands."""
        matcher = self.matcher(query)

        # Get current agents
        current_agents = self._get_current_agents()

        commands = []

        # Switch agent commands
        for agent in current_agents:
            agent_id = agent.get("agent_id", "")
            agent_name = agent.get("name", agent_id)
            adapter_type = agent.get("adapter_type", "")

            display_name = (
                f"{agent_name} ({adapter_type})" if adapter_type else agent_name
            )
            commands.append(
                (
                    f"Switch to {display_name}",
                    f"switch-agent-{agent_id}",
                    "switch",
                    agent_id,
                )
            )

        # Remove agent commands
        for agent in current_agents:
            agent_id = agent.get("agent_id", "")
            agent_name = agent.get("name", agent_id)

            commands.append(
                (
                    f"Remove Agent: {agent_name}",
                    f"remove-agent-{agent_id}",
                    "remove",
                    agent_id,
                )
            )

        for title, command_id, action, agent_id in commands:
            match = matcher.match(title)
            if match > 0:
                if action == "switch":
                    callback = partial(switch_agent, self.app, agent_id)
                elif action == "remove":
                    callback = partial(remove_agent, self.app, agent_id)
                else:
                    continue

                yield Hit(
                    match,
                    matcher.highlight(title),
                    callback,
                    help=f"{action.title()} agent {agent_id}",
                )

    def _get_current_agents(self) -> list[dict[str, Any]]:
        """Get list of current agents."""
        try:
            container = self.app.query_one("#main_container", MultiAgentContainer)
            return container.get_active_agents()
        except Exception:
            return []

    async def discover(self) -> Hits:
        """Provide default suggestions for agent management."""
        current_agents = self._get_current_agents()

        for agent in current_agents:
            agent_id = agent.get("agent_id", "")
            agent_name = agent.get("name", agent_id)
            adapter_type = agent.get("adapter_type", "")
            display_name = (
                f"{agent_name} ({adapter_type})" if adapter_type else agent_name
            )

            yield DiscoveryHit(
                f"Switch to {display_name}",
                partial(switch_agent, self.app, agent_id),
                text=f"switch-agent-{agent_id}",
                help=f"Switch to agent {agent_name}",
            )

        for agent in current_agents:
            agent_id = agent.get("agent_id", "")
            agent_name = agent.get("name", agent_id)

            yield DiscoveryHit(
                f"Remove Agent: {agent_name}",
                partial(remove_agent, self.app, agent_id),
                text=f"remove-agent-{agent_id}",
                help=f"Remove agent {agent_name}",
            )


def switch_agent(app: Any, agent_id: str) -> None:
    """Switch to a specific agent."""
    from .events import AgentSelected

    # Post event to container, not app (events bubble up, not down)
    try:
        container = app.query_one("#main_container", MultiAgentContainer)
        container.post_message(AgentSelected(agent_id))
    except Exception:
        pass


async def remove_agent(app: Any, agent_id: str) -> None:
    """Remove a specific agent."""
    try:
        container = app.query_one("#main_container", MultiAgentContainer)
        await container.unregister_agent(agent_id)
    except Exception as e:
        # Show error in chat
        from .events import AgentResponseReceived

        app.post_message(
            AgentResponseReceived(
                "system", f"Failed to remove agent: {e}", {"type": "error"}
            )
        )


class PresetManagementProvider(Provider):
    """Provider for preset management commands."""

    async def search(self, query: str) -> Hits:
        """Search for preset management commands."""
        matcher = self.matcher(query)

        # Get available presets
        available_presets = self._get_available_presets()

        commands = []

        # Switch preset commands
        for preset in available_presets:
            commands.append(
                (
                    f"Switch to Preset: {preset}",
                    f"switch-preset-{preset}",
                    "switch",
                    preset,
                )
            )

        for title, command_id, action, preset in commands:
            match = matcher.match(title)
            if match > 0:
                yield Hit(
                    match,
                    matcher.highlight(title),
                    partial(switch_preset, self.app, preset),
                    help=f"Switch to {preset} preset",
                )

    def _get_available_presets(self) -> list[str]:
        """Get list of available presets."""
        try:
            from ..preset import PresetManager

            preset_manager = PresetManager()
            presets = preset_manager.list_presets()
            # Return list of preset names
            return [name for name, _ in presets]
        except Exception:
            return ["ds", "88cc", "ar"]

    async def discover(self) -> Hits:
        """Show preset actions by default."""
        for preset in self._get_available_presets():
            yield DiscoveryHit(
                f"Switch to Preset: {preset}",
                partial(switch_preset, self.app, preset),
                text=f"switch-preset-{preset}",
                help=f"Activate preset {preset}",
            )


def switch_preset(app: Any, preset: str) -> None:
    """Switch to a specific preset."""
    from .events import PresetChanged

    app.post_message(PresetChanged(preset))
