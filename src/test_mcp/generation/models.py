"""Data models for test generation"""

from pydantic import BaseModel, Field


class UserResources(BaseModel):
    """User-provided resources for Stage 2 research"""

    documentation_urls: list[str] = Field(default_factory=list)
    github_repos: list[str] = Field(default_factory=list)
    example_workflows: list[str] = Field(default_factory=list)
    reference_suite_id: str | None = None


class WebResearchResults(BaseModel):
    """Results from Stage 3 autonomous web research"""

    sources_found: list[str] = Field(default_factory=list)
    key_insights: list[str] = Field(default_factory=list)
    usage_patterns: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    best_practices: list[str] = Field(default_factory=list)
    code_examples: list[str] = Field(default_factory=list)


class ToolInfo(BaseModel):
    """Information about an MCP tool"""

    name: str
    description: str | None = None
    input_schema: dict | None = None


class ResourceInfo(BaseModel):
    """Information about an MCP resource"""

    name: str
    uri: str
    description: str | None = None


class ServerContext(BaseModel):
    """Complete research context from all stages"""

    # Stage 1: MCP Introspection (always present)
    mcp_tools: list[ToolInfo] = Field(default_factory=list)
    mcp_resources: list[ResourceInfo] = Field(default_factory=list)
    mcp_prompts: list[str] = Field(default_factory=list)

    # Stage 2: User Resources (optional)
    documentation_content: list[str] = Field(default_factory=list)
    example_workflows: list[str] = Field(default_factory=list)

    # Stage 3: Web Research (optional)
    web_findings: WebResearchResults | None = None

    # Meta
    user_intent: str
    custom_notes: list[str] = Field(default_factory=list)
    research_summary: str = ""


class GenerationRequest(BaseModel):
    """User input from wizard for test generation"""

    server_id: str

    # Suite identifier - used as ID, name, and filename
    suite_id: str = Field(
        ...,
        description="Suite identifier used as ID, name, and filename (without .json)",
    )

    # Optional: user can provide intent or let system do comprehensive testing
    user_intent: str = Field(
        default="Comprehensive testing of all available tools, resources, and capabilities",
        description="Testing focus - defaults to comprehensive testing",
    )

    # Stage 2 inputs
    user_resources: UserResources | None = None

    # Stage 3 control
    enable_web_search: bool = False
    web_search_focus: str = "general"  # "general" or custom

    # Other
    custom_notes: list[str] = Field(default_factory=list)
