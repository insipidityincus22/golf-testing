#!/bin/bash

# MCP Testing CLI Shell Integration
# Source this file to enable tab completion and aliases

# Enable tab completion for mcp-t command
if command -v mcp-t &> /dev/null; then
    eval "$(_MCP_T_COMPLETE=bash_source mcp-t)"
fi

# Enable tab completion for mcp-testing command  
if command -v mcp-testing &> /dev/null; then
    eval "$(_MCP_TESTING_COMPLETE=bash_source mcp-testing)"
fi

# Silent completion setup - no aliases or printouts