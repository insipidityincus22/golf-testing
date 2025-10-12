"""
MCP Testing Framework

A comprehensive testing framework for MCP (Model Context Protocol) servers with AI agents.
Supports both single-response testing and multi-turn conversation testing.
"""

# Import main subpackages
from . import conversation, core

__version__ = "0.2.0"
__all__ = ["conversation", "core"]
