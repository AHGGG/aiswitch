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

from .base_adapter import BaseAdapter
from ..types import Task, TaskResult


class ClaudeAdapter(BaseAdapter):
    """Claude adapter using claude-agent-sdk."""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__("claude")
        self.config = config or {}
        self._current_options: ClaudeAgentOptions | None = None  # ClaudeAgentOptions, Track current options for reinitialization
        self.env_vars: Dict[str, str] = {}
        self.client: ClaudeSDKClient | None = None  # ClaudeSDKClient instance for continuous conversation

    async def initialize(self) -> bool:
        """Initialize Claude adapter with persistent ClaudeSDKClient."""
        options = ClaudeAgentOptions(env=self.env_vars.copy())
        self._current_options = options

        # Create persistent ClaudeSDKClient for continuous conversation
        try:
            self.client = ClaudeSDKClient(options=options)
            # Enter the async context manager
            await self.client.__aenter__()
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

    async def set_env(self, preset: str, env_vars: Dict[str, str]) -> bool:
        """Switch environment variables by recreating the client with new environment."""
        try:
            # Update environment variables
            self.env_vars = env_vars.copy()

            # # Apply to process environment for SDK compatibility
            # for key, value in self.env_vars.items():
            #     os.environ[key] = value
            #
            # # Handle ANTHROPIC_AUTH_TOKEN -> ANTHROPIC_API_KEY mapping
            # if "ANTHROPIC_AUTH_TOKEN" in self.env_vars and "ANTHROPIC_API_KEY" not in self.env_vars:
            #     os.environ["ANTHROPIC_API_KEY"] = self.env_vars["ANTHROPIC_AUTH_TOKEN"]

            # Close existing client if any
            if self.client:
                try:
                    await self.client.__aexit__(None, None, None)
                except Exception:
                    pass

            # Create new client with updated environment
            new_options = ClaudeAgentOptions(env=self.env_vars.copy())
            self._current_options = new_options
            self.client = ClaudeSDKClient(options=new_options)
            await self.client.__aenter__()

            return True
        except Exception as e:
            print(f"Failed to set env: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def close(self) -> None:
        """Clean up ClaudeSDKClient resources."""
        if self.client:
            try:
                # Exit the async context manager
                await self.client.__aexit__(None, None, None)
            except Exception:
                # Ignore errors during cleanup
                pass
            finally:
                self.client = None

        # Call parent close
        await super().close()
