"""Research agent for gathering context about MCP servers"""

import json
import logging
from typing import Any

import anthropic
import httpx
from bs4 import BeautifulSoup

from ..mcp_client.client_manager import MCPClientManager
from .models import (
    GenerationRequest,
    ResourceInfo,
    ServerContext,
    ToolInfo,
    WebResearchResults,
)


class ResearchAgent:
    """Agent that researches MCP servers to gather context for test generation"""

    def __init__(self, anthropic_api_key: str):
        self.anthropic_api_key = anthropic_api_key
        self.client = anthropic.Anthropic(api_key=anthropic_api_key)
        self.mcp_client = MCPClientManager()
        self.logger = logging.getLogger(__name__)

    async def research(
        self, request: GenerationRequest, server_config: dict, status=None
    ) -> ServerContext:
        """Execute full 3-stage research process"""

        context = ServerContext(
            user_intent=request.user_intent, custom_notes=request.custom_notes
        )

        if status:
            status.update("Stage 1: MCP introspection")
        await self._stage1_mcp_introspection(server_config, context)

        if request.user_resources:
            if status:
                status.update("Stage 2: Processing user resources")
            await self._stage2_user_resources(request.user_resources, context)

        if request.enable_web_search:
            if status:
                status.update("Stage 3: Web research")
            await self._stage3_web_research(
                server_config, request.web_search_focus, context
            )

        context.research_summary = await self._generate_summary(context)

        return context

    async def _stage1_mcp_introspection(
        self, server_config: dict, context: ServerContext
    ) -> None:
        """Stage 1: Connect to MCP server and analyze capabilities"""

        server_id = None
        try:
            server_id = await self.mcp_client.connect_server(server_config)

            tools_response = await self.mcp_client.get_tools_for_llm([server_id])
            for tool in tools_response:
                context.mcp_tools.append(
                    ToolInfo(
                        name=tool.get("name", ""),
                        description=tool.get("description"),
                        input_schema=tool.get("inputSchema"),
                    )
                )

            try:
                resources = await self.mcp_client.get_resources_for_llm([server_id])
                for resource in resources:
                    context.mcp_resources.append(
                        ResourceInfo(
                            name=resource.get("name", ""),
                            uri=resource.get("uri", ""),
                            description=resource.get("description"),
                        )
                    )
            except Exception as e:
                self.logger.debug(f"No resources available: {e}")

            # Discover prompts
            try:
                prompts = await self.mcp_client.get_prompts_for_llm([server_id])
                for prompt in prompts:
                    prompt_name = prompt.get("name", "")
                    if prompt_name:
                        context.mcp_prompts.append(prompt_name)
            except Exception as e:
                self.logger.debug(f"No prompts available: {e}")

        except Exception as e:
            self.logger.error(f"MCP introspection failed: {e}")
            raise

    async def _stage2_user_resources(
        self, user_resources: Any, context: ServerContext
    ) -> None:
        """Stage 2: Process user-provided documentation and examples"""

        for url in user_resources.documentation_urls:
            try:
                content = await self._fetch_url_content(url)
                if content:
                    summary = await self._extract_documentation_insights(
                        url, content, context.user_intent
                    )
                    context.documentation_content.append(summary)
            except Exception as e:
                self.logger.debug(f"Failed to fetch {url}: {e}")

        context.example_workflows.extend(user_resources.example_workflows)

    async def _stage3_web_research(
        self, server_config: dict, search_focus: str, context: ServerContext
    ) -> None:
        """Stage 3: Web research"""

        server_name = server_config.get("name", "unknown")

        if search_focus == "general":
            query = (
                f"{server_name} MCP server documentation examples usage best practices"
            )
        else:
            query = f"{server_name} MCP server {search_focus}"

        self.logger.info(f"🔍 Web research query: '{query}'")
        self.logger.info("🌐 Phase 1: Finding documentation URLs...")

        urls = await self._find_documentation_urls(query, server_name)

        if not urls:
            self.logger.info("⚠️  No URLs found, using knowledge-based fallback")
            web_findings = await self._knowledge_based_fallback(server_name, context)
            context.web_findings = web_findings
            return

        self.logger.info(f"✅ Found {len(urls)} documentation URL(s)")
        self.logger.info("📄 Phase 2: Analyzing documentation content...")

        sources_found = []
        key_insights = []

        for i, url in enumerate(urls[:3], 1):
            try:
                self.logger.info(f"   [{i}/{len(urls[:3])}] Processing: {url}")

                content = await self._fetch_url_content(url)
                if not content:
                    self.logger.debug(f"   ⚠️  No content fetched from {url}")
                    continue

                summary = await self._extract_documentation_insights(
                    url, content, context.user_intent
                )

                if summary and not summary.startswith("[Error"):
                    sources_found.append(url)
                    key_insights.append(summary)
                    self.logger.info("   ✅ Analyzed successfully")
                else:
                    self.logger.debug("   ⚠️  Failed to extract insights")

            except Exception as e:
                self.logger.debug(f"   ⚠️  Error processing {url}: {e}")
                continue

        web_findings = WebResearchResults(
            sources_found=sources_found,
            key_insights=key_insights,
            usage_patterns=[],
            limitations=[],
            best_practices=[],
            code_examples=[],
        )
        context.web_findings = web_findings

        self.logger.info(
            f"\n✅ Web research complete: {len(sources_found)} source(s) analyzed"
        )

        if key_insights:
            self.logger.info(f"\n💡 Key Insights ({len(key_insights)}):")
            for i, insight in enumerate(key_insights, 1):
                max_preview_length = 200
                if len(insight) > max_preview_length:
                    insight_preview = insight[:max_preview_length] + "..."
                else:
                    insight_preview = insight
                self.logger.info(f"   {i}. {insight_preview}")

        if sources_found:
            self.logger.info("\n📚 Sources Analyzed:")
            for source in sources_found:
                self.logger.info(f"   • {source}")

        self.logger.info("")

    async def _fetch_url_content(self, url: str) -> str:
        """Fetch content from URL"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            for script in soup(["script", "style"]):
                script.decompose()

            text = soup.get_text()

            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = "\n".join(chunk for chunk in chunks if chunk)

            max_content_length = 5000
            if len(text) > max_content_length:
                text = text[:max_content_length] + "\n...[truncated]"

            return text

    async def _extract_documentation_insights(
        self, url: str, content: str, user_intent: str
    ) -> str:
        """Use Claude to extract key insights from documentation"""

        prompt = f"""Analyze this documentation and extract key insights relevant to testing.

URL: {url}

User wants to test: {user_intent}

Documentation content:
{content}

Extract:
1. Key features and capabilities
2. Usage examples
3. Common patterns
4. Limitations or constraints
5. Best practices

Provide a concise summary (max 500 words)."""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=600,
                messages=[{"role": "user", "content": prompt}],
            )

            if not response or not response.content:
                self.logger.debug("Empty response from documentation extraction")
                return ""

            return response.content[0].text if response.content else ""
        except Exception as e:
            self.logger.debug(f"Failed to extract insights: {e}")
            return f"[Error extracting insights from {url}]"

    async def _find_documentation_urls(self, query: str, server_name: str) -> list[str]:
        """Lightweight web search that only returns documentation URLs"""

        prompt = f"""Find official documentation, GitHub repositories, or examples for: {server_name}

Search query: {query}

Return ONLY a JSON array of 2-3 top URLs. Format: ["url1", "url2", "url3"]

Focus on:
- Official documentation sites
- GitHub repositories
- Tutorial/example pages

Return only the JSON array, nothing else."""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
                tools=[
                    {
                        "type": "web_search_20250305",
                        "name": "web_search",
                        "max_uses": 1,
                    }
                ],
            )

            citation_urls = []
            if response and response.content:
                for block in response.content:
                    if hasattr(block, "citations") and block.citations:
                        for citation in block.citations:
                            if hasattr(citation, "url") and citation.url:
                                url = citation.url
                                if url.startswith(("http://", "https://")):
                                    citation_urls.append(url)

            if citation_urls:
                return citation_urls[:3]

            result_text = ""
            if response and response.content:
                for block in response.content:
                    if hasattr(block, "text"):
                        result_text += block.text

            if not result_text.strip():
                return []

            if "```json" in result_text:
                start = result_text.find("```json") + 7
                end = result_text.find("```", start)
                result_text = result_text[start:end].strip()
            elif "```" in result_text:
                start = result_text.find("```") + 3
                end = result_text.find("```", start)
                result_text = result_text[start:end].strip()

            urls = json.loads(result_text)
            if isinstance(urls, list):
                valid_urls = [
                    url
                    for url in urls
                    if isinstance(url, str) and url.startswith(("http://", "https://"))
                ]
                self.logger.info(f"Found {len(valid_urls)} valid URLs")
                return valid_urls[:3]

            self.logger.info("No valid URLs found")
            return []

        except Exception as e:
            self.logger.debug(f"URL search failed: {e}")
            return []

    async def _claude_web_research(
        self, query: str, server_name: str, context: ServerContext
    ) -> WebResearchResults:
        """Use Claude's native web search to conduct real-time research"""

        tools_info = "\n".join(
            [
                f"- {tool.name}: {tool.description or 'No description'}"
                for tool in context.mcp_tools
            ]
        )

        prompt = f"""Research the MCP server: {server_name}

Available tools from server introspection:
{tools_info}

User intent: {context.user_intent}

Please search the web to find:
1. Documentation, examples, or GitHub repositories for this MCP server
2. Common usage patterns for these types of tools
3. Best practices and known limitations
4. Real-world examples of how users interact with similar servers

Provide your findings as structured JSON with these fields:
- sources_found: list of source URLs you found
- key_insights: list of important findings
- usage_patterns: list of common usage patterns
- limitations: list of potential limitations
- best_practices: list of recommended practices
- code_examples: list of example usage descriptions

Return only valid JSON, no other text."""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
                tools=[
                    {
                        "type": "web_search_20250305",
                        "name": "web_search",
                        "max_uses": 1,
                    }
                ],
            )

            result_text = ""
            citation_sources = []

            if not response or not response.content:
                self.logger.debug("Empty response from web search API")
                return await self._knowledge_based_fallback(server_name, context)

            for block in response.content:
                if hasattr(block, "text"):
                    result_text += block.text

                if hasattr(block, "citations") and block.citations:
                    for citation in block.citations:
                        if hasattr(citation, "url") and citation.url:
                            citation_sources.append(citation.url)

            if not result_text.strip():
                self.logger.debug("No text content in web search response")
                return await self._knowledge_based_fallback(server_name, context)

            if "```json" in result_text:
                start = result_text.find("```json") + 7
                end = result_text.find("```", start)
                result_text = result_text[start:end].strip()
            elif "```" in result_text:
                start = result_text.find("```") + 3
                end = result_text.find("```", start)
                result_text = result_text[start:end].strip()

            try:
                result_data = json.loads(result_text)

                all_sources = list(
                    set(citation_sources + result_data.get("sources_found", []))
                )
                result_data["sources_found"] = all_sources

                return WebResearchResults(**result_data)

            except json.JSONDecodeError as e:
                self.logger.warning(f"Failed to parse web research JSON: {e}")
                self.logger.debug(f"Response was: {result_text[:500]}")
                return WebResearchResults(
                    sources_found=citation_sources,
                    key_insights=["Web search completed - check logs for details"],
                )

        except Exception as e:
            self.logger.debug(f"Web search failed: {e}")
            return await self._knowledge_based_fallback(server_name, context)

    async def _knowledge_based_fallback(
        self, server_name: str, context: ServerContext
    ) -> WebResearchResults:
        """Fallback method when web search is unavailable or fails"""

        tools_info = "\n".join(
            [
                f"- {tool.name}: {tool.description or 'No description'}"
                for tool in context.mcp_tools
            ]
        )

        prompt = f"""You are analyzing the MCP server: {server_name}

Available tools:
{tools_info}

User intent: {context.user_intent}

Based on the tools available and typical MCP server patterns, generate insights about:
1. Common usage patterns for these types of tools
2. Potential limitations or edge cases
3. Best practices for using this server
4. Typical user workflows

Return your analysis as JSON with these fields:
- sources_found: list of relevant documentation types (e.g., ["MCP introspection"])
- key_insights: list of important findings
- usage_patterns: list of common usage patterns
- limitations: list of potential limitations
- best_practices: list of recommended practices
- code_examples: list of example usage descriptions

Return only valid JSON, no other text."""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )

            if not response or not response.content:
                self.logger.debug("Empty response from knowledge-based fallback")
                return WebResearchResults(
                    sources_found=["MCP introspection"],
                    key_insights=["Analysis based on discovered server capabilities"],
                )

            result_text = response.content[0].text if response.content else "{}"

            if "```json" in result_text:
                start = result_text.find("```json") + 7
                end = result_text.find("```", start)
                result_text = result_text[start:end].strip()
            elif "```" in result_text:
                start = result_text.find("```") + 3
                end = result_text.find("```", start)
                result_text = result_text[start:end].strip()

            try:
                result_data = json.loads(result_text)
                return WebResearchResults(**result_data)
            except json.JSONDecodeError:
                return WebResearchResults(
                    sources_found=["MCP introspection"],
                    key_insights=["Analysis based on available tools"],
                )

        except Exception as e:
            self.logger.warning(f"Fallback research failed: {e}")
            return WebResearchResults()

    async def _generate_summary(self, context: ServerContext) -> str:
        """Generate human-readable summary of research findings"""

        tools_summary = f"{len(context.mcp_tools)} tools"
        resources_summary = f"{len(context.mcp_resources)} resources"
        prompts_summary = f"{len(context.mcp_prompts)} prompts"
        docs_summary = f"{len(context.documentation_content)} documentation sources"

        web_summary = ""
        if context.web_findings:
            web_summary = f", {len(context.web_findings.sources_found)} web sources"

        return (
            f"Research complete: {tools_summary}, {resources_summary}, "
            f"{prompts_summary}, {docs_summary}{web_summary}"
        )

    async def cleanup(self):
        """Clean up resources"""
        try:
            await self.mcp_client.disconnect_all()
        except Exception as e:
            self.logger.debug(f"Cleanup warning (safe to ignore): {e}")
