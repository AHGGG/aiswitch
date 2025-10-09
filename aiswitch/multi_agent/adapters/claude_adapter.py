"""Claude adapter for multi-agent system."""

from __future__ import annotations

import time
from typing import Dict, Any

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    TextBlock,
    ClaudeSDKError,
    CLINotFoundError,
    CLIConnectionError,
    ProcessError,
    CLIJSONDecodeError,
)

from aiswitch import PresetManager
from .base_adapter import BaseAdapter, DEFAULT_PRESET
from ..types import Task, TaskResult


class ClaudeAdapter(BaseAdapter):
    """Claude adapter using claude-agent-sdk."""

    def change_preset(self, preset):
        preset_manager = PresetManager()
        preset_config, _, _ = preset_manager.use_preset(preset, apply_to_env=False)
        self.env_vars = preset_config.variables or {}

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__("claude")
        self.config = config or {}
        self._current_options: ClaudeAgentOptions | None = None  # ClaudeAgentOptions, Track current options for reinitialization
        self.env_vars: Dict[str, str] = {}
        self.client: ClaudeSDKClient | None = None  # ClaudeSDKClient instance for continuous conversation

    async def initialize(self) -> bool:
        """Initialize Claude adapter with persistent ClaudeSDKClient."""
        preset = self.config.get("preset", DEFAULT_PRESET)
        self.change_preset(preset)

        options = ClaudeAgentOptions(env=self.env_vars.copy())
        self._current_options = options

        # Create persistent ClaudeSDKClient for continuous conversation
        try:
            self.client = ClaudeSDKClient(options=options)
            # Enter the async context manager
            await self.client.connect()
        except Exception as e:
            raise RuntimeError(f"Failed to create ClaudeSDKClient: {e}")

        self._initialized = True
        return True

    async def execute_task(self, task: Task, timeout: float = 30.0) -> TaskResult:
        """Execute a task using persistent ClaudeSDKClient for continuous conversation."""
        if not self._initialized or not self.client:
            raise RuntimeError("Adapter not initialized or client not available")

        start_time = time.time()

        try:
            # Send message to Claude (maintains conversation context)
            # Note: ClaudeSDKClient uses query() method, not send_message()
            await self.client.query(task.prompt)

            # Receive response (streaming)
            response_chunks = []
            has_response = False

            async for response_message in self.client.receive_response():
                has_response = True

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

            duration = time.time() - start_time

            if has_response and response_chunks:
                result_text = "".join(response_chunks)
                return TaskResult(
                    task_id=task.id,
                    success=True,
                    result=result_text,
                    metadata={
                        "adapter": "claude",
                        "chunks": len(response_chunks),
                        "duration": duration,
                    },
                    duration=duration,
                )
            else:
                return TaskResult(
                    task_id=task.id,
                    success=False,
                    error="No response received from Claude",
                    duration=duration,
                )
        except CLINotFoundError:
            return TaskResult(
                task_id=task.id,
                success=False,
                error="Claude Code CLI not found. Install with: npm install -g @anthropic-ai/claude-code",
                duration=time.time() - start_time,
            )
        except CLIConnectionError as exc:
            return TaskResult(
                task_id=task.id,
                success=False,
                error=f"Claude Code connection failed: {exc}",
                duration=time.time() - start_time,
            )
        except ProcessError as exc:
            error_msg = f"Claude process failed: {exc}"
            if hasattr(exc, "exit_code"):
                error_msg = f"Claude process failed (exit code: {exc.exit_code}): {exc}"
            return TaskResult(
                task_id=task.id,
                success=False,
                error=error_msg,
                duration=time.time() - start_time,
            )
        except CLIJSONDecodeError as exc:
            return TaskResult(
                task_id=task.id,
                success=False,
                error=f"Response parsing failed: {exc}",
                duration=time.time() - start_time,
            )
        except ClaudeSDKError as exc:
            return TaskResult(
                task_id=task.id,
                success=False,
                error=f"Claude SDK error: {exc}",
                duration=time.time() - start_time,
            )
        except Exception as exc:
            return TaskResult(
                task_id=task.id,
                success=False,
                error=f"Unexpected error: {exc}",
                duration=time.time() - start_time,
            )

    async def close(self) -> None:
        """Clean up ClaudeSDKClient resources."""
        if self.client:
            try:
                # Exit the async context manager
                await self.client.disconnect()
            except Exception:
                # Ignore errors during cleanup
                pass
            finally:
                self.client = None

        # Call parent close
        await super().close()
