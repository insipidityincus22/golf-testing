from unittest.mock import AsyncMock, MagicMock

import pytest

from test_mcp.mcp_client.capability_router import MCPCapabilityRouter


class TestMCPCapabilityRouter:
    def test_format_tools_for_anthropic(self):
        """Test converting MCP tools to Anthropic format"""
        mock_client = MagicMock()
        router = MCPCapabilityRouter(mock_client)

        mcp_tools = [
            {
                "name": "test_tool",
                "description": "A test tool",
                "inputSchema": {
                    "type": "object",
                    "properties": {"arg": {"type": "string"}},
                    "required": ["arg"],
                },
                "_mcp_server_id": "server1",
            }
        ]

        anthropic_tools = router.format_tools_for_anthropic(mcp_tools)

        assert len(anthropic_tools) == 1
        assert anthropic_tools[0]["name"] == "test_tool"
        assert anthropic_tools[0]["description"] == "A test tool"
        assert anthropic_tools[0]["input_schema"]["type"] == "object"

    def test_format_tools_for_openai(self):
        """Test converting MCP tools to OpenAI format"""
        mock_client = MagicMock()
        router = MCPCapabilityRouter(mock_client)

        mcp_tools = [
            {
                "name": "test_tool",
                "description": "A test tool",
                "inputSchema": {
                    "type": "object",
                    "properties": {"arg": {"type": "string"}},
                    "required": ["arg"],
                },
                "_mcp_server_id": "server1",
            }
        ]

        openai_tools = router.format_tools_for_openai(mcp_tools)

        assert len(openai_tools) == 1
        assert openai_tools[0]["type"] == "function"
        assert openai_tools[0]["function"]["name"] == "test_tool"
        assert openai_tools[0]["function"]["description"] == "A test tool"
        assert openai_tools[0]["function"]["parameters"]["type"] == "object"

    def test_parse_anthropic_tool_calls(self):
        """Test parsing tool calls from Anthropic response"""
        mock_client = MagicMock()
        router = MCPCapabilityRouter(mock_client)

        # Mock Anthropic response
        mock_response = MagicMock()
        mock_block = MagicMock()
        mock_block.type = "tool_use"
        mock_block.name = "test_tool"
        mock_block.input = {"arg": "value"}
        mock_block.id = "call_123"
        mock_response.content = [mock_block]

        tool_calls = router.parse_anthropic_tool_calls(mock_response)

        assert len(tool_calls) == 1
        assert tool_calls[0]["tool_name"] == "test_tool"
        assert tool_calls[0]["arguments"] == {"arg": "value"}
        assert tool_calls[0]["call_id"] == "call_123"

    def test_parse_openai_tool_calls(self):
        """Test parsing tool calls from OpenAI response"""
        mock_client = MagicMock()
        router = MCPCapabilityRouter(mock_client)

        # Mock OpenAI response
        mock_response = MagicMock()
        mock_tool_call = MagicMock()
        mock_tool_call.function.name = "test_tool"
        mock_tool_call.function.arguments = '{"arg": "value"}'
        mock_tool_call.id = "call_123"
        mock_response.tool_calls = [mock_tool_call]

        tool_calls = router.parse_openai_tool_calls(mock_response)

        assert len(tool_calls) == 1
        assert tool_calls[0]["tool_name"] == "test_tool"
        assert tool_calls[0]["arguments"] == {"arg": "value"}
        assert tool_calls[0]["call_id"] == "call_123"

    def test_parse_openai_tool_calls_empty(self):
        """Test parsing empty tool calls from OpenAI response"""
        mock_client = MagicMock()
        router = MCPCapabilityRouter(mock_client)

        # Mock OpenAI response with no tool calls
        mock_response = MagicMock()
        mock_response.tool_calls = None

        tool_calls = router.parse_openai_tool_calls(mock_response)

        assert len(tool_calls) == 0

    @pytest.mark.asyncio
    async def test_execute_tool_calls(self):
        """Test executing tool calls via MCP client"""
        mock_client = AsyncMock()
        mock_client.execute_tool.return_value = {
            "success": True,
            "content": [{"type": "text", "text": "Tool result"}],
        }
        mock_client.connections = {"server1": "mock_connection"}

        router = MCPCapabilityRouter(mock_client)

        tool_calls = [
            {
                "tool_name": "test_tool",
                "arguments": {"arg": "value"},
                "call_id": "call_123",
            }
        ]

        tools_metadata = [{"name": "test_tool", "_mcp_server_id": "server1"}]

        results = await router.execute_tool_calls(tool_calls, tools_metadata)

        assert len(results) == 1
        assert results[0]["success"] is True
        assert results[0]["tool_name"] == "test_tool"
        assert results[0]["call_id"] == "call_123"
        mock_client.execute_tool.assert_called_once_with(
            server_id="server1", tool_name="test_tool", arguments={"arg": "value"}
        )

    @pytest.mark.asyncio
    async def test_execute_tool_calls_no_server(self):
        """Test executing tool calls with missing server"""
        mock_client = AsyncMock()
        mock_client.connections = {}  # No connections
        router = MCPCapabilityRouter(mock_client)

        tool_calls = [
            {
                "tool_name": "unknown_tool",
                "arguments": {"arg": "value"},
                "call_id": "call_123",
            }
        ]

        tools_metadata = []  # Empty metadata

        results = await router.execute_tool_calls(tool_calls, tools_metadata)

        assert len(results) == 1
        assert results[0]["success"] is False
        assert "No MCP servers connected" in results[0]["error"]

    def test_format_results_for_llm_anthropic(self):
        """Test formatting results for Anthropic"""
        mock_client = MagicMock()
        router = MCPCapabilityRouter(mock_client)

        results = [
            {
                "success": True,
                "tool_name": "test_tool",
                "content": [{"type": "text", "text": "Tool executed successfully"}],
            }
        ]

        formatted = router.format_results_for_llm(results, "tool", "anthropic")

        assert "Tool test_tool result:" in formatted
        assert "Tool executed successfully" in formatted

    def test_format_results_for_llm_openai(self):
        """Test formatting results for OpenAI"""
        mock_client = MagicMock()
        router = MCPCapabilityRouter(mock_client)

        results = [
            {
                "success": True,
                "tool_name": "test_tool",
                "call_id": "call_123",
                "content": [{"type": "text", "text": "Tool executed successfully"}],
            }
        ]

        formatted = router.format_results_for_llm(results, "tool", "openai")

        assert isinstance(formatted, list)
        assert len(formatted) == 1
        assert formatted[0]["tool_call_id"] == "call_123"
        assert formatted[0]["role"] == "tool"
        assert "Tool executed successfully" in formatted[0]["content"]
