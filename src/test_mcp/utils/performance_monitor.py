import statistics
from dataclasses import dataclass, field
from typing import Optional, Union


@dataclass
class TestExecutionMetrics:
    """Metrics for individual test execution"""

    test_id: str
    start_time: float
    end_time: Optional[float] = None
    duration: Optional[float] = (
        None  # Duration in seconds (optional for incomplete tests)
    )
    turns_completed: int = 0
    api_calls_made: int = 0
    # tokens_consumed removed - unreliable estimation
    success: bool = False
    error_message: Optional[str] = None


@dataclass
class SuiteExecutionMetrics:
    """Metrics for entire test suite execution"""

    suite_id: str
    start_time: float
    test_metrics: list[TestExecutionMetrics] = field(default_factory=list)
    parallelism_used: int = 1
    total_duration: Optional[float] = (
        None  # Total duration in seconds (optional until completion)
    )

    def get_summary_stats(self) -> dict[str, Union[str, int, float]]:
        """Generate summary statistics for the test suite"""
        completed_tests = [t for t in self.test_metrics if t.duration is not None]

        if not completed_tests:
            return {"status": "no_completed_tests"}

        durations = [t.duration for t in completed_tests if t.duration is not None]

        return {
            "total_tests": len(self.test_metrics),
            "completed_tests": len(completed_tests),
            "success_rate": len([t for t in completed_tests if t.success])
            / len(completed_tests),
            "average_duration": statistics.mean(durations),  # Duration in seconds
            "median_duration": statistics.median(durations),  # Duration in seconds
            "total_api_calls": sum(t.api_calls_made for t in completed_tests),
            # Token consumption removed for simplicity
            "parallelism_efficiency": len(completed_tests) / (self.total_duration or 1),
        }
