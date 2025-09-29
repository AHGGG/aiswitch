# aiswitch 多代理并发系统架构设计

## 概述

aiswitch多代理系统旨在实现一个local-first的多CLI代理协调平台，支持同时管理和协调多个AI CLI工具（如claude、codex等），提供统一的接口和强大的协调机制。

## 设计原则

### 1. Local-first
- **无外部依赖**: 不依赖Redis、数据库等外部服务
- **本地状态管理**: 所有状态存储在本地文件系统
- **离线可用**: 完全离线环境下可正常运行

### 2. 父子进程架构
- **父进程**: aiswitch作为协调器和管理中心
- **子进程**: 各种AI CLI工具作为独立的代理进程
- **通信机制**: 基于stdio的JSON-RPC 2.0协议

### 3. 高可用性
- **故障隔离**: 单个代理故障不影响其他代理
- **自动恢复**: 支持代理进程自动重启
- **状态持久化**: 关键状态持久化到本地文件

## 系统架构

### 核心组件图

```
┌─────────────────────────────────────────────────────────┐
│                    aiswitch (父进程)                     │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────┐ │
│  │   多代理协调器   │  │    指标收集器    │  │ 环境管理器│ │
│  └─────────────────┘  └─────────────────┘  └──────────┘ │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────┐ │
│  │  代理进程管理器  │  │   Token追踪器   │  │ 本地锁管理│ │
│  └─────────────────┘  └─────────────────┘  └──────────┘ │
│  ┌─────────────────┐  ┌─────────────────┐               │
│  │  JSON-RPC通信   │  │   代理注册器    │               │
│  └─────────────────┘  └─────────────────┘               │
└─────────────────────────────────────────────────────────┘
           │ stdio/JSON-RPC        │ stdio/JSON-RPC        │
┌─────────────────┐      ┌─────────────────┐      ┌──────────────┐
│ claude-cli      │      │ codex-cli       │      │ other-agent  │
│ (子进程1)       │      │ (子进程2)       │      │ (子进程N)    │
└─────────────────┘      └─────────────────┘      └──────────────┘
```

### 文件系统结构

```
~/.aiswitch/
├── config/
│   ├── presets.yaml          # 预设配置
│   ├── agents.yaml           # 代理配置
│   └── coordination.yaml     # 协调配置
├── locks/
│   ├── global.lock           # 全局操作锁
│   ├── resource_*.lock       # 资源特定锁
│   └── task_*.lock           # 任务执行锁
├── state/
│   ├── agents.json           # 代理状态
│   ├── tasks.json            # 任务状态
│   ├── metrics.json          # 指标数据
│   └── tokens.json           # Token统计
├── logs/
│   ├── coordinator.log       # 协调器日志
│   ├── agents/               # 代理日志目录
│   └── metrics/              # 指标日志
└── tmp/
    ├── sockets/              # 临时socket文件
    └── pids/                 # 进程ID文件
```

## 核心模块设计

### 1. 多代理协调器 (multi_agent.py)

```python
class MultiAgentCoordinator:
    """多代理协调器，负责任务分配和结果聚合"""

    def __init__(self):
        self.agent_manager = AgentProcessManager()
        self.lock_manager = LocalLockManager()
        self.metrics_collector = MetricsCollector()
        self.token_tracker = TokenTracker()
        self.env_manager = DynamicEnvManager()

    async def execute_parallel(self, preset: str, agents: List[str], task: str):
        """并行执行任务"""

    async def execute_sequential(self, preset: str, agents: List[str], task: str):
        """串行执行任务"""

    def aggregate_results(self, results: List[AgentResult]) -> AggregatedResult:
        """聚合多个代理的执行结果"""
```

### 2. 代理进程管理器 (agent_process.py)

```python
class AgentProcessManager:
    """代理进程管理器，负责子进程的生命周期管理"""

    def __init__(self):
        self.processes: Dict[str, AgentProcess] = {}
        self.metrics_collector = MetricsCollector()

    async def start_agent(self, agent_id: str, preset: str) -> AgentProcess:
        """启动代理进程"""

    async def stop_agent(self, agent_id: str):
        """停止代理进程"""

    def get_agent_status(self, agent_id: str) -> AgentStatus:
        """获取代理状态"""

    async def restart_agent(self, agent_id: str):
        """重启代理进程"""

class AgentProcess:
    """单个代理进程的封装"""

    def __init__(self, agent_id: str, command: List[str], env: Dict[str, str]):
        self.agent_id = agent_id
        self.process: Optional[subprocess.Popen] = None
        self.rpc_client: Optional[JSONRPCClient] = None
        self.status = AgentStatus.STOPPED
        self.metrics = AgentMetrics()

    async def start(self):
        """启动进程并建立RPC连接"""

    async def send_task(self, task: Task) -> TaskResult:
        """发送任务给代理"""

    async def switch_env(self, preset: str, variables: Dict[str, str]):
        """动态切换环境变量"""

    def collect_metrics(self) -> AgentMetrics:
        """收集进程指标"""
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

## 通信协议

### JSON-RPC 2.0 扩展

基于标准JSON-RPC 2.0协议，添加以下自定义方法：

#### 代理管理方法
- `agent.initialize` - 代理初始化
- `agent.shutdown` - 代理关闭
- `agent.status` - 获取状态
- `agent.restart` - 重启代理

#### 任务执行方法
- `task.assign` - 分配任务
- `task.cancel` - 取消任务
- `task.status` - 查询任务状态
- `task.result` - 获取任务结果

#### 环境管理方法
- `env.switch` - 切换环境变量
- `env.snapshot` - 创建环境快照
- `env.rollback` - 回滚环境

#### 指标上报方法
- `metrics.report` - 上报指标数据
- `metrics.query` - 查询指标
- `tokens.usage` - 上报token使用

## 错误处理策略

### 1. 进程级错误
- **进程崩溃**: 自动重启机制，最大重试3次
- **通信中断**: 重建RPC连接，超时机制
- **资源不足**: 降级运行，暂停部分代理

### 2. 任务级错误
- **任务超时**: 可配置超时时间，自动取消
- **执行失败**: 错误传播，结果标记失败状态
- **部分失败**: 继续执行其他代理，聚合部分结果

### 3. 协调级错误
- **锁冲突**: 指数退避重试机制
- **状态不一致**: 状态同步和修复
- **资源竞争**: 优先级调度算法

## 性能考虑

### 1. 并发处理
- **异步IO**: 全面使用asyncio进行异步处理
- **进程池**: 复用进程，减少启动开销
- **连接池**: 复用RPC连接

### 2. 内存管理
- **状态清理**: 定期清理过期状态和日志
- **流式处理**: 大型任务结果流式传输
- **缓存策略**: LRU缓存频繁访问的数据

### 3. 磁盘IO优化
- **批量写入**: 指标数据批量写入磁盘
- **日志轮转**: 自动日志轮转和压缩
- **索引优化**: 关键查询建立索引

## 安全考虑

### 1. 进程隔离
- **环境隔离**: 每个代理独立的环境变量空间
- **权限控制**: 最小权限原则
- **资源限制**: CPU和内存使用限制

### 2. 数据安全
- **敏感信息**: API密钥等敏感信息加密存储
- **访问控制**: 基于角色的访问控制
- **审计日志**: 关键操作审计记录

### 3. 通信安全
- **输入验证**: 严格的输入验证和清理
- **协议安全**: RPC消息完整性校验
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

这个架构设计为aiswitch提供了一个完整、可扩展、高可用的多代理协调平台，能够满足复杂的多CLI工具协同工作需求。