import uuid
from typing import Any

from ..models.reporting import IssueCategory, IssueReport
from ..services.reporting_client import get_reporting_client
from ..shared.console_shared import get_console
from ..utils.command_tracker import get_command_tracker
from ..utils.user_tracking import get_user_tracker


def suggest_issue_reporting():
    """Show issue reporting suggestion after every command (non-intrusive)"""
    console = get_console()

    # Very subtle, non-intrusive suggestion (similar to update notifier)
    console.console.print()
    console.console.print(
        "[dim]💡 Found a bug or have feedback? [/dim][cyan]mcp-t report issue[/cyan]"
    )
    console.console.print()


def create_error_report(
    title: str,
    description: str,
    category: IssueCategory = IssueCategory.BUG,
    error_context: dict[str, Any] | None = None,
) -> IssueReport:
    """Create issue report with full diagnostic context"""
    user_tracker = get_user_tracker()
    command_tracker = get_command_tracker()

    return IssueReport(
        report_id=str(uuid.uuid4()),
        user_id=user_tracker.get_or_create_user_id(),
        category=category,
        title=title,
        description=description,
        command_history=command_tracker.get_recent_history(limit=10),
        error_context=error_context,
    )


async def submit_report_with_feedback(report: IssueReport) -> bool:
    """Submit report and provide user feedback"""
    console = get_console()
    client = get_reporting_client()

    console.print_info("📤 Submitting issue report...")

    result = await client.submit_report(report)

    if result and result.success:
        report_id_short = result.report_id[:8] if result.report_id else "unknown"
        console.print_success(
            f"✅ Report submitted successfully (ID: {report_id_short}...)"
        )
        console.print_info("Thank you for helping improve the MCP Testing Framework!")
        return True
    else:
        error_msg = result.error_message if result else "Unknown error"
        console.print_warning(f"⚠️  Report submission failed: {error_msg}")
        console.print_info(
            "Your feedback is valuable - please try again later or contact us at founders@golf.dev"
        )
        return False
