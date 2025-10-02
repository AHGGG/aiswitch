"""标准输入输出控制器"""

import asyncio
import subprocess
from typing import Optional, AsyncIterator, TYPE_CHECKING
from .types import RawCommandResult

if TYPE_CHECKING:
    from .adapters.base_adapter import BaseCliAdapter


class StdioController:
    """标准输入输出控制器，处理与CLI进程的通信"""

    def __init__(self, process: subprocess.Popen, adapter: "BaseCliAdapter"):
        self.process = process
        self.adapter = adapter
        self.output_buffer = asyncio.Queue()
        self.input_lock = asyncio.Lock()
        self.running = False
        self.output_task: Optional[asyncio.Task] = None
        self.error_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """启动输出监听任务"""
        self.running = True
        self.output_task = asyncio.create_task(self._output_reader())
        self.error_task = asyncio.create_task(self._error_reader())

    async def stop(self) -> None:
        """停止监听任务"""
        self.running = False

        if self.output_task:
            self.output_task.cancel()
            try:
                await self.output_task
            except asyncio.CancelledError:
                pass

        if self.error_task:
            self.error_task.cancel()
            try:
                await self.error_task
            except asyncio.CancelledError:
                pass

    async def _output_reader(self) -> None:
        """后台任务：读取stdout"""
        try:
            while self.running and self.process.poll() is None:
                line = await asyncio.to_thread(self.process.stdout.readline)
                if not line:
                    break
                await self.output_buffer.put(('stdout', line.rstrip('\n\r')))
        except Exception as e:
            await self.output_buffer.put(('error', f"Output reader error: {e}"))

    async def _error_reader(self) -> None:
        """后台任务：读取stderr"""
        try:
            while self.running and self.process.poll() is None:
                line = await asyncio.to_thread(self.process.stderr.readline)
                if not line:
                    break
                await self.output_buffer.put(('stderr', line.rstrip('\n\r')))
        except Exception as e:
            await self.output_buffer.put(('error', f"Error reader error: {e}"))

    async def send_input(self, text: str) -> None:
        """发送输入到CLI进程"""
        async with self.input_lock:
            try:
                self.process.stdin.write(text + '\n')
                self.process.stdin.flush()
            except Exception as e:
                raise RuntimeError(f"Failed to send input: {e}")

    async def execute_command(self, command: str, timeout: float = 30.0) -> RawCommandResult:
        """执行命令并收集完整输出"""
        output_lines = []
        error_lines = []

        # 发送命令
        await self.send_input(command)

        # 收集输出直到检测到命令完成
        start_time = asyncio.get_event_loop().time()

        try:
            while True:
                # 检查超时
                if asyncio.get_event_loop().time() - start_time > timeout:
                    raise asyncio.TimeoutError("Command execution timeout")

                # 获取输出
                try:
                    output_type, line = await asyncio.wait_for(
                        self.output_buffer.get(),
                        timeout=1.0
                    )

                    if output_type == 'stdout':
                        output_lines.append(line)
                    elif output_type == 'stderr':
                        error_lines.append(line)
                    elif output_type == 'error':
                        error_lines.append(line)

                    # 检查是否命令执行完成
                    if await self.adapter.is_command_complete(output_lines, error_lines):
                        break

                except asyncio.TimeoutError:
                    # 检查进程状态
                    if self.process.poll() is not None:
                        break
                    continue

        except Exception as e:
            error_lines.append(f"Execution error: {e}")

        return RawCommandResult(
            stdout=output_lines,
            stderr=error_lines,
            command=command,
            completed=True
        )

    async def get_real_time_output(self) -> AsyncIterator[tuple[str, str]]:
        """获取实时输出流"""
        while self.running:
            try:
                output_type, line = await asyncio.wait_for(
                    self.output_buffer.get(),
                    timeout=1.0
                )
                yield output_type, line
            except asyncio.TimeoutError:
                continue
            except Exception:
                break