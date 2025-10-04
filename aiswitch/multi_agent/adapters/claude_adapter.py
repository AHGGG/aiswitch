"""Claude adapter for multi-agent system."""

from __future__ import annotations

import os
import time
from typing import Dict, Any

from .base_adapter import BaseAdapter
from ..types import Task, TaskResult

try:
    from claude_agent_sdk import (
        query,
        ClaudeAgentOptions,
        AssistantMessage,
        TextBlock,
        ClaudeSDKError,
        CLINotFoundError,
        CLIConnectionError,
        ProcessError,
        CLIJSONDecodeError,
    )
    CLAUDE_SDK_AVAILABLE = True
except ImportError:
    CLAUDE_SDK_AVAILABLE = False
    # Fallback classes for type checking
    query = None
    ClaudeAgentOptions = object
    AssistantMessage = object
    TextBlock = object
    ClaudeSDKError = Exception
    CLINotFoundError = Exception
    CLIConnectionError = Exception
    ProcessError = Exception
    CLIJSONDecodeError = Exception


class ClaudeAdapter(BaseAdapter):
    """Claude adapter using claude-agent-sdk."""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__("claude")
        self.config = config or {}
        self.env_vars: Dict[str, str] = {}

    async def initialize(self) -> bool:
        """Initialize Claude adapter."""
        if not CLAUDE_SDK_AVAILABLE:
            raise RuntimeError("claude-agent-sdk not available")

        # Check for required environment variables
        # Claude SDK can use either ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN
        required_vars = ["ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"]
        has_auth = any(os.getenv(var) for var in required_vars)

        if not has_auth:
            raise RuntimeError(f"Missing required environment variables: {required_vars}")

        # If using ANTHROPIC_AUTH_TOKEN, also set ANTHROPIC_API_KEY for compatibility
        if os.getenv("ANTHROPIC_AUTH_TOKEN") and not os.getenv("ANTHROPIC_API_KEY"):
            os.environ["ANTHROPIC_API_KEY"] = os.getenv("ANTHROPIC_AUTH_TOKEN")

        self._initialized = True
        return True

    async def execute_task(self, task: Task, timeout: float = 30.0) -> TaskResult:
        """Execute a task using Claude SDK."""
        if not self._initialized:
            raise RuntimeError("Adapter not initialized")

        if not CLAUDE_SDK_AVAILABLE or not query:
            return TaskResult(
                task_id=task.id,
                success=False,
                error="Claude SDK not available"
            )

        start_time = time.time()

        try:
            # Apply environment variables
            original_env = {}
            for key, value in self.env_vars.items():
                original_env[key] = os.environ.get(key)
                os.environ[key] = value

            try:
                # Prepare options
                options = ClaudeAgentOptions()
                if hasattr(task, 'system_prompt') and task.system_prompt:
                    options.system_prompt = task.system_prompt
                if hasattr(task, 'max_tokens') and task.max_tokens:
                    options.max_tokens = task.max_tokens
                if hasattr(task, 'temperature') and task.temperature is not None:
                    options.temperature = task.temperature

                # Execute query
                response_chunks = []
                has_response = False

                async for response_message in query(prompt=task.prompt, options=options):
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
                    result_text = ''.join(response_chunks)
                    return TaskResult(
                        task_id=task.id,
                        success=True,
                        result=result_text,
                        metadata={
                            "adapter": "claude",
                            "chunks": len(response_chunks),
                            "duration": duration
                        },
                        duration=duration
                    )
                else:
                    return TaskResult(
                        task_id=task.id,
                        success=False,
                        error="No response received from Claude",
                        duration=duration
                    )

            finally:
                # Restore original environment variables
                for key, original_value in original_env.items():
                    if original_value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = original_value

        except CLINotFoundError:
            return TaskResult(
                task_id=task.id,
                success=False,
                error="Claude Code CLI not found. Install with: npm install -g @anthropic-ai/claude-code",
                duration=time.time() - start_time
            )
        except CLIConnectionError as exc:
            return TaskResult(
                task_id=task.id,
                success=False,
                error=f"Claude Code connection failed: {exc}",
                duration=time.time() - start_time
            )
        except ProcessError as exc:
            error_msg = f"Claude process failed: {exc}"
            if hasattr(exc, 'exit_code'):
                error_msg = f"Claude process failed (exit code: {exc.exit_code}): {exc}"
            return TaskResult(
                task_id=task.id,
                success=False,
                error=error_msg,
                duration=time.time() - start_time
            )
        except CLIJSONDecodeError as exc:
            return TaskResult(
                task_id=task.id,
                success=False,
                error=f"Response parsing failed: {exc}",
                duration=time.time() - start_time
            )
        except ClaudeSDKError as exc:
            return TaskResult(
                task_id=task.id,
                success=False,
                error=f"Claude SDK error: {exc}",
                duration=time.time() - start_time
            )
        except Exception as exc:
            return TaskResult(
                task_id=task.id,
                success=False,
                error=f"Unexpected error: {exc}",
                duration=time.time() - start_time
            )

    async def switch_environment(self, preset: str, env_vars: Dict[str, str]) -> bool:
        """Switch environment variables."""
        try:
            self.env_vars = env_vars.copy()
            return True
        except Exception:
            return False

    def get_capabilities(self) -> Dict[str, Any]:
        """Get Claude adapter capabilities."""
        return {
            "adapter_type": self.adapter_type,
            "supports_streaming": True,
            "supports_tools": True,
            "supports_files": False,
            "max_tokens": 4000,
            "models": ["claude-3-5-sonnet-latest"],
        }