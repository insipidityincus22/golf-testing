"""
test-mcp: Comprehensive testing framework for MCP (Model Context Protocol) servers

A sophisticated testing framework that combines AI agents with MCP server connectivity
for automated testing and CI/CD integration.
"""

__version__ = "0.1.0"
__author__ = "MCP Testing Suite"
__email__ = "info@example.com"

# Import main components for easy access
from .agent.agent import ClaudeAgent
from .testing.conversation.conversation_judge import ConversationJudge
from .testing.conversation.conversation_manager import ConversationManager
from .testing.core.test_models import TestCase, TestRun, TestSuite

__all__ = [
    "__version__",
    "ClaudeAgent",
    "TestCase",
    "TestSuite",
    "TestRun",
    "ConversationManager",
    "ConversationJudge",
]
