"""
Configuration constants and settings for the MCP Testing Framework.

Local-first configuration for standalone CLI testing tool.
"""

import os

# API Keys for Local Testing
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Validate required API keys
if not ANTHROPIC_API_KEY:
    import warnings

    warnings.warn(
        "ANTHROPIC_API_KEY environment variable is not set. Agent functionality will be limited.",
        stacklevel=2,
    )

if not OPENAI_API_KEY:
    import warnings

    warnings.warn(
        "OPENAI_API_KEY environment variable is not set. Judge and user simulator functionality will be limited.",
        stacklevel=2,
    )

# Task Configuration
MAX_RESULT_SIZE_MB = int(os.getenv("MAX_TASK_RESULT_SIZE_MB", "50"))
