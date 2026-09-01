"""Gemini API rate limiter — token bucket, 12 calls / 60 seconds (free tier)."""

from __future__ import annotations

import time
import threading
from collections import deque

from utils.exceptions import GeminiRateLimitError


class TokenBucketRateLimiter:
    """
    Thread-safe sliding-window rate limiter for the Gemini API.

    Default limits: 12 requests per 60 seconds.
    (Free tier allows 15 req/min — we use 12 to leave a 3-request safety buffer.)
    """

    def __init__(self, max_calls: int = 12, period_seconds: float = 60.0):
        self.max_calls = max_calls
        self.period = period_seconds
        self._calls: deque[float] = deque()
        self._lock = threading.Lock()

    def wait_if_needed(self) -> None:
        """
        Block the calling thread until a request slot is available.
        Must be called before every Gemini API call.

        Raises GeminiRateLimitError if a slot cannot be obtained within 120s.
        """
        deadline = time.time() + 120.0  # hard timeout to prevent infinite block

        while True:
            with self._lock:
                now = time.time()
                # Expire calls older than the rate window
                while self._calls and now - self._calls[0] > self.period:
                    self._calls.popleft()

                if len(self._calls) < self.max_calls:
                    self._calls.append(now)
                    return

                # Calculate how long to wait
                oldest = self._calls[0]
                sleep_time = self.period - (now - oldest) + 0.05

            if time.time() + sleep_time > deadline:
                raise GeminiRateLimitError(
                    "Gemini rate limit: could not obtain a slot within 120 seconds."
                )

            time.sleep(min(sleep_time, 5.0))  # sleep in chunks to stay responsive

    def calls_in_window(self) -> int:
        """Return the number of calls made within the current rate window."""
        with self._lock:
            now = time.time()
            return sum(1 for t in self._calls if now - t <= self.period)


# Global singleton — import from everywhere Gemini is called
gemini_rate_limiter = TokenBucketRateLimiter(max_calls=12, period_seconds=60.0)
