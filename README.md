<div align="center">
  <h1>🧪 MCP Testing</h1>
  <p><strong>AI-powered testing framework for MCP servers</strong></p>
  <p>Test your MCP servers with real AI agents conducting conversations and LLM judges evaluating results</p>
</div>

<div align="center">
  <a href="https://docs.golf.dev/mcp-testing/getting-started/quickstart"><img src="https://img.shields.io/badge/docs-golf.dev-blue.svg" alt="Documentation"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue.svg" alt="License"></a>
  <a href="https://github.com/golf-mcp/golf-testing/pulls"><img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg" alt="PRs Welcome"></a>
  <a href="https://pypi.org/project/mcp-testing/"><img src="https://img.shields.io/pypi/v/mcp-testing" alt="PyPI"></a>
  <a href="#"><img src="https://img.shields.io/badge/python-3.12+-blue.svg" alt="Python"></a>
</div>

## Why MCP Testing?

Traditional testing doesn't work for MCP servers. You can't write unit tests for natural language interactions. MCP Testing solves this with:

- **🤖 Real AI Agents** - Claude and ChatGPT actually use your MCP server
- **👤 User Simulation** - AI simulates realistic multi-turn user behavior
- **⚖️ LLM-as-a-Judge** - Intelligent evaluation instead of brittle assertions
- **🎭 Comprehensive Testing** - Security, compliance and performace all in one framework
- **🔌 Multiple Transports** - Supports HTTP and stdio servers

## Quick Start

Get testing in 3 steps:

1. **Install & Setup**

   ```bash
   pip install mcp-testing
   export ANTHROPIC_API_KEY="sk-ant-..."  # For AI agents
   export OPENAI_API_KEY="sk-..."         # For LLM judge
   ```

2. **Interactive Onboarding**

   ```bash
   mcp-t quickstart  # Creates your first server & test suite
   ```

3. **Run Tests**
   ```bash
   mcp-t run <suite-id> <server-id>
   # Example: mcp-t run example_suite_001 hackernews_mcp_server
   ```

## Core Concepts

### Test Flow

```
Your Test Case → AI Agent (Claude/GPT-4) → Your MCP Server
      ↓                    ↓                      ↓
 User Message         Tool Calls            Server Response
      ↓                    ↓                      ↓
User Simulator      Conversation Loop         More Tools
      ↓                    ↓                      ↓
   LLM Judge       Complete Transcript      Pass/Fail + Reasoning
```

### Configuration Files

**Server Config - HTTP** (`examples/server.json`):

```json
{
  "name": "linear_mcp_server",
  "transport": "http",
  "url": "https://mcp.linear.app/mcp"
}
```

**Server Config - stdio** (`examples/servers/time-server-stdio.json`):

```json
{
  "name": "Time Server",
  "transport": "stdio",
  "command": "npx -y @modelcontextprotocol/server-time"
}
```

**Server Config - stdio with env** (`examples/servers/brave-search-stdio.json`):

```json
{
  "name": "Brave Search",
  "transport": "stdio",
  "command": "npx -y @modelcontextprotocol/server-brave-search",
  "env": {
    "BRAVE_API_KEY": "your-api-key-here"
  }
}
```

**Test Suite** (`examples/suite.json`):

```json
{
  "suite_id": "example_suite_001",
  "name": "Hacker News MCP Server Tests",
  "test_cases": [
    {
      "test_id": "hackernews_greeting",
      "user_message": "Hello! Can you help me browse Hacker News?",
      "success_criteria": "Agent should respond politely and explain Hacker News capabilities",
      "max_turns": 5
    }
  ]
}
```

### Test Types

- **💬 Conversational** - Real user workflows
- **🔒 Security** - Authentication & vulnerabilities
- **✅ Compliance** - MCP protocol validation

## Commands

### Test Execution

```bash
mcp-t run <suite-id> <server-id>           # Run specific suite
mcp-t run example_suite_001 hackernews_mcp_server -v   # Verbose output
```

### Configuration Management

```bash
mcp-t quickstart                 # Complete onboarding
mcp-t create server              # Interactive server setup
mcp-t create suite               # Create test suite
mcp-t create test-case           # Add test to suite
mcp-t list                       # Show all configs
mcp-t show suite example_suite_001   # View specific config
```

### Test Generation

Run wizard that analyzes your MCP server and automatically generates comprehensive test cases

```bash
mcp-t generate
```

## Test Results

### Understanding Evaluation

```json
{
  "test_id": "hackernews_stories",
  "verdict": "PASS",
  "confidence_score": 0.89,
  "judge_reasoning": "The agent successfully fetched and displayed Hacker News stories. Good use of available tools and clear presentation of results.",
  "conversation_quality": 0.87,
  "tool_calls": [
    { "tool": "get_top_stories", "args": {} },
    { "tool": "get_story_details", "args": { "story_id": 123 } }
  ]
}
```

## Support

- [Documentation](https://docs.golf.dev/mcp-testing/getting-started/quickstart)
- [Contributing Guide](CONTRIBUTING.md)

---

<div align="center">
  <p>Built with ❤️ for the MCP ecosystem</p>
  <p><sub>Made in San Francisco, CA</sub></p>
</div>
