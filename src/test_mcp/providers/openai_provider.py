import time
from typing import Any

import httpx

from ..mcp_client.capability_router import MCPCapabilityRouter
from ..mcp_client.client_manager import MCPClientManager
from .provider_interface import ProviderInterface, ProviderType


class OpenAIProvider(ProviderInterface):
    """OpenAI GPT provider implementation"""

    def __init__(self, config: dict[str, str]):
        super().__init__(ProviderType.OPENAI, config)
        self.api_key = config["api_key"]
        self.model = config.get("model", "gpt-4")
        self.sessions: dict[str, Any] = {}

        # Initialize MCP client
        self.mcp_client = MCPClientManager()
        self.capability_router = MCPCapabilityRouter(self.mcp_client)
        self.server_ids: list[str] = []
        self.mcp_tools: list[dict[str, Any]] = []
        self.mcp_resources: list[dict[str, Any]] = []
        self.mcp_prompts: list[dict[str, Any]] = []

    async def send_message(self, message: str, system_prompt: str | None = None) -> str:
        """Send message using OpenAI API"""
        start_time = time.perf_counter()
        self.metrics.requests_made += 1

        try:
            response = await self._openai_api_call(message, system_prompt)

            # Update metrics
            latency = (time.perf_counter() - start_time) * 1000
            self.metrics.total_latency_ms += latency

            return response

        except Exception:
            self.metrics.error_count += 1
            raise

    async def send_message_with_tools(
        self, message: str, tools: list[dict], system_prompt: str | None = None
    ) -> tuple[str, list[dict]]:
        """Send message with MCP tool support"""

        # Prepare messages
        messages = [{"role": "user", "content": message}]
        if system_prompt:
            messages.insert(0, {"role": "system", "content": system_prompt})

        # Convert tools to OpenAI format
        if self.mcp_tools:
            openai_tools = self.capability_router.format_tools_for_openai(
                self.mcp_tools
            )
        else:
            openai_tools = []

        # Prepare API call
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            payload = {
                "model": self.model,
                "messages": messages,
                "max_tokens": 1000,
                "temperature": 0.7,
            }

            if openai_tools:
                payload["tools"] = openai_tools

            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                json=payload,
                headers=headers,
            )

            if response.status_code != 200:
                raise Exception(
                    f"OpenAI API error {response.status_code}: {response.text}"
                )

            response_data = response.json()
            message_response = response_data["choices"][0]["message"]

            # Parse tool calls
            tool_calls = self.capability_router.parse_openai_tool_calls(
                message_response
            )

            if tool_calls:
                # Execute via MCP client
                tool_results = await self.capability_router.execute_tool_calls(
                    tool_calls, self.mcp_tools
                )

                # Format and combine
                response_text = message_response.get("content", "")
                return response_text, tool_results
            else:
                return message_response.get("content", ""), []

    async def send_mcp_request(
        self, method: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Send direct MCP protocol request for compliance testing"""
        start_time = time.perf_counter()
        self.metrics.requests_made += 1

        try:
            # Build JSON-RPC 2.0 request
            import uuid

            request: dict[str, Any] = {
                "jsonrpc": "2.0",
                "id": str(uuid.uuid4()),
                "method": method,
            }

            if params:
                request["params"] = params

            # Send direct HTTP request to MCP server endpoint
            mcp_server_url: str | None = self.config.get("mcp_server_url")
            if not mcp_server_url:
                raise ValueError("Direct MCP requests require mcp_server_url in config")

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(mcp_server_url, json=request)

                if response.status_code == 200:
                    response_data: dict[str, Any] = response.json()

                    # Update metrics
                    latency = (time.perf_counter() - start_time) * 1000
                    self.metrics.total_latency_ms += latency

                    return response_data
                else:
                    raise Exception(f"MCP HTTP {response.status_code}: {response.text}")

        except Exception:
            self.metrics.error_count += 1
            raise

    async def start_session(self, session_id: str) -> bool:
        """Initialize MCP connections"""
        self.sessions[session_id] = {"created_at": time.time(), "message_count": 0}

        mcp_servers = self.config.get("mcp_servers", [])

        for server_config in mcp_servers:
            try:
                server_id = await self.mcp_client.connect_server(server_config)
                self.server_ids.append(server_id)
            except Exception as e:
                print(f"Failed to connect: {e}")

        if self.server_ids:
            self.mcp_tools = await self.mcp_client.get_tools_for_llm(self.server_ids)
            self.mcp_resources = await self.mcp_client.get_resources_for_llm(
                self.server_ids
            )
            self.mcp_prompts = await self.mcp_client.get_prompts_for_llm(
                self.server_ids
            )

        return True

    async def end_session(self, session_id: str) -> None:
        """Clean up session"""
        if session_id in self.sessions:
            del self.sessions[session_id]

        # Clean up MCP connections
        await self.mcp_client.disconnect_all()

    async def _openai_api_call(self, message: str, system_prompt: str | None) -> str:
        """Internal OpenAI API call implementation"""

        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": message})

            payload = {
                "model": self.model,
                "messages": messages,
                "max_tokens": 1000,
                "temperature": 0.7,
            }

            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                json=payload,
                headers=headers,
            )

            if response.status_code == 200:
                response_data = response.json()
                return str(response_data["choices"][0]["message"]["content"])
            else:
                raise Exception(
                    f"OpenAI API error {response.status_code}: {response.text}"
                )
