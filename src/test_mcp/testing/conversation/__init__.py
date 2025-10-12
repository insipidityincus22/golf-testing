"""
Conversation Testing Framework

Enhanced testing framework for multi-turn conversation testing with MCP servers.
Includes user simulation, conversation management, and conversation-aware evaluation.
"""

from .conversation_judge import ConversationJudge
from .conversation_manager import ConversationManager
from .conversation_models import (
    ConversationConfig,
    ConversationResult,
    ConversationStatus,
    ConversationTurn,
    UserSimulatorResponse,
)
from .user_simulator import UserSimulator

__all__ = [
    # Models
    "ConversationStatus",
    "ConversationTurn",
    "ConversationResult",
    "UserSimulatorResponse",
    "ConversationConfig",
    # Components
    "UserSimulator",
    "ConversationManager",
    "ConversationJudge",
]
