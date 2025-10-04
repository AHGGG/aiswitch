# aiswitch 多代理集成设计方案

## 概述

本文档描述了aiswitch多代理系统的设计方案，基于claude-agent-sdk直接集成不同的AI代理，实现统一的多代理协调和管理平台。该设计摒弃了复杂的CLI stdio拦截方案，采用SDK直接集成的方式，提供更简洁、稳定和高效的解决方案。

## 核心目标

1. **代理集成**: 基于claude-agent-sdk等SDK直接集成各种AI代理
2. **统一接口**: 提供统一的API来控制不同的AI代理
3. **并发支持**: 支持多个代理同时运行和协调
4. **会话管理**: 管理长期运行的代理会话状态
5. **环境管理**: 动态切换不同的API预设和环境变量
6. **监控追踪**: 实时监控代理状态和token使用情况

## 技术架构

### 核心组件图

```
┌─────────────────────────────────────────────────────────┐
│                MultiAgentManager                        │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────┐ │
│  │   AgentWrapper  │  │   AgentWrapper  │  │    ...   │ │
│  │   (claude)      │  │   (openai)      │  │          │ │
│  └─────────────────┘  └─────────────────┘  └──────────┘ │
└─────────────────────────────────────────────────────────┘
           │                     │                     │
┌─────────────────┐    ┌─────────────────┐    ┌──────────────┐
│  AgentSession   │    │  AgentSession   │    │      ...     │
│ + SDK Client    │    │ + SDK Client    │    │              │
│ + Adapter       │    │ + Adapter       │    │              │
└─────────────────┘    └─────────────────┘    └──────────────┘
           │                     │                     │
┌─────────────────┐    ┌─────────────────┐    ┌──────────────┐
│ claude-agent-   │    │   openai-sdk    │    │ other-agent  │
│     sdk         │    │                 │    │     sdk      │
└─────────────────┘    └─────────────────┘    └──────────────┘
```

### 文件结构

```
aiswitch/
├── multi_agent/
│   ├── __init__.py
│   ├── manager.py                # MultiAgentManager主类
│   ├── agent_wrapper.py          # AgentWrapper包装器
│   ├── session.py                # Agent会话管理
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── base_adapter.py       # 适配器基类
│   │   ├── claude_adapter.py     # Claude SDK适配器
│   │   ├── openai_adapter.py     # OpenAI SDK适配器
│   │   └── generic_adapter.py    # 通用适配器
│   ├── coordination.py           # 多代理协调
│   ├── metrics.py                # 指标收集
│   └── types.py                  # 类型定义
├── textual_interactive.py        # 已有的交互式UI
└── cli.py                        # 扩展现有CLI命令
```

## 核心类设计

### 1. MultiAgentManager (multi_agent/manager.py)

多代理管理器，统一管理和协调多个AI代理。

```python
from typing import Dict, List, Any, Optional
import asyncio
from .agent_wrapper import AgentWrapper
from .adapters import ClaudeAdapter, OpenAIAdapter, GenericAdapter
from .types import Task, TaskResult, AgentConfig
from .coordination import MultiAgentCoordinator
from .metrics import MetricsCollector

class MultiAgentManager:
    """多代理管理器，统一管理多个AI代理"""

    def __init__(self):
        self.agents: Dict[str, AgentWrapper] = {}
        self.coordinator = MultiAgentCoordinator()
        self.metrics_collector = MetricsCollector()
        self.adapters = {
            'claude': ClaudeAdapter,
            'openai': OpenAIAdapter,
            'generic': GenericAdapter
        }

    async def register_agent(self, agent_id: str, adapter_type: str, config: AgentConfig = None) -> None:
        """注册新代理"""
        if adapter_type not in self.adapters:
            raise ValueError(f"Unknown adapter type: {adapter_type}")

        adapter_class = self.adapters[adapter_type]
        adapter = adapter_class(config or {})

        agent = AgentWrapper(agent_id, adapter)
        await agent.initialize()
        self.agents[agent_id] = agent

    async def execute_task(self, agent_ids: List[str], task: Task, mode: str = "parallel") -> List[TaskResult]:
        """执行任务在指定的代理上"""
        if mode == "parallel":
            return await self.coordinator.execute_parallel(self.agents, agent_ids, task)
        elif mode == "sequential":
            return await self.coordinator.execute_sequential(self.agents, agent_ids, task)
        else:
            raise ValueError(f"Unknown execution mode: {mode}")

    async def switch_agent_env(self, agent_id: str, preset: str) -> bool:
        """切换指定代理的环境变量"""
        if agent_id not in self.agents:
            raise ValueError(f"Agent {agent_id} not found")

        return await self.agents[agent_id].switch_environment(preset)

    def get_agent_status(self, agent_id: str) -> Dict[str, Any]:
        """获取代理状态"""
        if agent_id not in self.agents:
            return {"error": "Agent not found"}

        return self.agents[agent_id].get_status()

    async def list_agents(self) -> List[Dict[str, Any]]:
        """列出所有代理"""
        agents_info = []
        for agent_id, agent in self.agents.items():
            status = agent.get_status()
            metrics = await self.metrics_collector.get_agent_metrics(agent_id)
            agents_info.append({
                "agent_id": agent_id,
                "adapter_type": agent.adapter.adapter_type,
                "status": status,
                "metrics": metrics
            })
        return agents_info

    async def terminate_agent(self, agent_id: str) -> None:
        """终止指定代理"""
        if agent_id in self.agents:
            await self.agents[agent_id].terminate()
            del self.agents[agent_id]
```

### 2. AgentWrapper (multi_agent/agent_wrapper.py)

代理包装器，管理单个AI代理的生命周期和状态。

```python
import asyncio
import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from .adapters.base_adapter import BaseAdapter
from .session import AgentSession
from .types import Task, TaskResult, AgentStatus

class AgentWrapper:
    """代理包装器，管理单个AI代理"""

    def __init__(self, agent_id: str, adapter: BaseAdapter):
        self.agent_id = agent_id
        self.adapter = adapter
        self.session: Optional[AgentSession] = None
        self.status = AgentStatus.STOPPED
        self.created_at = datetime.now()
        self.last_activity = datetime.now()
        self.task_count = 0
        self.current_task: Optional[str] = None

    async def initialize(self) -> Dict[str, Any]:
        """初始化代理"""
        try:
            await self.adapter.initialize()
            self.status = AgentStatus.IDLE
            self.last_activity = datetime.now()

            return {
                "agent_id": self.agent_id,
                "adapter_type": self.adapter.adapter_type,
                "status": self.status.value,
                "initialized_at": self.created_at.isoformat()
            }
        except Exception as e:
            self.status = AgentStatus.ERROR
            raise RuntimeError(f"Failed to initialize agent {self.agent_id}: {e}")

    async def create_session(self, preset: str, env_vars: Dict[str, str] = None) -> str:
        """创建新会话"""
        if self.session:
            await self.session.close()

        session_id = str(uuid.uuid4())
        self.session = AgentSession(
            session_id=session_id,
            agent_id=self.agent_id,
            adapter=self.adapter,
            preset=preset,
            env_vars=env_vars or {}
        )

        await self.session.start()
        return session_id

    async def execute_task(self, task: Task, timeout: float = 30.0) -> TaskResult:
        """执行任务"""
        if self.status != AgentStatus.IDLE:
            raise RuntimeError(f"Agent {self.agent_id} is not available, status: {self.status}")

        self.status = AgentStatus.BUSY
        self.current_task = task.id
        self.task_count += 1
        self.last_activity = datetime.now()

        try:
            if not self.session:
                # 如果没有会话，创建一个默认会话
                await self.create_session("default")

            result = await self.session.execute_task(task, timeout)

            self.status = AgentStatus.IDLE
            self.current_task = None
            self.last_activity = datetime.now()

            return result

        except Exception as e:
            self.status = AgentStatus.ERROR
            self.current_task = None
            raise RuntimeError(f"Task execution failed: {e}")

    async def switch_environment(self, preset: str) -> bool:
        """切换环境变量"""
        try:
            if self.session:
                await self.session.switch_environment(preset)
            self.last_activity = datetime.now()
            return True
        except Exception as e:
            print(f"Failed to switch environment for {self.agent_id}: {e}")
            return False

    def get_status(self) -> Dict[str, Any]:
        """获取代理状态"""
        return {
            "agent_id": self.agent_id,
            "status": self.status.value,
            "current_task": self.current_task,
            "task_count": self.task_count,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "session_id": self.session.session_id if self.session else None
        }

    async def terminate(self) -> None:
        """终止代理"""
        self.status = AgentStatus.STOPPING

        if self.session:
            await self.session.close()
            self.session = None

        if hasattr(self.adapter, 'close'):
            await self.adapter.close()

        self.status = AgentStatus.STOPPED
```

### 3. ClaudeAdapter (multi_agent/adapters/claude_adapter.py)

Claude代理适配器，基于claude-agent-sdk实现。

```python
import os
from typing import Dict, Any, AsyncIterator
from .base_adapter import BaseAdapter
from ..types import Task, TaskResult

try:
    from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, TextBlock
    CLAUDE_SDK_AVAILABLE = True
except ImportError:
    CLAUDE_SDK_AVAILABLE = False

class ClaudeAdapter(BaseAdapter):
    """Claude代理适配器，使用claude-agent-sdk"""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__("claude")
        self.config = config or {}
        self.env_vars: Dict[str, str] = {}

    async def initialize(self) -> bool:
        """初始化Claude适配器"""
        if not CLAUDE_SDK_AVAILABLE:
            raise RuntimeError("claude-agent-sdk not available")

        # 检查必要的环境变量
        required_vars = ["ANTHROPIC_API_KEY"]
        missing_vars = [var for var in required_vars if not os.getenv(var)]

        if missing_vars:
            raise RuntimeError(f"Missing required environment variables: {missing_vars}")

        return True

    async def execute_task(self, task: Task, timeout: float = 30.0) -> TaskResult:
        """执行任务"""
        try:
            # 应用环境变量
            for key, value in self.env_vars.items():
                os.environ[key] = value

            # 准备选项
            options = ClaudeAgentOptions(
                system_prompt=task.system_prompt if hasattr(task, 'system_prompt') else None,
                max_tokens=task.max_tokens if hasattr(task, 'max_tokens') else 4000,
                temperature=task.temperature if hasattr(task, 'temperature') else 0.7
            )

            # 执行查询
            response_chunks = []
            async for message in query(prompt=task.prompt, options=options):
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            response_chunks.append(block.text)

            result_text = ''.join(response_chunks)

            return TaskResult(
                task_id=task.id,
                success=True,
                result=result_text,
                metadata={"adapter": "claude", "chunks": len(response_chunks)}
            )

        except Exception as e:
            return TaskResult(
                task_id=task.id,
                success=False,
                error=str(e),
                metadata={"adapter": "claude"}
            )

    async def switch_environment(self, preset: str, env_vars: Dict[str, str]) -> bool:
        """切换环境变量"""
        try:
            self.env_vars = env_vars.copy()
            return True
        except Exception:
            return False
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
aiswitch apply gpt4 --agents claude,openai --parallel --task "实现二分查找算法"

# 串行执行，可以利用前一个代理的输出
aiswitch apply gpt4 --agents claude,openai --task "先分析需求，再写代码" --stop-on-error

# 交互式模式使用Claude SDK
aiswitch apply ds --interactive --interactive-mode textual --agents claude

# 管理代理
aiswitch agents list                    # 列出所有活跃代理
aiswitch agents status claude           # 查看Claude代理详细状态
aiswitch agents terminate claude        # 终止Claude代理
```

### 高级用法

```bash
# 自定义超时时间
aiswitch apply gpt4 --agents claude --task "复杂任务" --timeout 60

# 环境切换
aiswitch env switch claude anthropic-claude-sonnet

# 监控代理状态
aiswitch metrics show --agent claude --timeframe day
```

## 实现优先级

### Phase 1: 核心SDK集成 (1-2周)
1. 实现基础类框架：MultiAgentManager, AgentWrapper, AgentSession
2. 实现基础适配器：BaseAdapter, ClaudeAdapter
3. 集成claude-agent-sdk到现有textual_interactive.py
4. 扩展CLI支持--agents参数

### Phase 2: 多代理协调 (1周)
1. 实现MultiAgentCoordinator协调器
2. 支持并行/串行执行模式
3. 完善错误处理和异常恢复
4. 添加代理状态监控

### Phase 3: 扩展和优化 (1周)
1. 添加OpenAI等其他SDK适配器
2. 实现环境动态切换功能
3. 添加指标收集和token追踪
4. 完善CLI命令和用户体验

## 技术注意事项

### 1. SDK集成
- 使用各种AI SDK的最新版本和最佳实践
- 正确处理SDK的异步模式和错误处理
- 管理不同SDK的认证和配置

### 2. 异步编程
- 所有IO操作使用asyncio
- 正确处理异步任务的生命周期
- 避免阻塞事件循环

### 3. 错误处理
- SDK错误的优雅处理和重试机制
- 详细的错误日志记录
- 用户友好的错误信息

### 4. 环境管理
- 安全的环境变量切换
- 防止敏感信息泄露
- 环境隔离和状态一致性

### 5. 性能优化
- SDK连接复用和池化
- 合理的并发控制
- 内存使用监控和优化

这个设计方案基于SDK直接集成，摒弃了复杂的CLI进程管理，提供了更简洁、稳定和高效的多代理协调解决方案。