# MCP Testing Framework

![License](https://img.shields.io/badge/license-MIT-black.svg)
![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)
![PRs](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)

**Automated testing for MCP servers using AI agents**

Test your Model Context Protocol servers with realistic AI conversations and get automated pass/fail results.

## Install

```bash
git clone https://github.com/golf-mcp/golf-testing
cd golf-testing
pip install -e .
```

## Setup

```bash
# Add your API keys to .env
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env
echo "OPENAI_API_KEY=sk-..." >> .env
```

## Demo

```bash
mcp-t quickstart
```

Runs test conversations using your example configurations.

## Version

Check your installed version:

```bash
mcp-t --version
```


## Features

- Multi‑turn, realistic conversations with your MCP server
- LLM judge provides automated pass/fail with reasoning
- Simple JSON config for servers and test suites
- CLI with progress bar, verbose/debug modes
- Local JSON reports for runs, evaluations and summaries

## Usage

**Test your MCP server:**

```bash
mcp-t run my-tests my-server
```

**Server config** (`my-server.json`):
```json
{
  "type": "url",
  "url": "https://your-mcp-server.com/mcp",
  "name": "my_server"
}
```

**Test suite** (`my-tests.json`):
```json
{
  "suite_id": "my_tests",
  "name": "My Tests",
  "test_cases": [{
    "test_id": "basic_test",
    "user_message": "What tools do you have?",
    "success_criteria": "Agent lists available tools"
  }]
}
```

## How it Works

1. **AI agent** connects to your MCP server
2. **User simulator** sends test messages  
3. **Agent** responds using your server's tools
4. **LLM judge** evaluates conversation success
5. **Results** saved as JSON with pass/fail status

## Examples

- `examples/suite.json` - Basic 3-test demo
- `examples/complex-suite.json` - Advanced scenarios  
- `examples/server.json` - Hacker News MCP config

## Options

```bash
mcp-t run suite-id server-id --verbose
mcp-t compliance server-id --verbose
mcp-t health server-id --verbose
mcp-t --version
```

- `--verbose` - Debug output
- `--version` - Show installed version
- `mcp-t init` - Setup wizard for configuration
- `mcp-t help` - Enhanced help system with workflows

## Results

Results saved to `test_results/`:
- Conversation logs
- Judge evaluations
- Pass/fail summary

## Requirements

- Python 3.9+
- Anthropic API key
- OpenAI API key

## License

MIT

---

• Contributing guidelines: see [CONTRIBUTING.md](CONTRIBUTING.md)  
• Changelog & versioning: see [CHANGELOG.md](CHANGELOG.md)