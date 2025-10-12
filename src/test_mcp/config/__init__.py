"""
Configuration management system for MCP Testing Framework.

Provides organized config storage with memorable IDs instead of complex file paths.
"""

from .config_manager import ConfigManager, ConfigTemplate, MCPPaths

__all__ = ["ConfigManager", "ConfigTemplate", "MCPPaths"]
