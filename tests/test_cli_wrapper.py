"""测试CLI代理包装器功能"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from aiswitch.cli_wrapper.types import SessionStatus, CommandResult, AgentConfig, ParsedResult
from aiswitch.cli_wrapper.adapters.generic_adapter import GenericAdapter
from aiswitch.cli_wrapper.manager import CLIAgentManager
from aiswitch.cli_wrapper.agent_wrapper import CLIAgentWrapper


class TestGenericAdapter:
    """测试通用适配器"""

    def setup_method(self):
        self.adapter = GenericAdapter(
            name="test",
            command=["echo", "test"],
            prompt_pattern=r'.*\$\s*$'
        )

    @pytest.mark.asyncio
    async def test_build_command(self):
        """测试构建命令"""
        command = await self.adapter.build_command("test_preset")
        assert command == ["echo", "test"]

    @pytest.mark.asyncio
    async def test_format_command(self):
        """测试格式化命令"""
        formatted = await self.adapter.format_command("test command")
        assert formatted == "test command"

    @pytest.mark.asyncio
    async def test_is_command_complete(self):
        """测试命令完成检测"""
        # 测试未完成的情况
        complete = await self.adapter.is_command_complete(["output line"], [])
        assert not complete

        # 测试完成的情况
        complete = await self.adapter.is_command_complete(["output line", "$ "], [])
        assert complete

    @pytest.mark.asyncio
    async def test_get_capabilities(self):
        """测试获取能力"""
        capabilities = await self.adapter.get_capabilities()
        assert capabilities["name"] == "test"
        assert capabilities["supports_interactive"] is True


class TestCLIAgentWrapper:
    """测试CLI代理包装器"""

    def setup_method(self):
        self.adapter = Mock()
        self.adapter.name = "test_adapter"
        self.adapter.get_capabilities = AsyncMock(return_value={
            "name": "test",
            "supports_interactive": True
        })
        self.wrapper = CLIAgentWrapper("test_agent", self.adapter)

    @pytest.mark.asyncio
    async def test_initialize(self):
        """测试初始化"""
        result = await self.wrapper.initialize()
        assert result["agent_id"] == "test_agent"
        assert result["status"] == "initialized"
        assert "capabilities" in result
        assert "initialized_at" in result

    @pytest.mark.asyncio
    async def test_session_management(self):
        """测试会话管理"""
        # Mock session creation
        with patch('aiswitch.cli_wrapper.agent_wrapper.CLIProcessSession') as mock_session:
            mock_instance = Mock()
            mock_instance.start = AsyncMock()
            mock_instance.get_status = AsyncMock(return_value={"status": "running"})
            mock_instance.created_at = Mock()
            mock_instance.created_at.isoformat.return_value = "2023-01-01T00:00:00"
            mock_session.return_value = mock_instance

            # 创建会话
            session_id = await self.wrapper.new_session("test_preset")
            assert session_id in self.wrapper.sessions

            # 获取会话状态
            status = await self.wrapper.get_session_status(session_id)
            assert status["status"] == "running"

            # 列出会话
            sessions = await self.wrapper.list_sessions()
            assert len(sessions) == 1
            assert sessions[0]["session_id"] == session_id

            # 终止会话
            mock_instance.terminate = AsyncMock()
            await self.wrapper.terminate_session(session_id)
            assert session_id not in self.wrapper.sessions


class TestCLIAgentManager:
    """测试CLI代理管理器"""

    def setup_method(self):
        self.manager = CLIAgentManager()

    @pytest.mark.asyncio
    async def test_register_agent(self):
        """测试注册代理"""
        config = AgentConfig(
            command=["echo", "test"],
            prompt_pattern=r'.*\$\s*$'
        )

        with patch('aiswitch.cli_wrapper.manager.CLIAgentWrapper') as mock_wrapper:
            mock_instance = Mock()
            mock_instance.initialize = AsyncMock(return_value={"status": "initialized"})
            mock_wrapper.return_value = mock_instance

            await self.manager.register_agent("test_agent", "generic", config)
            assert "test_agent" in self.manager.agents

    @pytest.mark.asyncio
    async def test_session_operations(self):
        """测试会话操作"""
        # 先注册一个代理
        mock_agent = Mock()
        mock_agent.new_session = AsyncMock(return_value="session_123")
        mock_agent.execute_command = AsyncMock(return_value=CommandResult(
            session_id="session_123",
            agent_id="test_agent",
            command="test",
            result=ParsedResult(
                output="test output",
                error="",
                metadata={},
                success=True
            ),
            timestamp=Mock(),
            success=True
        ))
        self.manager.agents["test_agent"] = mock_agent

        # 创建会话
        session_id = await self.manager.create_session("test_agent", "test_preset")
        assert session_id == "session_123"

        # 执行命令
        result = await self.manager.execute_command("test_agent", "session_123", "test command")
        assert result.success is True
        assert result.result.output == "test output"


    @pytest.mark.asyncio
    async def test_list_agents(self):
        """测试列出代理"""
        # 添加mock代理
        mock_agent = Mock()
        mock_agent.adapter.name = "test_adapter"
        mock_agent.capabilities = {"name": "test"}
        mock_agent.list_sessions = AsyncMock(return_value=[])
        self.manager.agents["test_agent"] = mock_agent

        agents_info = await self.manager.list_agents()
        assert len(agents_info) == 1
        assert agents_info[0]["agent_id"] == "test_agent"
        assert agents_info[0]["adapter"] == "test_adapter"

    @pytest.mark.asyncio
    async def test_terminate_agent(self):
        """测试终止代理"""
        # 添加mock代理
        mock_agent = Mock()
        mock_agent.sessions = {"session1": Mock(), "session2": Mock()}
        mock_agent.terminate_session = AsyncMock()
        self.manager.agents["test_agent"] = mock_agent

        await self.manager.terminate_agent("test_agent")
        assert "test_agent" not in self.manager.agents
        assert mock_agent.terminate_session.call_count == 2


if __name__ == "__main__":
    pytest.main([__file__])