#!/usr/bin/env python3
"""
Markdown report generator for test results
"""

from pathlib import Path
from typing import Any

# Maximum message length before truncation in conversation transcripts
MAX_MESSAGE_LENGTH = 300


def generate_markdown_report(test_run_data: dict[str, Any], output_path: Path) -> None:
    """
    Generate a concise markdown report from test run data.

    Uses top-down communication: summary → test list → detailed results
    Ensures no information duplication and progressive disclosure.

    Args:
        test_run_data: Serialized test run data (same as JSON output)
        output_path: Path where markdown file should be written
    """
    sections = [
        _generate_header(test_run_data),
        _generate_executive_summary(test_run_data),
        _generate_test_results_overview(test_run_data),
        _generate_detailed_results(test_run_data),
    ]

    markdown_content = "\n\n".join(sections)

    output_path.write_text(markdown_content, encoding="utf-8")


def _generate_header(data: dict) -> str:
    """Generate report header with run metadata"""
    timestamp = data.get("timestamp", "Unknown")
    run_id = data.get("run_id", "Unknown")
    suite_name = data.get("test_suite", {}).get("name", "Unknown")
    server_name = data.get("server_config", {}).get("name", "Unknown")

    return f"""# Test Report: {suite_name}

**Run ID**: `{run_id}`
**Timestamp**: {timestamp}
**Server**: {server_name}
**Report Type**: MCP Test Execution"""


def _generate_executive_summary(data: dict) -> str:
    """Generate high-level summary with key metrics"""
    summary = data.get("summary", {})

    total = summary.get("total_tests", 0)
    pass_rate = summary.get("pass_rate", 0.0)
    passed = int(total * pass_rate)
    failed = total - passed
    duration = summary.get("duration_seconds", 0.0)

    lines = [
        "## Executive Summary",
        "",
        f"**Total Tests**: {total}  ",
        f"**Passed**: {passed} ({pass_rate * 100:.1f}%)  ",
        f"**Failed**: {failed}  ",
        f"**Duration**: {duration:.2f}s  ",
    ]

    return "\n".join(lines)


def _generate_test_results_overview(data: dict) -> str:
    """Generate compact list of all test results"""
    results = data.get("results", [])

    if not results:
        return "## Test Results\n\nNo tests executed."

    lines = [
        "## Test Results Overview",
        "",
        "| Status | Test ID | Duration |",
        "|--------|---------|----------|",
    ]

    for result in results:
        test_id = result.get("test_id", "Unknown")
        success = result.get("success", False)
        duration = result.get("execution_time", 0.0)

        status = "✅ PASS" if success else "❌ FAIL"
        lines.append(f"| {status} | `{test_id}` | {duration:.2f}s |")

    return "\n".join(lines)


def _generate_detailed_results(data: dict) -> str:
    """Generate detailed information for each test"""
    results = data.get("results", [])

    if not results:
        return ""

    sections = ["## Detailed Test Results"]

    for result in results:
        section = _generate_single_test_detail(result)
        sections.append(section)

    return "\n\n".join(sections)


def _generate_single_test_detail(result: dict) -> str:
    """Generate detailed section for a single test"""
    test_id = result.get("test_id", "Unknown")
    success = result.get("success", False)
    message = result.get("message", "")
    duration = result.get("execution_time", 0.0)

    status = "✅ PASSED" if success else "❌ FAILED"

    lines = [
        f"### {test_id}",
        "",
        f"**Status**: {status}  ",
        f"**Duration**: {duration:.2f}s  ",
    ]

    # Wrap message in code block if it exists to prevent markdown injection
    if message:
        lines.append("**Message**:")
        lines.append("```")
        lines.append(message)
        lines.append("```")
        lines.append("")

    # Add conversation details if available
    details = result.get("details", {})
    conv_result = details.get("conversation_result")

    if conv_result:
        lines.extend(_generate_conversation_details(conv_result))

    # Add compliance/security details if available
    if "compliance_results" in details:
        lines.extend(_generate_compliance_details(details["compliance_results"]))

    if "security_result" in details:
        lines.extend(_generate_security_details(details["security_result"]))

    return "\n".join(lines)


def _generate_conversation_details(conv: dict) -> list[str]:
    """Generate conversation-specific details"""
    lines = [
        "",
        "#### Conversation Details",
        "",
        f"**Total Turns**: {conv.get('total_turns', 0)}  ",
        f"**Status**: {conv.get('status', 'Unknown')}  ",
        f"**Goal Achieved**: {conv.get('goal_achieved', False)}  ",
    ]

    # Tool usage summary
    tools_used = conv.get("tools_used", [])
    if tools_used:
        lines.append(f"**Tools Used**: {', '.join(set(tools_used))}  ")

    # Conversation turns
    turns = conv.get("turns", [])
    if turns:
        lines.extend(
            [
                "",
                "#### Conversation Transcript",
                "",
            ]
        )

        for turn in turns:
            speaker = turn.get("speaker", "Unknown")
            message = turn.get("message", "")
            tool_calls = turn.get("tool_calls", [])

            # Truncate long messages
            if len(message) > MAX_MESSAGE_LENGTH:
                message = message[: MAX_MESSAGE_LENGTH - 3] + "..."

            # Wrap message in code block to prevent markdown injection
            lines.append(f"**{speaker.upper()}**:")
            lines.append("```")
            lines.append(message)
            lines.append("```")

            if tool_calls:
                for tool_call in tool_calls:
                    # ToolCall model uses 'tool_name' field, not 'name'
                    tool_name = tool_call.get("tool_name", tool_call.get("name", "Unknown"))
                    lines.append(f"  - 🔧 Called tool: `{tool_name}`")

            lines.append("")

    return lines


def _generate_compliance_details(compliance_results: list[dict]) -> list[str]:
    """Generate compliance test details"""
    if not compliance_results:
        return []

    lines = [
        "",
        "#### Compliance Results",
        "",
    ]

    for result in compliance_results:
        check_name = result.get("check_name", "Unknown")
        passed = result.get("compliance_passed", False)
        severity = result.get("severity", "Unknown")
        message = result.get("message", "")

        status = "✅" if passed else "❌"
        lines.append(f"{status} **{check_name}** ({severity}):")
        if message:
            lines.append("```")
            lines.append(message)
            lines.append("```")
        lines.append("")

    return lines


def _generate_security_details(security_result: dict) -> list[str]:
    """Generate security test details"""
    lines = [
        "",
        "#### Security Assessment",
        "",
        f"**Overall Score**: {security_result.get('overall_security_score', 0)}/100  ",
    ]

    # Vulnerability counts
    critical = security_result.get("critical_vulnerabilities", 0)
    high = security_result.get("high_vulnerabilities", 0)
    medium = security_result.get("medium_vulnerabilities", 0)
    low = security_result.get("low_vulnerabilities", 0)

    if any([critical, high, medium, low]):
        lines.extend(
            [
                "",
                "**Vulnerabilities Found**:",
                f"- Critical: {critical}",
                f"- High: {high}",
                f"- Medium: {medium}",
                f"- Low: {low}",
            ]
        )

    # Individual test results
    test_results = security_result.get("test_results", [])
    if test_results:
        lines.extend(
            [
                "",
                "**Security Checks**:",
            ]
        )

        for test in test_results:
            name = test.get("name", "Unknown")
            vuln_detected = test.get("vulnerability_detected", False)
            severity = test.get("severity", "Unknown")

            status = "❌" if vuln_detected else "✅"
            lines.append(f"{status} {name} ({severity})")

    return lines
