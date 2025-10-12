from .compliance import ComplianceTestSuite
from .conversational import ConversationTestSuite
from .security import SecurityTestSuite

TestSuiteType = ComplianceTestSuite | SecurityTestSuite | ConversationTestSuite

# Simple factory without overload complexity
SUITE_TYPES = {
    "compliance": ComplianceTestSuite,
    "security": SecurityTestSuite,
    "conversational": ConversationTestSuite,
}


class TestSuiteFactory:
    """Simplified factory for creating test suites"""

    @staticmethod
    def create_suite(suite_type: str, config_data: dict) -> TestSuiteType:
        """Create a test suite with simple class mapping"""
        suite_class = SUITE_TYPES.get(suite_type)
        if not suite_class:
            supported_types = list(SUITE_TYPES.keys())
            raise ValueError(
                f"Unknown test suite type: {suite_type}. Supported types: {supported_types}"
            )

        return suite_class(**config_data)

    @staticmethod
    def get_supported_types() -> list[str]:
        """Get list of supported suite types"""
        return list(SUITE_TYPES.keys())
