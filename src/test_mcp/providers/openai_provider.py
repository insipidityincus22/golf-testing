# asyncio imported but not used - removing for clean code
import time
from typing import Any, Optional

import httpx

from .provider_interface import ProviderInterface, ProviderType


class OpenAIProvider(ProviderInterface):
    """OpenAI GPT provider implementation"""

    def __init__(self, config: dict[str, Any]):
        super().__init__(ProviderType.OPENAI, config)
        self.api_key = config["api_key"]
        self.model = config.get("model", "gpt-4")
        self.sessions: dict[str, Any] = {}

    async def send_message(
        self, message: str, system_prompt: Optional[str] = None
    ) -> str:
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
        self, message: str, tools: list[dict], system_prompt: Optional[str] = None
    ) -> tuple[str, list[dict]]:
        """Send message with tool calling"""
        response = await self.send_message(message, system_prompt)
        tool_results: list[dict] = []  # Would be populated if tools were used
        return response, tool_results

    async def send_mcp_request(
        self, method: str, params: Optional[dict[str, Any]] = None
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
            mcp_server_url: Optional[str] = self.config.get("mcp_server_url")
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

    async def _openai_api_call(self, message: str, system_prompt: Optional[str]) -> str:
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
