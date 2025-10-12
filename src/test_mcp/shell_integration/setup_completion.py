#!/usr/bin/env python3

"""Setup script for MCP Testing CLI shell completion and integration"""

import os
import subprocess
from pathlib import Path
from typing import Union

try:
    from ..shared.console_shared import MCPConsole, get_console

    console: Union[MCPConsole, "FallbackConsole"] = get_console()
except ImportError:
    # Fallback for standalone usage
    class FallbackConsole:
        def print_success(self, msg):
            print(f"✅ {msg}")

        def print_warning(self, msg):
            print(f"⚠️ {msg}")

        def print_error(self, msg):
            print(f"❌ {msg}")

        def print_info(self, msg):
            print(f"💡 {msg}")

        def print(self, msg):
            print(msg)

    console = FallbackConsole()


def detect_shell():
    """Detect user's shell"""
    shell = os.environ.get("SHELL", "")

    if "zsh" in shell:
        return "zsh"
    elif "bash" in shell:
        return "bash"
    elif "fish" in shell:
        return "fish"
    else:
        return "bash"  # Default fallback


def setup_completion(shell_type="auto"):
    """Setup shell completion for MCP Testing CLI"""

    if shell_type == "auto":
        shell_type = detect_shell()

    script_dir = Path(__file__).parent
    home = Path.home()

    console.print_info(f"Setting up {shell_type} completion for MCP Testing CLI")

    if shell_type == "bash":
        setup_bash_completion(script_dir, home)
    elif shell_type == "zsh":
        setup_zsh_completion(script_dir, home)
    else:
        console.print_error(f"Shell '{shell_type}' not yet supported")
        return False

    return True


def setup_bash_completion(script_dir, home):
    """Setup bash completion"""
    bashrc = home / ".bashrc"
    completion_script = script_dir / "completion.sh"

    # Source line to add to .bashrc
    source_line = f"source {completion_script}"

    # Check if already added
    if bashrc.exists():
        with open(bashrc) as f:
            if source_line in f.read():
                console.print_success("Bash completion already configured")
                return

    # Add source line to .bashrc
    with open(bashrc, "a") as f:
        f.write(f"\n# MCP Testing CLI completion\n{source_line}\n")

    console.print_success(f"Added completion to {bashrc}")
    console.print_info("Run 'source ~/.bashrc' or start a new shell session")


def setup_zsh_completion(script_dir, home):
    """Setup zsh completion"""
    zshrc = home / ".zshrc"
    completion_script = script_dir / "completion.zsh"

    # Source line to add to .zshrc
    source_line = f"source {completion_script}"

    # Check if already added
    if zshrc.exists():
        with open(zshrc) as f:
            if source_line in f.read():
                console.print_success("Zsh completion already configured")
                return

    # Add source line to .zshrc
    with open(zshrc, "a") as f:
        f.write(f"\n# MCP Testing CLI completion\n{source_line}\n")

    console.print_success(f"Added completion to {zshrc}")
    console.print_info("Run 'source ~/.zshrc' or start a new shell session")


def is_completion_configured(shell_type="auto"):
    """Check if shell completion is already configured"""
    if shell_type == "auto":
        shell_type = detect_shell()

    script_dir = Path(__file__).parent
    home = Path.home()

    if shell_type == "bash":
        bashrc = home / ".bashrc"
        completion_script = script_dir / "completion.sh"
        source_line = f"source {completion_script}"

        if bashrc.exists():
            with open(bashrc) as f:
                return source_line in f.read()

    elif shell_type == "zsh":
        zshrc = home / ".zshrc"
        completion_script = script_dir / "completion.zsh"
        source_line = f"source {completion_script}"

        if zshrc.exists():
            with open(zshrc) as f:
                return source_line in f.read()

    return False


def verify_installation():
    """Verify that mcp-t is installed and accessible"""
    try:
        result = subprocess.run(
            ["mcp-t", "--help"], capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def main():
    """Main setup function"""
    console.print("MCP Testing CLI Shell Integration Setup")
    console.print("=" * 50)

    # Verify installation
    if not verify_installation():
        console.print_error(
            "mcp-t command not found. Please install mcp-testing first:"
        )
        console.print("   pip install mcp-testing")
        return 1

    # Setup completion
    if setup_completion():
        console.print_success("Shell completion setup complete!")
        console.print()
        console.print_info("Quick Start:")
        console.print("  mcp-t quickstart           # Try the demo")
        console.print("  mcp-t help                 # Enhanced help")
        console.print("  mcp-t <TAB>                # See all commands")
        console.print("  mcp-t help <TAB>           # Help topics")
        console.print("  mcp-t run <TAB> <TAB>      # Browse configurations")
        return 0
    else:
        return 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
