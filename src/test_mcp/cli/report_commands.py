import asyncio

import click
from rich.prompt import Confirm, Prompt

from ..cli.reporting_integration import create_error_report, submit_report_with_feedback
from ..models.reporting import IssueCategory, IssueReport
from ..shared.console_shared import get_console
from ..utils.command_tracker import get_command_tracker


def create_report_group():
    """Create the report command group following CLI factory pattern"""

    @click.group(name="report")
    def mcpt_report():
        """Report issues and provide feedback to improve mcp-t"""
        pass

    # Add subcommands to group
    mcpt_report.add_command(create_issue_command())
    return mcpt_report


def create_issue_command():
    """Create the issue reporting command"""

    @click.command(name="issue")
    @click.option(
        "--category",
        type=click.Choice([c.value for c in IssueCategory], case_sensitive=False),
        help="Issue category",
    )
    @click.option("--title", help="Brief issue title")
    @click.option("--description", help="Detailed issue description")
    @click.option(
        "--no-diagnostics",
        is_flag=True,
        help="Exclude system diagnostic information",
    )
    @click.option("--no-history", is_flag=True, help="Exclude recent command history")
    @click.option("--dry-run", is_flag=True, help="Show report data without submitting")
    def mcpt_report_issue(
        category: str | None,
        title: str | None,
        description: str | None,
        no_diagnostics: bool,
        no_history: bool,
        dry_run: bool,
    ):
        """Report an issue to help improve the MCP Testing Framework

        \\b
        This command collects diagnostic information to help identify and fix issues.
        All data collection requires your consent and no sensitive information is included.

        Examples:
          mcp-t report issue                           # Interactive mode
          mcp-t report issue --category=bug            # Pre-select category
          mcp-t report issue --dry-run                 # Preview report without sending
        """
        console = get_console()

        # Record this command execution
        command_tracker = get_command_tracker()
        command_tracker.record_command("mcp-t report issue")

        try:
            # Interactive prompts if values not provided
            if not title:
                title = Prompt.ask(
                    "[bold]Brief issue title[/bold]", default="Issue with mcp-t command"
                )

            if not description:
                description = Prompt.ask(
                    "[bold]Detailed description[/bold]\n[dim]What happened? What did you expect?[/dim]"
                )

            if not category:
                console.console.print("\n[bold]Issue category:[/bold]")
                categories = list(IssueCategory)
                for i, cat in enumerate(categories, 1):
                    console.console.print(
                        f"  {i}. {cat.value.replace('_', ' ').title()}"
                    )

                choice = Prompt.ask(
                    "Select category",
                    choices=[str(i) for i in range(1, len(categories) + 1)],
                    default="1",
                )
                category = categories[int(choice) - 1].value

            # User consent for data collection
            include_diagnostics = not no_diagnostics
            include_history = not no_history

            # Skip consent prompts in dry-run mode
            if not dry_run:
                if not no_diagnostics and not Confirm.ask(
                    "\n[yellow]Include system diagnostic information?[/yellow]\n[dim](CLI version, Python version, OS)[/dim]"
                ):
                    include_diagnostics = False

                if not no_history and not Confirm.ask(
                    "\n[yellow]Include recent command history?[/yellow]\n[dim](Last 10 commands for debugging context)[/dim]"
                ):
                    include_history = False

            # Create report
            report = create_error_report(
                title=title,
                description=description,
                category=IssueCategory(category),
            )

            # Apply user preferences
            report.include_diagnostics = include_diagnostics
            report.include_command_history = include_history

            if not include_diagnostics:
                report.system_info = None
            if not include_history:
                report.command_history = []

            # Dry run mode
            if dry_run:
                _preview_report(report)
                return

            # Confirm submission
            if not Confirm.ask(
                f"\n[green]Submit report?[/green]\n[dim]Report ID: {report.report_id[:8]}...[/dim]"
            ):
                console.print_info("Report cancelled.")
                return

            # Submit report
            success = asyncio.run(submit_report_with_feedback(report))

            if success:
                command_tracker.record_command("mcp-t report issue", exit_code=0)
            else:
                command_tracker.record_command("mcp-t report issue", exit_code=1)

        except KeyboardInterrupt:
            console.print_info("\nReport cancelled by user.")
        except Exception as e:
            console.print_error(f"Failed to create report: {e!s}")
            command_tracker.record_command("mcp-t report issue", exit_code=1)

    return mcpt_report_issue


def _preview_report(report: IssueReport):
    """Preview report data in dry-run mode"""
    console = get_console()

    console.print_header("📋 Report Preview (Dry Run)")
    console.console.print()
    console.console.print(f"[bold]Report ID:[/bold] {report.report_id}")
    console.console.print(f"[bold]Category:[/bold] {report.category.value}")
    console.console.print(f"[bold]Title:[/bold] {report.title}")
    console.console.print("[bold]Description:[/bold]")
    console.console.print(f"  {report.description}")
    console.console.print()

    if report.include_diagnostics and report.system_info:
        console.console.print(
            f"[bold]System Info:[/bold] {report.system_info.cli_version}, {report.system_info.platform}"
        )

    if report.include_command_history and report.command_history:
        console.console.print("[bold]Command History:[/bold]")
        for cmd in report.command_history[-10:]:
            console.console.print(f"  • {cmd.command}")

    console.console.print(
        "\n[dim]Use --dry-run=false to actually submit this report.[/dim]"
    )
