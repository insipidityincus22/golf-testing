#!/bin/zsh

# MCP Testing CLI Shell Integration for Zsh
# Source this file to enable tab completion and aliases

# Enable tab completion for mcp-t command
if command -v mcp-t &> /dev/null; then
    eval "$(_MCP_T_COMPLETE=zsh_source mcp-t)"
fi

# Enable tab completion for mcp-testing command  
if command -v mcp-testing &> /dev/null; then
    eval "$(_MCP_TESTING_COMPLETE=zsh_source mcp-testing)"
fi

# Silent completion setup - no aliases

# Enhanced zsh-specific features
setopt AUTO_MENU
setopt COMPLETE_IN_WORD
setopt COMPLETE_ALIASES

# Silent completion - no printouts