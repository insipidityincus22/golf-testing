import platform
import sys
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from .. import __version__


class IssueCategory(str, Enum):
    """Issue category enumeration"""

    BUG = "bug"
    PERFORMANCE = "performance"
    USABILITY = "usability"
    FEATURE_REQUEST = "feature_request"
    DOCUMENTATION = "documentation"
    OTHER = "other"


class SystemInfo(BaseModel):
    """System diagnostic information"""

    cli_version: str = Field(default=__version__, description="CLI version")
    python_version: str = Field(
        default_factory=lambda: sys.version, description="Python version"
    )
    platform: str = Field(
        default_factory=lambda: platform.platform(), description="OS platform"
    )
    architecture: str = Field(
        default_factory=lambda: platform.machine(), description="CPU architecture"
    )


class CommandHistoryEntry(BaseModel):
    """Single command history entry"""

    command: str = Field(..., description="Command that was executed")
    timestamp: datetime = Field(..., description="When command was executed")
    exit_code: int | None = Field(default=None, description="Command exit code")
    duration_ms: float | None = Field(default=None, description="Command duration")


class IssueReport(BaseModel):
    """Complete issue report data model"""

    # Report metadata
    report_id: str = Field(..., description="Unique report identifier")
    user_id: str = Field(..., description="Anonymous user identifier")
    submitted_at: datetime = Field(
        default_factory=datetime.now, description="Submission timestamp"
    )

    # Issue classification
    category: IssueCategory = Field(
        default=IssueCategory.BUG, description="Issue category"
    )
    title: str = Field(..., description="Brief issue title")
    description: str = Field(..., description="Detailed issue description")

    # Context information
    system_info: SystemInfo | None = Field(
        default_factory=SystemInfo, description="System diagnostic data"
    )
    command_history: list[CommandHistoryEntry] = Field(
        default_factory=list, description="Recent command history"
    )
    error_context: dict[str, Any] | None = Field(
        default=None, description="Error context if available"
    )

    # User consent
    include_diagnostics: bool = Field(
        default=True, description="User agreed to include diagnostic data"
    )
    include_command_history: bool = Field(
        default=True, description="User agreed to include command history"
    )


class ReportSubmissionResult(BaseModel):
    """Result of report submission attempt"""

    success: bool = Field(..., description="Whether submission succeeded")
    report_id: str | None = Field(default=None, description="Server-assigned report ID")
    submitted_at: datetime | None = Field(
        default=None, description="Actual submission timestamp"
    )
    error_message: str | None = Field(
        default=None, description="Error message if failed"
    )
