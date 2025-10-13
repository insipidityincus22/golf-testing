import re

from ...agent.agent import ClaudeAgent
from ..core.test_models import ToolCall


def extract_tool_calls_from_agent(
    agent: ClaudeAgent, recent_only: bool = False, target_server: str | None = None
) -> list[ToolCall]:
    """
    Extract tool calls from agent's stored tool results (not from conversation text).

    Args:
        agent: The Claude agent instance
        recent_only: If True, only return tool calls from recent messages
        target_server: Specific server name to use, or None to auto-detect

    Returns:
        List of ToolCall objects representing tools used by the agent with results
    """
    tool_calls: list[ToolCall] = []

    # Get tool results directly from agent session (not from conversation text)
    tool_results = agent.get_recent_tool_results()

    if not tool_results:
        return tool_calls

    # Get server name dynamically
    if target_server is None:
        server_name = _get_primary_server_name(agent)
    else:
        server_name = target_server

    # Also extract tool names from conversation text to match with results
    history = agent.get_session_history()
    if not history:
        return tool_calls

    # Get recent messages based on recent_only flag
    if recent_only:
        # Only check the most recent assistant message
        latest_message = None
        for message in reversed(history):
            if message.role == "assistant":
                latest_message = message
                break
        messages_to_check = [latest_message] if latest_message else []
    else:
        # Check all assistant messages
        messages_to_check = [msg for msg in history if msg.role == "assistant"]

    # Extract tool names from messages
    all_tool_names = []
    for message in messages_to_check:
        if "Using " in message.content and " tool" in message.content:
            # Extract tool names using the pattern: "Using toolname tool" (with or without emoji)
            tool_matches = re.findall(r"(?:🔧 )?Using ([\w-]+) tool", message.content)
            all_tool_names.extend(tool_matches)

    # Remove duplicates while preserving order
    unique_tool_names = list(dict.fromkeys(all_tool_names))

    # Match tool names with their results
    for i, tool_name in enumerate(unique_tool_names):
        if tool_name:  # Skip empty matches
            # Try to match tool call with its result
            result_data = None
            error_message = None

            # Get corresponding result if available
            if i < len(tool_results):
                result_info = tool_results[i]
                if result_info.get("is_error"):
                    error_message = result_info.get("content", "Tool execution failed")
                else:
                    result_data = result_info.get("content")

            tool_call = ToolCall(
                tool_name=tool_name,
                server_name=server_name,
                input_params={},  # Could be enhanced to extract parameters
                result=result_data,
                error=error_message,
            )
            tool_calls.append(tool_call)

    return tool_calls


def _get_primary_server_name(agent: ClaudeAgent) -> str:
    """
    Dynamically determine the primary MCP server name from agent configuration.

    Args:
        agent: The Claude agent instance

    Returns:
        The name of the primary MCP server, or "unknown" if none configured
    """
    if not agent.config.mcp_servers:
        return "unknown"

    # For now, return the first configured server
    # In the future, this could be enhanced with more sophisticated logic
    # such as determining which server was actually used for the tool call
    return agent.config.mcp_servers[0].name


def get_available_server_names(agent: ClaudeAgent) -> list[str]:
    """
    Get list of all configured MCP server names from agent.

    Args:
        agent: The Claude agent instance

    Returns:
        List of configured server names
    """
    return [server.name for server in agent.config.mcp_servers]


def extract_tool_calls_for_server(
    agent: ClaudeAgent, server_name: str, recent_only: bool = False
) -> list[ToolCall]:
    """
    Extract tool calls for a specific server only.

    Args:
        agent: The Claude agent instance
        server_name: Name of the specific MCP server
        recent_only: If True, only check the most recent assistant message

    Returns:
        List of ToolCall objects for the specified server
    """
    return extract_tool_calls_from_agent(
        agent=agent, recent_only=recent_only, target_server=server_name
    )
