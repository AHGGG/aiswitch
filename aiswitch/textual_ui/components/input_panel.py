"""Input panel component for AISwitch."""

from __future__ import annotations

from typing import List, Optional

from textual import on
from textual.containers import Container, Horizontal
from textual.reactive import reactive
from textual.widgets import Button, Input

from ..events import UserMessageSubmitted


class InputPanel(Container):
    """Intelligent input panel with multi-agent support."""

    current_agent = reactive("", layout=False)
    input_mode = reactive("single", layout=False)  # single, multi, command
    suggestions_enabled = reactive(True, layout=False)
    input_history: List[str] = []
    history_index: int = -1

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.input_history = []
        self.history_index = -1

    def compose(self):
        """Compose the input panel UI."""
        with Horizontal():
            yield Input(
                placeholder="Type your message...",
                id="main_input"
            )
            yield Button("Send", id="send_btn", variant="primary")
            yield Button("⚙️", id="settings_btn", variant="default")

    async def on_mount(self) -> None:
        """Focus input when mounted."""
        input_widget = self.query_one("#main_input", Input)
        input_widget.focus()

    def watch_current_agent(self, agent: str) -> None:
        """Update input placeholder when agent changes."""
        placeholders = {
            "claude": "Ask Claude anything...",
            "openai": "Chat with GPT...",
            "generic": "Enter command...",
            "": "Type your message..."
        }

        placeholder = placeholders.get(agent, "Type your message...")
        input_widget = self.query_one("#main_input", Input)
        input_widget.placeholder = placeholder

        # Update input styling based on agent
        input_widget.remove_class("claude", "openai", "generic")
        if agent:
            input_widget.add_class(agent)

    def watch_input_mode(self, mode: str) -> None:
        """Update UI based on input mode."""
        input_widget = self.query_one("#main_input", Input)

        if mode == "command":
            input_widget.placeholder = "Enter command (prefix with /)..."
            input_widget.add_class("command-mode")
        else:
            input_widget.remove_class("command-mode")

    @on(Input.Submitted, "#main_input")
    async def handle_input_submit(self, event: Input.Submitted) -> None:
        """Handle input submission."""
        message = event.value.strip()
        if not message:
            return

        # Handle special commands
        if message.startswith("/"):
            await self._handle_command(message)
            event.input.value = ""
            return

        # Add to history
        self._add_to_history(message)

        # Clear input
        event.input.value = ""

        # Emit message event
        self.post_message(UserMessageSubmitted(message, self.current_agent))

    @on(Button.Pressed, "#send_btn")
    async def handle_send_button(self, event: Button.Pressed) -> None:
        """Handle send button click."""
        input_widget = self.query_one("#main_input", Input)
        message = input_widget.value.strip()

        if message:
            if message.startswith("/"):
                await self._handle_command(message)
            else:
                self._add_to_history(message)
                self.post_message(UserMessageSubmitted(message, self.current_agent))

            input_widget.value = ""

    @on(Button.Pressed, "#settings_btn")
    async def handle_settings_button(self, event: Button.Pressed) -> None:
        """Handle settings button click."""
        # TODO: Implement settings modal
        pass

    @on(Input.Changed, "#main_input")
    def handle_input_change(self, event: Input.Changed) -> None:
        """Handle input text changes for suggestions."""
        if not self.suggestions_enabled:
            return

        text = event.value
        if len(text) > 2:
            # TODO: Implement smart suggestions
            pass

    async def on_key(self, event) -> None:
        """Handle keyboard shortcuts.

        Only handle keys specific to input panel functionality.
        Let app-level navigation keys (ctrl+left/right) propagate to parent.
        """
        input_widget = self.query_one("#main_input", Input)

        # Only handle keys when input is focused
        if not input_widget.has_focus:
            return

        # Navigation keys that InputPanel owns
        if event.key == "up":
            self._navigate_history(-1)
            event.prevent_default()
            event.stop()  # Don't propagate to parent
        elif event.key == "down":
            self._navigate_history(1)
            event.prevent_default()
            event.stop()  # Don't propagate to parent
        elif event.key == "ctrl+l":
            # Only clear if this is the input-specific clear command
            # Let app-level ctrl+l propagate for global clear
            if len(input_widget.value) > 0:
                input_widget.value = ""
                event.prevent_default()
                event.stop()
        elif event.key == "tab":
            # TODO: Implement auto-completion
            event.prevent_default()
            event.stop()
        # DO NOT handle ctrl+left, ctrl+right, or other app-level navigation keys
        # Let them propagate to the App level for agent switching

    def _add_to_history(self, message: str) -> None:
        """Add message to input history."""
        # Avoid duplicates
        if self.input_history and self.input_history[-1] == message:
            return

        self.input_history.append(message)

        # Limit history size
        if len(self.input_history) > 100:
            self.input_history = self.input_history[-100:]

        # Reset history index
        self.history_index = -1

    def _navigate_history(self, direction: int) -> None:
        """Navigate through input history."""
        if not self.input_history:
            return

        input_widget = self.query_one("#main_input", Input)

        # Calculate new index
        new_index = self.history_index + direction

        if new_index < -1:
            new_index = len(self.input_history) - 1
        elif new_index >= len(self.input_history):
            new_index = -1

        self.history_index = new_index

        # Update input value
        if self.history_index == -1:
            input_widget.value = ""
        else:
            input_widget.value = self.input_history[self.history_index]

        # Move cursor to end
        input_widget.cursor_position = len(input_widget.value)

    async def _handle_command(self, command: str) -> None:
        """Handle special commands."""
        cmd = command.lower().strip()

        if cmd == "/clear":
            from ..events import ChatCleared
            self.post_message(ChatCleared())

        elif cmd == "/help":
            self._show_help()

        elif cmd.startswith("/agent "):
            agent_name = cmd[7:].strip()
            if agent_name:
                from ..events import AgentSelected
                self.post_message(AgentSelected(agent_name))

        elif cmd.startswith("/mode "):
            mode = cmd[6:].strip()
            if mode in ["parallel", "sequential"]:
                from ..events import ExecutionModeChanged
                self.post_message(ExecutionModeChanged(mode))

        elif cmd.startswith("/preset "):
            preset = cmd[8:].strip()
            if preset:
                from ..events import PresetChanged
                self.post_message(PresetChanged(preset))

        elif cmd == "/save":
            from ..events import SessionSaveRequested
            self.post_message(SessionSaveRequested())

        elif cmd.startswith("/load "):
            session_name = cmd[6:].strip()
            if session_name:
                from ..events import SessionLoadRequested
                self.post_message(SessionLoadRequested(session_name))

        else:
            # Unknown command, show help
            self._show_help()

    def _show_help(self) -> None:
        """Show available commands."""
        help_text = """Available commands:
/clear              - Clear chat history
/agent <name>       - Switch to agent
/mode <mode>        - Set execution mode (parallel/sequential)
/preset <name>      - Switch to preset
/save               - Save current session
/load <name>        - Load saved session
/help               - Show this help

For agent management, use Ctrl+P to open the command palette."""

        # Send as system message
        from ..events import AgentResponseReceived
        self.post_message(AgentResponseReceived("system", help_text, {"type": "help"}))

    def set_agent(self, agent: str) -> None:
        """Set the current agent."""
        self.current_agent = agent

    def focus_input(self) -> None:
        """Focus the input field."""
        input_widget = self.query_one("#main_input", Input)
        input_widget.focus()

    def clear_input(self) -> None:
        """Clear the input field."""
        input_widget = self.query_one("#main_input", Input)
        input_widget.value = ""

    def set_input_text(self, text: str) -> None:
        """Set input field text."""
        input_widget = self.query_one("#main_input", Input)
        input_widget.value = text
        input_widget.cursor_position = len(text)

    def get_input_text(self) -> str:
        """Get current input text."""
        input_widget = self.query_one("#main_input", Input)
        return input_widget.value

    def enable_suggestions(self, enabled: bool = True) -> None:
        """Enable or disable input suggestions."""
        self.suggestions_enabled = enabled

    def get_history(self) -> List[str]:
        """Get input history."""
        return self.input_history.copy()

    def clear_history(self) -> None:
        """Clear input history."""
        self.input_history.clear()
        self.history_index = -1

    def set_placeholder(self, placeholder: str) -> None:
        """Set input placeholder text."""
        input_widget = self.query_one("#main_input", Input)
        input_widget.placeholder = placeholder