import json
import os
from datetime import datetime
from typing import Any

from ..config.config_manager import MCPServerConfig
from .models import AgentConfig


def get_default_system_prompt() -> str:
    """Load the Claude Sonnet 4 system prompt from template file"""
    from pathlib import Path

    current_date = datetime.now().strftime("%B %d, %Y")

    # Get the template file path relative to this config file
    config_dir = Path(__file__).parent
    template_path = config_dir.parent / "templates" / "claude_system_prompt.txt"

    try:
        with open(template_path, encoding="utf-8") as f:
            prompt_template = f.read()

        # Format the template with current date
        return prompt_template.format(current_date=current_date)

    except FileNotFoundError:
        # Fallback to a basic prompt if template file is missing
        return f"""The assistant is Claude, created by Anthropic.
The current date is {current_date}
Claude is now being connected with a person."""


def load_agent_config(config_file: str | None = None) -> AgentConfig:
    """Load agent configuration from environment and optional config file"""

    # Get API key from environment
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable is required")

    # Default configuration
    config_data: dict[str, Any] = {
        "anthropic_api_key": api_key,
        "mcp_servers": [],
    }

    # Load additional configuration from file if provided
    if config_file and os.path.exists(config_file):
        with open(config_file) as f:
            file_config = json.load(f)
            config_data.update(file_config)

    # Parse MCP servers from environment or config
    mcp_servers_env = os.getenv("MCP_SERVERS")
    if mcp_servers_env and not config_data.get("mcp_servers"):
        try:
            mcp_servers_data = json.loads(mcp_servers_env)
            config_data["mcp_servers"] = [
                MCPServerConfig(**server) for server in mcp_servers_data
            ]
        except json.JSONDecodeError:
            print("Warning: Invalid MCP_SERVERS JSON in environment variable")

    return AgentConfig(**config_data)


def build_agent_config_from_server(
    server_config: "MCPServerConfig", api_key: str | None = None
) -> AgentConfig:
    """
    Build AgentConfig directly from MCPServerConfig without using files.
    This eliminates unnecessary file I/O when processing API requests.
    """

    # Use provided API key or fall back to environment
    anthropic_key = api_key or os.getenv("ANTHROPIC_API_KEY")
    if not anthropic_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable is required")

    # Convert API server config to agent format
    # Copy all fields to support both HTTP and stdio transports
    agent_server = MCPServerConfig(
        name=server_config.name,
        transport=server_config.transport,
        url=server_config.url,
        command=server_config.command,
        env=server_config.env,
        cwd=server_config.cwd,
        authorization_token=server_config.authorization_token,
        oauth=server_config.oauth,
    )

    return AgentConfig(anthropic_api_key=anthropic_key, mcp_servers=[agent_server])
