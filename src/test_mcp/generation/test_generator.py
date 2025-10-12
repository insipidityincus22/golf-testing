"""Test generator using Claude for creating conversational tests"""

import json
import logging

import anthropic

from ..models.conversational import ConversationalTestConfig
from .models import GenerationRequest, ServerContext


class TestGenerator:
    """Generates conversational test cases using Claude"""

    def __init__(self, anthropic_api_key: str):
        self.client = anthropic.Anthropic(api_key=anthropic_api_key)
        self.logger = logging.getLogger(__name__)

    async def generate_tests(
        self, request: GenerationRequest, context: ServerContext, status=None
    ) -> list[ConversationalTestConfig]:
        """Generate test cases based on research context"""

        # Automatically determine number of tests based on discovered capabilities
        num_tools = len(context.mcp_tools)
        num_resources = len(context.mcp_resources)
        num_prompts = len(context.mcp_prompts)

        # Generate tests: 6 per tool (1 happy path + 5 edge cases),
        # 6 per resource (1 valid + 5 edge cases), 1 per prompt
        # Plus 1-2 integration tests
        estimated_tests = (num_tools * 6) + (num_resources * 6) + num_prompts + 2
        # Cap at reasonable number
        num_tests = min(max(estimated_tests, 3), 30)

        if status:
            status.update(f"Generating {num_tests} test cases")

        prompt = self._build_generation_prompt(request, context, num_tests)

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4000,
                temperature=0.3,  # Slightly creative but consistent
                messages=[{"role": "user", "content": prompt}],
            )

            # Safely extract text from response
            if not response or not response.content:
                self.logger.error("Empty response from API")
                return []

            result_text = response.content[0].text if response.content else "[]"

            # Parse JSON response - extract JSON from markdown if needed
            if "```json" in result_text:
                # Extract JSON from markdown code block
                start = result_text.find("```json") + 7
                end = result_text.find("```", start)
                result_text = result_text[start:end].strip()
            elif "```" in result_text:
                # Extract from generic code block
                start = result_text.find("```") + 3
                end = result_text.find("```", start)
                result_text = result_text[start:end].strip()

            self.logger.debug(f"Parsing test JSON (length: {len(result_text)})")
            tests_data = json.loads(result_text)

            # Convert to ConversationalTestConfig objects
            tests = []
            for i, test_data in enumerate(tests_data, 1):
                try:
                    test = ConversationalTestConfig(**test_data)
                    tests.append(test)

                    # Log what was generated
                    test_type = (
                        test.metadata.get("test_type", "unknown")
                        if test.metadata
                        else "unknown"
                    )
                    tool_name = (
                        test.metadata.get("tool_name", "") if test.metadata else ""
                    )
                    resource_name = (
                        test.metadata.get("resource_name", "") if test.metadata else ""
                    )

                    target = tool_name or resource_name or "integration"
                    self.logger.info(
                        f"   ✓ Test {i}: {test.test_id} ({test_type} - {target})"
                    )

                except Exception as e:
                    self.logger.warning(f"   ✗ Failed to parse test case {i}: {e}")
                    continue

            self.logger.info("")
            self.logger.info(f"✅ Successfully generated {len(tests)} test cases")
            return tests

        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse generated tests JSON: {e}")
            self.logger.debug(f"Response was: {result_text[:1000]}")
            return []
        except Exception as e:
            self.logger.error(f"Test generation failed: {e}")
            import traceback

            self.logger.debug(f"Traceback: {traceback.format_exc()}")
            return []

    def _build_generation_prompt(
        self, request: GenerationRequest, context: ServerContext, num_tests: int
    ) -> str:
        """Build comprehensive prompt for test generation"""

        # Format tools with emphasis on comprehensive coverage
        tools_section = "### Available MCP Tools:\n"
        if not context.mcp_tools:
            tools_section += "No tools discovered.\n"
        else:
            for tool in context.mcp_tools:
                tools_section += f"\n**{tool.name}**\n"
                if tool.description:
                    tools_section += f"Description: {tool.description}\n"
                if tool.input_schema:
                    tools_section += (
                        f"Schema: {json.dumps(tool.input_schema, indent=2)}\n"
                    )

        # Format resources
        resources_section = ""
        if context.mcp_resources:
            resources_section = "\n### Available MCP Resources:\n"
            for resource in context.mcp_resources:
                resources_section += f"\n**{resource.name}** ({resource.uri})\n"
                if resource.description:
                    resources_section += f"Description: {resource.description}\n"

        # Format prompts
        prompts_section = ""
        if context.mcp_prompts:
            prompts_section = "\n### Available MCP Prompts:\n"
            for prompt in context.mcp_prompts:
                prompts_section += f"- {prompt}\n"

        # Format context
        context_section = ""
        if context.documentation_content:
            context_section += "\n### Documentation Insights:\n"
            for doc in context.documentation_content:
                context_section += f"\n{doc}\n"

        if context.example_workflows:
            context_section += "\n### Example Workflows:\n"
            for workflow in context.example_workflows:
                context_section += f"- {workflow}\n"

        if context.web_findings:
            context_section += "\n### Research Findings:\n"
            if context.web_findings.usage_patterns:
                context_section += "\nCommon patterns:\n"
                for pattern in context.web_findings.usage_patterns:
                    context_section += f"- {pattern}\n"
            if context.web_findings.best_practices:
                context_section += "\nBest practices:\n"
                for practice in context.web_findings.best_practices:
                    context_section += f"- {practice}\n"
            if context.web_findings.limitations:
                context_section += "\nLimitations:\n"
                for limitation in context.web_findings.limitations:
                    context_section += f"- {limitation}\n"

        # Build full prompt with automatic test generation instructions
        prompt = f"""You are an expert at creating conversational tests for MCP servers.

## Server Information:
{context.research_summary}

{tools_section}
{resources_section}
{prompts_section}

{context_section}

## Testing Focus:
{request.user_intent}

## Custom Notes:
{chr(10).join(f"- {note}" for note in request.custom_notes) if request.custom_notes else "None"}

## Task:
Generate {num_tests} comprehensive conversational test cases that:

**Coverage Requirements:**
- Create 6 tests for EACH tool: 
  1. ONE happy path test (valid inputs, successful execution)
  2. FIVE edge case tests covering:
     - Invalid input parameters
     - Boundary conditions (min/max values, empty inputs)
     - Error scenarios (non-existent resources, timeouts)
     - Malformed data
     - Unexpected data types
- Create 6 tests for EACH resource:
  1. ONE valid resource access test
  2. FIVE edge case tests (non-existent resources, invalid access patterns, permissions, etc.)
- Create 1 test for EACH prompt
- Include 1-2 integration tests that combine multiple tools/resources
- CRITICAL: Generate diverse, comprehensive edge cases for every capability

**Test Complexity Guidelines:**
- Happy path tests: 3-6 turns
- Edge case tests: 4-7 turns (each edge case should be a separate test)
- Integration tests: 8-12 turns

**Quality Requirements:**
- Clear, measurable success criteria
- Realistic user scenarios
- Natural conversation flow
- Proper error handling expectations
- Test names should clearly indicate what is being tested

## Output Format:
Return a JSON array of test cases. Each test case must have:
- test_id: string (descriptive, snake_case, e.g., "tool_name_happy_path" or "tool_name_edge_cases")
- user_message: string (natural user message to start conversation)
- success_criteria: string (clear criteria for LLM judge)
- max_turns: integer (appropriate for complexity)
- context_persistence: boolean (usually true)
- metadata: object with:
  - tool_name: string (name of the tool being tested, if applicable)
  - resource_name: string (name of the resource being tested, if applicable)
  - prompt_name: string (name of the prompt being tested, if applicable)
  - test_type: string ("happy_path", "edge_cases", or "integration")

## Examples of Good Test Cases:

```json
[
  {{
    "test_id": "fetch_url_happy_path",
    "user_message": "Can you fetch the content from https://example.com for me?",
    "success_criteria": "Agent successfully uses fetch_url tool and returns the content",
    "max_turns": 5,
    "context_persistence": true,
    "metadata": {{
      "tool_name": "fetch_url",
      "test_type": "happy_path"
    }}
  }},
  {{
    "test_id": "fetch_url_invalid_url",
    "user_message": "Please fetch content from an invalid URL: not-a-valid-url",
    "success_criteria": "Agent handles invalid URL gracefully, explains the error, and suggests corrections",
    "max_turns": 6,
    "context_persistence": true,
    "metadata": {{
      "tool_name": "fetch_url",
      "test_type": "edge_cases"
    }}
  }},
  {{
    "test_id": "fetch_url_empty_url",
    "user_message": "Fetch content from an empty URL",
    "success_criteria": "Agent handles empty URL parameter, provides helpful error message",
    "max_turns": 5,
    "context_persistence": true,
    "metadata": {{
      "tool_name": "fetch_url",
      "test_type": "edge_cases"
    }}
  }},
  {{
    "test_id": "fetch_url_nonexistent_domain",
    "user_message": "Fetch https://this-domain-definitely-does-not-exist-12345.com",
    "success_criteria": "Agent handles DNS resolution failure appropriately",
    "max_turns": 6,
    "context_persistence": true,
    "metadata": {{
      "tool_name": "fetch_url",
      "test_type": "edge_cases"
    }}
  }},
  {{
    "test_id": "fetch_url_timeout",
    "user_message": "Fetch content from a very slow server that might timeout",
    "success_criteria": "Agent handles timeout scenarios and provides user-friendly response",
    "max_turns": 7,
    "context_persistence": true,
    "metadata": {{
      "tool_name": "fetch_url",
      "test_type": "edge_cases"
    }}
  }},
  {{
    "test_id": "fetch_url_malformed_response",
    "user_message": "Fetch content from a URL that returns malformed data",
    "success_criteria": "Agent handles malformed responses without crashing, provides helpful feedback",
    "max_turns": 6,
    "context_persistence": true,
    "metadata": {{
      "tool_name": "fetch_url",
      "test_type": "edge_cases"
    }}
  }},
  {{
    "test_id": "multi_tool_integration",
    "user_message": "I need to fetch data from multiple sources and compare them",
    "success_criteria": "Agent uses multiple tools in sequence, handles results properly",
    "max_turns": 10,
    "context_persistence": true,
    "metadata": {{
      "test_type": "integration"
    }}
  }}
]
```

Generate {num_tests} test cases now. Return ONLY valid JSON array, no other text."""

        return prompt
