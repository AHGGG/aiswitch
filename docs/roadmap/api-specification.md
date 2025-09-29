# aiswitch 多代理系统 API 规范

## 概述

本文档定义了aiswitch多代理系统中各组件间通信的API规范，基于JSON-RPC 2.0协议，扩展了多代理协调所需的方法和数据结构。

## 协议基础

### 传输层
- **主要传输方式**: stdio (标准输入/输出)
- **备用传输方式**: Unix Domain Socket, TCP Socket
- **数据格式**: JSON
- **编码**: UTF-8
- **消息分隔**: 换行符 (`\n`)

### JSON-RPC 2.0 基础结构

所有消息都遵循JSON-RPC 2.0规范：

```json
{
  "jsonrpc": "2.0",
  "method": "method_name",
  "params": {},
  "id": 1
}
```

**响应格式**:
```json
{
  "jsonrpc": "2.0",
  "result": {},
  "id": 1
}
```

**错误格式**:
```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32000,
    "message": "Error message",
    "data": {}
  },
  "id": 1
}
```

## 数据类型定义

### 基础数据类型

#### AgentStatus
```typescript
enum AgentStatus {
  STOPPED = "stopped",
  STARTING = "starting",
  RUNNING = "running",
  BUSY = "busy",
  IDLE = "idle",
  ERROR = "error",
  STOPPING = "stopping"
}
```

#### TaskStatus
```typescript
enum TaskStatus {
  PENDING = "pending",
  ASSIGNED = "assigned",
  RUNNING = "running",
  COMPLETED = "completed",
  FAILED = "failed",
  CANCELLED = "cancelled",
  TIMEOUT = "timeout"
}
```

#### CoordinationMode
```typescript
enum CoordinationMode {
  STRICT = "strict",     // 严格协调，需要锁机制
  LOOSE = "loose",       // 松散协调，仅状态同步
  ISOLATED = "isolated"  // 完全隔离，无协调
}
```

### 复合数据类型

#### Task
```typescript
interface Task {
  id: string;                    // 任务唯一标识
  type: string;                  // 任务类型
  payload: any;                  // 任务载荷
  timeout?: number;              // 超时时间(秒)
  priority?: number;             // 优先级 (1-10)
  metadata?: Record<string, any>; // 元数据
  created_at: string;            // 创建时间 (ISO 8601)
}
```

#### TaskResult
```typescript
interface TaskResult {
  task_id: string;               // 任务ID
  agent_id: string;              // 代理ID
  status: TaskStatus;            // 任务状态
  result?: any;                  // 执行结果
  error?: string;                // 错误信息
  tokens_used?: TokenUsage;      // Token使用量
  execution_time_ms: number;     // 执行时间(毫秒)
  completed_at: string;          // 完成时间
}
```

#### AgentMetrics
```typescript
interface AgentMetrics {
  agent_id: string;              // 代理ID
  timestamp: string;             // 时间戳
  status: AgentStatus;           // 当前状态
  cpu_percent: number;           // CPU使用率
  memory_mb: number;             // 内存使用(MB)
  disk_io_kb: number;            // 磁盘IO(KB)
  network_io_kb: number;         // 网络IO(KB)
  response_time_ms: number;      // 平均响应时间
  error_count: number;           // 错误计数
  task_count: number;            // 任务计数
  uptime_seconds: number;        // 运行时长
}
```

#### TokenUsage
```typescript
interface TokenUsage {
  input_tokens: number;          // 输入token数
  output_tokens: number;         // 输出token数
  total_tokens: number;          // 总token数
  cost_usd?: number;             // 费用(美元)
  model?: string;                // 使用的模型
}
```

#### EnvSnapshot
```typescript
interface EnvSnapshot {
  snapshot_id: string;           // 快照ID
  agent_id: string;              // 代理ID
  timestamp: string;             // 创建时间
  preset_name: string;           // 预设名称
  variables: Record<string, string>; // 环境变量
  checksum: string;              // 数据校验和
}
```

## API 方法定义

### 1. 代理生命周期管理

#### 1.1 agent.initialize
初始化代理实例。

**请求参数**:
```typescript
interface InitializeParams {
  agent_id: string;              // 代理唯一标识
  preset: string;                // 预设名称
  config?: Record<string, any>;  // 额外配置
  timeout?: number;              // 初始化超时
}
```

**响应结果**:
```typescript
interface InitializeResult {
  agent_id: string;
  status: AgentStatus;
  capabilities: string[];        // 代理能力列表
  version: string;               // 代理版本
  initialized_at: string;
}
```

**示例**:
```json
{
  "jsonrpc": "2.0",
  "method": "agent.initialize",
  "params": {
    "agent_id": "claude-001",
    "preset": "anthropic-claude",
    "config": {
      "max_tokens": 4000,
      "temperature": 0.7
    },
    "timeout": 30
  },
  "id": 1
}
```

#### 1.2 agent.shutdown
优雅关闭代理实例。

**请求参数**:
```typescript
interface ShutdownParams {
  force?: boolean;               // 是否强制关闭
  timeout?: number;              // 关闭超时
}
```

**响应结果**:
```typescript
interface ShutdownResult {
  status: AgentStatus;
  shutdown_at: string;
  final_metrics: AgentMetrics;
}
```

#### 1.3 agent.restart
重启代理实例。

**请求参数**:
```typescript
interface RestartParams {
  preserve_state?: boolean;      // 是否保留状态
  timeout?: number;              // 重启超时
}
```

#### 1.4 agent.status
获取代理状态。

**请求参数**: 无

**响应结果**:
```typescript
interface StatusResult {
  agent_id: string;
  status: AgentStatus;
  current_task?: string;         // 当前执行的任务ID
  metrics: AgentMetrics;
  last_heartbeat: string;
}
```

### 2. 任务执行管理

#### 2.1 task.assign
分配任务给代理。

**请求参数**:
```typescript
interface AssignTaskParams {
  task: Task;
  coordination_mode?: CoordinationMode;
  dependencies?: string[];       // 依赖的任务ID列表
}
```

**响应结果**:
```typescript
interface AssignTaskResult {
  task_id: string;
  assigned_at: string;
  estimated_completion: string;
}
```

#### 2.2 task.cancel
取消正在执行的任务。

**请求参数**:
```typescript
interface CancelTaskParams {
  task_id: string;
  reason?: string;               // 取消原因
}
```

#### 2.3 task.status
查询任务状态。

**请求参数**:
```typescript
interface TaskStatusParams {
  task_id: string;
}
```

**响应结果**:
```typescript
interface TaskStatusResult {
  task: Task;
  status: TaskStatus;
  progress?: number;             // 进度百分比 (0-100)
  result?: TaskResult;
  updated_at: string;
}
```

#### 2.4 task.result
获取任务执行结果。

**请求参数**:
```typescript
interface TaskResultParams {
  task_id: string;
  include_metadata?: boolean;    // 是否包含元数据
}
```

**响应结果**: `TaskResult`

### 3. 环境管理

#### 3.1 env.switch
切换环境变量预设。

**请求参数**:
```typescript
interface SwitchEnvParams {
  preset: string;                // 新预设名称
  variables?: Record<string, string>; // 覆盖变量
  create_snapshot?: boolean;     // 是否创建切换前快照
}
```

**响应结果**:
```typescript
interface SwitchEnvResult {
  previous_preset: string;
  current_preset: string;
  snapshot_id?: string;          // 快照ID（如果创建了快照）
  switched_at: string;
}
```

#### 3.2 env.snapshot
创建环境变量快照。

**请求参数**:
```typescript
interface CreateSnapshotParams {
  snapshot_id?: string;          // 可选的快照ID
  description?: string;          // 快照描述
}
```

**响应结果**: `EnvSnapshot`

#### 3.3 env.rollback
回滚到指定快照。

**请求参数**:
```typescript
interface RollbackParams {
  snapshot_id: string;
  force?: boolean;               // 强制回滚
}
```

**响应结果**:
```typescript
interface RollbackResult {
  snapshot: EnvSnapshot;
  rolled_back_at: string;
}
```

#### 3.4 env.list_snapshots
列出所有快照。

**请求参数**: 无

**响应结果**:
```typescript
interface ListSnapshotsResult {
  snapshots: EnvSnapshot[];
  total_count: number;
}
```

### 4. 指标和监控

#### 4.1 metrics.report
上报代理指标数据。

**请求参数**:
```typescript
interface ReportMetricsParams {
  metrics: AgentMetrics;
  additional_data?: Record<string, any>;
}
```

**响应结果**:
```typescript
interface ReportMetricsResult {
  reported_at: string;
  accepted: boolean;
}
```

#### 4.2 metrics.query
查询历史指标数据。

**请求参数**:
```typescript
interface QueryMetricsParams {
  agent_id?: string;             // 代理ID过滤
  start_time?: string;           // 开始时间
  end_time?: string;             // 结束时间
  metric_types?: string[];       // 指标类型过滤
  aggregation?: "avg" | "max" | "min" | "sum"; // 聚合方式
  interval?: number;             // 采样间隔(秒)
}
```

**响应结果**:
```typescript
interface QueryMetricsResult {
  metrics: AgentMetrics[];
  aggregated?: Record<string, number>;
  total_count: number;
}
```

#### 4.3 tokens.usage
上报Token使用情况。

**请求参数**:
```typescript
interface ReportTokenUsageParams {
  task_id: string;
  usage: TokenUsage;
}
```

#### 4.4 tokens.summary
获取Token使用摘要。

**请求参数**:
```typescript
interface TokenSummaryParams {
  agent_id?: string;
  timeframe?: "hour" | "day" | "week" | "month";
  start_time?: string;
  end_time?: string;
}
```

**响应结果**:
```typescript
interface TokenSummaryResult {
  total_usage: TokenUsage;
  usage_by_model: Record<string, TokenUsage>;
  usage_by_task_type: Record<string, TokenUsage>;
  peak_usage_time: string;
  cost_breakdown: Record<string, number>;
}
```

### 5. 协调和通信

#### 5.1 coordination.lock
申请协调锁。

**请求参数**:
```typescript
interface AcquireLockParams {
  lock_name: string;             // 锁名称
  timeout?: number;              // 超时时间
  lock_type?: "shared" | "exclusive"; // 锁类型
}
```

**响应结果**:
```typescript
interface AcquireLockResult {
  lock_id: string;               // 锁ID
  acquired_at: string;
  expires_at: string;
}
```

#### 5.2 coordination.unlock
释放协调锁。

**请求参数**:
```typescript
interface ReleaseLockParams {
  lock_id: string;
}
```

#### 5.3 coordination.heartbeat
发送心跳信号。

**请求参数**:
```typescript
interface HeartbeatParams {
  agent_id: string;
  status: AgentStatus;
  current_tasks?: string[];      // 当前任务列表
}
```

**响应结果**:
```typescript
interface HeartbeatResult {
  acknowledged_at: string;
  server_time: string;
  coordination_status: "active" | "standby" | "degraded";
}
```

### 6. 事件和通知

#### 6.1 event.subscribe
订阅事件通知。

**请求参数**:
```typescript
interface SubscribeParams {
  event_types: string[];         // 事件类型列表
  filter?: Record<string, any>;  // 事件过滤条件
}
```

#### 6.2 event.unsubscribe
取消事件订阅。

**请求参数**:
```typescript
interface UnsubscribeParams {
  subscription_id: string;
}
```

#### 6.3 event.publish
发布事件。

**请求参数**:
```typescript
interface PublishEventParams {
  event_type: string;
  data: any;
  timestamp?: string;
  agent_id?: string;
}
```

## 错误代码定义

### JSON-RPC 标准错误代码
- `-32700`: Parse error (解析错误)
- `-32600`: Invalid Request (无效请求)
- `-32601`: Method not found (方法未找到)
- `-32602`: Invalid params (无效参数)
- `-32603`: Internal error (内部错误)

### aiswitch 扩展错误代码

#### 代理相关错误 (-40000 ~ -40099)
- `-40001`: Agent not found (代理未找到)
- `-40002`: Agent already exists (代理已存在)
- `-40003`: Agent initialization failed (代理初始化失败)
- `-40004`: Agent not responding (代理无响应)
- `-40005`: Agent busy (代理忙碌)

#### 任务相关错误 (-40100 ~ -40199)
- `-40101`: Task not found (任务未找到)
- `-40102`: Task already exists (任务已存在)
- `-40103`: Task timeout (任务超时)
- `-40104`: Task cancelled (任务被取消)
- `-40105`: Task dependencies not met (任务依赖未满足)

#### 环境相关错误 (-40200 ~ -40299)
- `-40201`: Preset not found (预设未找到)
- `-40202`: Environment switch failed (环境切换失败)
- `-40203`: Snapshot not found (快照未找到)
- `-40204`: Rollback failed (回滚失败)
- `-40205`: Environment validation failed (环境验证失败)

#### 协调相关错误 (-40300 ~ -40399)
- `-40301`: Lock acquisition failed (锁获取失败)
- `-40302`: Lock not found (锁未找到)
- `-40303`: Lock timeout (锁超时)
- `-40304`: Coordination conflict (协调冲突)
- `-40305`: Resource contention (资源竞争)

#### 系统相关错误 (-40400 ~ -40499)
- `-40401`: Insufficient resources (资源不足)
- `-40402`: Permission denied (权限拒绝)
- `-40403`: Configuration error (配置错误)
- `-40404`: Storage error (存储错误)
- `-40405`: Network error (网络错误)

## 使用示例

### 基本代理交互流程

```bash
# 1. 初始化代理
curl -X POST -H "Content-Type: application/json" -d '{
  "jsonrpc": "2.0",
  "method": "agent.initialize",
  "params": {
    "agent_id": "claude-001",
    "preset": "anthropic-claude"
  },
  "id": 1
}' http://localhost:8080/rpc

# 2. 分配任务
curl -X POST -H "Content-Type: application/json" -d '{
  "jsonrpc": "2.0",
  "method": "task.assign",
  "params": {
    "task": {
      "id": "task-001",
      "type": "code_generation",
      "payload": {
        "prompt": "Generate a Python function to calculate fibonacci",
        "language": "python"
      },
      "timeout": 60
    }
  },
  "id": 2
}' http://localhost:8080/rpc

# 3. 查询任务状态
curl -X POST -H "Content-Type: application/json" -d '{
  "jsonrpc": "2.0",
  "method": "task.status",
  "params": {
    "task_id": "task-001"
  },
  "id": 3
}' http://localhost:8080/rpc

# 4. 获取任务结果
curl -X POST -H "Content-Type: application/json" -d '{
  "jsonrpc": "2.0",
  "method": "task.result",
  "params": {
    "task_id": "task-001"
  },
  "id": 4
}' http://localhost:8080/rpc
```

### 环境切换流程

```json
// 1. 创建当前环境快照
{
  "jsonrpc": "2.0",
  "method": "env.snapshot",
  "params": {
    "snapshot_id": "before-switch",
    "description": "切换前备份"
  },
  "id": 1
}

// 2. 切换到新环境
{
  "jsonrpc": "2.0",
  "method": "env.switch",
  "params": {
    "preset": "openai-gpt4",
    "create_snapshot": true
  },
  "id": 2
}

// 3. 如果需要，回滚到之前的快照
{
  "jsonrpc": "2.0",
  "method": "env.rollback",
  "params": {
    "snapshot_id": "before-switch"
  },
  "id": 3
}
```

### 指标查询示例

```json
// 查询最近1小时的指标数据
{
  "jsonrpc": "2.0",
  "method": "metrics.query",
  "params": {
    "agent_id": "claude-001",
    "start_time": "2024-01-01T10:00:00Z",
    "end_time": "2024-01-01T11:00:00Z",
    "metric_types": ["cpu_percent", "memory_mb", "response_time_ms"],
    "aggregation": "avg",
    "interval": 300
  },
  "id": 1
}

// Token使用摘要
{
  "jsonrpc": "2.0",
  "method": "tokens.summary",
  "params": {
    "agent_id": "claude-001",
    "timeframe": "day"
  },
  "id": 2
}
```

## 版本兼容性

### 协议版本控制
- 主版本号变更: 不兼容的API变更
- 次版本号变更: 向后兼容的功能添加
- 修订版本号变更: 向后兼容的问题修复

### 当前版本
- **协议版本**: 1.0.0
- **JSON-RPC版本**: 2.0
- **最低支持的aiswitch版本**: 0.2.0

### 版本协商
代理在初始化时会声明支持的协议版本，协调器会选择兼容的最高版本进行通信。

```json
{
  "jsonrpc": "2.0",
  "method": "agent.initialize",
  "params": {
    "agent_id": "claude-001",
    "protocol_version": "1.0.0",
    "supported_features": ["env_switching", "metrics_reporting"]
  },
  "id": 1
}
```

## 安全考虑

### 输入验证
- 所有API参数必须经过严格验证
- 防止JSON注入和其他注入攻击
- 限制字符串长度和数据大小

### 权限控制
- 代理只能访问分配给它的资源
- 敏感操作需要额外验证
- 审计日志记录所有关键操作

### 数据保护
- 敏感数据（如API密钥）加密传输和存储
- 定期清理临时数据和日志
- 防止信息泄露到错误消息中

这个API规范为aiswitch多代理系统提供了完整的通信协议定义，确保了各组件间的可靠、高效通信。