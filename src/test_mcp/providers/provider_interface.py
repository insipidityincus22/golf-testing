import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any


class ProviderType(str, Enum):
    """Supported LLM providers (simplified to core providers)"""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GEMINI = "gemini"


@dataclass
class ProviderMetrics:
    """Performance metrics for provider operations"""

    provider: ProviderType
    requests_made: int = 0
    # total_tokens removed - unreliable estimation
    total_latency_ms: float = 0
    error_count: int = 0

    @property
    def average_latency_ms(self) -> float:
        return self.total_latency_ms / max(self.requests_made, 1)

    @property
    def error_rate(self) -> float:
        return self.error_count / max(self.requests_made, 1)


class ProviderInterface(ABC):
    """Abstract interface for LLM providers with async support"""

    def __init__(self, provider_type: ProviderType, config: dict[str, str]):
        self.provider_type = provider_type
        self.config = config
        self.metrics = ProviderMetrics(provider=provider_type)

    @abstractmethod
    async def send_message(self, message: str, system_prompt: str | None = None) -> str:
        """Send message and get response"""
        pass

    @abstractmethod
    async def send_message_with_tools(
        self, message: str, tools: list[dict], system_prompt: str | None = None
    ) -> tuple[str, list[dict]]:
        """Send message with tool calling capability"""
        pass

    @abstractmethod
    async def send_mcp_request(
        self, method: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Send direct MCP protocol request (for compliance testing)"""
        pass

    @abstractmethod
    async def start_session(self, session_id: str) -> bool:
        """Start new session for parallel execution safety"""
        pass

    @abstractmethod
    async def end_session(self, session_id: str) -> None:
        """Clean up session"""
        pass

    def get_metrics(self) -> ProviderMetrics:
        """Get performance metrics"""
        return self.metrics


class AnthropicProvider(ProviderInterface):
    """Anthropic Claude provider implementation"""

    def __init__(self, config: dict[str, str]):
        super().__init__(ProviderType.ANTHROPIC, config)
        self.api_key = config["api_key"]
        self.model = config.get("model", "claude-sonnet-4-20250514")
        self.sessions: dict[str, Any] = {}

    async def send_message(self, message: str, system_prompt: str | None = None) -> str:
        """Send message using Anthropic API"""
        start_time = time.perf_counter()
        self.metrics.requests_made += 1

        try:
            # Implementation using existing ClaudeAgent logic
            # This maintains backward compatibility while adding async support
            response = await self._anthropic_api_call(message, system_prompt)

            # Update metrics
            latency = (time.perf_counter() - start_time) * 1000
            self.metrics.total_latency_ms += latency
            # Token tracking removed - rely on provider's actual usage metrics

            return response

        except Exception:
            self.metrics.error_count += 1
            raise

    async def send_message_with_tools(
        self, message: str, tools: list[dict], system_prompt: str | None = None
    ) -> tuple[str, list[dict]]:
        """Send message with tool calling"""
        # Implementation will reuse existing agent tool calling logic
        response = await self.send_message(message, system_prompt)
        tool_results: list[dict] = []  # Extract from existing implementation
        return response, tool_results

    async def send_mcp_request(
        self, method: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Send direct MCP protocol request for compliance testing"""
        start_time = time.perf_counter()
        self.metrics.requests_made += 1

        try:
            # Build JSON-RPC 2.0 request
            import uuid

            import httpx

            request: dict[str, Any] = {
                "jsonrpc": "2.0",
                "id": str(uuid.uuid4()),
                "method": method,
            }

            if params:
                request["params"] = params

            # Send direct HTTP request to MCP server endpoint
            # This bypasses the Anthropic API for direct protocol access
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
        """Start isolated session"""
        self.sessions[session_id] = {"created_at": time.time(), "message_count": 0}
        return True

    async def end_session(self, session_id: str) -> None:
        """Clean up session"""
        if session_id in self.sessions:
            del self.sessions[session_id]

    async def _anthropic_api_call(self, message: str, system_prompt: str | None) -> str:
        """Internal API call implementation"""
        # Reuse existing ClaudeAgent implementation logic
        # This ensures compatibility while providing async interface

        # For now, we'll import and use the existing ClaudeAgent
        # In a full implementation, this would be refactored to be fully async
        from ..agent.agent import ClaudeAgent
        from ..agent.models import AgentConfig
        from ..agent.models import MCPServerConfig as AgentMCPServerConfig

        # Convert our config to AgentConfig format
        # This is a temporary bridge while we transition to the new architecture
        mcp_servers = []
        if "mcp_servers" in self.config:
            for server in self.config["mcp_servers"]:
                mcp_server = AgentMCPServerConfig(
                    url=server["url"],
                    name=server["name"],
                    authorization_token=server.get("authorization_token"),
                )
                mcp_servers.append(mcp_server)

        agent_config = AgentConfig(
            anthropic_api_key=self.api_key, mcp_servers=mcp_servers
        )

        # Create agent and execute asynchronously
        agent = ClaudeAgent(agent_config)
        agent.start_new_session()

        # Call async method directly
        response = await agent.send_message(message)
        return response
