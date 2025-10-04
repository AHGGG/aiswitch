"""Status bar component for AISwitch."""

from __future__ import annotations

from typing import Optional, Dict, Any

from textual.containers import Container, Horizontal
from textual.reactive import reactive
from textual.widgets import Static


class StatusBar(Container):
    """Intelligent status bar with connection and system info."""

    connection_status = reactive("disconnected", layout=False)
    message_count = reactive(0, layout=False)
    current_preset = reactive("", layout=False)
    execution_mode = reactive("sequential", layout=False)
    current_status = reactive("Ready", layout=False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._temporary_message_timer = None

    def compose(self):
        """Compose the status bar UI."""
        with Horizontal():
            yield Static("●", id="connection_indicator")
            yield Static("Messages: 0", id="message_counter")
            yield Static("Preset: none", id="preset_display")
            yield Static("Mode: sequential", id="mode_display")
            yield Static("Ready", id="status_message")

    def watch_connection_status(self, status: str) -> None:
        """Update connection status indicator."""
        indicator = self.query_one("#connection_indicator", Static)

        # Status colors and styles
        status_config = {
            "connected": {"color": "green", "symbol": "●"},
            "connecting": {"color": "yellow", "symbol": "◐"},
            "disconnected": {"color": "red", "symbol": "○"},
            "error": {"color": "red", "symbol": "✕"},
            "busy": {"color": "blue", "symbol": "◑"},
            "ready": {"color": "green", "symbol": "✓"}
        }

        config = status_config.get(status, {"color": "gray", "symbol": "?"})

        indicator.styles.color = config["color"]
        indicator.update(config["symbol"])

        # Update status message if not showing temporary message
        if not self._temporary_message_timer:
            status_messages = {
                "connected": "Connected",
                "connecting": "Connecting...",
                "disconnected": "Disconnected",
                "error": "Connection Error",
                "busy": "Processing...",
                "ready": "Ready"
            }
            self.current_status = status_messages.get(status, "Unknown")

    def watch_message_count(self, count: int) -> None:
        """Update message counter."""
        counter = self.query_one("#message_counter", Static)
        counter.update(f"Messages: {count}")

    def watch_current_preset(self, preset: str) -> None:
        """Update current preset display."""
        preset_display = self.query_one("#preset_display", Static)
        display_text = f"Preset: {preset}" if preset else "Preset: none"
        preset_display.update(display_text)

        # Add CSS class for preset styling
        preset_display.remove_class("default", "claude", "openai", "custom")
        if preset:
            # Map common presets to CSS classes
            preset_classes = {
                "default": "default",
                "claude": "claude",
                "openai": "openai",
                "gpt": "openai"
            }
            css_class = preset_classes.get(preset.lower(), "custom")
            preset_display.add_class(css_class)

    def watch_execution_mode(self, mode: str) -> None:
        """Update execution mode display."""
        mode_display = self.query_one("#mode_display", Static)
        mode_display.update(f"Mode: {mode}")

        # Add CSS class for mode styling
        mode_display.remove_class("sequential", "parallel")
        mode_display.add_class(mode)

    def watch_current_status(self, status: str) -> None:
        """Update status message."""
        status_widget = self.query_one("#status_message", Static)
        status_widget.update(status)

    def show_temporary_message(self, message: str, duration: float = 3.0) -> None:
        """Show a temporary status message."""
        status_widget = self.query_one("#status_message", Static)

        # Store original message
        original_message = self.current_status

        # Show temporary message
        status_widget.update(message)
        status_widget.add_class("temporary")

        # Clear any existing timer
        if self._temporary_message_timer:
            self._temporary_message_timer.cancel()

        # Set timer to restore original message
        def restore_message():
            status_widget.update(original_message)
            status_widget.remove_class("temporary")
            self._temporary_message_timer = None

        self._temporary_message_timer = self.set_timer(duration, restore_message)

    def update_agent_info(self, agent: str, info: Dict[str, Any]) -> None:
        """Update status bar with agent-specific information."""
        # Update connection status based on agent status
        agent_status = info.get("status", "unknown")
        if agent_status in ["online", "ready", "idle"]:
            self.connection_status = "connected"
        elif agent_status == "busy":
            self.connection_status = "busy"
        elif agent_status in ["error", "failed"]:
            self.connection_status = "error"
        else:
            self.connection_status = "disconnected"

        # Show agent-specific temporary message
        if info.get("last_response_time"):
            response_time = info["last_response_time"]
            self.show_temporary_message(f"Response: {response_time:.2f}s")

    def update_execution_info(self, agents: list[str], mode: str, status: str) -> None:
        """Update status bar during command execution."""
        self.execution_mode = mode

        if status == "started":
            agent_list = ", ".join(agents)
            self.show_temporary_message(f"Executing on {agent_list}...")
            self.connection_status = "busy"
        elif status == "completed":
            self.show_temporary_message("Execution completed", 2.0)
            self.connection_status = "connected"
        elif status == "failed":
            self.show_temporary_message("Execution failed", 3.0)
            self.connection_status = "error"

    def update_preset_info(self, preset: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Update preset information."""
        self.current_preset = preset

        if details:
            # Show temporary message with preset details
            if details.get("env_count"):
                env_count = details["env_count"]
                self.show_temporary_message(f"Loaded {env_count} environment variables")

    def show_error(self, error: str, duration: float = 5.0) -> None:
        """Show an error message."""
        self.connection_status = "error"
        self.show_temporary_message(f"Error: {error}", duration)

    def show_success(self, message: str, duration: float = 2.0) -> None:
        """Show a success message."""
        self.show_temporary_message(f"✓ {message}", duration)

    def show_warning(self, message: str, duration: float = 3.0) -> None:
        """Show a warning message."""
        self.show_temporary_message(f"⚠ {message}", duration)

    def show_info(self, message: str, duration: float = 2.0) -> None:
        """Show an info message."""
        self.show_temporary_message(f"ℹ {message}", duration)

    def update_performance_info(self, info: Dict[str, Any]) -> None:
        """Update performance-related information."""
        # Update message count if provided
        if "message_count" in info:
            self.message_count = info["message_count"]

        # Show performance metrics temporarily
        if "cpu_usage" in info or "memory_usage" in info:
            metrics = []
            if "cpu_usage" in info:
                metrics.append(f"CPU: {info['cpu_usage']:.1f}%")
            if "memory_usage" in info:
                metrics.append(f"Memory: {info['memory_usage']:.1f}MB")

            if metrics:
                self.show_temporary_message(" | ".join(metrics), 2.0)

    def set_connection_status(self, status: str) -> None:
        """Set connection status."""
        self.connection_status = status

    def set_message_count(self, count: int) -> None:
        """Set message count."""
        self.message_count = count

    def increment_message_count(self) -> None:
        """Increment message count by 1."""
        self.message_count += 1

    def set_preset(self, preset: str) -> None:
        """Set current preset."""
        self.current_preset = preset

    def set_execution_mode(self, mode: str) -> None:
        """Set execution mode."""
        self.execution_mode = mode

    def set_status(self, status: str) -> None:
        """Set status message."""
        self.current_status = status

    def get_status_info(self) -> Dict[str, Any]:
        """Get current status information."""
        return {
            "connection_status": self.connection_status,
            "message_count": self.message_count,
            "current_preset": self.current_preset,
            "execution_mode": self.execution_mode,
            "current_status": self.current_status
        }

    def reset_status(self) -> None:
        """Reset status bar to default state."""
        self.connection_status = "disconnected"
        self.message_count = 0
        self.current_preset = ""
        self.execution_mode = "sequential"
        self.current_status = "Ready"

        # Clear any temporary message
        if self._temporary_message_timer:
            self._temporary_message_timer.cancel()
            self._temporary_message_timer = None