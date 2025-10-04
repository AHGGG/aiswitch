# AISwitch Textual TUI 设计文档

## 概述

本文档描述了AISwitch项目中使用Textual框架构建的终端用户界面(TUI)设计方案。基于对现有实现和Textual官方文档的分析，提供了一套完整的设计指导原则，确保TUI界面的一致性、可维护性和用户体验。

## 当前实现分析

### 现有架构

当前AISwitch的Textual实现位于`aiswitch/textual_interactive.py`，采用了以下架构模式：

```
BaseChatApp (基础聊天应用)
    ├── ClaudeSDKApp (Claude SDK集成)
    └── SubprocessAgentApp (CLI回退模式)
```

### 核心设计模式

1. **基础组件模式**: `BaseChatApp`提供共享的UI布局和通用功能
2. **适配器模式**: 通过不同的App子类适配不同的后端(SDK vs CLI)
3. **响应式编程**: 使用事件驱动处理用户输入和界面更新
4. **异步处理**: 所有IO操作都使用`async/await`模式

### 现有组件分析

#### 1. BaseChatApp - 共享基础类

```python
class BaseChatApp(App[None]):
    """共享的Textual布局和聊天应用助手"""

    # 组件结构
    - Header: 顶部标题栏
    - RichLog (chat_log): 主要的聊天显示区域
    - Input (user_input): 底部输入框
    - Footer: 底部状态栏
```

**优势**:
- 统一的UI布局和样式
- 共享的事件处理逻辑
- 一致的用户体验

**可改进点**:
- 缺乏模块化的组件复用
- 硬编码的布局结构
- 有限的自定义能力

#### 2. ClaudeSDKApp - SDK集成实现

```python
class ClaudeSDKApp(BaseChatApp):
    """基于Claude Agent SDK的交互式会话"""

    # 核心功能
    - 环境变量管理
    - claude-agent-sdk集成
    - 流式响应处理
    - 错误处理和重试
```

**优势**:
- 直接SDK集成，性能优秀
- 完善的错误处理
- 流式响应支持

**可改进点**:
- 可扩展性有限，只支持Claude
- 配置管理较为简单
- 缺乏多代理协调能力

## Textual 框架最佳实践

基于对Textual官方文档的研究，总结以下关键设计原则：

### 1. 响应式编程 (Reactive Programming)

**核心概念**: 使用reactive属性自动处理状态变化

```python
from textual.reactive import reactive

class ChatWidget(Widget):
    # 响应式属性自动触发UI更新
    message_count = reactive(0)
    current_agent = reactive("claude")

    def watch_message_count(self, count: int) -> None:
        """响应消息数量变化"""
        self.update_status(f"Messages: {count}")

    def watch_current_agent(self, agent: str) -> None:
        """响应代理切换"""
        self.update_title(f"Agent: {agent}")
```

**应用场景**:
- 实时消息计数更新
- 代理状态显示
- 连接状态指示
- 配置变更反映

### 2. 组件化设计 (Component Architecture)

**设计原则**: 创建可复用、独立的组件

```python
# 单一职责的组件
class MessageDisplay(Static):
    """消息显示组件"""

class AgentSelector(Select):
    """代理选择组件"""

class StatusIndicator(Widget):
    """状态指示组件"""

# 组合使用
class ChatInterface(Container):
    def compose(self) -> ComposeResult:
        yield MessageDisplay()
        yield AgentSelector()
        yield StatusIndicator()
```

### 3. 事件驱动架构 (Event-Driven Architecture)

**核心模式**: 使用消息传递处理组件间通信

```python
# 自定义事件
class AgentChanged(Message):
    def __init__(self, agent_name: str) -> None:
        super().__init__()
        self.agent_name = agent_name

class MultiAgentController(Widget):
    def on_agent_changed(self, event: AgentChanged) -> None:
        """处理代理切换事件"""
        self.switch_agent(event.agent_name)
```

### 4. 异步操作处理 (Async Operations)

**最佳实践**: 合理使用异步方法处理长时间操作

```python
class AIAgentWidget(Widget):
    async def handle_user_message(self, message: str) -> None:
        """异步处理用户消息"""
        self.show_thinking_indicator()

        try:
            # 异步调用AI API
            response = await self.ai_client.query(message)
            self.display_response(response)
        except Exception as e:
            self.show_error(str(e))
        finally:
            self.hide_thinking_indicator()
```

## 设计方案

### 整体架构

```
AISwitch Textual Application
├── Core Components (核心组件)
│   ├── MultiAgentContainer     # 多代理容器
│   ├── ChatDisplay            # 聊天显示
│   ├── InputPanel             # 输入面板
│   ├── StatusBar              # 状态栏
│   └── AgentSelector          # 代理选择器
├── Agent Adapters (代理适配器)
│   ├── ClaudeAdapter          # Claude SDK适配器
│   ├── OpenAIAdapter          # OpenAI适配器
│   └── GenericAdapter         # 通用CLI适配器
├── Shared Utilities (共享工具)
│   ├── EventBus               # 事件总线
│   ├── StateManager           # 状态管理
│   └── ThemeManager           # 主题管理
└── Application Layer (应用层)
    ├── MainApp                # 主应用
    ├── SettingsScreen         # 设置界面
    └── HelpScreen             # 帮助界面
```

### 核心组件设计

#### 1. MultiAgentContainer - 多代理容器

```python
from textual.reactive import reactive
from textual.widgets import Container
from textual.message import Message

class AgentStatusChanged(Message):
    """代理状态变更事件"""
    def __init__(self, agent_id: str, status: str) -> None:
        super().__init__()
        self.agent_id = agent_id
        self.status = status

class MultiAgentContainer(Container):
    """多代理管理容器"""

    # 响应式属性
    active_agents = reactive(list)  # 活跃代理列表
    current_agent = reactive(str)   # 当前选中代理
    execution_mode = reactive("sequential")  # 执行模式

    def compose(self) -> ComposeResult:
        """组合UI"""
        with Horizontal():
            yield AgentSelector(id="agent_selector")
            yield ModeToggle(id="mode_toggle")
        yield ChatDisplay(id="chat_display")
        yield InputPanel(id="input_panel")
        yield StatusBar(id="status_bar")

    def watch_current_agent(self, agent: str) -> None:
        """响应代理切换"""
        self.post_message(AgentStatusChanged(agent, "selected"))
        self.query_one("#chat_display").switch_agent(agent)

    def watch_execution_mode(self, mode: str) -> None:
        """响应执行模式变更"""
        self.query_one("#mode_toggle").update_display(mode)

    async def execute_command(self, command: str) -> None:
        """执行命令"""
        if self.execution_mode == "parallel":
            await self._execute_parallel(command)
        else:
            await self._execute_sequential(command)
```

#### 2. ChatDisplay - 智能聊天显示

```python
from textual.widgets import RichLog
from textual.reactive import reactive
from rich.text import Text
from rich.syntax import Syntax

class ChatDisplay(RichLog):
    """智能聊天显示组件"""

    current_agent = reactive(str)
    message_count = reactive(0)
    auto_scroll = reactive(True)

    def __init__(self, **kwargs):
        super().__init__(highlight=True, markup=True, **kwargs)
        self.agents_colors = {
            "claude": "blue",
            "openai": "green",
            "generic": "yellow"
        }

    def watch_current_agent(self, agent: str) -> None:
        """代理切换时更新显示样式"""
        self.styles.border = ("solid", self.agents_colors.get(agent, "white"))

    def add_user_message(self, message: str) -> None:
        """添加用户消息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        text = Text()
        text.append(f"[{timestamp}] ", style="dim")
        text.append("👤 You: ", style="bold blue")
        text.append(message)
        self.write(text)
        self.message_count += 1

    def add_agent_message(self, agent: str, message: str, metadata: dict = None) -> None:
        """添加代理消息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        color = self.agents_colors.get(agent, "white")

        text = Text()
        text.append(f"[{timestamp}] ", style="dim")
        text.append(f"🤖 {agent.title()}: ", style=f"bold {color}")

        # 支持代码高亮
        if metadata and metadata.get("language"):
            syntax = Syntax(message, metadata["language"], theme="monokai")
            self.write(text)
            self.write(syntax)
        else:
            text.append(message)
            self.write(text)

        self.message_count += 1

    def add_error_message(self, error: str, agent: str = None) -> None:
        """添加错误消息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        text = Text()
        text.append(f"[{timestamp}] ", style="dim")
        text.append("❌ Error: ", style="bold red")
        if agent:
            text.append(f"[{agent}] ", style="red")
        text.append(error, style="red")
        self.write(text)

    def add_system_message(self, message: str, level: str = "info") -> None:
        """添加系统消息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        icons = {"info": "ℹ️", "warning": "⚠️", "success": "✅"}
        styles = {"info": "blue", "warning": "yellow", "success": "green"}

        text = Text()
        text.append(f"[{timestamp}] ", style="dim")
        text.append(f"{icons.get(level, 'ℹ️')} ", style=styles.get(level, "blue"))
        text.append(message, style=styles.get(level, "blue"))
        self.write(text)

    def switch_agent(self, agent: str) -> None:
        """切换代理"""
        self.current_agent = agent
        self.add_system_message(f"Switched to {agent}", "info")

    def clear_history(self) -> None:
        """清空聊天记录"""
        self.clear()
        self.message_count = 0
        self.add_system_message("Chat history cleared", "info")
```

#### 3. InputPanel - 智能输入面板

```python
from textual.widgets import Input, Container
from textual.containers import Horizontal
from textual.reactive import reactive

class InputPanel(Container):
    """智能输入面板"""

    current_agent = reactive(str)
    input_mode = reactive("single")  # single, multi, command
    suggestions_enabled = reactive(True)

    def compose(self) -> ComposeResult:
        """组合UI"""
        with Horizontal():
            yield Input(
                placeholder="Type your message...",
                id="main_input"
            )
            yield Button("Send", id="send_btn", variant="primary")
            yield Button("⚙️", id="settings_btn", variant="default")

    def watch_current_agent(self, agent: str) -> None:
        """代理变更时更新输入提示"""
        placeholders = {
            "claude": "Ask Claude anything...",
            "openai": "Chat with GPT...",
            "generic": "Enter command..."
        }
        self.query_one("#main_input").placeholder = placeholders.get(
            agent, "Type your message..."
        )

    @on(Input.Submitted, "#main_input")
    async def handle_input_submit(self, event: Input.Submitted) -> None:
        """处理输入提交"""
        message = event.value.strip()
        if not message:
            return

        # 清空输入框
        event.input.value = ""

        # 发送消息事件
        await self.emit_message(message)

    @on(Button.Pressed, "#send_btn")
    async def handle_send_button(self, event: Button.Pressed) -> None:
        """处理发送按钮点击"""
        input_widget = self.query_one("#main_input", Input)
        message = input_widget.value.strip()
        if message:
            input_widget.value = ""
            await self.emit_message(message)

    async def emit_message(self, message: str) -> None:
        """发送消息事件"""
        self.post_message(UserMessageSubmitted(message, self.current_agent))
```

#### 4. AgentSelector - 代理选择器

```python
from textual.widgets import Select, Static
from textual.containers import Horizontal
from textual.reactive import reactive

class AgentSelector(Container):
    """代理选择器组件"""

    available_agents = reactive(list)
    current_agent = reactive(str)
    agent_statuses = reactive(dict)  # {agent_id: status}

    def compose(self) -> ComposeResult:
        """组合UI"""
        with Horizontal():
            yield Static("Agent:", id="label")
            yield Select(
                options=[],
                prompt="Select agent",
                id="agent_select"
            )
            yield Static("●", id="status_indicator")

    def watch_available_agents(self, agents: list) -> None:
        """更新可用代理列表"""
        select = self.query_one("#agent_select", Select)
        select.set_options([
            (agent["name"], agent["id"])
            for agent in agents
        ])

    def watch_current_agent(self, agent: str) -> None:
        """更新当前选中代理"""
        select = self.query_one("#agent_select", Select)
        select.value = agent
        self.update_status_indicator(agent)

    def watch_agent_statuses(self, statuses: dict) -> None:
        """更新代理状态"""
        self.update_status_indicator(self.current_agent)

    def update_status_indicator(self, agent: str) -> None:
        """更新状态指示器"""
        status = self.agent_statuses.get(agent, "unknown")
        indicator = self.query_one("#status_indicator", Static)

        status_styles = {
            "online": "green",
            "busy": "yellow",
            "error": "red",
            "offline": "gray"
        }

        indicator.styles.color = status_styles.get(status, "gray")

    @on(Select.Changed, "#agent_select")
    def handle_agent_change(self, event: Select.Changed) -> None:
        """处理代理选择变更"""
        if event.value != Select.BLANK:
            self.current_agent = event.value
            self.post_message(AgentSelected(event.value))
```

#### 5. StatusBar - 智能状态栏

```python
from textual.widgets import Static
from textual.containers import Horizontal
from textual.reactive import reactive

class StatusBar(Container):
    """智能状态栏"""

    connection_status = reactive("disconnected")
    message_count = reactive(0)
    current_preset = reactive(str)
    execution_mode = reactive("sequential")

    def compose(self) -> ComposeResult:
        """组合UI"""
        with Horizontal():
            yield Static("●", id="connection_indicator")
            yield Static("Messages: 0", id="message_counter")
            yield Static("Preset: none", id="preset_display")
            yield Static("Mode: sequential", id="mode_display")
            yield Static("Ready", id="status_message")

    def watch_connection_status(self, status: str) -> None:
        """更新连接状态"""
        indicator = self.query_one("#connection_indicator", Static)
        colors = {
            "connected": "green",
            "connecting": "yellow",
            "disconnected": "red",
            "error": "red"
        }
        indicator.styles.color = colors.get(status, "gray")

        # 更新状态消息
        messages = {
            "connected": "Connected",
            "connecting": "Connecting...",
            "disconnected": "Disconnected",
            "error": "Connection Error"
        }
        self.query_one("#status_message", Static).update(
            messages.get(status, "Unknown")
        )

    def watch_message_count(self, count: int) -> None:
        """更新消息计数"""
        self.query_one("#message_counter", Static).update(f"Messages: {count}")

    def watch_current_preset(self, preset: str) -> None:
        """更新当前预设"""
        self.query_one("#preset_display", Static).update(f"Preset: {preset}")

    def watch_execution_mode(self, mode: str) -> None:
        """更新执行模式"""
        self.query_one("#mode_display", Static).update(f"Mode: {mode}")

    def show_temporary_message(self, message: str, duration: float = 3.0) -> None:
        """显示临时状态消息"""
        status_widget = self.query_one("#status_message", Static)
        original_message = status_widget.renderable

        # 显示临时消息
        status_widget.update(message)

        # 定时恢复原消息
        self.set_timer(duration, lambda: status_widget.update(original_message))
```

### 事件系统设计

#### 自定义事件

```python
from textual.message import Message

class UserMessageSubmitted(Message):
    """用户消息提交事件"""
    def __init__(self, message: str, agent: str) -> None:
        super().__init__()
        self.message = message
        self.agent = agent

class AgentSelected(Message):
    """代理选择事件"""
    def __init__(self, agent_id: str) -> None:
        super().__init__()
        self.agent_id = agent_id

class AgentResponseReceived(Message):
    """代理响应接收事件"""
    def __init__(self, agent: str, response: str, metadata: dict = None) -> None:
        super().__init__()
        self.agent = agent
        self.response = response
        self.metadata = metadata or {}

class ExecutionModeChanged(Message):
    """执行模式变更事件"""
    def __init__(self, mode: str) -> None:
        super().__init__()
        self.mode = mode

class PresetChanged(Message):
    """预设变更事件"""
    def __init__(self, preset: str) -> None:
        super().__init__()
        self.preset = preset
```

### 主应用设计

```python
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.reactive import reactive
from textual.containers import Container

class AISwitch(App):
    """AISwitch 主应用"""

    CSS_PATH = "aiswitch.tcss"

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", priority=True),
        Binding("ctrl+l", "clear_chat", "Clear Chat"),
        Binding("ctrl+s", "save_session", "Save Session"),
        Binding("ctrl+o", "load_session", "Load Session"),
        Binding("f1", "show_help", "Help"),
        Binding("f2", "show_settings", "Settings"),
        Binding("tab", "next_agent", "Next Agent"),
        Binding("shift+tab", "prev_agent", "Previous Agent"),
    ]

    # 响应式状态
    current_preset = reactive(str)
    available_agents = reactive(list)
    execution_mode = reactive("sequential")

    def __init__(self, preset: str = "default", **kwargs):
        super().__init__(**kwargs)
        self.current_preset = preset
        self.agent_manager = None

    def compose(self) -> ComposeResult:
        """组合主界面"""
        yield Header()
        yield MultiAgentContainer(id="main_container")
        yield Footer()

    async def on_mount(self) -> None:
        """应用启动时初始化"""
        # 初始化代理管理器
        await self.initialize_agent_manager()

        # 加载可用代理
        await self.load_available_agents()

        # 应用当前预设
        await self.apply_preset(self.current_preset)

    async def initialize_agent_manager(self) -> None:
        """初始化代理管理器"""
        from .multi_agent import MultiAgentManager
        self.agent_manager = MultiAgentManager()

        # 注册默认代理
        await self.register_default_agents()

    async def register_default_agents(self) -> None:
        """注册默认代理"""
        # Claude代理
        if claude_agent_sdk_available:
            await self.agent_manager.register_agent(
                "claude", "claude", {}
            )

        # 可以添加其他代理注册

    async def load_available_agents(self) -> None:
        """加载可用代理列表"""
        agents_info = await self.agent_manager.list_agents()
        self.available_agents = agents_info

        # 更新UI
        container = self.query_one("#main_container", MultiAgentContainer)
        container.available_agents = agents_info

        # 设置默认代理
        if agents_info:
            container.current_agent = agents_info[0]["agent_id"]

    async def apply_preset(self, preset: str) -> None:
        """应用环境预设"""
        # 加载预设配置
        from .preset import get_preset_env_vars
        env_vars = get_preset_env_vars(preset)

        # 应用到所有代理
        for agent_info in self.available_agents:
            await self.agent_manager.switch_agent_env(
                agent_info["agent_id"], preset
            )

        self.current_preset = preset

    # 事件处理
    async def on_user_message_submitted(self, event: UserMessageSubmitted) -> None:
        """处理用户消息提交"""
        container = self.query_one("#main_container", MultiAgentContainer)
        chat_display = container.query_one("#chat_display", ChatDisplay)

        # 显示用户消息
        chat_display.add_user_message(event.message)

        # 执行命令
        await container.execute_command(event.message)

    async def on_agent_selected(self, event: AgentSelected) -> None:
        """处理代理选择"""
        container = self.query_one("#main_container", MultiAgentContainer)
        container.current_agent = event.agent_id

    async def on_agent_response_received(self, event: AgentResponseReceived) -> None:
        """处理代理响应"""
        container = self.query_one("#main_container", MultiAgentContainer)
        chat_display = container.query_one("#chat_display", ChatDisplay)

        chat_display.add_agent_message(
            event.agent, event.response, event.metadata
        )

    # 动作处理
    def action_clear_chat(self) -> None:
        """清空聊天记录"""
        container = self.query_one("#main_container", MultiAgentContainer)
        chat_display = container.query_one("#chat_display", ChatDisplay)
        chat_display.clear_history()

    def action_next_agent(self) -> None:
        """切换到下一个代理"""
        container = self.query_one("#main_container", MultiAgentContainer)
        current_idx = self._get_current_agent_index()
        if current_idx < len(self.available_agents) - 1:
            next_agent = self.available_agents[current_idx + 1]["agent_id"]
            container.current_agent = next_agent

    def action_prev_agent(self) -> None:
        """切换到上一个代理"""
        container = self.query_one("#main_container", MultiAgentContainer)
        current_idx = self._get_current_agent_index()
        if current_idx > 0:
            prev_agent = self.available_agents[current_idx - 1]["agent_id"]
            container.current_agent = prev_agent

    def _get_current_agent_index(self) -> int:
        """获取当前代理索引"""
        container = self.query_one("#main_container", MultiAgentContainer)
        current = container.current_agent

        for i, agent in enumerate(self.available_agents):
            if agent["agent_id"] == current:
                return i
        return 0

    async def action_show_settings(self) -> None:
        """显示设置界面"""
        await self.push_screen(SettingsScreen())

    async def action_show_help(self) -> None:
        """显示帮助界面"""
        await self.push_screen(HelpScreen())
```

### 样式系统 (CSS)

```css
/* aiswitch.tcss - 主样式文件 */

/* 全局样式 */
Screen {
    background: $surface;
    color: $text;
}

/* 多代理容器 */
#main_container {
    padding: 1;
    height: 100%;
}

/* 代理选择器 */
#agent_selector {
    dock: top;
    height: 3;
    margin-bottom: 1;
}

#agent_selector Select {
    width: 1fr;
}

#agent_selector Static {
    width: auto;
    margin-right: 1;
}

#status_indicator {
    width: 3;
    text-align: center;
}

/* 聊天显示 */
#chat_display {
    height: 1fr;
    border: solid $primary;
    scrollbar-size: 1 1;
    margin-bottom: 1;
}

#chat_display:focus {
    border: solid $accent;
}

/* 代理特定颜色 */
#chat_display.claude {
    border: solid blue;
}

#chat_display.openai {
    border: solid green;
}

#chat_display.generic {
    border: solid yellow;
}

/* 输入面板 */
#input_panel {
    dock: bottom;
    height: 3;
    margin-bottom: 1;
}

#main_input {
    width: 1fr;
    margin-right: 1;
}

#send_btn {
    width: 8;
    margin-right: 1;
}

#settings_btn {
    width: 4;
}

/* 状态栏 */
#status_bar {
    dock: bottom;
    height: 1;
    background: $surface-lighten-1;
}

#status_bar Static {
    margin-right: 2;
}

#connection_indicator {
    width: 3;
    text-align: center;
}

/* 响应式布局 */
@media (max-width: 80) {
    #agent_selector {
        layout: vertical;
        height: 5;
    }

    #input_panel {
        layout: vertical;
        height: 6;
    }
}

/* 动画效果 */
ChatDisplay {
    transition: border 300ms;
}

StatusBar Static {
    transition: color 200ms;
}

/* 主题变量 */
:root {
    --primary-color: #007ACC;
    --success-color: #28A745;
    --warning-color: #FFC107;
    --error-color: #DC3545;
    --claude-color: #FF6B35;
    --openai-color: #10A37F;
}
```

## 实现计划

### Phase 1: 基础重构 (1周)

1. **组件拆分**
   - 将现有`BaseChatApp`拆分为独立组件
   - 实现`ChatDisplay`、`InputPanel`、`StatusBar`
   - 建立基础事件系统

2. **响应式状态管理**
   - 添加reactive属性到各组件
   - 实现watch方法处理状态变化
   - 统一状态传递机制

### Phase 2: 多代理集成 (1周)

1. **MultiAgentContainer实现**
   - 集成现有`ClaudeSDKApp`逻辑
   - 添加代理选择和状态管理
   - 实现并行/串行执行模式

2. **AgentSelector组件**
   - 动态代理列表
   - 状态指示器
   - 切换动画效果

### Phase 3: 高级功能 (1周)

1. **智能特性**
   - 命令建议和自动完成
   - 消息历史和搜索
   - 会话保存和加载

2. **UI增强**
   - 主题支持
   - 响应式布局
   - 动画效果

### Phase 4: 优化和测试 (1周)

1. **性能优化**
   - 大量消息时的性能
   - 内存使用优化
   - 响应速度提升

2. **测试和文档**
   - 单元测试
   - 集成测试
   - 用户文档

## 技术考虑

### 1. 性能优化

- **延迟加载**: 大量历史消息的延迟渲染
- **虚拟滚动**: 长聊天记录的虚拟滚动
- **状态管理**: 合理的reactive属性更新频率

### 2. 错误处理

- **网络错误**: 连接失败的自动重试
- **API错误**: 友好的错误消息显示
- **状态恢复**: 应用崩溃后的状态恢复

### 3. 可扩展性

- **插件系统**: 支持第三方代理插件
- **主题系统**: 自定义主题和样式
- **配置系统**: 灵活的配置管理

### 4. 用户体验

- **键盘导航**: 完整的键盘快捷键支持
- **视觉反馈**: 清晰的状态指示和动画
- **响应式设计**: 适应不同终端尺寸

## 结论

基于Textual框架的新设计将为AISwitch提供：

1. **更好的架构**: 模块化、可维护的组件设计
2. **更丰富的功能**: 多代理协调、智能特性
3. **更好的体验**: 响应式UI、流畅动画
4. **更强的扩展性**: 插件系统、主题支持

这个设计充分利用了Textual框架的优势，同时保持了与现有AISwitch架构的兼容性，为未来的功能扩展提供了坚实的基础。

<function_calls>
<invoke name="TodoWrite">
<parameter name="todos">[{"content": "Read existing docs directory structure", "status": "completed", "activeForm": "Reading existing docs directory structure"}, {"content": "Research Textual TUI library documentation using context7", "status": "completed", "activeForm": "Researching Textual TUI library documentation"}, {"content": "Analyze current Textual implementation patterns", "status": "completed", "activeForm": "Analyzing current Textual implementation patterns"}, {"content": "Create comprehensive Textual design document", "status": "completed", "activeForm": "Creating comprehensive Textual design document"}]