#!/usr/bin/env python3
"""
Create CLI commands: server, suite, and test-case creation with template selection
"""

import json
from typing import Optional

import click
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table

from ..config.config_manager import ConfigManager, ConfigTemplate
from ..models.conversational import ConversationalTestConfig
from ..shared.console_shared import get_console
from .post_command_hooks import trigger_post_command_hooks


def create_create_group():
    """Create the create command group"""

    @click.group(name="create")
    def mcpt_create():
        """Create new configurations with template selection

        Create servers, test suites, or individual test cases with
        interactive wizards and template selection.
        """
        pass

    # Add subcommands
    mcpt_create.add_command(create_server_command())
    mcpt_create.add_command(create_suite_command())
    mcpt_create.add_command(create_compliance_command())
    mcpt_create.add_command(create_security_command())
    mcpt_create.add_command(create_conversational_command())
    mcpt_create.add_command(create_test_case_command())

    return mcpt_create


def create_server_command():
    """Create the server subcommand"""

    @click.command(name="server")
    @click.option(
        "--global",
        "use_global",
        is_flag=True,
        help="Save configuration globally instead of locally",
    )
    @click.option("--id", "server_id", help="Server ID (if not provided, will prompt)")
    @click.pass_context
    def mcpt_create_server(ctx, use_global: bool, server_id: Optional[str]):
        """Create server configuration

        Interactive wizard to create a new MCP server configuration
        with authentication and tool settings.

        Examples:
          mcp-t create server
          mcp-t create server --id my-production-server
          mcp-t create server --global
        """
        console = get_console()
        config_manager = ConfigManager()

        console.print_header("Server Configuration Creator")

        # Determine storage location
        if use_global:
            console.print("📍 Saving configuration globally (system-wide)\n")
            paths = config_manager.paths.get_system_paths()
            for path in [paths["servers_dir"]]:
                path.mkdir(parents=True, exist_ok=True)
        else:
            console.print("📍 Saving configuration locally (current project)\n")
            paths = config_manager.paths.get_local_paths()
            for path in [paths["servers_dir"]]:
                path.mkdir(parents=True, exist_ok=True)

        # Server setup with memorable ID
        if not server_id:
            server_id = Prompt.ask("Server ID (easy to remember)", default="my-server")

        server_name = Prompt.ask("Server name", default="My MCP Server")
        server_url = Prompt.ask("Server URL")

        # Optional authentication
        if Confirm.ask("Does this server require authentication?", default=False):
            auth_token = Prompt.ask("Authorization token", password=True)
        else:
            auth_token = ""

        # Create server config
        server_config = {
            "name": server_name,
            "type": "url",
            "url": server_url,
            "tool_configuration": {"enabled": True},
        }

        if auth_token:
            server_config["authorization_token"] = auth_token

        # Save to appropriate location
        if use_global:
            system_paths = config_manager.paths.get_system_paths()
            server_file = system_paths["servers_dir"] / f"{server_id}.json"
        else:
            local_paths = config_manager.paths.get_local_paths()
            server_file = local_paths["servers_dir"] / f"{server_id}.json"

        with server_file.open("w") as f:
            json.dump(server_config, f, indent=2)

        console.print(f"✅ Server configuration saved: {server_file}")
        console.print(f"✅ Created server config: [cyan]{server_id}[/cyan]")
        console.print(
            f"\n[bold]Test it with:[/bold] [cyan]mcp-t health {server_id}[/cyan]"
        )

        trigger_post_command_hooks(ctx)

    return mcpt_create_server


def create_suite_command():
    """Create the suite subcommand"""

    @click.command(name="suite")
    @click.option(
        "--global",
        "use_global",
        is_flag=True,
        help="Save configuration globally instead of locally",
    )
    @click.option("--id", "suite_id", help="Suite ID (if not provided, will prompt)")
    @click.pass_context
    def mcpt_create_suite(ctx, use_global: bool, suite_id: Optional[str]):
        """Create test suite with interactive type selection

        Interactive wizard to create test suites with templates for different
        test types: Compliance, Security, or Conversational.

        Examples:
          mcp-t create suite
          mcp-t create suite --id my-security-tests
        """
        console = get_console()
        config_manager = ConfigManager()

        console.print_header("Test Suite Creator")

        # Determine storage location
        if use_global:
            console.print("📍 Saving configuration globally (system-wide)\n")
            paths = config_manager.paths.get_system_paths()
            for path in [paths["suites_dir"]]:
                path.mkdir(parents=True, exist_ok=True)
        else:
            console.print("📍 Saving configuration locally (current project)\n")
            paths = config_manager.paths.get_local_paths()
            for path in [paths["suites_dir"]]:
                path.mkdir(parents=True, exist_ok=True)

        # Always show interactive type selection
        test_type = show_test_type_menu(console)

        # Suite setup with memorable ID
        if not suite_id:
            default_id = f"{test_type}-tests"
            suite_id = Prompt.ask(
                "Test suite ID (easy to remember)", default=default_id
            )

        suite_name = Prompt.ask(
            "Test suite name", default=f"{test_type.title()} Test Suite"
        )

        # Create type-specific suite using new templates
        suite = create_suite_interactive(
            console, config_manager, test_type, suite_id, suite_name
        )

        # Save using type-safe method
        config_manager.save_test_suite(suite, use_global=use_global)

        console.print(f"✅ Created test suite config: [cyan]{suite_id}[/cyan]")
        console.print(f"✅ Suite type: [yellow]{type(suite).__name__}[/yellow]")
        console.print(
            f"\n[bold]Test it with:[/bold] [cyan]mcp-t run {suite_id} <server-id>[/cyan]"
        )

        trigger_post_command_hooks(ctx)

    return mcpt_create_suite


def create_compliance_command():
    """Create compliance suite command"""

    @click.command(name="compliance")
    @click.option(
        "--global", "use_global", is_flag=True, help="Save configuration globally"
    )
    @click.option("--id", "suite_id", help="Suite ID (auto-generated if not provided)")
    def mcpt_create_compliance(use_global: bool, suite_id: Optional[str]):
        """Create compliance test suite for MCP protocol validation

        Examples:
          mcp-t create compliance
          mcp-t create compliance --id my-compliance-tests
        """
        _create_typed_suite("compliance", use_global, suite_id)

    return mcpt_create_compliance


def create_security_command():
    """Create security suite command"""

    @click.command(name="security")
    @click.option(
        "--global", "use_global", is_flag=True, help="Save configuration globally"
    )
    @click.option("--id", "suite_id", help="Suite ID (auto-generated if not provided)")
    def mcpt_create_security(use_global: bool, suite_id: Optional[str]):
        """Create security test suite for auth and vulnerability testing

        Examples:
          mcp-t create security
          mcp-t create security --id my-security-tests
        """
        _create_typed_suite("security", use_global, suite_id)

    return mcpt_create_security


def create_conversational_command():
    """Create conversational suite command"""

    @click.command(name="conversational")
    @click.option(
        "--global", "use_global", is_flag=True, help="Save configuration globally"
    )
    @click.option("--id", "suite_id", help="Suite ID (auto-generated if not provided)")
    def mcpt_create_conversational(use_global: bool, suite_id: Optional[str]):
        """Create conversational test suite for multi-turn dialogue testing

        Examples:
          mcp-t create conversational
          mcp-t create conversational --id my-chat-tests
        """
        _create_typed_suite("conversational", use_global, suite_id)

    return mcpt_create_conversational


def _create_typed_suite(test_type: str, use_global: bool, suite_id: Optional[str]):
    """Helper function to create a specific test suite type"""
    console = get_console()
    config_manager = ConfigManager()

    console.print_header(f"{test_type.title()} Test Suite Creator")

    # Determine storage location
    if use_global:
        console.print("📍 Saving configuration globally (system-wide)\n")
    else:
        console.print("📍 Saving configuration locally (current project)\n")

    # Suite setup with memorable ID
    if not suite_id:
        default_id = f"{test_type}-tests"
        suite_id = Prompt.ask("Test suite ID (easy to remember)", default=default_id)

    suite_name = Prompt.ask(
        "Test suite name", default=f"{test_type.title()} Test Suite"
    )

    # Create type-specific suite
    suite = create_suite_interactive(
        console, config_manager, test_type, suite_id, suite_name
    )

    # Save using type-safe method
    config_manager.save_test_suite(suite)

    console.print(f"✅ Created {test_type} test suite: [cyan]{suite_id}[/cyan]")
    console.print(f"✅ Suite type: [yellow]{type(suite).__name__}[/yellow]")
    console.print(
        f"\n[bold]Test it with:[/bold] [cyan]mcp-t run {suite_id} <server-id>[/cyan]"
    )


def create_test_case_command():
    """Create the test-case subcommand"""

    @click.command(name="test-case")
    @click.option("--suite-id", required=True, help="Suite ID to add test case to")
    def mcpt_create_test_case(suite_id: str):
        """Add test case to existing suite

        Add a new test case to an existing test suite configuration.

        Examples:
          mcp-t create test-case --suite-id basic-tests
        """
        console = get_console()
        config_manager = ConfigManager()

        console.print_header(f"Add Test Case to Suite: {suite_id}")

        # Load existing suite
        try:
            suite = config_manager.get_suite_by_id(suite_id)
            suite_dict = suite.dict()
        except KeyError:
            console.print_error(
                f"Suite '{suite_id}' not found",
                [
                    "Use 'mcp-t list suites' to see available suites",
                    "Or create a new suite with 'mcp-t create suite'",
                ],
            )
            return

        console.print(
            f"📝 Current suite has {len(suite_dict['test_cases'])} test cases"
        )

        # Interactive test case creation
        console.print("\nNew test case:")
        test_id = Prompt.ask(
            "Test ID", default=f"test_{len(suite_dict['test_cases']) + 1}"
        )
        user_message = Prompt.ask("User message")
        success_criteria = Prompt.ask("Success criteria")
        timeout = IntPrompt.ask("Timeout (seconds)", default=60)

        new_test_case = {
            "test_id": test_id,
            "user_message": user_message,
            "success_criteria": success_criteria,
            "timeout_seconds": timeout,
        }

        # Add metadata if the suite has it
        existing_test = suite_dict["test_cases"][0] if suite_dict["test_cases"] else {}
        if "metadata" in existing_test:
            category = Prompt.ask("Category", default="general")
            priority = Prompt.ask("Priority", default="medium")
            new_test_case["metadata"] = {"category": category, "priority": priority}

        # Add to suite
        suite_dict["test_cases"].append(new_test_case)

        # Find and update the suite file
        paths = config_manager.paths.get_all_paths()
        suite_file = None

        for suites_dir in paths["suites_dirs"]:
            potential_file = suites_dir / f"{suite_id}.json"
            if potential_file.exists():
                suite_file = potential_file
                break

        if not suite_file:
            console.print_error("Could not locate suite file to update")
            return

        # Save updated suite
        with suite_file.open("w") as f:
            json.dump(suite_dict, f, indent=2)

        console.print(f"✅ Added test case '{test_id}' to suite '{suite_id}'")
        console.print(f"✅ Suite now has {len(suite_dict['test_cases'])} test cases")

    return mcpt_create_test_case


def show_test_type_menu(console) -> str:
    """Show interactive test type selection menu"""
    console.print("\n[bold]What type of test would you like to create?[/bold]\n")

    # Create table for options
    table = Table(show_header=True, header_style="bold blue")
    table.add_column("Option", style="cyan", no_wrap=True)
    table.add_column("Type", style="green")
    table.add_column("Description", style="dim")

    options = [
        ("1", "compliance", "MCP protocol conformance testing"),
        ("2", "security", "Authentication, validation, rate limiting"),
        ("3", "conversational", "Multi-turn dialogue and workflow testing"),
    ]

    for option, test_type, description in options:
        table.add_row(option, test_type, description)

    console.console.print(table)
    console.print()

    choice = Prompt.ask("Select test type", choices=["1", "2", "3"], default="1")

    type_map = {"1": "compliance", "2": "security", "3": "conversational"}

    selected_type = type_map[choice]
    console.print(f"Selected: [cyan]{selected_type}[/cyan] tests")
    return selected_type


def get_template_for_type(test_type: str) -> Optional[dict]:
    """Get template configuration for test type"""
    config_manager = ConfigManager()

    # Map test types to ConfigTemplate enums
    template_map = {
        "compliance": ConfigTemplate.SIMPLE_SUITE,  # Reuse simple as base compliance template
        "security": ConfigTemplate.SECURITY_SUITE,
        "conversational": ConfigTemplate.WORKFLOW_SUITE,  # Rename workflow to conversational
    }

    template_enum = template_map.get(test_type)
    if template_enum:
        return config_manager.templates[template_enum]

    return None


def customize_template_test_cases(console, template_test_cases: list) -> list:
    """Allow user to customize template test cases"""
    console.print("📝 Customizing template test cases...")

    customized_cases: list = []
    for i, test_case in enumerate(template_test_cases):
        console.print(f"\n[bold]Test Case {i + 1}: {test_case['test_id']}[/bold]")
        console.print(f"Message: {test_case['user_message']}")
        console.print(f"Success: {test_case['success_criteria']}")

        if Confirm.ask("Keep this test case?", default=True):
            if Confirm.ask("Modify it?", default=False):
                # Allow editing
                test_case["user_message"] = Prompt.ask(
                    "User message", default=test_case["user_message"]
                )
                test_case["success_criteria"] = Prompt.ask(
                    "Success criteria", default=test_case["success_criteria"]
                )

            customized_cases.append(test_case)

    # Offer to add more test cases
    while Confirm.ask("Add another test case?", default=False):
        additional_case = create_single_test_case_interactively(
            console, len(customized_cases) + 1
        )
        customized_cases.append(additional_case)

    return customized_cases


def create_test_cases_interactively(console) -> list:
    """Create test cases through interactive prompts"""
    test_cases: list = []

    while True:
        case = create_single_test_case_interactively(console, len(test_cases) + 1)
        test_cases.append(case)

        if not Confirm.ask("Add another test case?", default=len(test_cases) == 0):
            break

    return test_cases


def create_single_test_case_interactively(console, case_number: int) -> dict:
    """Create a single test case interactively"""
    console.print(f"\n[bold]Test case {case_number}:[/bold]")
    test_id = Prompt.ask("Test ID", default=f"test_{case_number}")
    user_message = Prompt.ask("User message")
    success_criteria = Prompt.ask("Success criteria")
    timeout = IntPrompt.ask("Timeout (seconds)", default=60)

    test_case = {
        "test_id": test_id,
        "user_message": user_message,
        "success_criteria": success_criteria,
        "timeout_seconds": timeout,
    }

    # Ask for optional metadata
    if Confirm.ask("Add metadata (category, priority)?", default=False):
        category = Prompt.ask("Category", default="general")
        priority = Prompt.ask("Priority", default="medium")
        test_case["metadata"] = {"category": category, "priority": priority}

    return test_case


def preview_template_test_cases(console, template_suite) -> None:
    """Preview the template test cases that will be included"""
    test_cases = template_suite.test_cases
    console.print(
        f"\n[bold]📋 Template Preview: {len(test_cases)} test case{'s' if len(test_cases) != 1 else ''}[/bold]\n"
    )

    for i, test_case in enumerate(test_cases, 1):
        console.print(f"[cyan]{i}. {test_case.test_id}[/cyan]")

        # Handle different test case types
        if hasattr(test_case, "user_message"):
            # ConversationalTestConfig
            console.print(f"   Message: {test_case.user_message}")
            console.print(f"   Success: {test_case.success_criteria}")
            if hasattr(test_case, "max_turns"):
                console.print(f"   Max Turns: {test_case.max_turns}")
        elif hasattr(test_case, "check_categories"):
            # ComplianceTestConfig
            console.print(f"   Categories: {', '.join(test_case.check_categories)}")
            if hasattr(test_case, "protocol_version"):
                console.print(f"   Protocol: {test_case.protocol_version}")
        elif hasattr(test_case, "vulnerability_checks"):
            # SecurityTestConfig
            console.print(f"   Auth Method: {test_case.auth_method}")
            console.print(f"   Checks: {', '.join(test_case.vulnerability_checks)}")
            if hasattr(test_case, "rate_limit_threshold"):
                console.print(f"   Rate Limit: {test_case.rate_limit_threshold}")

        console.print()


def show_customization_menu(console) -> str:
    """Show customization options menu"""
    console.print("\n[bold]How would you like to proceed with test cases?[/bold]\n")

    table = Table(show_header=True, header_style="bold blue")
    table.add_column("Option", style="cyan", no_wrap=True)
    table.add_column("Description", style="dim")

    options = [
        ("1", "Use template as-is (quick setup)"),
        ("2", "Customize template test cases"),
        ("3", "Add additional test cases"),
        ("4", "Start with empty suite (no templates)"),
    ]

    for option, description in options:
        table.add_row(option, description)

    console.console.print(table)
    console.print()

    choice = Prompt.ask("Select option", choices=["1", "2", "3", "4"], default="1")

    option_map = {
        "1": "use_template",
        "2": "customize_template",
        "3": "add_additional",
        "4": "empty_suite",
    }

    return option_map[choice]


def dict_to_conversational_test_config(test_dict: dict) -> ConversationalTestConfig:
    """Convert dict format test case to ConversationalTestConfig"""
    return ConversationalTestConfig(
        test_id=test_dict["test_id"],
        user_message=test_dict["user_message"],
        success_criteria=test_dict["success_criteria"],
        max_turns=test_dict.get("max_turns", 10),
        context_persistence=test_dict.get("context_persistence", True),
        metadata=test_dict.get("metadata"),
    )


def conversational_test_config_to_dict(test_config: ConversationalTestConfig) -> dict:
    """Convert ConversationalTestConfig to dict format for editing"""
    result = {
        "test_id": test_config.test_id,
        "user_message": test_config.user_message,
        "success_criteria": test_config.success_criteria,
        "timeout_seconds": 60,  # Default timeout for compatibility
    }

    if test_config.metadata:
        result["metadata"] = test_config.metadata

    return result


def customize_conversational_template_test_cases(
    console, template_test_cases: list
) -> list:
    """Allow user to customize conversational template test cases"""
    console.print("📝 Customizing conversational template test cases...")

    # Convert to dict format for compatibility with existing functions
    dict_test_cases = [
        conversational_test_config_to_dict(tc) for tc in template_test_cases
    ]

    # Use existing customization function
    customized_dict_cases = customize_template_test_cases(console, dict_test_cases)

    # Convert back to ConversationalTestConfig objects
    customized_cases = [
        dict_to_conversational_test_config(tc) for tc in customized_dict_cases
    ]

    return customized_cases


def create_conversational_test_cases_interactively(console) -> list:
    """Create conversational test cases through interactive prompts"""
    # Use existing function to get dict format
    dict_test_cases = create_test_cases_interactively(console)

    # Convert to ConversationalTestConfig objects
    conversational_cases = [
        dict_to_conversational_test_config(tc) for tc in dict_test_cases
    ]

    return conversational_cases


def create_suite_interactive(
    console, config_manager, test_type: str, suite_id: str, suite_name: str
):
    """Create suite interactively using type-specific templates with customization options"""

    if test_type == "compliance":
        return create_compliance_suite_interactive(
            console, config_manager, suite_id, suite_name
        )
    elif test_type == "security":
        return create_security_suite_interactive(
            console, config_manager, suite_id, suite_name
        )
    elif test_type == "conversational":
        return create_conversational_suite_interactive(
            console, config_manager, suite_id, suite_name
        )
    else:
        raise ValueError(f"Unknown test type: {test_type}")


def create_compliance_suite_interactive(
    console, config_manager, suite_id: str, suite_name: str
):
    """Interactive creation of compliance test suite"""
    # Start with template
    template = config_manager.create_compliance_template()
    template.suite_id = suite_id
    template.name = suite_name

    # Show template preview
    preview_template_test_cases(console, template)

    # Show customization options
    customization_choice = show_customization_menu(console)

    # Handle different customization choices
    if customization_choice == "use_template":
        console.print("Using template as-is")
    elif customization_choice == "customize_template":
        console.print("Customizing template test cases...")
        # Note: customize_template_test_cases works with dict format, need to adapt for Pydantic models
        console.print(
            "⚠️  Template customization for compliance tests not yet supported"
        )
        console.print("Using template as-is for now")
    elif customization_choice == "add_additional":
        console.print("Adding additional test cases...")
        # Note: create_test_cases_interactively creates dict format, need to adapt
        console.print(
            "⚠️  Additional test case creation for compliance tests not yet supported"
        )
        console.print("Using template as-is for now")
    elif customization_choice == "empty_suite":
        console.print("Starting with empty suite")
        template.test_cases = []

    # Customize compliance-specific settings
    auth_required = Confirm.ask("Require authentication?", default=False)
    strict_mode = Confirm.ask("Enable strict protocol checking?", default=True)

    template.auth_required = auth_required
    template.strict_mode = strict_mode

    console.print(f"✅ Created compliance suite with {len(template.test_cases)} tests")
    return template


def create_security_suite_interactive(
    console, config_manager, suite_id: str, suite_name: str
):
    """Interactive creation of security test suite"""
    template = config_manager.create_security_template()
    template.suite_id = suite_id
    template.name = suite_name

    # Show template preview
    preview_template_test_cases(console, template)

    # Show customization options
    customization_choice = show_customization_menu(console)

    # Handle different customization choices
    if customization_choice == "use_template":
        console.print("Using template as-is")
    elif customization_choice == "customize_template":
        console.print("Customizing template test cases...")
        console.print("⚠️  Template customization for security tests not yet supported")
        console.print("Using template as-is for now")
    elif customization_choice == "add_additional":
        console.print("Adding additional test cases...")
        console.print(
            "⚠️  Additional test case creation for security tests not yet supported"
        )
        console.print("Using template as-is for now")
    elif customization_choice == "empty_suite":
        console.print("Starting with empty suite")
        template.test_cases = []

    # Security-specific customizations
    include_pentest = Confirm.ask("Include penetration testing?", default=False)
    template.include_penetration_tests = include_pentest

    console.print(f"✅ Created security suite with {len(template.test_cases)} tests")
    return template


def create_conversational_suite_interactive(
    console, config_manager, suite_id: str, suite_name: str
):
    """Interactive creation of conversational test suite"""
    template = config_manager.create_conversational_template()
    template.suite_id = suite_id
    template.name = suite_name

    # Show template preview
    preview_template_test_cases(console, template)

    # Show customization options
    customization_choice = show_customization_menu(console)

    # Handle different customization choices
    if customization_choice == "use_template":
        console.print("Using template as-is")
    elif customization_choice == "customize_template":
        customized_test_cases = customize_conversational_template_test_cases(
            console, template.test_cases
        )
        template.test_cases = customized_test_cases
    elif customization_choice == "add_additional":
        console.print("Adding additional test cases to template...")
        additional_cases = create_conversational_test_cases_interactively(console)
        template.test_cases.extend(additional_cases)
    elif customization_choice == "empty_suite":
        console.print("Starting with empty suite")
        template.test_cases = []
        # Still allow adding test cases to empty suite
        if Confirm.ask("Add test cases to the empty suite?", default=True):
            new_cases = create_conversational_test_cases_interactively(console)
            template.test_cases = new_cases

    # Conversation-specific customizations
    patience_levels = ["low", "medium", "high"]
    patience = Prompt.ask(
        "User patience level", choices=patience_levels, default="medium"
    )
    template.user_patience_level = patience

    console.print(
        f"✅ Created conversational suite with {len(template.test_cases)} tests"
    )
    return template
