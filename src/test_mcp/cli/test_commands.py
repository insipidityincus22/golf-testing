#!/usr/bin/env python3
"""
Test execution CLI commands: run, compliance, security, health
"""

import sys
from datetime import datetime

import click

from ..config.config_manager import ConfigManager
from ..models.compliance import ComplianceTestConfig, ComplianceTestSuite
from ..models.security import SecurityTestConfig, SecurityTestSuite
from ..shared.console_shared import get_console
from .completion import complete_server_ids, complete_suite_ids
from .post_command_hooks import trigger_post_command_hooks
from .suggestions import enhanced_error_handler
from .test_execution import (
    run_test_suite,
    run_with_mcpt_inference,
)


def validate_server_id_enhanced(ctx, param, value):
    """Enhanced server ID validation with suggestions"""
    return enhanced_error_handler(ctx, param, value, "server")


def validate_suite_id_enhanced(ctx, param, value):
    """Enhanced suite ID validation with suggestions"""
    return enhanced_error_handler(ctx, param, value, "suite")


def get_or_create_compliance_suite() -> ComplianceTestSuite:
    """Create default compliance test suite"""
    return ComplianceTestSuite(
        suite_id="default-compliance",
        name="Default MCP Compliance Tests",
        description="Standard MCP protocol validation tests",
        compliance_tests=[
            ComplianceTestConfig(
                test_id="protocol_handshake",
                name="Protocol Handshake Validation",
                protocol_version="1.0",
                check_categories=["handshake"],
            ),
            ComplianceTestConfig(
                test_id="capabilities_discovery",
                name="Server Capabilities Discovery",
                check_categories=["capabilities"],
            ),
            ComplianceTestConfig(
                test_id="tool_enumeration",
                name="Tool Discovery and Validation",
                check_categories=["tools"],
            ),
        ],
        oauth_required=False,
        strict_mode=True,
        created_at=datetime.utcnow(),
    )


def get_or_create_security_suite() -> SecurityTestSuite:
    """Create default security test suite"""
    return SecurityTestSuite(
        suite_id="default-security",
        name="Default Security Tests",
        description="Authentication and vulnerability testing",
        security_tests=[
            SecurityTestConfig(
                test_id="auth_validation",
                name="Authentication Method Validation",
                auth_method="oauth",
                vulnerability_checks=["auth"],
            ),
            SecurityTestConfig(
                test_id="rate_limiting",
                name="Rate Limiting Assessment",
                auth_method="token",
                rate_limit_threshold=100,
                vulnerability_checks=["rate_limit"],
            ),
        ],
        auth_required=True,
        include_penetration_tests=False,
        created_at=datetime.utcnow(),
    )


def create_run_command():
    """Create the run command"""

    @click.command(name="run")
    @click.argument(
        "suite_id",
        callback=validate_suite_id_enhanced,
        shell_complete=complete_suite_ids,
    )
    @click.argument(
        "server_id",
        callback=validate_server_id_enhanced,
        shell_complete=complete_server_ids,
    )
    @click.option("--verbose", "-v", is_flag=True, help="Detailed output")
    @click.option(
        "--global",
        "use_global_dir",
        is_flag=True,
        help="Save results to global directory (~/.local/share/mcp-t) instead of local ./test_results/",
    )
    @click.pass_context
    def mcpt_run_complete(
        ctx, suite_id: str, server_id: str, verbose: bool, use_global_dir: bool
    ):
        """Run test suite against MCP server with enhanced validation and suggestions

        Examples (with tab completion):
          mcp-t run basic-tests dev-server
          mcp-t run compliance-suite prod-server -v

        Tip: Use 'mcp-t help run' for detailed examples and troubleshooting
        """
        # Enhanced implementation with better error handling
        config_manager = ConfigManager()
        console = get_console()

        try:
            # Load configs using type-safe methods
            suite = config_manager.load_test_suite(suite_id)
            server_config = config_manager.get_server_by_id(server_id)

            console.print_info(f"Running {suite.name} against {server_config.name}")

            # Use type-safe execution dispatcher
            results = run_test_suite(
                suite, server_config.model_dump(), verbose, use_global_dir
            )

            # Extract actual success status from results dict
            if isinstance(results, dict):
                success = results.get("overall_success", False)
                successful_tests = results.get("successful_tests", 0)
                total_tests = results.get("total_tests", 0)
            else:
                # Fallback for boolean return (shouldn't happen but safety check)
                success = bool(results)
                successful_tests = 0
                total_tests = 0

            if success:
                console.print_success("All tests completed successfully!")
                # Add post-command hook before exit
                trigger_post_command_hooks(ctx)
                sys.exit(0)
            else:
                # Show detailed failure information
                console.print_error(
                    f"Test run failed: {successful_tests}/{total_tests} tests passed"
                )

                if isinstance(results, dict) and "test_results" in results:
                    console.print("\n[bold red]Failed Tests:[/bold red]")
                    failed_count = 0
                    for result in results["test_results"]:
                        if not result.get("success", True):  # Show failed tests
                            failed_count += 1
                            test_id = result.get("test_id", "unknown")
                            error_msg = result.get(
                                "error", result.get("message", "Unknown error")
                            )

                            # Clean up and shorten error messages
                            if len(error_msg) > 100:
                                error_msg = error_msg[:100] + "..."

                            console.print(f"  ❌ [red]{test_id}[/red]: {error_msg}")

                    if failed_count == 0:
                        console.print(
                            "  [yellow]No specific test failures found - check test execution logs[/yellow]"
                        )

                console.print(
                    "\n[dim]Use --verbose flag for more detailed output[/dim]"
                )
                trigger_post_command_hooks(ctx)
                sys.exit(1)

        except Exception as e:
            console.print_error(
                f"Unexpected error: {str(e)}", ["Use 'mcp-t COMMAND --help' for help"]
            )
            trigger_post_command_hooks(ctx)  # Ensure hooks run even on error
            sys.exit(1)

    return mcpt_run_complete


def create_compliance_command():
    """Create the compliance command"""

    @click.command(name="compliance")
    @click.argument(
        "server_id",
        callback=validate_server_id_enhanced,
        shell_complete=complete_server_ids,
    )
    @click.option("--verbose", "-v", is_flag=True, help="Detailed output")
    @click.option(
        "--global",
        "use_global_dir",
        is_flag=True,
        help="Save results to global directory (~/.local/share/mcp-t) instead of local ./test_results/",
    )
    @click.pass_context
    def mcpt_compliance_complete(
        ctx, server_id: str, verbose: bool, use_global_dir: bool
    ):
        """Run compliance tests against server (uses default compliance suite)

        Examples:
          mcp-t compliance dev-server
          mcp-t compliance prod-server -v
        """
        config_manager = ConfigManager()
        console = get_console()

        try:
            # Load server config
            server_config = config_manager.get_server_by_id(server_id)

            # Create default compliance test suite
            compliance_suite = get_or_create_compliance_suite()

            # Type-safe execution
            success = run_test_suite(
                compliance_suite, server_config.model_dump(), verbose, use_global_dir
            )

            if success:
                console.print_success("✅ Compliance tests passed!")
                trigger_post_command_hooks(ctx)
                sys.exit(0)
            else:
                console.print_error("❌ Compliance tests failed!")
                trigger_post_command_hooks(ctx)
                sys.exit(1)

        except Exception as e:
            console.print_error(f"Compliance testing failed: {e}")
            trigger_post_command_hooks(ctx)
            sys.exit(1)

    return mcpt_compliance_complete


def create_security_command():
    """Create the security command"""

    @click.command(name="security")
    @click.argument(
        "server_id",
        callback=validate_server_id_enhanced,
        shell_complete=complete_server_ids,
    )
    @click.option("--verbose", "-v", is_flag=True, help="Detailed output")
    @click.option(
        "--global",
        "use_global_dir",
        is_flag=True,
        help="Save results to global directory (~/.local/share/mcp-t) instead of local ./test_results/",
    )
    @click.pass_context
    def mcpt_security_complete(
        ctx, server_id: str, verbose: bool, use_global_dir: bool
    ):
        """Run security tests against server (uses default security suite)

        Examples:
          mcp-t security staging-server
          mcp-t security prod-server --verbose
        """
        config_manager = ConfigManager()
        console = get_console()

        try:
            # Load server config
            server_config = config_manager.get_server_by_id(server_id)

            # Create default security test suite
            security_suite = get_or_create_security_suite()

            # Type-safe execution
            success = run_test_suite(
                security_suite, server_config.model_dump(), verbose, use_global_dir
            )

            if success:
                console.print_success("✅ Security tests passed!")
                trigger_post_command_hooks(ctx)
                sys.exit(0)
            else:
                console.print_error("❌ Security tests failed!")
                trigger_post_command_hooks(ctx)
                sys.exit(1)

        except Exception as e:
            console.print_error(f"Security testing failed: {e}")
            trigger_post_command_hooks(ctx)
            sys.exit(1)

    return mcpt_security_complete


def create_health_command():
    """Create the health command"""

    @click.command(name="health")
    @click.argument(
        "server_id",
        callback=validate_server_id_enhanced,
        shell_complete=complete_server_ids,
    )
    @click.option("--verbose", "-v", is_flag=True, help="Detailed output")
    @click.option(
        "--global",
        "use_global_dir",
        is_flag=True,
        help="Save results to global directory (~/.local/share/mcp-t) instead of local ./test_results/",
    )
    @click.pass_context
    def mcpt_health_complete(ctx, server_id: str, verbose: bool, use_global_dir: bool):
        """Run health check against server (infers test suite)

        Examples:
          mcp-t health my-server
        """
        try:
            run_with_mcpt_inference("health", server_id, verbose, use_global_dir)
            trigger_post_command_hooks(ctx)
        except Exception:
            trigger_post_command_hooks(ctx)
            raise

    return mcpt_health_complete
