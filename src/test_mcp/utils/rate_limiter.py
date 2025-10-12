import asyncio
import time
from collections import defaultdict, deque


class RateLimiter:
    """Simple rate limiter with RPM and token limits"""

    def __init__(self) -> None:
        self.providers = {
            "anthropic": {"requests_per_minute": 50, "tokens_per_minute": 40000},
            "openai": {"requests_per_minute": 500, "tokens_per_minute": 150000},
            "gemini": {"requests_per_minute": 300, "tokens_per_minute": 100000},
        }
        self.request_history: dict[str, deque] = defaultdict(
            deque
        )  # (timestamp, unused)

    async def acquire_request_slot(self, provider: str) -> None:
        """Acquire permission to make API request (simplified approach)"""
        # Simple semaphore-based rate limiting
        # Actual rate limiting handled by provider's own retry logic and API limits
        limits = self.providers.get(provider, {})
        rpm_limit = limits.get("requests_per_minute", 50)

        # Wait if we're at the limit
        now = time.time()
        self._clean_old_requests(provider, now)

        while len(self.request_history[provider]) >= rpm_limit:
            await asyncio.sleep(1)
            now = time.time()
            self._clean_old_requests(provider, now)

        # Record the request
        self.request_history[provider].append((now, 0))  # No token estimation

    def _clean_old_requests(self, provider: str, current_time: float) -> None:
        """Remove requests older than 1 minute"""
        cutoff_time = current_time - 60  # 1 minute ago
        while (
            self.request_history[provider]
            and self.request_history[provider][0][0] < cutoff_time
        ):
            self.request_history[provider].popleft()
