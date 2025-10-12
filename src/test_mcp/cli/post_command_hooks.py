"""Centralized post-command hook system for consistent notifications across all CLI commands."""


def trigger_post_command_hooks(ctx):
    """Execute post-command hooks with support for all global flags

    This function should be called at the end of every CLI command to ensure
    consistent behavior for update notifications and issue reporting suggestions.

    Args:
        ctx: Click context object containing global flags
    """
    # Handle both main command context and subcommand context
    if ctx.parent and ctx.parent.obj:
        # Subcommand - get flags from parent context
        no_update_notifier = ctx.parent.obj.get("no_update_notifier", False)
        no_report_suggestions = ctx.parent.obj.get("no_report_suggestions", False)
    elif ctx.obj:
        # Main command - get flags from current context
        no_update_notifier = ctx.obj.get("no_update_notifier", False)
        no_report_suggestions = ctx.obj.get("no_report_suggestions", False)
    else:
        # Fallback - no flags available, show everything
        no_update_notifier = False
        no_report_suggestions = False

    # Show update notification first (existing behavior)
    if not no_update_notifier:
        from .update_notifier import check_for_updates

        check_for_updates()

    # Show issue reporting suggestion (this was missing from subcommands)
    if not no_report_suggestions:
        from .reporting_integration import suggest_issue_reporting

        suggest_issue_reporting()
