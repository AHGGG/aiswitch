# AISwitch 多代理界面使用指南

AISwitch 现在支持全新的多代理Textual界面，提供更强大的AI代理协调和管理功能。

## 快速开始

### 1. 启动多代理界面

```bash
# 使用默认预设启动
aiswitch apply ds --interactive --interactive-mode multi-agent

# 或者直接指定多代理模式（auto模式会优先选择多代理界面）
aiswitch apply ds --interactive
```

### 2. 界面概览

新的多代理界面包含四个主要区域：

```
┌─────────────────────────────────────────────────────────┐
│                    AISwitch Header                      │
├─────────────────────────────────────────────────────────┤
│ Agent: [Claude ▼] ● Ready                              │  <- 代理选择器
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Chat Display Area                                     │  <- 聊天显示区域
│  👤 You: Hello!                                        │
│  🤖 Claude: Hi there! How can I help you today?       │
│                                                         │
├─────────────────────────────────────────────────────────┤
│ [Type your message...          ] [Send] [⚙️]           │  <- 输入面板
├─────────────────────────────────────────────────────────┤
│ ● Messages: 2  Preset: ds  Mode: sequential  Ready     │  <- 状态栏
└─────────────────────────────────────────────────────────┘
```

## 核心功能

### 代理管理

- **代理选择**: 使用顶部的下拉菜单切换不同的AI代理
- **状态指示**: 实时显示代理的连接状态（绿色=在线，黄色=忙碌，红色=错误）
- **多代理支持**: 支持Claude、OpenAI等多种代理（需要相应的API密钥）

### 智能聊天

- **富文本显示**: 支持代码高亮、语法着色
- **消息类型**: 用户消息（👤）、代理响应（🤖）、系统信息（ℹ️）
- **错误处理**: 优雅地显示错误信息和重试机制
- **代码块**: 自动识别和高亮显示代码内容

### 执行模式

- **Sequential（串行）**: 依次在多个代理上执行命令
- **Parallel（并行）**: 同时在多个代理上执行命令
- **切换模式**: 使用快捷键 Ctrl+1（串行）和 Ctrl+2（并行）

## 快捷键

| 快捷键 | 功能 |
|--------|------|
| `Ctrl+Q` | 退出应用 |
| `Ctrl+L` | 清空聊天记录 |
| `Ctrl+S` | 保存当前会话 |
| `Ctrl+O` | 加载保存的会话 |
| `Tab` | 切换到下一个代理 |
| `Shift+Tab` | 切换到上一个代理 |
| `Ctrl+1` | 设置为串行模式 |
| `Ctrl+2` | 设置为并行模式 |
| `Ctrl+R` | 刷新代理列表 |
| `F1` | 显示帮助 |
| `F2` | 显示设置 |

## 命令系统

在输入框中，你可以使用以下命令：

| 命令 | 功能 |
|------|------|
| `/clear` | 清空聊天历史 |
| `/agent <name>` | 切换到指定代理 |
| `/mode <mode>` | 设置执行模式（parallel/sequential） |
| `/preset <name>` | 切换到指定预设 |
| `/save` | 保存当前会话 |
| `/load <name>` | 加载保存的会话 |
| `/help` | 显示命令帮助 |

## 高级功能

### 会话管理

- **自动保存**: 会话状态会自动保存到 `~/.aiswitch/sessions/`
- **手动保存**: 使用 `Ctrl+S` 或 `/save` 命令保存会话
- **加载会话**: 使用 `Ctrl+O` 或 `/load <name>` 命令加载保存的会话

### 多代理协调

1. **并行执行**: 同一个消息发送给所有活跃代理，对比不同的响应
2. **串行执行**: 将任务依次交给不同代理处理，形成处理链
3. **智能路由**: 根据任务类型自动选择最适合的代理

### 环境变量管理

- **预设切换**: 使用 `/preset <name>` 动态切换API配置
- **实时应用**: 预设变更立即应用到所有代理
- **安全处理**: 敏感信息（API密钥）会被自动隐藏

## 故障排除

### 常见问题

1. **"Claude SDK not available"**
   ```bash
   # 安装Claude Agent SDK
   pip install claude-agent-sdk
   ```

2. **"Missing required environment variables"**
   ```bash
   # 确保设置了必要的API密钥
   aiswitch add ds ANTHROPIC_API_KEY your-key-here
   ```

3. **"Agent not found"**
   - 检查代理是否正确注册
   - 使用 `Ctrl+R` 刷新代理列表

### 调试模式

如果遇到问题，可以查看详细错误信息：

```bash
# 直接使用Python运行以查看详细错误
python -c "from aiswitch.textual_ui.app import run_aiswitch_app; run_aiswitch_app('ds')"
```

## 与旧版本的差异

| 功能 | 旧版本 | 新版本 |
|------|-------|--------|
| 界面 | 基础终端界面 | 富文本Textual界面 |
| 代理数量 | 单个 | 多个同时管理 |
| 执行模式 | 仅单一 | 串行/并行可选 |
| 状态显示 | 基础文本 | 实时状态指示器 |
| 快捷键 | 有限 | 完整快捷键支持 |
| 会话管理 | 无 | 保存/加载会话 |
| 命令系统 | 无 | 内建命令系统 |

## 扩展开发

新架构支持轻松添加新的代理类型：

1. 继承 `BaseAdapter` 类
2. 实现必要的方法（`initialize`, `execute_task`, `switch_environment`）
3. 在 `MultiAgentManager` 中注册新适配器

详细的开发文档请参考 `docs/textual-design.md`。

---

**注意**: 此新界面是实验性功能，如果遇到问题可以回退到原有的单代理模式：
```bash
aiswitch apply ds --interactive --interactive-mode textual
```