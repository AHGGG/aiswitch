"""Chat display component for AISwitch."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Dict, Any, Optional

from rich.syntax import Syntax
from rich.text import Text
from textual.reactive import reactive
from textual.widgets import RichLog


class ChatDisplay(RichLog):
    """Intelligent chat display component with multi-agent support."""

    current_agent = reactive("", layout=False)
    message_count = reactive(0, layout=False)
    auto_scroll = reactive(True, layout=False)

    def __init__(self, **kwargs):
        super().__init__(highlight=True, markup=True, **kwargs)
        self.agents_colors = {
            "claude": "blue",
            "openai": "green",
            "generic": "yellow",
            "default": "white",
        }
        self.agents_icons = {
            "claude": "🧠",
            "openai": "🤖",
            "generic": "💻",
            "default": "🔮",
        }
        # Store message history for each agent separately
        self._agent_histories: Dict[str, list[Any]] = {}

    def watch_current_agent(self, agent: str) -> None:
        """Update display style when agent changes."""
        color = self.agents_colors.get(agent, "white")
        self.styles.border = ("solid", color)

        # Add CSS class for agent-specific styling
        self.remove_class(*self.agents_colors.keys())
        if agent:
            self.add_class(agent)

        # Reload history for the new agent
        self._reload_agent_history(agent)

    def add_user_message(
        self, message: str, timestamp: Optional[datetime] = None
    ) -> None:
        """Add a user message to the chat display."""
        if timestamp is None:
            timestamp = datetime.now()

        time_str = timestamp.strftime("%H:%M:%S")

        text = Text()
        text.append(f"[{time_str}] ", style="dim")
        text.append("👤 You: ", style="bold cyan")
        text.append(message)

        self.write(text)
        self.message_count += 1

        # Store in current agent history
        msg_data = {
            "type": "user",
            "message": message,
            "timestamp": timestamp,
            "text": text,
        }
        if self.current_agent:
            if self.current_agent not in self._agent_histories:
                self._agent_histories[self.current_agent] = []
            self._agent_histories[self.current_agent].append(msg_data)

        if self.auto_scroll:
            self.scroll_end()

    def add_agent_message(
        self,
        agent: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Add an agent message to the chat display."""
        if timestamp is None:
            timestamp = datetime.now()

        metadata = metadata or {}
        time_str = timestamp.strftime("%H:%M:%S")
        color = self.agents_colors.get(agent, "white")
        icon = self.agents_icons.get(agent, "🔮")

        text = Text()
        text.append(f"[{time_str}] ", style="dim")
        text.append(f"{icon} {agent.title()}: ", style=f"bold {color}")

        # Check if message contains code and should be syntax highlighted
        has_code = self._should_highlight_code(message, metadata)
        if has_code:
            language = metadata.get("language", "python")
            self.write(text)
            self._write_code_block(message, language)
        else:
            text.append(message)
            self.write(text)

        # Add metadata info if present
        if metadata and metadata.get("tokens"):
            self._add_metadata_info(metadata)

        self.message_count += 1

        # Store in agent-specific history
        msg_data = {
            "type": "agent",
            "agent": agent,
            "message": message,
            "metadata": metadata,
            "timestamp": timestamp,
            "text": text,
            "has_code": has_code,
            "language": metadata.get("language", "python") if has_code else None,
        }
        if agent not in self._agent_histories:
            self._agent_histories[agent] = []
        self._agent_histories[agent].append(msg_data)

        if self.auto_scroll:
            self.scroll_end()

    def add_error_message(
        self,
        error: str,
        agent: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Add an error message to the chat display."""
        if timestamp is None:
            timestamp = datetime.now()

        time_str = timestamp.strftime("%H:%M:%S")

        text = Text()
        text.append(f"[{time_str}] ", style="dim")
        text.append("❌ Error: ", style="bold red")

        if agent:
            text.append(f"[{agent}] ", style="red")

        text.append(error, style="red")
        self.write(text)

        # Store error messages in agent-specific history
        msg_data = {
            "type": "error",
            "error": error,
            "agent": agent,
            "timestamp": timestamp,
            "text": text,
        }
        if agent and agent in self._agent_histories:
            self._agent_histories[agent].append(msg_data)

        if self.auto_scroll:
            self.scroll_end()

    def add_system_message(
        self, message: str, level: str = "info", timestamp: Optional[datetime] = None
    ) -> None:
        """Add a system message to the chat display."""
        if timestamp is None:
            timestamp = datetime.now()

        time_str = timestamp.strftime("%H:%M:%S")

        icons = {"info": "ℹ️", "warning": "⚠️", "success": "✅", "debug": "🔍"}
        styles = {
            "info": "blue",
            "warning": "yellow",
            "success": "green",
            "debug": "magenta",
        }

        text = Text()
        text.append(f"[{time_str}] ", style="dim")
        text.append(f"{icons.get(level, 'ℹ️')} ", style=styles.get(level, "blue"))
        text.append(message, style=styles.get(level, "blue"))

        self.write(text)

        # Store system messages in current agent history
        if self.current_agent:
            msg_data = {
                "type": "system",
                "message": message,
                "level": level,
                "timestamp": timestamp,
                "text": text,
            }
            if self.current_agent not in self._agent_histories:
                self._agent_histories[self.current_agent] = []
            self._agent_histories[self.current_agent].append(msg_data)

        if self.auto_scroll:
            self.scroll_end()

    def add_execution_status(
        self,
        message: str,
        agents: list[str],
        mode: str,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Add execution status message."""
        if timestamp is None:
            timestamp = datetime.now()

        time_str = timestamp.strftime("%H:%M:%S")

        text = Text()
        text.append(f"[{time_str}] ", style="dim")
        text.append("🚀 ", style="green")
        text.append(f"Executing {mode}: ", style="bold green")
        text.append(f"{', '.join(agents)} - ", style="green")
        text.append(message, style="green")

        self.write(text)

        if self.auto_scroll:
            self.scroll_end()

    def switch_agent(self, agent: str) -> None:
        """Switch to a different agent."""
        old_agent = self.current_agent
        self.current_agent = agent

        if old_agent != agent:
            self.add_system_message(f"Switched to {agent}", "info")

    def _reload_agent_history(self, agent: str) -> None:
        """Reload chat history for a specific agent."""
        # Clear current display
        self.clear()

        # Get history for this agent (or empty list)
        agent_history = self._agent_histories.get(agent, [])

        # Replay all messages for this agent
        for msg_data in agent_history:
            msg_type = msg_data["type"]

            if msg_type == "user":
                # Recreate user message
                text = msg_data["text"]
                self.write(text)
            elif msg_type == "agent":
                # Recreate agent message
                text = msg_data["text"]
                if msg_data.get("has_code"):
                    self.write(text)
                    self._write_code_block(msg_data["message"], msg_data["language"])
                else:
                    self.write(text)

                # Re-add metadata if present
                metadata = msg_data.get("metadata", {})
                if metadata and metadata.get("tokens"):
                    self._add_metadata_info(metadata)
            elif msg_type == "system":
                # Recreate system message
                text = msg_data["text"]
                self.write(text)
            elif msg_type == "error":
                # Recreate error message
                text = msg_data["text"]
                self.write(text)

        # Update message count
        self.message_count = len(agent_history)

        # Scroll to end
        if self.auto_scroll:
            self.scroll_end()

    def clear_history(self) -> None:
        """Clear chat history."""
        self.clear()
        self.message_count = 0
        # Clear all stored histories
        self._agent_histories.clear()
        self.add_system_message("Chat history cleared", "info")

    def _should_highlight_code(self, message: str, metadata: Dict[str, Any]) -> bool:
        """Determine if message should be syntax highlighted."""
        # Check metadata first
        if metadata.get("language"):
            return True

        # Check for code block markers
        if "```" in message:
            return True

        # Check for common code patterns
        code_patterns = [
            r"def\s+\w+\s*\(",  # Python function
            r"class\s+\w+\s*:",  # Python class
            r"import\s+\w+",  # Python import
            r"function\s+\w+\s*\(",  # JavaScript function
            r"const\s+\w+\s*=",  # JavaScript const
            r"let\s+\w+\s*=",  # JavaScript let
            r"var\s+\w+\s*=",  # JavaScript var
        ]

        for pattern in code_patterns:
            if re.search(pattern, message):
                return True

        return False

    def _write_code_block(self, message: str, language: str) -> None:
        """Write a syntax-highlighted code block."""
        try:
            # Remove code block markers if present
            if message.startswith("```"):
                lines = message.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                message = "\n".join(lines)

            syntax = Syntax(message, language, theme="monokai", line_numbers=True)
            self.write(syntax)
        except Exception:
            # Fallback to plain text if syntax highlighting fails
            self.write(Text(message, style="white on black"))

    def _add_metadata_info(self, metadata: Dict[str, Any]) -> None:
        """Add metadata information as a subtle info line."""
        info_parts = []

        if metadata.get("tokens"):
            info_parts.append(f"tokens: {metadata['tokens']}")

        if metadata.get("model"):
            info_parts.append(f"model: {metadata['model']}")

        if metadata.get("duration"):
            info_parts.append(f"time: {metadata['duration']:.2f}s")

        if info_parts:
            info_text = Text()
            info_text.append("    ", style="dim")
            info_text.append("📊 ", style="dim blue")
            info_text.append(" | ".join(info_parts), style="dim")
            self.write(info_text)

    def set_auto_scroll(self, enabled: bool) -> None:
        """Enable or disable auto-scrolling."""
        self.auto_scroll = enabled

    def search_messages(self, query: str) -> list[int]:
        """Search for messages containing the query. Returns line numbers."""
        # This is a simplified implementation
        # In a real implementation, you'd want to search through stored messages
        lines = []
        for i, line in enumerate(str(self.renderable).split("\n")):
            if query.lower() in line.lower():
                lines.append(i)
        return lines

    def export_chat_history(self) -> str:
        """Export chat history as plain text."""
        return str(self.renderable)

    def get_message_count(self) -> int:
        """Get the current message count."""
        return self.message_count

    def get_current_agent(self) -> str:
        """Get the current agent."""
        return self.current_agent
