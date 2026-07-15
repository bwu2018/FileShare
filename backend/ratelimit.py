import time
from collections import defaultdict
from threading import Lock


class RateLimiter:
    # In-memory sliding-window-log limiter, keyed by an arbitrary string (the
    # client's remote address in practice). Deliberately simple: no Redis, no
    # persistence across restarts -- appropriate for a single-process, low-traffic
    # personal tool, not a multi-worker production service. Note this only limits
    # correctly with a single gunicorn worker process (--workers 1); each worker
    # process would otherwise keep its own independent counters. See backend/README.md.
    def __init__(self, max_requests: int, window_seconds: float) -> None:
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._lock = Lock()
        self._hits: dict[str, list[float]] = defaultdict(list)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        cutoff = now - self._window_seconds
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] < cutoff:
                hits.pop(0)
            if len(hits) >= self._max_requests:
                return False
            hits.append(now)
            return True
