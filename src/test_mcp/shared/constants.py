"""Shared constants and defaults for MCP Testing Framework"""

# Test execution defaults
DEFAULT_PARALLELISM = 5
DEFAULT_MAX_TURNS = 10
DEFAULT_TIMEOUT = 60  # seconds

# Configuration defaults
DEFAULT_SERVER_TYPE = "url"
DEFAULT_TOOL_CONFIG = {"enabled": True}

# Test status values
STATUS_QUEUED = "queued"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
