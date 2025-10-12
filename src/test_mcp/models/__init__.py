"""
Type-specific test models for MCP Testing Framework.

This module provides separate, type-safe models for different test types:
- Compliance tests: MCP protocol spec validation
- Security tests: Authentication/authorization testing
- Conversational tests: Multi-turn dialogue testing

Replaces the monolithic shared models to eliminate field pollution
and enable compile-time type safety.
"""

from .base import BaseTestConfig, BaseTestSuite
from .compliance import ComplianceTestConfig, ComplianceTestSuite
from .conversational import ConversationalTestConfig, ConversationTestSuite
from .security import SecurityTestConfig, SecurityTestSuite

__all__ = [
    "BaseTestConfig",
    "BaseTestSuite",
    "ComplianceTestConfig",
    "ComplianceTestSuite",
    "ConversationTestSuite",
    "ConversationalTestConfig",
    "SecurityTestConfig",
    "SecurityTestSuite",
]
