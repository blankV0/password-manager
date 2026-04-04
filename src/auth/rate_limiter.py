"""
Thread-safe sliding-window rate limiter.

Uses an in-memory deque per key (typically ``ip:email``) to track
timestamps of recent failures.  Timestamps outside the current window
are pruned lazily on every access.

This limiter is intentionally **not** distributed — it runs inside each
Uvicorn worker.  For a single-instance deployment (the current setup)
this is sufficient and avoids an external dependency like Redis.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Deque, DefaultDict


class SlidingWindowRateLimiter:
    def __init__(self, max_attempts: int, window_seconds: int):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._events: DefaultDict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> None:
        window = self._events[key]
        while window and now - window[0] > self.window_seconds:
            window.popleft()
        if not window:
            self._events.pop(key, None)

    def allow(self, key: str) -> tuple[bool, int]:
        now = time.monotonic()
        with self._lock:
            self._prune(key, now)
            window = self._events.get(key)
            if window and len(window) >= self.max_attempts:
                retry_after = max(1, int(self.window_seconds - (now - window[0])))
                return False, retry_after
            return True, 0

    def register_failure(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            self._events[key].append(now)
            self._prune(key, now)

    def reset(self, key: str) -> None:
        with self._lock:
            self._events.pop(key, None)
