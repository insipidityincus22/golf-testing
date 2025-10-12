#!/usr/bin/env python3
"""Validate color usage consistency across CLI"""

import os
import re
import sys


def extract_color_usage(file_path: str) -> dict[str, list[str]]:
    """Extract Rich color usage from Python file"""
    with open(file_path) as f:
        content = f.read()

    # Find Rich color patterns like [green], [bold blue], etc.
    color_pattern = r"\[([^\]]+)\]([^[]*)\[/\1\]"
    matches = re.findall(color_pattern, content)

    colors = {}
    for color, text in matches:
        if color not in colors:
            colors[color] = []
        colors[color].append(text.strip())

    return colors


def validate_consistency() -> bool:
    """Validate color usage follows consistent patterns"""
    cli_dir = "src/test_mcp/cli"
    all_colors = {}
    violations = []


    for filename in os.listdir(cli_dir):
        if filename.endswith(".py"):
            filepath = os.path.join(cli_dir, filename)
            colors = extract_color_usage(filepath)

            # Check for inconsistent patterns
            for color, usages in colors.items():
                if color not in all_colors:
                    all_colors[color] = []
                all_colors[color].extend([(filename, usage) for usage in usages])

    # Validate patterns
    success_colors = [c for c in all_colors.keys() if "green" in c.lower()]
    if len(set(success_colors)) > 1:
        violations.append(f"Inconsistent success colors: {success_colors}")

    error_colors = [c for c in all_colors.keys() if "red" in c.lower()]
    if len(set(error_colors)) > 1:
        violations.append(f"Inconsistent error colors: {error_colors}")

    if violations:
        print("❌ Color consistency violations found:")
        for violation in violations:
            print(f"  • {violation}")
        return False
    else:
        print("✅ Color usage is consistent across CLI")
        return True


if __name__ == "__main__":
    success = validate_consistency()
    sys.exit(0 if success else 1)
