from pydantic import Field

from .base import BaseTestConfig, BaseTestSuite


class SecurityTestConfig(BaseTestConfig):
    """Security-focused test configuration"""

    auth_method: str = Field(..., description="Authentication method to test")
    rate_limit_threshold: int = Field(
        default=100, description="Expected rate limit threshold"
    )
    vulnerability_checks: list[str] = Field(
        default_factory=lambda: ["injection", "auth", "rate_limit"],
        description="Security vulnerability checks to perform",
    )
    severity_threshold: str = Field(
        default="medium", description="Minimum severity to report"
    )


class SecurityTestSuite(BaseTestSuite):
    """Security test suite with auth and vulnerability focus"""

    # Override inherited fields with security-specific defaults
    auth_required: bool = Field(
        default=True, description="Whether authentication is required"
    )

    # Direct fields - consistent naming
    test_cases: list[SecurityTestConfig] = Field(
        default_factory=list, description="Security test cases to execute"
    )

    # Type-specific settings
    include_penetration_tests: bool = Field(
        default=False, description="Include penetration testing"
    )

    def get_tests(self) -> list[SecurityTestConfig]:
        return self.test_cases
