from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from threading import Lock
from time import monotonic


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    retry_after_seconds: int
    remaining: int


class InMemoryRateLimiter:
    def __init__(self, max_requests: int, window_seconds: int = 60) -> None:
        if max_requests <= 0:
            raise ValueError("max_requests must be positive.")
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._buckets: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str) -> RateLimitDecision:
        now = monotonic()
        with self._lock:
            bucket = self._buckets[key]
            cutoff = now - self._window_seconds
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()

            if len(bucket) >= self._max_requests:
                retry_after = int(max(1, self._window_seconds - (now - bucket[0])))
                return RateLimitDecision(
                    allowed=False,
                    retry_after_seconds=retry_after,
                    remaining=0,
                )

            bucket.append(now)
            remaining = self._max_requests - len(bucket)
            return RateLimitDecision(
                allowed=True,
                retry_after_seconds=0,
                remaining=remaining,
            )

