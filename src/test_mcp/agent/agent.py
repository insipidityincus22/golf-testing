import json
import time
import uuid
from typing import Any, Optional

import anthropic

from .models import (
    AgentConfig,
    ChatMessage,
    ChatSession,
)


class ClaudeAgent:
    """AI Agent that integrates with Anthropic's API and supports MCP servers"""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.client = anthropic.Anthropic(api_key=config.anthropic_api_key)
        self.current_session: Optional[ChatSession] = None

    def start_new_session(self) -> ChatSession:
        """Start a new chat session"""
        session_id = str(uuid.uuid4())
        self.current_session = ChatSession(
            session_id=session_id, mcp_servers=self.config.mcp_servers
        )
        return self.current_session

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the current session"""
        if not self.current_session:
            self.current_session = self.start_new_session()

        message = ChatMessage(role=role, content=content)
        self.current_session.messages.append(message)

    def _prepare_mcp_servers_config(self) -> list[dict[str, Any]]:
        """Prepare MCP servers configuration for API call"""
        mcp_servers = []

        for server in self.config.mcp_servers:
            server_config: dict[str, Any] = {
                "type": "url",  # Anthropic API only accepts 'url' type
                "url": str(server.url),
                "name": server.name,
            }

            # Pass through tool_configuration as-is if it exists
            # It's already a dict from the backend, so just pass it through
            if server.tool_configuration is not None:
                if isinstance(server.tool_configuration, dict):
                    # Already a dict, use as-is
                    server_config["tool_configuration"] = server.tool_configuration
                else:
                    # It's an MCPToolConfiguration object, convert to dict
                    server_config["tool_configuration"] = (
                        server.tool_configuration.model_dump()
                    )

            if server.authorization_token:
                server_config["authorization_token"] = server.authorization_token

            mcp_servers.append(server_config)

        return mcp_servers

    def _prepare_messages(self) -> list[dict[str, str]]:
        """Prepare messages for API call"""
        if not self.current_session:
            return []

        messages = []
        for msg in self.current_session.messages:
            if msg.role != "system":  # System message handled separately
                messages.append({"role": msg.role, "content": msg.content})

        return messages

    def _format_tool_result(self, result_text: str) -> str:
        """Format tool result JSON like jq - generic and works with any structure"""
        try:
            # Try to parse as JSON
            data = json.loads(result_text)

            # Pretty print with proper indentation, like jq
            formatted = json.dumps(data, indent=2, ensure_ascii=False)

            # If it's very long, truncate but keep it readable
            if len(formatted) > 2000:
                lines = formatted.split("\n")
                if len(lines) > 50:
                    # Keep first 40 lines and last 5 lines with a truncation message
                    truncated = (
                        lines[:40]
                        + [f"  ... ({len(lines) - 45} lines truncated) ..."]
                        + lines[-5:]
                    )
                    formatted = "\n".join(truncated)
                else:
                    # Just truncate characters but try to end on a complete line
                    formatted = formatted[:1950] + "\n  ... (truncated) ...\n}"

            return formatted

        except (json.JSONDecodeError, TypeError):
            # If not valid JSON, return as-is but maybe truncate if very long
            if len(result_text) > 1000:
                return result_text[:997] + "..."
            return result_text

    def _process_response_content(
        self, content: list[Any]
    ) -> tuple[str, list[dict[str, Any]]]:
        """Process response content and handle MCP tool calls

        Returns:
            tuple: (clean_message, tool_results)
        """
        claude_content = []
        tool_results = []

        for block in content:
            # Use attribute access for BetaTextBlock and structured MCP types
            if block.type == "text":
                claude_content.append(block.text)
            elif block.type == "mcp_tool_use":
                # Use structured MCP tool use block attributes directly
                claude_content.append(f"\nUsing {block.name} tool...")
            elif block.type == "mcp_tool_result":
                # Use structured MCP tool result block attributes directly
                if block.is_error:
                    tool_results.append(
                        {"is_error": True, "content": "Tool execution failed"}
                    )
                else:
                    # Process structured content array
                    for result_content in block.content:
                        if result_content.type == "text":
                            try:
                                # Try to parse as JSON for structured data
                                parsed_result = json.loads(result_content.text)
                                tool_results.append(
                                    {"is_error": False, "content": parsed_result}
                                )
                            except json.JSONDecodeError:
                                # If not JSON, store as text
                                tool_results.append(
                                    {
                                        "is_error": False,
                                        "content": {"text": result_content.text},
                                    }
                                )

        # Return clean message without embedded tool results
        clean_message = "".join(claude_content)

        return clean_message, tool_results

    def _prepare_api_call(
        self, user_message: str
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Extract common API preparation logic for both send and stream methods"""
        # Add user message to session
        self.add_message("user", user_message)

        # Prepare API call parameters
        messages = self._prepare_messages()
        mcp_servers = self._prepare_mcp_servers_config()

        # Prepare API call
        api_params = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "system": self.config.system_prompt,
            "messages": messages,
        }

        return api_params, mcp_servers

    def _handle_api_error(self, error: Exception) -> str:
        """Common error handling for API calls"""
        error_message = f"Error communicating with Claude: {str(error)}"
        self.add_message("assistant", error_message)
        return error_message

    def _should_retry_error(self, error: Exception) -> bool:
        """Determine if an error should be retried"""
        error_str = str(error).lower()

        # Check for 529 overloaded errors
        if "529" in error_str or "overloaded" in error_str:
            return True

        # Check for other retryable errors
        retryable_errors = [
            "502",  # Bad Gateway
            "503",  # Service Unavailable
            "504",  # Gateway Timeout
            "rate_limit_error",
            "timeout",
            "connection error",
            "server error",
        ]

        return any(retryable in error_str for retryable in retryable_errors)

    def _make_api_call_with_retry(self, api_params: dict, mcp_servers: list) -> Any:
        """Make API call with retry logic for transient errors"""
        max_retries = 3
        base_delay = 1.0  # Start with 1 second

        for attempt in range(max_retries + 1):
            try:
                # Make API call using beta client for MCP support
                response = self.client.beta.messages.create(
                    **api_params,
                    mcp_servers=mcp_servers,
                    betas=["mcp-client-2025-04-04"],
                )
                return response

            except Exception as e:
                # Check if this is the last attempt
                if attempt == max_retries:
                    raise e

                # Check if we should retry this error
                if not self._should_retry_error(e):
                    raise e

                # Calculate delay with exponential backoff + jitter
                delay = base_delay * (2**attempt) + (time.time() % 1)  # Add jitter

                print(
                    f"   Warning: API error (attempt {attempt + 1}/{max_retries + 1}): {str(e)}"
                )
                print(f"   Retrying in {delay:.1f}s...")

                time.sleep(delay)

        # This shouldn't be reached, but just in case
        raise Exception("Max retries exceeded")

    def send_message(self, user_message: str) -> str:
        """Send a message and get response from Claude"""
        try:
            api_params, mcp_servers = self._prepare_api_call(user_message)

            # Make API call with retry logic
            response = self._make_api_call_with_retry(api_params, mcp_servers)

            # Process response
            assistant_message, tool_results = self._process_response_content(
                response.content
            )

            # Store tool results separately in session
            if tool_results and self.current_session:
                self.current_session.tool_results.extend(tool_results)

            # Add assistant response to session
            self.add_message("assistant", assistant_message)

            return assistant_message

        except Exception as e:
            return self._handle_api_error(e)

    def get_session_history(self) -> list[ChatMessage]:
        """Get current session message history"""
        if not self.current_session:
            return []
        return self.current_session.messages

    def get_recent_tool_results(self) -> list[dict[str, Any]]:
        """Get tool results from the current session"""
        if not self.current_session:
            return []
        return self.current_session.tool_results

    def clear_tool_results(self) -> None:
        """Clear stored tool results from the current session"""
        if self.current_session:
            self.current_session.tool_results = []

    def cleanup_session_messages(self, keep_last_n: int = 10) -> None:
        """
        Clean up session messages to prevent memory leak.
        Keeps the last N messages to maintain context while preventing unbounded growth.
        """
        if self.current_session and len(self.current_session.messages) > keep_last_n:
            # Keep the last N messages to maintain some context
            self.current_session.messages = self.current_session.messages[-keep_last_n:]

    def reset_session(self) -> None:
        """Reset the current session completely, clearing all messages and tool results"""
        if self.current_session:
            self.current_session.messages = []
            self.current_session.tool_results = []

    def get_session_message_count(self) -> int:
        """Get the current number of messages in the session"""
        return len(self.current_session.messages) if self.current_session else 0

    def get_available_mcp_tools(self) -> dict[str, list[str]]:
        """Get information about available MCP tools"""
        # This would typically query the MCP servers for available tools
        # For now, return configured server information
        tools_info = {}
        for server in self.config.mcp_servers:
            # Handle both dict and MCPToolConfiguration object
            if server.tool_configuration:
                if isinstance(server.tool_configuration, dict):
                    # Extract allowed_tools from dict if present
                    allowed_tools = server.tool_configuration.get("allowed_tools")
                    tools_info[server.name] = (
                        allowed_tools if allowed_tools else ["All tools available"]
                    )
                else:
                    # It's an MCPToolConfiguration object
                    tools_info[server.name] = (
                        server.tool_configuration.allowed_tools
                        if server.tool_configuration.allowed_tools
                        else ["All tools available"]
                    )
            else:
                tools_info[server.name] = ["All tools available"]
        return tools_info
