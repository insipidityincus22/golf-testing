import asyncio
import time
import uuid
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
        # Track correlation IDs to provider/timestamp mapping
        self._pending_requests: dict[str, tuple[str, float]] = {}

    async def acquire_request_slot(self, provider: str) -> str:
        """Acquire permission to make API request and return correlation ID"""
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

        # Generate correlation ID and record the request
        correlation_id = f"{provider}_{int(now)}_{uuid.uuid4().hex[:8]}"
        self.request_history[provider].append((now, 0, correlation_id))
        self._pending_requests[correlation_id] = (provider, now)

        return correlation_id

    def record_token_usage(self, correlation_id: str, tokens_used: int) -> None:
        """Record actual token usage from API response using correlation ID"""
        if correlation_id not in self._pending_requests:
            print(f"Warning: Unknown correlation ID {correlation_id}")
            return

        provider, _timestamp = self._pending_requests[correlation_id]
        self.token_usage[provider] += tokens_used

        # Find and update the specific request entry
        for i, entry in enumerate(self.request_history[provider]):
            if len(entry) >= 3 and entry[2] == correlation_id:
                req_time, _req_tokens, req_id = entry
                self.request_history[provider][i] = (req_time, tokens_used, req_id)
                break

        # Clean up pending request
        del self._pending_requests[correlation_id]

    def _clean_old_requests(self, provider: str, current_time: float) -> None:
        """Remove requests older than 1 minute and their token usage"""
        cutoff_time = current_time - 60

        tokens_to_remove = 0
        while (
            self.request_history[provider]
            and self.request_history[provider][0][0] < cutoff_time
        ):
            entry = self.request_history[provider].popleft()
            if len(entry) >= 2:
                tokens = entry[1]
                tokens_to_remove += tokens

                # Clean up any pending request that got orphaned
                if len(entry) >= 3:
                    correlation_id = entry[2]
                    if correlation_id in self._pending_requests:
                        del self._pending_requests[correlation_id]

        # Remove old tokens from current usage
        self.token_usage[provider] = max(
            0, self.token_usage[provider] - tokens_to_remove
        )

    def cleanup_pending_request(self, correlation_id: str) -> None:
        """Clean up pending request on error"""
        if correlation_id in self._pending_requests:
            del self._pending_requests[correlation_id]
