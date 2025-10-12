"""Orchestrator for test generation flow"""

import logging
import os

from ..config.config_manager import ConfigManager
from ..models.conversational import ConversationTestSuite
from .models import GenerationRequest
from .research_agent import ResearchAgent
from .test_generator import TestGenerator


class TestGenerationOrchestrator:
    """Coordinates the full test generation process"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.config_manager = ConfigManager()

        # Get API key from environment
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        if not self.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable required")

        self.research_agent = ResearchAgent(self.anthropic_api_key)
        self.test_generator = TestGenerator(self.anthropic_api_key)

    async def generate_test_suite(
        self,
        request: GenerationRequest,
        use_global: bool = False,
        status=None,
    ) -> ConversationTestSuite:
        """Generate a complete test suite from user request"""

        # Update status if provided
        if status:
            status.update("Connecting to server...")

        # Load server configuration
        server_config = self.config_manager.get_server_by_id(request.server_id)
        if not server_config:
            raise ValueError(f"Server '{request.server_id}' not found")

        server_dict = (
            server_config.model_dump()
            if hasattr(server_config, "model_dump")
            else dict(server_config)
        )

        try:
            # Research phase - let research_agent handle status updates
            context = await self.research_agent.research(request, server_dict, status)

            # Generation phase - let test_generator handle status updates
            tests = await self.test_generator.generate_tests(request, context, status)

            if not tests:
                raise ValueError(
                    "No tests were generated. Check logs for details. "
                    "This may be due to API issues or invalid server configuration."
                )

            # Create test suite - use suite_id from request as both ID and name
            suite = ConversationTestSuite(
                suite_id=request.suite_id,
                name=request.suite_id,
                description=f"Generated based on: {request.user_intent}",
                suite_type="conversational",
                test_cases=tests,
                user_patience_level="medium",
                conversation_style="natural",
            )

            # Save test suite
            if status:
                status.update("Saving test suite...")
            self.config_manager.save_test_suite(suite, use_global=use_global)

            return suite
        finally:
            # Always cleanup
            await self.cleanup()

    async def cleanup(self):
        """Clean up resources"""
        await self.research_agent.cleanup()
