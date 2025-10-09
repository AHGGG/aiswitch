"""Claude adapter for multi-agent system."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Dict, List, Optional

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    TextBlock,
    SystemMessage,
    ResultMessage,
    UserMessage,
    ToolUseBlock,
    ToolResultBlock,
    ThinkingBlock,
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

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__("claude")
        self.config = config or {}
        self._current_options: ClaudeAgentOptions | None = None  # ClaudeAgentOptions, Track current options for reinitialization
        self.env_vars: Dict[str, str] = {}
        self.client: ClaudeSDKClient | None = None  # ClaudeSDKClient instance for continuous conversation
        self._session_id: str | None = None

    async def initialize(self) -> bool:
        """Initialize Claude adapter with persistent ClaudeSDKClient."""
        preset = self.config.get("preset", DEFAULT_PRESET)
        await self.change_preset(preset)
        return True

    async def change_preset(self, preset: str) -> None:
        """Load preset variables and rebuild the Claude client."""
        preset_manager = PresetManager()
        preset_config, _, _ = preset_manager.use_preset(preset, apply_to_env=False)
        self.env_vars = preset_config.variables or {}
        self.config["preset"] = preset

        await self._recreate_client()
        self._initialized = True

    async def _recreate_client(self) -> None:
        """Tear down and rebuild the ClaudeSDKClient with current env vars."""
        await self._shutdown_client()

        options = ClaudeAgentOptions(
            env=self.env_vars.copy(),
            resume=self._session_id,
            continue_conversation=bool(self._session_id),
        )
        self._current_options = options

        try:
            self.client = ClaudeSDKClient(options=options)
            await self.client.connect()
        except Exception as exc:
            self.client = None
            self._initialized = False
            raise RuntimeError(f"Failed to create ClaudeSDKClient: {exc}")

    async def _shutdown_client(self) -> None:
        """Safely disconnect the existing Claude client if present."""
        if not self.client:
            return

        try:
            await self._safe_interrupt()
        except Exception:
            # Interrupt best-effort; continue with disconnect
            pass

        try:
            await self.client.disconnect()
        except Exception:
            pass
        finally:
            self.client = None

    async def execute_task(self, task: Task, timeout: float = 60.0) -> TaskResult:
        """Execute a task using persistent ClaudeSDKClient for continuous conversation."""
        if not self._initialized or not self.client:
            raise RuntimeError("Adapter not initialized or client not available")

        start_time = time.time()

        try:
            session_id = self._session_id or "default"
            await self.client.query(task.prompt, session_id=session_id)

            # Receive response (streaming)
            response_chunks: List[str] = []
            has_response = False
            metadata: Dict[str, Any] = {"adapter": "claude"}
            result_message: Optional[ResultMessage] = None

            async def consume_messages() -> None:
                nonlocal has_response, result_message
                async for response_message in self.client.receive_response():
                    has_response = True

                    if isinstance(response_message, AssistantMessage):
                        response_chunks.extend(self._extract_assistant_chunks(response_message))
                    elif isinstance(response_message, SystemMessage):
                        system_meta = self._extract_system_metadata(response_message)
                        if system_meta:
                            metadata.update(system_meta)
                    elif isinstance(response_message, ResultMessage):
                        result_message = response_message
                        metadata.update(self._extract_result_metadata(response_message))
                        break
                    elif isinstance(response_message, UserMessage):
                        rendered = self._render_user_message(response_message)
                        if rendered:
                            response_chunks.append(rendered)
                    else:
                        rendered = self._render_generic_message(response_message)
                        if rendered:
                            response_chunks.append(rendered)

            await consume_messages()

            duration = time.time() - start_time
            metadata.update({"chunks": len(response_chunks), "duration": duration})

            result_text = "\n\n".join(chunk for chunk in response_chunks if chunk.strip()).strip()
            result_subtype = metadata.get("result_subtype")
            success_allowed = result_subtype in (None, "success")

            if has_response and success_allowed and (result_text or result_subtype == "success"):
                return TaskResult(
                    task_id=task.id,
                    success=True,
                    result=result_text,
                    metadata=metadata,
                    duration=duration,
                )
            return TaskResult(
                task_id=task.id,
                success=False,
                error="No response received from Claude",
                metadata=metadata,
                duration=duration,
            )
        except asyncio.TimeoutError:
            await self._safe_interrupt()
            return TaskResult(
                task_id=task.id,
                success=False,
                error=f"Timed out after {timeout} seconds waiting for Claude response",
                duration=time.time() - start_time,
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

    async def _safe_interrupt(self) -> None:
        if self.client is None:
            return
        try:
            await self.client.interrupt()
        except Exception:
            pass

    def _extract_assistant_chunks(self, message: AssistantMessage) -> List[str]:
        chunks: List[str] = []
        for block in message.content:
            if isinstance(block, TextBlock):
                text = block.text.strip()
                if text:
                    chunks.append(text)
            elif isinstance(block, ToolUseBlock):
                chunks.append(f"[Tool request] {block.name} -> {self._format_payload(block.input)}")
            elif isinstance(block, ToolResultBlock):
                status = "error" if block.is_error else "ok"
                payload = self._format_payload(block.content)
                chunks.append(f"[Tool result:{status}] {payload}")
            elif isinstance(block, ThinkingBlock):
                # Thinking blocks typically contain internal reasoning; omit from user-facing output.
                continue
            else:
                chunks.append(f"[{type(block).__name__}] {block}")
        return chunks

    def _extract_system_metadata(self, message: SystemMessage) -> Dict[str, Any]:
        metadata: Dict[str, Any] = {}
        if message.subtype == "init":
            session_id = message.data.get("session_id")
            if session_id:
                self._session_id = session_id
                metadata["session_id"] = session_id
        if message.subtype == "compact_boundary":
            metadata["compaction"] = {
                "pre_tokens": message.data.get("compact_metadata", {}).get("pre_tokens"),
                "trigger": message.data.get("compact_metadata", {}).get("trigger"),
            }
        if message.subtype == "mcp_server_update":
            servers = message.data.get("mcp_servers")
            if servers:
                metadata["mcp_servers"] = servers
        return metadata

    def _extract_result_metadata(self, message: ResultMessage) -> Dict[str, Any]:
        metadata: Dict[str, Any] = {
            "result_subtype": message.subtype,
            "num_turns": message.num_turns,
        }
        if message.session_id:
            self._session_id = message.session_id
            metadata["session_id"] = message.session_id
        if message.total_cost_usd is not None:
            metadata["total_cost_usd"] = message.total_cost_usd
        if message.usage is not None:
            metadata["usage"] = message.usage
        if message.result:
            metadata.setdefault("result_summary", message.result)
        return metadata

    def _render_user_message(self, message: UserMessage) -> Optional[str]:
        content = message.content
        if isinstance(content, str):
            text = content.strip()
            return f"[User echo] {text}" if text else None
        return None

    def _render_generic_message(self, message: Any) -> Optional[str]:
        text = str(message).strip()
        return f"[{type(message).__name__}] {text}" if text else None

    @staticmethod
    def _format_payload(payload: Any) -> str:
        if isinstance(payload, str):
            return payload
        if payload is None:
            return "None"
        try:
            return json.dumps(payload, ensure_ascii=True)
        except (TypeError, ValueError):
            return repr(payload)
