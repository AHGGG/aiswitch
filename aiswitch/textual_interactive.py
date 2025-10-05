"""Textual interactive experiences for AISwitch agents.

This module provides the new multi-agent interface and a legacy Claude SDK interface
for backward compatibility.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List

from rich.text import Text
from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.widgets import Footer, Header, Input, RichLog

try:  # Optional dependency for Claude SDK mode
    from claude_agent_sdk import (  # type: ignore
        query,
        ClaudeSDKError,
        CLINotFoundError,
        CLIConnectionError,
        ProcessError,
        CLIJSONDecodeError,
        AssistantMessage,
        TextBlock
    )
    claude_agent_sdk_available = True
except Exception:  # pragma: no cover - claude-agent-sdk may be missing in minimal installs
    query = None  # type: ignore
    ClaudeSDKError = Exception  # type: ignore
    CLINotFoundError = Exception  # type: ignore
    CLIConnectionError = Exception  # type: ignore
    ProcessError = Exception  # type: ignore
    CLIJSONDecodeError = Exception  # type: ignore
    AssistantMessage = object  # type: ignore
    TextBlock = object  # type: ignore
    claude_agent_sdk_available = False


@dataclass
class ClaudeAgentConfig:
    """Configuration for Claude Agent SDK."""
    # claude-agent-sdk uses environment variables and doesn't need explicit config
    # We keep this for consistency with the existing interface
    pass


DEFAULT_MODEL = "claude-3-5-sonnet-latest"
DEFAULT_MAX_OUTPUT_TOKENS = 1024


class BaseChatApp(App[None]):
    """Shared Textual layout and helpers for chat style apps."""

    CSS = """
    #chat_log {
        background: $surface;
        color: $text;
        height: 1fr;
        scrollbar-size: 1 1;
        border: solid $primary;
    }

    #input_container {
        height: 3;
        dock: bottom;
        background: $surface;
    }

    #user_input {
        height: 1;
        background: $surface;
        color: $text;
        border: solid $accent;
    }

    .prompt {
        color: $accent;
        text-style: bold;
    }

    .response {
        color: $text;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "退出"),
        Binding("ctrl+l", "clear", "清空对话"),
    ]

    def __init__(self) -> None:
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Header()
        yield RichLog(id="chat_log", highlight=True, markup=True)
        with Container(id="input_container"):
            yield Input(placeholder="输入消息...", id="user_input")
        yield Footer()

    def on_mount(self) -> None:  # pragma: no cover - UI binding
        chat_log = self.chat_log
        chat_log.write(Text("🤖 AI Agent 已启动，输入消息开始对话...", style="bold green"))
        self.input_widget.focus()

    @property
    def chat_log(self) -> RichLog:
        return self.query_one("#chat_log", RichLog)

    @property
    def input_widget(self) -> Input:
        return self.query_one("#user_input", Input)

    def log_info(self, message: str, style: str = "dim") -> None:
        self.chat_log.write(Text(message, style=style))

    def log_user(self, message: str) -> None:
        self.chat_log.write(Text(f"👤 {message}", style="prompt"))

    def log_assistant(self, message: str) -> None:
        self.chat_log.write(Text(f"🤖 {message}", style="response"))

    def log_error(self, message: str) -> None:
        self.chat_log.write(Text(message, style="bold red"))

    @on(Input.Submitted, "#user_input")
    async def _handle_submit(self, event: Input.Submitted) -> None:
        message = event.value.strip()
        if not message:
            return

        event.input.value = ""
        self.log_info(f"📝 提交消息: '{message}'", style="bold yellow")
        self.log_user(message)

        try:
            await self.handle_user_message(message)
        except asyncio.CancelledError:  # pragma: no cover - defensive
            raise
        except Exception as exc:  # pragma: no cover - defensive logging
            self.log_error(f"❌ 处理消息时出错: {exc}")

    async def handle_user_message(self, message: str) -> None:
        """具体实现由子类提供。"""
        raise NotImplementedError

    def action_clear(self) -> None:  # pragma: no cover - UI binding
        self.chat_log.clear()
        self.log_info("🧹 对话历史已清空", style="bold yellow")

    def action_quit(self) -> None:  # pragma: no cover - UI binding
        self.exit()


class ClaudeSDKApp(BaseChatApp):
    """Interactive session powered by the Claude Agent SDK."""

    def __init__(self, env_vars: Dict[str, str]):
        super().__init__()
        self.env_vars = env_vars
        self.config = ClaudeAgentConfig()
        self._apply_env_vars()

    def _apply_env_vars(self) -> None:
        """Apply environment variables to the current process."""
        for key, value in self.env_vars.items():
            os.environ[key] = value

    def on_mount(self) -> None:  # pragma: no cover - UI binding
        super().on_mount()
        if not claude_agent_sdk_available:
            self.log_error("❌ 未安装 claude-agent-sdk 包，无法使用 Claude SDK 模式。")
            self.input_widget.disabled = True
            return

        # Check for required environment variables
        # According to claude-agent-sdk docs, it primarily uses ANTHROPIC_API_KEY
        required_env_vars = [
            "ANTHROPIC_API_KEY"
        ]

        has_credentials = any(
            self.env_vars.get(var) or os.environ.get(var)
            for var in required_env_vars
        )

        if not has_credentials:
            self.log_error("❌ 未检测到 Claude API 凭证，无法调用 Claude SDK。")
            self.input_widget.disabled = True
            return

        self.log_info("✅ 已连接 Claude Agent SDK", style="green")

    async def handle_user_message(self, message: str) -> None:
        if not claude_agent_sdk_available or not query:
            self.log_error("❌ Claude Agent SDK 尚未就绪")
            return

        self.log_info("⌛ Claude 正在生成回复...", style="dim")

        try:
            # Use claude-agent-sdk's query function with streaming
            response_chunks = []
            has_response = False

            async for response_message in query(prompt=message):
                has_response = True

                # Handle according to official claude-agent-sdk documentation
                if isinstance(response_message, AssistantMessage):
                    # Extract text from AssistantMessage content blocks
                    for block in response_message.content:
                        if isinstance(block, TextBlock):
                            chunk = block.text
                            if chunk and chunk.strip():
                                response_chunks.append(chunk)
                        else:
                            # Handle other block types (tool use, etc.)
                            chunk = str(block)
                            if chunk and chunk.strip():
                                response_chunks.append(f"[Block: {chunk}]")
                elif isinstance(response_message, str):
                    # Handle string responses
                    chunk = response_message
                    if chunk and chunk.strip():
                        response_chunks.append(chunk)
                else:
                    # Handle any other message types
                    chunk = str(response_message)
                    if chunk and chunk.strip():
                        response_chunks.append(f"[Message: {chunk}]")

            # Display the complete response
            if has_response and response_chunks:
                full_response = ''.join(response_chunks)
                self.log_assistant(full_response)
            elif not has_response:
                self.log_info("⚠️ Claude 返回了空响应", style="yellow")

        except CLINotFoundError:
            self.log_error("❌ 未找到 Claude Code CLI，请确保已安装 @anthropic-ai/claude-code")
            self.log_error("安装命令: npm install -g @anthropic-ai/claude-code")
            return
        except CLIConnectionError as exc:
            self.log_error(f"❌ Claude Code 连接失败: {exc}")
            return
        except ProcessError as exc:
            if hasattr(exc, 'exit_code'):
                self.log_error(f"❌ Claude 进程失败 (退出代码: {exc.exit_code}): {exc}")
            else:
                self.log_error(f"❌ Claude 进程失败: {exc}")
            return
        except CLIJSONDecodeError as exc:
            self.log_error(f"❌ 响应解析失败: {exc}")
            return
        except ClaudeSDKError as exc:
            self.log_error(f"❌ Claude SDK 错误: {exc}")
            return
        except Exception as exc:  # pragma: no cover - defensive logging
            import traceback
            error_details = traceback.format_exc()
            self.log_error(f"❌ Claude 请求失败: {exc}")
            self.log_error(f"详细错误信息: {error_details}")
            return

    def action_quit(self) -> None:  # pragma: no cover - UI binding
        # claude-agent-sdk doesn't require explicit cleanup
        super().action_quit()


def _has_claude_credentials(env_vars: Dict[str, str]) -> bool:
    """Check if Claude Agent SDK credentials are available."""
    # claude-agent-sdk primarily uses ANTHROPIC_API_KEY
    key = "ANTHROPIC_API_KEY"
    return bool(env_vars.get(key) or os.environ.get(key))


def run_textual_interactive(
    agent_name: str,
    agent_command: List[str],
    env_vars: Dict[str, str],
    multi_agent: bool = False,
    preset: str = "default"
) -> None:
    """Entry point for launching the Textual chat UI.

    Args:
        agent_name: Name of the agent to run
        agent_command: Command to run the agent (for legacy mode, not used)
        env_vars: Environment variables
        multi_agent: Whether to use the new multi-agent interface
        preset: Environment preset to use
    """

    # Use new multi-agent interface if requested
    if multi_agent:
        from .textual_ui.app import run_aiswitch_app
        return run_aiswitch_app(preset=preset)

    # Legacy single-agent interface using Claude SDK
    if agent_name.lower() == "claude" and claude_agent_sdk_available and _has_claude_credentials(env_vars):
        app: BaseChatApp = ClaudeSDKApp(env_vars)
        app.run()
    else:
        # If Claude SDK is not available, use multi-agent interface instead
        from .textual_ui.app import run_aiswitch_app
        run_aiswitch_app(preset=preset)


def run_multi_agent_interface(preset: str = "default") -> None:
    """Run the new multi-agent Textual interface.

    This is a convenience function that directly launches the new interface.
    """
    from .textual_ui.app import run_aiswitch_app
    run_aiswitch_app(preset=preset)
