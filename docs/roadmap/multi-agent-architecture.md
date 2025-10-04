# aiswitch 多代理SDK集成系统架构设计

## 概述

aiswitch多代理系统基于SDK直接集成实现一个local-first的多AI代理协调平台，支持同时管理和协调多个AI代理（如Claude、OpenAI等），通过各自的SDK提供统一的接口和强大的协调机制。

## 设计原则

### 1. Local-first
- **无外部依赖**: 不依赖Redis、数据库等外部服务
- **本地状态管理**: 所有状态存储在本地文件系统
- **离线可用**: 在有API连接的前提下本地运行

### 2. SDK直接集成架构
- **主进程**: aiswitch作为协调器和管理中心
- **SDK集成**: 直接集成各种AI SDK（claude-agent-sdk、openai等）
- **适配器模式**: 统一的适配器接口封装不同SDK的差异

### 3. 高可用性
- **故障隔离**: 单个代理故障不影响其他代理
- **SDK重连**: 支持SDK连接断开后自动重连
- **状态持久化**: 关键状态持久化到本地文件

## 系统架构

### 核心组件图

```
┌─────────────────────────────────────────────────────────┐
│                    aiswitch (主进程)                     │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────┐ │
│  │   多代理协调器   │  │    指标收集器    │  │ 环境管理器│ │
│  └─────────────────┘  └─────────────────┘  └──────────┘ │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────┐ │
│  │  代理管理器     │  │   Token追踪器   │  │ 配置管理器│ │
│  └─────────────────┘  └─────────────────┘  └──────────┘ │
│  ┌─────────────────┐  ┌─────────────────┐               │
│  │  SDK适配器层    │  │   会话管理器    │               │
│  └─────────────────┘  └─────────────────┘               │
└─────────────────────────────────────────────────────────┘
           │ Direct SDK Call       │ Direct SDK Call       │
┌─────────────────┐      ┌─────────────────┐      ┌──────────────┐
│ claude-agent-   │      │   openai-sdk    │      │ other-agent  │
│     sdk         │      │                 │      │     sdk      │
└─────────────────┘      └─────────────────┘      └──────────────┘
           │                       │                       │
    ┌─────────────┐        ┌─────────────┐        ┌─────────────┐
    │ Claude API  │        │ OpenAI API  │        │ Other APIs  │
    └─────────────┘        └─────────────┘        └─────────────┘
```

### 文件系统结构

```
~/.aiswitch/
├── config/
│   ├── presets.yaml          # 预设配置（扩展支持多代理）
│   ├── agents.yaml           # 代理配置和SDK设置
│   └── coordination.yaml     # 协调配置
├── state/
│   ├── agents.json           # 代理状态
│   ├── sessions.json         # 会话状态
│   ├── metrics.json          # 指标数据
│   └── tokens.json           # Token统计
├── logs/
│   ├── coordinator.log       # 协调器日志
│   ├── agents/               # 代理日志目录
│   │   ├── claude.log        # Claude代理日志
│   │   └── openai.log        # OpenAI代理日志
│   └── metrics/              # 指标日志
└── cache/
    ├── sdk_sessions/         # SDK会话缓存
    └── credentials/          # 认证信息缓存
```

## 核心模块设计

### 1. 多代理协调器 (multi_agent/coordinator.py)

```python
class MultiAgentCoordinator:
    """多代理协调器，负责任务分配和结果聚合"""

    def __init__(self):
        self.agent_manager = MultiAgentManager()
        self.metrics_collector = MetricsCollector()
        self.token_tracker = TokenTracker()
        self.env_manager = DynamicEnvManager()

    async def execute_parallel(self, agent_ids: List[str], task: Task) -> List[TaskResult]:
        """并行执行任务"""
        tasks = []
        for agent_id in agent_ids:
            tasks.append(self.agent_manager.execute_task([agent_id], task, "single"))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        return self.aggregate_results(results)

    async def execute_sequential(self, agent_ids: List[str], task: Task) -> List[TaskResult]:
        """串行执行任务"""
        results = []
        for agent_id in agent_ids:
            result = await self.agent_manager.execute_task([agent_id], task, "single")
            results.extend(result)

            # 如果启用了依赖模式，将前一个结果传递给下一个任务
            if hasattr(task, 'chain_mode') and task.chain_mode:
                task.context = result[-1].result

        return results

    def aggregate_results(self, results: List[TaskResult]) -> AggregatedResult:
        """聚合多个代理的执行结果"""
        successful_results = [r for r in results if r.success]
        failed_results = [r for r in results if not r.success]

        return AggregatedResult(
            total_count=len(results),
            success_count=len(successful_results),
            failed_count=len(failed_results),
            results=results,
            aggregated_output=self._merge_outputs(successful_results)
        )
```

### 2. SDK适配器系统 (multi_agent/adapters/)

```python
class BaseAdapter(ABC):
    """SDK适配器基类"""

    def __init__(self, adapter_type: str):
        self.adapter_type = adapter_type
        self.config: Dict[str, Any] = {}
        self.env_vars: Dict[str, str] = {}

    @abstractmethod
    async def initialize(self) -> bool:
        """初始化SDK连接"""
        pass

    @abstractmethod
    async def execute_task(self, task: Task, timeout: float = 30.0) -> TaskResult:
        """执行任务"""
        pass

    @abstractmethod
    async def switch_environment(self, preset: str, env_vars: Dict[str, str]) -> bool:
        """切换环境变量"""
        pass

    async def close(self):
        """关闭SDK连接"""
        pass

class ClaudeAdapter(BaseAdapter):
    """Claude SDK适配器"""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__("claude")
        self.config = config or {}

    async def initialize(self) -> bool:
        """初始化Claude SDK"""
        if not claude_agent_sdk_available:
            raise RuntimeError("claude-agent-sdk not available")
        return True

    async def execute_task(self, task: Task, timeout: float = 30.0) -> TaskResult:
        """使用Claude SDK执行任务"""
        # 应用环境变量
        for key, value in self.env_vars.items():
            os.environ[key] = value

        options = ClaudeAgentOptions(
            system_prompt=getattr(task, 'system_prompt', None),
            max_tokens=getattr(task, 'max_tokens', 4000)
        )

        try:
            response_chunks = []
            async for message in query(prompt=task.prompt, options=options):
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            response_chunks.append(block.text)

            return TaskResult(
                task_id=task.id,
                success=True,
                result=''.join(response_chunks),
                metadata={"adapter": "claude"}
            )
        except Exception as e:
            return TaskResult(
                task_id=task.id,
                success=False,
                error=str(e),
                metadata={"adapter": "claude"}
            )
```

### 3. 本地锁管理器 (local_lock.py)

```python
class LocalLockManager:
    """本地文件锁管理器"""

    def __init__(self, lock_dir: Path = Path.home() / ".aiswitch" / "locks"):
        self.lock_dir = lock_dir
        self.active_locks: Dict[str, FileLock] = {}

    @contextmanager
    def acquire_lock(self, lock_name: str, timeout: float = 30.0):
        """获取文件锁"""

    def release_all_locks(self):
        """释放所有锁"""

    def cleanup_stale_locks(self):
        """清理过期锁文件"""

class FileLock:
    """文件锁实现"""

    def __init__(self, lock_file: Path, timeout: float = 30.0):
        self.lock_file = lock_file
        self.timeout = timeout
        self.fd: Optional[int] = None

    def acquire(self) -> bool:
        """获取锁"""

    def release(self):
        """释放锁"""
```

### 4. JSON-RPC通信层 (jsonrpc_stdio.py)

```python
class JSONRPCClient:
    """JSON-RPC客户端，用于与子进程通信"""

    def __init__(self, process: subprocess.Popen):
        self.process = process
        self.request_id = 0
        self.pending_requests: Dict[int, asyncio.Future] = {}

    async def call(self, method: str, params: Dict = None) -> Any:
        """调用RPC方法"""

    async def notify(self, method: str, params: Dict = None):
        """发送通知（无需响应）"""

    async def _handle_response(self, response: Dict):
        """处理RPC响应"""

class JSONRPCServer:
    """JSON-RPC服务器，用于代理适配器"""

    def __init__(self):
        self.methods: Dict[str, Callable] = {}

    def register_method(self, name: str, method: Callable):
        """注册RPC方法"""

    async def handle_request(self, request: Dict) -> Optional[Dict]:
        """处理RPC请求"""
```

### 5. 指标收集器 (metrics_collector.py)

```python
class MetricsCollector:
    """指标收集器，负责收集和存储各种指标"""

    def __init__(self):
        self.metrics_store = MetricsStore()
        self.collectors: List[BaseCollector] = []

    def collect_agent_metrics(self, agent_id: str) -> AgentMetrics:
        """收集代理指标"""

    def collect_system_metrics(self) -> SystemMetrics:
        """收集系统指标"""

    def store_metrics(self, metrics: BaseMetrics):
        """存储指标数据"""

@dataclass
class AgentMetrics:
    """代理指标数据"""
    agent_id: str
    timestamp: datetime
    status: AgentStatus
    cpu_percent: float
    memory_mb: float
    tokens_input: int
    tokens_output: int
    response_time_ms: float
    error_count: int
    task_count: int
```

### 6. Token追踪器 (token_tracker.py)

```python
class TokenTracker:
    """Token使用追踪器"""

    def __init__(self):
        self.usage_store = TokenUsageStore()

    def track_usage(self, agent_id: str, input_tokens: int, output_tokens: int, cost: float = None):
        """记录token使用"""

    def get_usage_summary(self, agent_id: str = None, timeframe: str = "day") -> TokenUsageSummary:
        """获取使用摘要"""

    def check_quota(self, agent_id: str) -> QuotaStatus:
        """检查配额状态"""

    def set_quota_limit(self, agent_id: str, daily_limit: int):
        """设置配额限制"""

@dataclass
class TokenUsageSummary:
    """Token使用摘要"""
    total_input_tokens: int
    total_output_tokens: int
    total_cost: float
    avg_tokens_per_request: float
    peak_usage_time: datetime
    quota_remaining: int
```

### 7. 动态环境管理器 (env_manager.py)

```python
class DynamicEnvManager:
    """动态环境变量管理器"""

    def __init__(self):
        self.preset_manager = PresetManager()
        self.active_envs: Dict[str, Dict[str, str]] = {}

    async def switch_agent_env(self, agent_id: str, preset: str) -> bool:
        """为指定代理切换环境变量"""

    def create_env_snapshot(self, agent_id: str) -> EnvSnapshot:
        """创建环境变量快照"""

    async def rollback_env(self, agent_id: str, snapshot: EnvSnapshot):
        """回滚环境变量"""

    def validate_env_switch(self, preset: str) -> ValidationResult:
        """验证环境切换的有效性"""

@dataclass
class EnvSnapshot:
    """环境变量快照"""
    agent_id: str
    timestamp: datetime
    variables: Dict[str, str]
    preset_name: str
```

## 通信机制

### SDK直接调用

不再使用JSON-RPC 2.0进程间通信，而是直接调用各种AI SDK：

#### Claude SDK集成
```python
from claude_agent_sdk import query, ClaudeAgentOptions

# 直接调用Claude SDK
async for message in query(prompt=task.prompt, options=options):
    # 处理响应
    pass
```

#### OpenAI SDK集成
```python
from openai import AsyncOpenAI

client = AsyncOpenAI(api_key=api_key)
response = await client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": task.prompt}]
)
```

#### 内部API方法
- `agent.initialize()` - 代理初始化
- `agent.execute_task()` - 执行任务
- `agent.switch_environment()` - 切换环境
- `agent.get_status()` - 获取状态
- `coordinator.execute_parallel()` - 并行执行
- `coordinator.execute_sequential()` - 串行执行

## 错误处理策略

### 1. SDK级错误
- **连接超时**: 自动重试机制，指数退避
- **API限流**: 智能等待和重试
- **认证失败**: 环境变量验证和错误提示

### 2. 任务级错误
- **任务超时**: 可配置超时时间，自动取消
- **执行失败**: 错误传播，结果标记失败状态
- **部分失败**: 继续执行其他代理，聚合部分结果

### 3. 协调级错误
- **代理不可用**: 跳过失败代理，继续执行
- **状态不一致**: 状态同步和修复
- **资源竞争**: 基于优先级的任务调度

## 性能考虑

### 1. 并发处理
- **异步IO**: 全面使用asyncio进行异步处理
- **SDK连接池**: 复用SDK连接，减少初始化开销
- **任务队列**: 高效的任务分配和执行

### 2. 内存管理
- **状态清理**: 定期清理过期状态和日志
- **流式处理**: 大型任务结果流式传输
- **SDK缓存**: 缓存SDK实例和认证信息

### 3. 网络优化
- **连接复用**: 复用HTTP连接到AI服务
- **请求合并**: 在可能的情况下合并请求
- **智能重试**: 基于错误类型的重试策略

## 安全考虑

### 1. 认证安全
- **环境隔离**: 每个代理独立的环境变量空间
- **凭据管理**: API密钥等敏感信息安全存储
- **最小权限**: 代理只能访问必要的资源

### 2. 数据安全
- **敏感信息**: API密钥等加密存储
- **传输安全**: HTTPS加密传输到AI服务
- **日志脱敏**: 避免在日志中记录敏感信息

### 3. 输入安全
- **输入验证**: 严格的输入验证和清理
- **注入防护**: 防止prompt注入攻击
- **错误处理**: 避免敏感信息泄露

## 监控和可观测性

### 1. 指标监控
- **实时指标**: CPU、内存、token使用等
- **趋势分析**: 历史数据趋势分析
- **异常检测**: 自动异常检测和告警

### 2. 日志系统
- **结构化日志**: JSON格式结构化日志
- **日志聚合**: 多代理日志统一聚合
- **查询分析**: 支持复杂查询和分析

### 3. 健康检查
- **进程健康**: 定期健康检查
- **服务依赖**: 依赖服务状态监控
- **自动恢复**: 故障自动恢复机制

这个基于SDK直接集成的架构设计为aiswitch提供了一个简洁、稳定、高效的多代理协调平台，摒弃了复杂的进程间通信，直接利用各种AI SDK的强大功能。