#!/usr/bin/env python3
"""
Quickstart and demo CLI commands: quickstart group with demo subcommand
"""

import json
import warnings
from pathlib import Path

import click

from ..shared.console_shared import get_console
from .post_command_hooks import trigger_post_command_hooks
from .test_execution import run_tests_with_enhanced_progress
from .utils import validate_api_keys


def create_quickstart_group():
    """Create the quickstart command group"""

    @click.command(name="quickstart")
    @click.option(
        "--skip-config", is_flag=True, help="Skip configuration creation step"
    )
    @click.pass_context
    def mcpt_quickstart(ctx, skip_config):
        """Complete onboarding experience for first-time users

        Streamlined workflow: setup guide → configuration creation → shell completion
        """
        console = get_console()

        # Step 1: Show setup guide
        show_quickstart_guide()

        # Step 2: API key validation (skip demo, go straight to config)
        anthropic_key, _ = validate_api_keys()
        if not anthropic_key:
            console.print_error("Missing ANTHROPIC_API_KEY environment variable")
            console.console.print("\n[bold]Set up your API key:[/bold]")
            console.console.print("  [dim]export ANTHROPIC_API_KEY=your_key_here[/dim]")
            console.console.print(
                "  [dim]# Get your API key: https://console.anthropic.com/[/dim]"
            )
            trigger_post_command_hooks(ctx)
            return

        console.print_success("API keys ready! Let's create your configurations.")

        # Step 3: Create persistent configuration (main focus)
        if not skip_config:
            create_configuration_step(console)

        # Step 4: Set up shell completion
        setup_completion_step(console)

        # Trigger post-command hooks
        trigger_post_command_hooks(ctx)

    return mcpt_quickstart


def run_quickstart_demo(console):
    """Run the demo test with built-in configuration - extracted from old demo subcommand"""
    warnings.filterwarnings("ignore")

    console.print_header("MCP Testing Quick Demo")
    console.console.print("=" * 50)

    # Check API keys first
    anthropic_key, openai_key = validate_api_keys()
    if not anthropic_key:
        console.print_error("Missing ANTHROPIC_API_KEY environment variable")
        console.console.print("\n[bold]Set up your API key:[/bold]")
        console.console.print("  [dim]export ANTHROPIC_API_KEY=your_key_here[/dim]")
        console.console.print(
            "  [dim]# Get your API key: https://console.anthropic.com/[/dim]"
        )
        console.console.print("\n[dim]Then run: mcp-t quickstart[/dim]")
        return False

    console.print_success("API keys ready!")
    console.print_info("Running demo with Hacker News MCP server...")
    console.console.print("   This will test real MCP functionality with AI agents")
    console.console.print()

    # Check that required example files exist
    examples_dir = Path("examples")
    suite_file = examples_dir / "suite.json"
    server_file = examples_dir / "server.json"

    if not suite_file.exists() or not server_file.exists():
        missing_files = []
        if not suite_file.exists():
            missing_files.append(f"{suite_file} (test suite configuration)")
        if not server_file.exists():
            missing_files.append(f"{server_file} (server configuration)")

        console.print_error(
            "Missing required example files",
            ["Creating configurations in next step will resolve this"],
        )
        console.console.print("\n[bold]Required files:[/bold]")
        for file_desc in missing_files:
            console.console.print(f"  • {file_desc}")

        # Use built-in demo configurations instead
        console.print_info("Using built-in demo configuration instead...")
        return run_demo_with_builtin_config(console)

    try:
        console.print("Starting quickstart demo...")

        # Load example configurations from files
        with open(suite_file) as f:
            demo_suite = json.load(f)
        with open(server_file) as f:
            demo_server = json.load(f)

        run_tests_with_enhanced_progress(demo_suite, demo_server, verbose=False)

        # If we get here, the run was successful
        console.console.print()
        results_content = """✅ Framework is working correctly
💡 What just happened:
  • Tested MCP server functionality
  • Ran conversation tests with AI agents
  • Used real MCP protocol communication
  • Saved results to test_results/

Next step: Create your own configurations"""

        results_panel = console.create_results_panel(
            "Quickstart Demo Complete", results_content, success=True
        )
        console.console.print(results_panel)
        return True

    except Exception as e:
        console.print_error(
            f"Demo failed: {str(e)}",
            [
                "This can happen if the demo server is unavailable",
                "Don't worry - we'll set up your own configurations next",
            ],
        )
        return False


def run_demo_with_builtin_config(console):
    """Run demo using built-in configurations when example files are missing"""
    try:
        console.print("Running demo with built-in configuration...")

        # Use the built-in demo suite and server
        demo_suite = get_built_in_demo_suite()
        demo_server = get_built_in_demo_server()

        run_tests_with_enhanced_progress(demo_suite, demo_server, verbose=False)

        console.console.print()
        results_content = """✅ Framework is working correctly
💡 What just happened:
  • Tested built-in demo configuration
  • Validated MCP Testing framework
  • Ready to create your own configurations

Next step: Set up your server and test configurations"""

        results_panel = console.create_results_panel(
            "Demo Complete", results_content, success=True
        )
        console.console.print(results_panel)
        return True

    except Exception as e:
        console.print_error(
            f"Built-in demo failed: {str(e)}",
            ["Framework may need configuration - let's set up your configs"],
        )
        return False


def create_configuration_step(console):
    """Step 3: Offer to create persistent configuration"""
    from rich.prompt import Confirm

    console.console.print()
    console.print_header("Configuration Setup")

    if not Confirm.ask("Create your own server and test configurations?", default=True):
        console.print_info("You can create configurations later with 'mcp-t create'")
        return

    # Import and use the config manager
    from datetime import datetime

    from rich.prompt import Prompt

    from ..config.config_manager import ConfigManager

    config_manager = ConfigManager()

    console.print("📍 Creating local project configuration\n")

    # Ensure local directories exist
    paths = config_manager.paths.get_local_paths()
    for path in [paths["servers_dir"], paths["suites_dir"]]:
        path.mkdir(parents=True, exist_ok=True)

    # Server setup with memorable ID
    server_id = Prompt.ask("Server ID (easy to remember)", default="my-server")
    server_name = Prompt.ask("Server name", default="My MCP Server")
    server_url = Prompt.ask("Server URL")

    # Create server config with ID
    server_config = {
        "name": server_name,
        "type": "url",
        "url": server_url,
        "tool_configuration": {"enabled": True},
    }

    # Save to local location
    local_paths = config_manager.paths.get_local_paths()
    server_file = local_paths["servers_dir"] / f"{server_id}.json"

    with server_file.open("w") as f:
        json.dump(server_config, f, indent=2)

    console.print(f"✅ Server configuration saved: {server_file}")
    console.print(f"✅ Created server config: [cyan]{server_id}[/cyan]")

    # Test suite setup with memorable ID
    suite_id = Prompt.ask("Test suite ID (easy to remember)", default="basic-tests")
    suite_name = Prompt.ask("Test suite name", default="Basic Test Suite")

    # Interactive test creation
    test_cases = []
    while True:
        console.print(f"\nTest case {len(test_cases) + 1}:")
        test_id = Prompt.ask("Test ID", default=f"test_{len(test_cases) + 1}")
        user_message = Prompt.ask("User message")
        success_criteria = Prompt.ask("Success criteria")

        test_cases.append(
            {
                "test_id": test_id,
                "user_message": user_message,
                "success_criteria": success_criteria,
                "timeout_seconds": 60,
            }
        )

        if not Confirm.ask("Add another test case?", default=False):
            break

    # Create suite config with ID
    suite_config = {
        "suite_id": suite_id,
        "name": suite_name,
        "test_type": "basic",
        "test_cases": test_cases,
        "created_at": datetime.now().isoformat(),
    }

    # Save to local location
    suite_file = local_paths["suites_dir"] / f"{suite_id}.json"

    with suite_file.open("w") as f:
        json.dump(suite_config, f, indent=2)

    console.print(f"✅ Suite configuration saved: {suite_file}")
    console.print(f"✅ Created test suite config: [cyan]{suite_id}[/cyan]")
    console.print()
    console.print_success("Configuration complete! Now try:")
    console.print(f"  [cyan]mcp-t run {suite_id} {server_id}[/cyan]")


def setup_completion_step(console):
    """Step 4: Set up shell completion"""
    from rich.prompt import Confirm

    # Import shell completion functions
    from ..shell_integration.setup_completion import (
        is_completion_configured,
        setup_completion,
        verify_installation,
    )

    console.console.print()
    console.print_header("Shell Completion Setup")

    # Check if already configured
    if is_completion_configured():
        console.print_success("Shell completion already configured!")
        console.console.print()
        console.console.print("[bold]Quickstart complete! 🎉[/bold]")
        return

    if not Confirm.ask("Would you like to set up shell tab completion?", default=True):
        console.print_info(
            "You can set up completion later with 'mcp-t completion-setup'"
        )
        console.console.print()
        console.console.print("[bold]Quickstart complete! 🎉[/bold]")
        return

    if not verify_installation():
        console.print_warning("mcp-t command not accessible, skipping completion setup")
        console.console.print()
        console.console.print("[bold]Quickstart complete! 🎉[/bold]")
        return

    try:
        setup_completion()
        console.print_success("Shell completion configured!")
        console.console.print()
        console.console.print("[bold]Quickstart complete! 🎉[/bold]")
        console.console.print(
            "Start a new shell or run 'source ~/.bashrc' (bash) / 'source ~/.zshrc' (zsh)"
        )
    except Exception as e:
        console.print_error(f"Shell completion setup failed: {str(e)}")
        console.console.print()
        console.console.print("[bold]Quickstart complete! 🎉[/bold]")


def show_quickstart_guide():
    """Show step-by-step setup guide with nice panel like the old help system"""
    from rich.panel import Panel

    console = get_console()

    # Create the nice panel display reflecting unified quickstart flow
    content = """[bold blue]🚀 Complete Onboarding in One Command![/bold blue]

[bold]Step 1: Set Up API Keys[/bold]
  [cyan]$ export ANTHROPIC_API_KEY=your_key_here[/cyan]
  [cyan]$ export OPENAI_API_KEY=your_key_here[/cyan]

[bold]Step 2: Complete Onboarding[/bold]
  [cyan]$ mcp-t quickstart[/cyan]
  Streamlined workflow: guide → your configs → shell completion

[bold]Step 3: Run Your First Test[/bold]
  [cyan]$ mcp-t run basic-tests my-server[/cyan]
  (Use the IDs you created in quickstart)

[bold]Step 4: Create More Tests[/bold]
  [cyan]$ mcp-t create suite[/cyan]          # Interactive test creation
  [cyan]$ mcp-t create server[/cyan]         # Add more servers

[bold]Step 5: Explore More[/bold]
  [cyan]$ mcp-t list[/cyan]                  # See your configurations
  [cyan]$ mcp-t compliance my-server[/cyan]  # Run compliance tests
  [cyan]$ mcp-t security my-server[/cyan]    # Run security tests

[bold]Pro Tips:[/bold]
• Use Tab completion to see available configurations
• Add -v flag for detailed output
• Use mcp-t COMMAND --help for command-specific help"""

    panel = Panel(
        content,
        title="First-Time User Guide",
        border_style="blue",
        padding=(1, 2),
    )

    console.console.print(panel)


def get_built_in_demo_suite():
    """Built-in demo configuration - no file creation needed"""
    return {
        "suite_id": "demo_suite",
        "name": "Demo Test Suite",
        "description": "Built-in demo for first-time users",
        "test_type": "basic",
        "test_cases": [
            {
                "test_id": "greeting_test",
                "user_message": "Hello! Can you help me test this MCP server?",
                "success_criteria": "Responds helpfully to greeting",
                "timeout_seconds": 60,
            },
            {
                "test_id": "capability_test",
                "user_message": "What capabilities do you have?",
                "success_criteria": "Lists available tools or capabilities",
                "timeout_seconds": 90,
            },
        ],
        "created_at": "2024-01-01T00:00:00Z",
    }


def get_built_in_demo_server():
    """Built-in demo server configuration"""
    # Use existing example server URL if available, otherwise use demo URL
    return {
        "name": "Demo MCP Server",
        "type": "url",
        "url": "https://api.example.com/mcp",  # Demo URL - will fail gracefully
        "tool_configuration": {"enabled": True},
    }
