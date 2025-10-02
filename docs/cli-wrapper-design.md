# aiswitch CLI代理包装器设计方案

## 概述

本文档详细描述了aiswitch CLI代理包装器的完整设计方案，目标是实现一个能够管理和协调多个AI CLI工具的系统，支持模拟用户输入、捕获CLI输出、并提供统一的接口来控制多个CLI工具。

## 核心目标

1. **进程管理**: 启动、管理和终止外部CLI工具进程
2. **输入模拟**: 模拟用户输入，向CLI工具发送命令和数据
3. **输出捕获**: 实时捕获并处理CLI工具的输出
4. **统一接口**: 提供统一的API来控制不同的CLI工具
5. **并发支持**: 支持多个CLI工具同时运行和协调
6. **会话管理**: 管理长期运行的CLI会话状态

## 技术架构

### 核心组件图

```
┌─────────────────────────────────────────────────────────┐
│                CLIAgentManager                          │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────┐ │
│  │ CLIAgentWrapper │  │ CLIAgentWrapper │  │    ...   │ │
│  │   (claude)      │  │   (codex)       │  │          │ │
│  └─────────────────┘  └─────────────────┘  └──────────┘ │
└─────────────────────────────────────────────────────────┘
           │                     │                     │
┌─────────────────┐    ┌─────────────────┐    ┌──────────────┐
│CLIProcessSession│    │CLIProcessSession│    │      ...     │
│   + stdio       │    │   + stdio       │    │              │
│   + adapter     │    │   + adapter     │    │              │
└─────────────────┘    └─────────────────┘    └──────────────┘
           │                     │                     │
┌─────────────────┐    ┌─────────────────┐    ┌──────────────┐
│   subprocess    │    │   subprocess    │    │      ...     │
│  claude-cli     │    │  codex-cli      │    │              │
└─────────────────┘    └─────────────────┘    └──────────────┘
```

### 文件结构

```
aiswitch/
├── cli_wrapper/
│   ├── __init__.py
│   ├── agent_wrapper.py          # CLIAgentWrapper主类
│   ├── process_session.py        # CLI进程会话管理
│   ├── stdio_controller.py       # 标准输入输出控制
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── base_adapter.py       # 适配器基类
│   │   ├── claude_adapter.py     # Claude CLI适配器
│   │   ├── generic_adapter.py    # 通用CLI适配器
│   │   └── codex_adapter.py      # Codex CLI适配器
│   ├── manager.py                # CLIAgentManager
│   └── types.py                  # 类型定义
└── cli.py                        # 扩展现有CLI命令
```

## 核心类设计

### 1. CLIAgentWrapper (agent_wrapper.py)

主要的CLI代理包装器类，类似于参考JS代码中的ClaudeAcpAgent。

```python
from typing import Dict, Optional, Any, List
import asyncio
import uuid
from datetime import datetime

class CLIAgentWrapper:
    """CLI代理包装器，管理单个CLI工具的多个会话"""

    def __init__(self, agent_id: str, adapter: BaseCliAdapter):
        self.agent_id = agent_id
        self.adapter = adapter
        self.sessions: Dict[str, CLIProcessSession] = {}
        self.tool_use_cache: Dict[str, Any] = {}
        self.file_content_cache: Dict[str, str] = {}
        self.background_processes: Dict[str, BackgroundProcess] = {}
        self.capabilities: Optional[Dict[str, Any]] = None

    async def initialize(self) -> Dict[str, Any]:
        """初始化代理，返回能力信息"""
        self.capabilities = await self.adapter.get_capabilities()
        return {
            "agent_id": self.agent_id,
            "capabilities": self.capabilities,
            "status": "initialized",
            "initialized_at": datetime.now().isoformat()
        }

    async def new_session(self, preset: str, cwd: str = None, env: Dict[str, str] = None) -> str:
        """创建新会话"""
        session_id = str(uuid.uuid4())

        session = CLIProcessSession(
            session_id=session_id,
            agent_id=self.agent_id,
            adapter=self.adapter,
            preset=preset,
            cwd=cwd,
            env=env or {}
        )

        await session.start()
        self.sessions[session_id] = session

        return session_id

    async def execute_command(self, session_id: str, command: str, timeout: float = 30.0) -> CommandResult:
        """在指定会话中执行命令"""
        if session_id not in self.sessions:
            raise ValueError(f"Session {session_id} not found")

        session = self.sessions[session_id]
        return await session.execute_command(command, timeout)

    async def terminate_session(self, session_id: str) -> None:
        """终止指定会话"""
        if session_id in self.sessions:
            await self.sessions[session_id].terminate()
            del self.sessions[session_id]

    async def get_session_status(self, session_id: str) -> Dict[str, Any]:
        """获取会话状态"""
        if session_id not in self.sessions:
            return {"error": "Session not found"}

        session = self.sessions[session_id]
        return await session.get_status()

    async def list_sessions(self) -> List[Dict[str, Any]]:
        """列出所有会话"""
        sessions_info = []
        for session_id, session in self.sessions.items():
            status = await session.get_status()
            sessions_info.append({
                "session_id": session_id,
                "status": status,
                "created_at": session.created_at.isoformat()
            })
        return sessions_info
```

### 2. CLIProcessSession (process_session.py)

管理单个CLI进程会话的生命周期。

```python
import subprocess
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any
from .stdio_controller import StdioController
from .types import CommandResult, SessionStatus

class CLIProcessSession:
    """CLI进程会话，管理单个CLI工具实例"""

    def __init__(self, session_id: str, agent_id: str, adapter, preset: str, cwd: str = None, env: Dict[str, str] = None):
        self.session_id = session_id
        self.agent_id = agent_id
        self.adapter = adapter
        self.preset = preset
        self.cwd = cwd
        self.env = env or {}
        self.created_at = datetime.now()

        # 进程相关
        self.process: Optional[subprocess.Popen] = None
        self.stdio_controller: Optional[StdioController] = None
        self.status = SessionStatus.STOPPED
        self.cancelled = False

        # 状态跟踪
        self.command_count = 0
        self.last_activity = datetime.now()

    async def start(self) -> None:
        """启动CLI进程"""
        try:
            # 构建命令和环境
            command = await self.adapter.build_command(self.preset)
            full_env = {**os.environ, **self.env}

            # 启动进程
            self.process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=0,
                cwd=self.cwd,
                env=full_env
            )

            # 创建stdio控制器
            self.stdio_controller = StdioController(self.process, self.adapter)
            await self.stdio_controller.start()

            # 等待初始化完成
            await self.adapter.wait_for_ready(self.stdio_controller)

            self.status = SessionStatus.RUNNING
            self.last_activity = datetime.now()

        except Exception as e:
            self.status = SessionStatus.ERROR
            raise RuntimeError(f"Failed to start session: {e}")

    async def execute_command(self, command: str, timeout: float = 30.0) -> CommandResult:
        """执行命令并返回结果"""
        if self.status != SessionStatus.RUNNING:
            raise RuntimeError(f"Session not running, status: {self.status}")

        self.command_count += 1
        self.last_activity = datetime.now()

        try:
            # 格式化命令
            formatted_command = await self.adapter.format_command(command)

            # 发送命令并等待响应
            result = await self.stdio_controller.execute_command(formatted_command, timeout)

            # 解析结果
            parsed_result = await self.adapter.parse_result(result)

            return CommandResult(
                session_id=self.session_id,
                agent_id=self.agent_id,
                command=command,
                result=parsed_result,
                timestamp=datetime.now(),
                success=True
            )

        except asyncio.TimeoutError:
            return CommandResult(
                session_id=self.session_id,
                agent_id=self.agent_id,
                command=command,
                result={"error": "Command timeout"},
                timestamp=datetime.now(),
                success=False
            )
        except Exception as e:
            return CommandResult(
                session_id=self.session_id,
                agent_id=self.agent_id,
                command=command,
                result={"error": str(e)},
                timestamp=datetime.now(),
                success=False
            )

    async def terminate(self) -> None:
        """优雅终止进程"""
        self.cancelled = True
        self.status = SessionStatus.STOPPING

        if self.stdio_controller:
            await self.stdio_controller.stop()

        if self.process:
            try:
                # 尝试优雅关闭
                self.process.terminate()
                await asyncio.wait_for(self.process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                # 强制关闭
                self.process.kill()
                await self.process.wait()

        self.status = SessionStatus.STOPPED

    async def get_status(self) -> Dict[str, Any]:
        """获取会话状态"""
        return {
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "command_count": self.command_count,
            "cancelled": self.cancelled,
            "process_id": self.process.pid if self.process else None
        }
```

### 3. StdioController (stdio_controller.py)

控制标准输入输出，处理与CLI进程的实际通信。

```python
import asyncio
import re
from typing import Optional, AsyncIterator, Dict, Any
from .types import RawCommandResult

class StdioController:
    """标准输入输出控制器，处理与CLI进程的通信"""

    def __init__(self, process: subprocess.Popen, adapter):
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
```

### 4. 适配器系统

#### BaseCliAdapter (adapters/base_adapter.py)

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from ..types import RawCommandResult, ParsedResult

class BaseCliAdapter(ABC):
    """CLI适配器基类，定义统一接口"""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    async def build_command(self, preset: str) -> List[str]:
        """构建启动CLI的命令"""
        pass

    @abstractmethod
    async def wait_for_ready(self, stdio_controller) -> None:
        """等待CLI初始化完成"""
        pass

    @abstractmethod
    async def format_command(self, command: str) -> str:
        """格式化要发送的命令"""
        pass

    @abstractmethod
    async def is_command_complete(self, stdout_lines: List[str], stderr_lines: List[str]) -> bool:
        """判断命令是否执行完成"""
        pass

    @abstractmethod
    async def parse_result(self, raw_result: RawCommandResult) -> ParsedResult:
        """解析命令执行结果"""
        pass

    async def get_capabilities(self) -> Dict[str, Any]:
        """返回适配器能力"""
        return {
            "name": self.name,
            "supports_interactive": True,
            "supports_files": True,
            "supports_streaming": True
        }
```

#### ClaudeAdapter (adapters/claude_adapter.py)

```python
import re
from typing import List, Dict, Any
from .base_adapter import BaseCliAdapter
from ..types import RawCommandResult, ParsedResult

class ClaudeAdapter(BaseCliAdapter):
    """Claude CLI适配器"""

    def __init__(self):
        super().__init__("claude")
        self.prompt_pattern = re.compile(r'.*\$\s*$')  # 匹配Claude CLI提示符

    async def build_command(self, preset: str) -> List[str]:
        """构建Claude CLI启动命令"""
        # 注意：这里需要根据实际的Claude CLI命令调整
        return ["claude", "--interactive"]

    async def wait_for_ready(self, stdio_controller) -> None:
        """等待Claude CLI准备就绪"""
        # 等待看到提示符
        async for output_type, line in stdio_controller.get_real_time_output():
            if output_type == 'stdout' and self.prompt_pattern.match(line):
                break

    async def format_command(self, command: str) -> str:
        """格式化Claude命令"""
        # Claude CLI可能需要特殊格式
        return command

    async def is_command_complete(self, stdout_lines: List[str], stderr_lines: List[str]) -> bool:
        """判断Claude命令是否完成"""
        if not stdout_lines:
            return False

        # 检查最后一行是否是提示符
        last_line = stdout_lines[-1] if stdout_lines else ""
        return self.prompt_pattern.match(last_line) is not None

    async def parse_result(self, raw_result: RawCommandResult) -> ParsedResult:
        """解析Claude输出"""
        output_text = '\n'.join(raw_result.stdout)
        error_text = '\n'.join(raw_result.stderr)

        # 提取token信息（如果有）
        token_info = self._extract_token_info(output_text)

        # 移除提示符行
        cleaned_output = self._clean_output(output_text)

        return ParsedResult(
            output=cleaned_output,
            error=error_text,
            metadata={
                "tokens": token_info,
                "adapter": "claude",
                "raw_lines": len(raw_result.stdout)
            },
            success=len(error_text) == 0
        )

    def _extract_token_info(self, output: str) -> Dict[str, Any]:
        """提取token使用信息"""
        token_pattern = re.compile(r'tokens used: (\d+)')
        match = token_pattern.search(output)

        if match:
            return {"total_tokens": int(match.group(1))}
        return {}

    def _clean_output(self, output: str) -> str:
        """清理输出，移除提示符等"""
        lines = output.split('\n')
        # 移除最后的提示符行
        if lines and self.prompt_pattern.match(lines[-1]):
            lines = lines[:-1]
        return '\n'.join(lines)
```

#### GenericAdapter (adapters/generic_adapter.py)

```python
import re
from typing import List, Dict, Any
from .base_adapter import BaseCliAdapter
from ..types import RawCommandResult, ParsedResult

class GenericAdapter(BaseCliAdapter):
    """通用CLI适配器，适用于大多数CLI工具"""

    def __init__(self, name: str, command: List[str], prompt_pattern: str = None):
        super().__init__(name)
        self.command = command
        self.prompt_pattern = re.compile(prompt_pattern or r'.*[$#>]\s*$')

    async def build_command(self, preset: str) -> List[str]:
        """构建启动命令"""
        return self.command

    async def wait_for_ready(self, stdio_controller) -> None:
        """等待CLI准备就绪"""
        async for output_type, line in stdio_controller.get_real_time_output():
            if output_type == 'stdout' and self.prompt_pattern.match(line):
                break

    async def format_command(self, command: str) -> str:
        """格式化命令（默认不修改）"""
        return command

    async def is_command_complete(self, stdout_lines: List[str], stderr_lines: List[str]) -> bool:
        """判断命令是否完成"""
        if not stdout_lines:
            return False

        last_line = stdout_lines[-1] if stdout_lines else ""
        return self.prompt_pattern.match(last_line) is not None

    async def parse_result(self, raw_result: RawCommandResult) -> ParsedResult:
        """解析输出"""
        output_text = '\n'.join(raw_result.stdout)
        error_text = '\n'.join(raw_result.stderr)

        # 移除提示符行
        lines = output_text.split('\n')
        if lines and self.prompt_pattern.match(lines[-1]):
            lines = lines[:-1]
        cleaned_output = '\n'.join(lines)

        return ParsedResult(
            output=cleaned_output,
            error=error_text,
            metadata={
                "adapter": self.name,
                "raw_lines": len(raw_result.stdout)
            },
            success=len(error_text) == 0
        )
```

### 5. CLIAgentManager (manager.py)

管理多个CLI代理的高级接口。

```python
from typing import Dict, List, Any, Optional
import asyncio
from .agent_wrapper import CLIAgentWrapper
from .adapters import ClaudeAdapter, GenericAdapter
from .types import CommandResult, AgentConfig

class CLIAgentManager:
    """CLI代理管理器，统一管理多个代理"""

    def __init__(self):
        self.agents: Dict[str, CLIAgentWrapper] = {}
        self.adapters: Dict[str, Any] = {
            'claude': ClaudeAdapter(),
            'generic': GenericAdapter
        }

    async def register_agent(self, agent_id: str, adapter_name: str, config: AgentConfig = None) -> None:
        """注册新代理"""
        if adapter_name not in self.adapters:
            raise ValueError(f"Unknown adapter: {adapter_name}")

        adapter = self.adapters[adapter_name]
        if adapter_name == 'generic' and config:
            # 为通用适配器创建实例
            adapter = GenericAdapter(
                name=agent_id,
                command=config.command,
                prompt_pattern=config.prompt_pattern
            )

        agent = CLIAgentWrapper(agent_id, adapter)
        await agent.initialize()
        self.agents[agent_id] = agent

    async def create_session(self, agent_id: str, preset: str, **kwargs) -> str:
        """为指定代理创建会话"""
        if agent_id not in self.agents:
            raise ValueError(f"Agent {agent_id} not found")

        return await self.agents[agent_id].new_session(preset, **kwargs)

    async def execute_command(self, agent_id: str, session_id: str, command: str, **kwargs) -> CommandResult:
        """在指定代理的会话中执行命令"""
        if agent_id not in self.agents:
            raise ValueError(f"Agent {agent_id} not found")

        return await self.agents[agent_id].execute_command(session_id, command, **kwargs)

    async def execute_parallel(self, commands: List[Dict[str, Any]]) -> List[CommandResult]:
        """并行执行多个命令"""
        tasks = []

        for cmd_info in commands:
            agent_id = cmd_info['agent_id']
            session_id = cmd_info['session_id']
            command = cmd_info['command']

            if agent_id in self.agents:
                task = self.agents[agent_id].execute_command(session_id, command)
                tasks.append(task)

        return await asyncio.gather(*tasks, return_exceptions=True)

    async def execute_sequential(self, commands: List[Dict[str, Any]]) -> List[CommandResult]:
        """串行执行多个命令"""
        results = []

        for cmd_info in commands:
            agent_id = cmd_info['agent_id']
            session_id = cmd_info['session_id']
            command = cmd_info['command']

            if agent_id in self.agents:
                try:
                    result = await self.agents[agent_id].execute_command(session_id, command)
                    results.append(result)

                    # 如果命令失败且设置了stop_on_error，则停止执行
                    if not result.success and cmd_info.get('stop_on_error', False):
                        break

                except Exception as e:
                    results.append(CommandResult(
                        session_id=session_id,
                        agent_id=agent_id,
                        command=command,
                        result={"error": str(e)},
                        timestamp=datetime.now(),
                        success=False
                    ))
                    break

        return results

    async def list_agents(self) -> List[Dict[str, Any]]:
        """列出所有代理"""
        agents_info = []
        for agent_id, agent in self.agents.items():
            sessions = await agent.list_sessions()
            agents_info.append({
                "agent_id": agent_id,
                "adapter": agent.adapter.name,
                "capabilities": agent.capabilities,
                "sessions": sessions
            })
        return agents_info

    async def terminate_agent(self, agent_id: str) -> None:
        """终止指定代理的所有会话"""
        if agent_id in self.agents:
            agent = self.agents[agent_id]
            for session_id in list(agent.sessions.keys()):
                await agent.terminate_session(session_id)
            del self.agents[agent_id]
```

### 6. 类型定义 (types.py)

```python
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum

class SessionStatus(Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"

@dataclass
class RawCommandResult:
    """原始命令执行结果"""
    stdout: List[str]
    stderr: List[str]
    command: str
    completed: bool

@dataclass
class ParsedResult:
    """解析后的结果"""
    output: str
    error: str
    metadata: Dict[str, Any]
    success: bool

@dataclass
class CommandResult:
    """完整的命令执行结果"""
    session_id: str
    agent_id: str
    command: str
    result: ParsedResult
    timestamp: datetime
    success: bool

@dataclass
class AgentConfig:
    """代理配置"""
    command: List[str]
    prompt_pattern: Optional[str] = None
    env: Optional[Dict[str, str]] = None
    cwd: Optional[str] = None

@dataclass
class BackgroundProcess:
    """后台进程信息"""
    process_id: str
    status: str
    started_at: datetime
    last_output: Optional[str] = None
```

## CLI集成

### 扩展现有CLI命令 (cli.py)

```python
import asyncio
from typing import List
import click
from .cli_wrapper.manager import CLIAgentManager
from .cli_wrapper.types import AgentConfig

# 全局管理器实例
_agent_manager: Optional[CLIAgentManager] = None

async def get_agent_manager() -> CLIAgentManager:
    """获取代理管理器实例"""
    global _agent_manager
    if _agent_manager is None:
        _agent_manager = CLIAgentManager()
    return _agent_manager

@cli.command()
@click.argument('preset')
@click.option('--agents', help='指定代理列表，逗号分隔，例如: claude,codex')
@click.option('--parallel', is_flag=True, help='并行执行（默认串行）')
@click.option('--task', help='要执行的任务内容')
@click.option('--timeout', type=float, default=30.0, help='命令超时时间（秒）')
@click.option('--stop-on-error', is_flag=True, help='遇到错误时停止执行（仅串行模式）')
def apply(preset, agents, parallel, task, timeout, stop_on_error):
    """扩展的apply命令，支持多代理执行"""
    if not agents:
        # 保持原有的单代理行为
        return _original_apply(preset)

    asyncio.run(_apply_with_agents(preset, agents, parallel, task, timeout, stop_on_error))

async def _apply_with_agents(preset: str, agents: str, parallel: bool, task: str, timeout: float, stop_on_error: bool):
    """多代理执行逻辑"""
    manager = await get_agent_manager()
    agent_list = [a.strip() for a in agents.split(',')]

    # 注册代理（如果还未注册）
    for agent_name in agent_list:
        try:
            await manager.register_agent(agent_name, _get_adapter_for_agent(agent_name))
        except ValueError:
            # 代理已存在
            pass

    # 为每个代理创建会话
    sessions = {}
    for agent_name in agent_list:
        try:
            session_id = await manager.create_session(agent_name, preset)
            sessions[agent_name] = session_id
            click.echo(f"✓ Created session for {agent_name}: {session_id[:8]}...")
        except Exception as e:
            click.echo(f"✗ Failed to create session for {agent_name}: {e}")
            return

    # 准备命令
    commands = []
    for agent_name, session_id in sessions.items():
        commands.append({
            'agent_id': agent_name,
            'session_id': session_id,
            'command': task,
            'stop_on_error': stop_on_error
        })

    # 执行命令
    click.echo(f"\n{'Executing in parallel' if parallel else 'Executing sequentially'}...")

    try:
        if parallel:
            results = await manager.execute_parallel(commands)
        else:
            results = await manager.execute_sequential(commands)

        # 显示结果
        _display_results(results, parallel)

    finally:
        # 清理会话
        for agent_name, session_id in sessions.items():
            try:
                await manager.agents[agent_name].terminate_session(session_id)
                click.echo(f"✓ Cleaned up session for {agent_name}")
            except Exception as e:
                click.echo(f"✗ Failed to cleanup session for {agent_name}: {e}")

def _get_adapter_for_agent(agent_name: str) -> str:
    """根据代理名称返回适配器类型"""
    adapters_map = {
        'claude': 'claude',
        'codex': 'generic',  # 需要额外配置
        'gpt': 'generic'     # 需要额外配置
    }
    return adapters_map.get(agent_name, 'generic')

def _display_results(results: List, parallel: bool):
    """显示执行结果"""
    click.echo(f"\n{'='*60}")
    click.echo("EXECUTION RESULTS")
    click.echo(f"{'='*60}")

    for i, result in enumerate(results, 1):
        if isinstance(result, Exception):
            click.echo(f"\n[{i}] ✗ Error: {result}")
            continue

        status_icon = "✓" if result.success else "✗"
        click.echo(f"\n[{i}] {status_icon} Agent: {result.agent_id}")
        click.echo(f"    Command: {result.command}")
        click.echo(f"    Time: {result.timestamp.strftime('%H:%M:%S')}")

        if result.success:
            click.echo(f"    Output:\n{_indent_text(result.result.output)}")
            if result.result.metadata:
                click.echo(f"    Metadata: {result.result.metadata}")
        else:
            click.echo(f"    Error:\n{_indent_text(result.result.error)}")

def _indent_text(text: str, spaces: int = 8) -> str:
    """缩进文本"""
    indent = " " * spaces
    return "\n".join(indent + line for line in text.split("\n"))

# 新增agents命令组
@cli.group()
def agents():
    """管理CLI代理"""
    pass

@agents.command('list')
def agents_list():
    """列出所有代理和会话"""
    asyncio.run(_agents_list())

async def _agents_list():
    """列出代理实现"""
    manager = await get_agent_manager()
    agents_info = await manager.list_agents()

    if not agents_info:
        click.echo("No active agents found.")
        return

    click.echo("Active Agents:")
    click.echo("-" * 50)

    for agent_info in agents_info:
        click.echo(f"\n🤖 {agent_info['agent_id']} ({agent_info['adapter']})")
        if agent_info['sessions']:
            click.echo("   Sessions:")
            for session in agent_info['sessions']:
                status_icon = "🟢" if session['status']['status'] == 'running' else "🔴"
                click.echo(f"   {status_icon} {session['session_id'][:8]}... ({session['status']['status']})")
        else:
            click.echo("   No active sessions")

@agents.command('status')
@click.argument('agent_id')
def agents_status(agent_id):
    """查看指定代理的详细状态"""
    asyncio.run(_agents_status(agent_id))

async def _agents_status(agent_id: str):
    """查看代理状态实现"""
    manager = await get_agent_manager()

    if agent_id not in manager.agents:
        click.echo(f"Agent '{agent_id}' not found.")
        return

    agent = manager.agents[agent_id]
    sessions = await agent.list_sessions()

    click.echo(f"Agent: {agent_id}")
    click.echo(f"Adapter: {agent.adapter.name}")
    click.echo(f"Capabilities: {agent.capabilities}")
    click.echo(f"Sessions: {len(sessions)}")

    if sessions:
        click.echo("\nSession Details:")
        for session in sessions:
            click.echo(f"  ID: {session['session_id']}")
            click.echo(f"  Status: {session['status']['status']}")
            click.echo(f"  Created: {session['created_at']}")
            click.echo(f"  Commands: {session['status']['command_count']}")
            click.echo()

@agents.command('terminate')
@click.argument('agent_id')
@click.confirmation_option(prompt='Are you sure you want to terminate this agent?')
def agents_terminate(agent_id):
    """终止指定代理的所有会话"""
    asyncio.run(_agents_terminate(agent_id))

async def _agents_terminate(agent_id: str):
    """终止代理实现"""
    manager = await get_agent_manager()

    try:
        await manager.terminate_agent(agent_id)
        click.echo(f"✓ Agent '{agent_id}' terminated successfully.")
    except ValueError as e:
        click.echo(f"✗ Error: {e}")
    except Exception as e:
        click.echo(f"✗ Failed to terminate agent: {e}")
```

## 使用示例

### 基本用法

```bash
# 使用单个代理执行任务
aiswitch apply gpt4 --agents claude --task "写一个Python快速排序函数"

# 并行使用多个代理对比结果
aiswitch apply gpt4 --agents claude,codex --parallel --task "实现二分查找算法"

# 串行执行，可以利用前一个代理的输出
aiswitch apply gpt4 --agents claude,codex --task "先分析需求，再写代码" --stop-on-error

# 管理代理
aiswitch agents list                    # 列出所有活跃代理
aiswitch agents status claude           # 查看Claude代理详细状态
aiswitch agents terminate claude        # 终止Claude代理所有会话
```

### 高级用法

```bash
# 自定义超时时间
aiswitch apply gpt4 --agents claude --task "复杂任务" --timeout 60

# 遇到错误时停止后续执行
aiswitch apply gpt4 --agents claude,codex,gpt --task "测试任务" --stop-on-error
```

## 实现优先级

### Phase 1: 核心功能 (1-2周)
1. 实现基础类框架：CLIAgentWrapper, CLIProcessSession, StdioController
2. 实现基础适配器：BaseCliAdapter, GenericAdapter
3. 实现CLIAgentManager基本功能
4. 集成到现有CLI，支持单代理执行

### Phase 2: 完善功能 (1周)
1. 实现ClaudeAdapter（需要根据实际Claude CLI调整）
2. 完善错误处理和异常恢复
3. 添加日志记录和调试功能
4. 实现并行/串行执行模式

### Phase 3: 优化和扩展 (1周)
1. 性能优化和内存管理
2. 添加更多适配器（根据需要）
3. 完善CLI命令和用户体验
4. 添加配置文件支持

## 技术注意事项

### 1. 异步编程
- 所有IO操作使用asyncio
- 正确处理异步任务的生命周期
- 避免阻塞事件循环

### 2. 进程管理
- 确保进程正确终止，避免僵尸进程
- 处理进程意外退出的情况
- 实现进程重启机制

### 3. 错误处理
- 网络超时和进程崩溃的优雅处理
- 详细的错误日志记录
- 用户友好的错误信息

### 4. 内存管理
- 定期清理输出缓冲区
- 限制日志文件大小
- 监控内存使用情况

### 5. 安全考虑
- 输入验证和清理
- 进程权限控制
- 敏感信息保护

这个设计方案提供了完整的CLI代理包装器实现路径，具备良好的扩展性和维护性，可以根据实际需求进行调整和优化。