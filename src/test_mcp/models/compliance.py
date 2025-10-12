from pydantic import Field

from .base import BaseTestConfig, BaseTestSuite


class ComplianceTestConfig(BaseTestConfig):
    """MCP protocol compliance test configuration"""

    protocol_version: str = Field(
        default="2025-06-18", description="MCP protocol version to test"
    )
    required_capabilities: list[str] = Field(
        default_factory=list, description="Required MCP capabilities to validate"
    )
    check_categories: list[str] = Field(
        default=["handshake", "capabilities", "tools", "resources"],
        description="Compliance check categories to run",
    )


class ComplianceTestSuite(BaseTestSuite):
    """Compliance test suite with protocol-specific settings"""

    # Override with typed test cases
    test_cases: list[ComplianceTestConfig] = Field(
        default_factory=list, description="Compliance test cases to execute"
    )

    # Type-specific settings
    strict_mode: bool = Field(
        default=True, description="Strict protocol compliance checking"
    )

    def get_tests(self) -> list[ComplianceTestConfig]:
        return self.test_cases
