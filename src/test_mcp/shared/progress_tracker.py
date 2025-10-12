import asyncio
import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from .console_shared import get_console
from .result_models import TestStatus, TestType


@dataclass
class TestProgress:
    """Progress tracking for any test type"""

    test_id: str
    test_type: TestType
    status: TestStatus = TestStatus.QUEUED
    start_time: datetime | None = None

    # Generic progress tracking
    current_step: int = 0
    total_steps: int = 1
    step_description: str = ""

    # Type-specific details (extensible)
    details: dict[str, Any] | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        if self.details is None:
            self.details = {}


class ProgressTracker:
    """Progress tracking for all test types"""

    def __init__(
        self, total_tests: int, parallelism: int, test_types: list[str] | None = None
    ):
        self.console = get_console().console
        self.total_tests = total_tests
        self.parallelism = parallelism
        self.test_types = test_types or ["conversation"]
        self.test_progress: dict[str, TestProgress] = {}

        # Use both threading and asyncio compatible synchronization
        self._thread_lock = threading.Lock()  # For synchronous calls
        self._async_lock = None  # Will be created when needed for async calls

        # Setup rich progress components
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=self.console,
        )

        self.overall_task = self.progress.add_task(
            f"Running {total_tests} tests (max {parallelism} parallel)",
            total=total_tests,
        )

    def _get_async_lock(self):
        """Get or create async lock for asyncio contexts"""
        if self._async_lock is None:
            try:
                # Only create async lock if we're in an async context
                asyncio.get_running_loop()
                self._async_lock = asyncio.Lock()
            except RuntimeError:
                # Not in async context, will use thread lock
                pass
        return self._async_lock

    def update_test_status(
        self, test_id: str, test_type: TestType, status: TestStatus, **kwargs: Any
    ) -> None:
        """Thread-safe update of test status"""
        with self._thread_lock:
            self._update_test_status_impl(test_id, test_type, status, **kwargs)

    async def async_update_test_status(
        self, test_id: str, test_type: TestType, status: TestStatus, **kwargs: Any
    ) -> None:
        """Async-safe update of test status"""
        async_lock = self._get_async_lock()
        if async_lock is not None:
            async with async_lock:
                self._update_test_status_impl(test_id, test_type, status, **kwargs)
        else:
            # Fallback to thread lock if not in async context
            with self._thread_lock:
                self._update_test_status_impl(test_id, test_type, status, **kwargs)

    def _update_test_status_impl(
        self, test_id: str, test_type: TestType, status: TestStatus, **kwargs: Any
    ) -> None:
        """Core test status update implementation (already inside lock)"""
        if test_id not in self.test_progress:
            self.test_progress[test_id] = TestProgress(
                test_id=test_id, test_type=test_type
            )

        progress = self.test_progress[test_id]
        progress.status = status

        # Update progress fields
        for key, value in kwargs.items():
            if hasattr(progress, key):
                setattr(progress, key, value)
            elif progress.details is not None:
                progress.details[key] = value

        if status in [TestStatus.COMPLETED, TestStatus.FAILED, TestStatus.TIMEOUT]:
            self.progress.advance(self.overall_task, 1)

    def generate_status_table(self) -> Table:
        """Generate real-time status table for all test types"""
        table = Table(title="Test Execution Status")
        table.add_column("Test ID", style="cyan", no_wrap=True)
        table.add_column("Type", style="yellow")
        table.add_column("Status", justify="center")
        table.add_column("Progress", justify="center")
        table.add_column("Details", style="dim")

        status_icons = {
            TestStatus.QUEUED: "...",
            TestStatus.RUNNING: "...",  # Simplified from 🔄
            TestStatus.COMPLETED: "✅",
            TestStatus.FAILED: "❌",
            TestStatus.TIMEOUT: "TIMEOUT",
            TestStatus.SKIPPED: "SKIP",
        }

        with self._thread_lock:
            # Show currently running tests
            running_tests = [
                (id, p)
                for id, p in self.test_progress.items()
                if p.status == TestStatus.RUNNING
            ]

            for test_id, progress in running_tests[:10]:  # Show max 10 running
                progress_text = f"{progress.current_step}/{progress.total_steps}"
                details = progress.step_description or (
                    progress.details.get("current_activity", "Running...")
                    if progress.details
                    else "Running..."
                )

                table.add_row(
                    test_id[:20],
                    progress.test_type,
                    status_icons.get(progress.status, "?"),
                    progress_text,
                    details[:40],
                )

            # Show recent completions/failures
            completed_tests = [
                (id, p)
                for id, p in self.test_progress.items()
                if p.status in [TestStatus.COMPLETED, TestStatus.FAILED]
            ]

            for test_id, progress in completed_tests[-5:]:  # Show last 5 completed
                details = (
                    progress.error_message[:30] if progress.error_message else "Success"
                )
                table.add_row(
                    test_id[:20],
                    progress.test_type,
                    status_icons.get(progress.status, "?"),
                    "Done",
                    details,
                )

        return table

    def add_test_type_support(
        self, test_type: str, step_names: list[str] | None = None
    ) -> None:
        """Extend progress tracker to support new test types"""
        if test_type not in self.test_types:
            self.test_types.append(test_type)

    def update_simple_progress(
        self, test_id: str, step_description: str = "", completed: bool = False
    ) -> None:
        """Thread-safe progress update - always synchronous for UI consistency"""
        with self._thread_lock:
            self._update_simple_progress_impl(test_id, step_description, completed)

    async def _async_update_simple_progress(
        self, test_id: str, step_description: str = "", completed: bool = False
    ):
        """Async version of simple progress update"""
        async with self._get_async_lock():
            self._update_simple_progress_impl(test_id, step_description, completed)

    def _update_simple_progress_impl(
        self, test_id: str, step_description: str, completed: bool
    ):
        """Core progress update implementation (thread-safe)"""
        current_time = datetime.now()

        # Update or create test progress entry using TestProgress objects
        if test_id not in self.test_progress:
            from .result_models import TestType

            self.test_progress[test_id] = TestProgress(
                test_id=test_id,
                test_type=TestType.CONVERSATION,  # Default type
                status=TestStatus.RUNNING,
                start_time=current_time,
            )

        progress = self.test_progress[test_id]
        progress.step_description = step_description
        if progress.details is None:
            progress.details = {}
        progress.details["last_update"] = current_time

        # Mark completed if specified
        if completed:
            progress.status = TestStatus.COMPLETED
            if progress.details is not None:
                progress.details["end_time"] = current_time

        # Update Rich progress bar
        self._update_rich_progress()

    def _update_rich_progress(self):
        """Update Rich progress display"""
        completed_count = len(
            [p for p in self.test_progress.values() if p.status == TestStatus.COMPLETED]
        )
        self.progress.update(self.overall_task, completed=completed_count)

    def get_simple_progress_display(
        self, suite_name: str = "", server_name: str = ""
    ) -> str:
        """Get simplified progress display for mcp-t commands"""
        with self._thread_lock:
            running_count = len(
                [
                    p
                    for p in self.test_progress.values()
                    if p.status == TestStatus.RUNNING
                ]
            )
            completed_count = len(
                [
                    p
                    for p in self.test_progress.values()
                    if p.status == TestStatus.COMPLETED
                ]
            )
            failed_count = len(
                [
                    p
                    for p in self.test_progress.values()
                    if p.status == TestStatus.FAILED
                ]
            )

            status_parts = []
            if suite_name and server_name:
                status_parts.append(
                    f"[cyan]{suite_name}[/cyan] → [cyan]{server_name}[/cyan]"
                )

            status_parts.append(
                f"Progress: {completed_count + failed_count}/{self.total_tests}"
            )

            if running_count > 0:
                # Show currently running test
                running_tests = [
                    p
                    for p in self.test_progress.values()
                    if p.status == TestStatus.RUNNING
                ]
                if running_tests:
                    current_test = running_tests[0]
                    status_parts.append(f"Current: {current_test.test_id}")
                    if current_test.step_description:
                        status_parts.append(f"({current_test.step_description})")

            return " | ".join(status_parts)
