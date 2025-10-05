"""Agent selector component for AISwitch."""

from __future__ import annotations

from typing import Dict, List, Any, Optional

from textual.containers import Container, Horizontal
from textual.reactive import reactive
from textual.widgets import Static


class AgentSelector(Container):
    """Agent selector component with status indicators."""

    available_agents = reactive([], layout=False)
    current_agent = reactive("", layout=False)
    agent_statuses = reactive({}, layout=False)  # {agent_id: status}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def compose(self):
        """Compose the agent selector UI."""
        with Horizontal():
            yield Static("Agent:", id="label")
            yield Static("No agent selected", id="agent_display")
            yield Static("●", id="status_indicator")
            yield Static("Ready", id="status_text")
            yield Static("[Tab] Next | [F3] Menu", id="shortcuts")

    def watch_available_agents(self, agents: List[Dict[str, Any]]) -> None:
        """Update available agents list."""
        # Set first agent as default if none selected
        if agents and not self.current_agent:
            first_agent = agents[0]
            agent_id = first_agent.get("agent_id", first_agent.get("id", ""))
            if agent_id:
                self.current_agent = agent_id

    def watch_current_agent(self, agent: str) -> None:
        """Update current selected agent."""
        agent_display = self.query_one("#agent_display", Static)

        # Update display text
        if agent:
            # Find agent info for display
            agent_info = None
            for a in self.available_agents:
                if a.get("agent_id", a.get("id", "")) == agent:
                    agent_info = a
                    break

            if agent_info:
                agent_name = agent_info.get("name", agent)
                adapter_type = agent_info.get("adapter_type", "")
                if adapter_type:
                    display_text = f"{agent_name} ({adapter_type})"
                else:
                    display_text = agent_name
            else:
                display_text = agent

            agent_display.update(display_text)
        else:
            agent_display.update("No agent selected")

        # Update status indicator
        self.update_status_indicator(agent)

        # Update CSS classes
        self._update_agent_classes(agent)

    def watch_agent_statuses(self, statuses: Dict[str, str]) -> None:
        """Update agent statuses."""
        self.update_status_indicator(self.current_agent)

    def update_status_indicator(self, agent: str) -> None:
        """Update status indicator for current agent."""
        status = self.agent_statuses.get(agent, "unknown")

        indicator = self.query_one("#status_indicator", Static)
        status_text = self.query_one("#status_text", Static)

        # Status colors and descriptions
        status_config = {
            "online": {"color": "green", "text": "Online"},
            "ready": {"color": "green", "text": "Ready"},
            "busy": {"color": "yellow", "text": "Busy"},
            "error": {"color": "red", "text": "Error"},
            "offline": {"color": "gray", "text": "Offline"},
            "connecting": {"color": "blue", "text": "Connecting"},
            "unknown": {"color": "gray", "text": "Unknown"},
        }

        config = status_config.get(status, status_config["unknown"])

        # Update indicator color
        indicator.styles.color = config["color"]

        # Update status text
        status_text.update(config["text"])

        # Add CSS class for status
        indicator.remove_class(*status_config.keys())
        indicator.add_class(status)

    def _update_agent_classes(self, agent: str) -> None:
        """Update CSS classes based on current agent."""
        # Remove all agent classes
        agent_classes = ["claude", "openai", "generic", "default"]
        self.remove_class(*agent_classes)

        # Add current agent class
        if agent:
            # Map agent names to CSS classes
            agent_class_map = {
                "claude": "claude",
                "openai": "openai",
                "gpt": "openai",
                "generic": "generic",
            }

            css_class = agent_class_map.get(agent.lower(), "default")
            self.add_class(css_class)

    def set_agents(self, agents: List[Dict[str, Any]]) -> None:
        """Set available agents."""
        self.available_agents = agents

    def set_current_agent(self, agent: str) -> None:
        """Set current agent."""
        self.current_agent = agent

    def update_agent_status(self, agent: str, status: str) -> None:
        """Update status for a specific agent."""
        statuses = dict(self.agent_statuses)
        statuses[agent] = status
        self.agent_statuses = statuses

    def get_current_agent(self) -> str:
        """Get current selected agent."""
        return self.current_agent

    def get_agent_status(self, agent: str) -> str:
        """Get status for a specific agent."""
        return self.agent_statuses.get(agent, "unknown")

    def get_available_agents(self) -> List[Dict[str, Any]]:
        """Get list of available agents."""
        return list(self.available_agents)

    def add_agent(self, agent: Dict[str, Any]) -> None:
        """Add a new agent to the list."""
        agents = list(self.available_agents)
        agents.append(agent)
        self.available_agents = agents

    def remove_agent(self, agent_id: str) -> None:
        """Remove an agent from the list."""
        agents = [
            a
            for a in self.available_agents
            if a.get("agent_id", a.get("id", "")) != agent_id
        ]
        self.available_agents = agents

        # If removed agent was current, select first available
        if self.current_agent == agent_id and agents:
            self.current_agent = agents[0].get("agent_id", agents[0].get("id", ""))

    def enable_agent(self, agent_id: str) -> None:
        """Enable an agent."""
        # Update agent status to indicate enabled state
        self.update_agent_status(agent_id, "online")

    def disable_agent(self, agent_id: str) -> None:
        """Disable an agent."""
        # Update status to indicate disabled state
        self.update_agent_status(agent_id, "offline")

        # If disabled agent is current, switch to first available
        if self.current_agent == agent_id:
            available = [
                a
                for a in self.available_agents
                if a.get("agent_id", a.get("id", "")) != agent_id
            ]
            if available:
                self.current_agent = available[0].get(
                    "agent_id", available[0].get("id", "")
                )

    def refresh_agents(self) -> None:
        """Refresh the agent list display."""
        self.watch_available_agents(self.available_agents)

    def get_agent_info(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific agent."""
        for agent in self.available_agents:
            if agent.get("agent_id", agent.get("id", "")) == agent_id:
                return agent
        return None

    def set_agent_metadata(self, agent_id: str, metadata: Dict[str, Any]) -> None:
        """Update metadata for a specific agent."""
        for i, agent in enumerate(self.available_agents):
            if agent.get("agent_id", agent.get("id", "")) == agent_id:
                # Create updated agent info
                updated_agent = dict(agent)
                updated_agent.update(metadata)

                # Update the list
                agents = list(self.available_agents)
                agents[i] = updated_agent
                self.available_agents = agents
                break
