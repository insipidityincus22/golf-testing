import asyncio
import time
from collections import defaultdict, deque


class RateLimiter:
    """Simple rate limiter with RPM and token limits"""

    def __init__(self) -> None:
        # Updated to realistic API limits (conservative defaults for reliable operation)
        self.providers = {
            "anthropic": {"requests_per_minute": 50, "tokens_per_minute": 10000},
            "openai": {"requests_per_minute": 500, "tokens_per_minute": 30000},
            "gemini": {"requests_per_minute": 60, "tokens_per_minute": 8000},
        }
        self.request_history: dict[str, deque] = defaultdict(deque)
        # Add token usage tracking
        self.token_usage: dict[str, int] = defaultdict(int)  # Current window total

    async def acquire_request_slot(self, provider: str) -> None:
        """Acquire permission to make API request with token awareness"""
        limits = self.providers.get(provider, {})
        rpm_limit = limits.get("requests_per_minute", 50)
        tpm_limit = limits.get("tokens_per_minute", 40000)

        now = time.time()
        self._clean_old_requests(provider, now)

        # Check both request and token limits
        while (
            len(self.request_history[provider]) >= rpm_limit
            or self.token_usage[provider] > tpm_limit * 0.8
        ):  # 80% threshold
            if self.token_usage[provider] > tpm_limit * 0.8:
                print(
                    f"   Approaching token limit for {provider}: {self.token_usage[provider]} tokens used"
                )

            await asyncio.sleep(1)
            now = time.time()
            self._clean_old_requests(provider, now)

        # Record the request
        self.request_history[provider].append(
            (now, 0)
        )  # Will be updated with actual usage

    def record_token_usage(self, provider: str, tokens_used: int) -> None:
        """Record actual token usage from API response"""
        self.token_usage[provider] += tokens_used

        # Update the most recent request with actual usage
        if self.request_history[provider]:
            timestamp, _ = self.request_history[provider][-1]
            self.request_history[provider][-1] = (timestamp, tokens_used)

    def _clean_old_requests(self, provider: str, current_time: float) -> None:
        """Remove requests older than 1 minute and their token usage"""
        cutoff_time = current_time - 60

        tokens_to_remove = 0
        while (
            self.request_history[provider]
            and self.request_history[provider][0][0] < cutoff_time
        ):
            _, tokens = self.request_history[provider].popleft()
            tokens_to_remove += tokens

        # Remove old tokens from current usage
        self.token_usage[provider] = max(
            0, self.token_usage[provider] - tokens_to_remove
        )
