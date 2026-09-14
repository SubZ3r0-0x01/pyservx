#!/usr/bin/env python3
"""Bandwidth throttling for PyServeX.

Provides a thread-safe token-bucket shared across all connections so a
global limit (e.g. --limit-speed 2M) is honoured collectively.
"""

import threading
import time

_UNITS = {"": 1, "B": 1,
          "K": 1024, "KB": 1024, "KIB": 1024,
          "M": 1024 ** 2, "MB": 1024 ** 2, "MIB": 1024 ** 2,
          "G": 1024 ** 3, "GB": 1024 ** 3, "GIB": 1024 ** 3}


def parse_speed(text):
    """'2M', '500kb', '1.5 MB/s', '1048576' -> bytes per second."""
    if text in (None, "", "0", "off"):
        return None
    s = str(text).strip().lower().replace("/s", "").replace("ps", "")
    num = ""
    i = 0
    while i < len(s) and (s[i].isdigit() or s[i] in ".+-"):
        num += s[i]
        i += 1
    unit = s[i:].strip().upper()
    if not num:
        raise ValueError(f"Invalid speed: {text!r}")
    if unit not in _UNITS:
        raise ValueError(f"Unknown speed unit: {unit!r}")
    value = float(num) * _UNITS[unit]
    if value <= 0:
        return None
    return value


class RateLimiter:
    """Thread-safe global token bucket (bytes/second)."""

    def __init__(self, bytes_per_sec):
        self.rate = float(bytes_per_sec)
        self._lock = threading.Lock()
        self._tokens = self.rate
        self._last = time.monotonic()

    def set_rate(self, bytes_per_sec):
        with self._lock:
            self.rate = float(bytes_per_sec)
            self._tokens = min(self._tokens, self.rate)

    def consume(self, n_bytes):
        """Block until n_bytes of budget are available."""
        if not self.rate or self.rate <= 0:
            return
        need = float(n_bytes)
        while need > 0:
            with self._lock:
                now = time.monotonic()
                elapsed = now - self._last
                self._last = now
                self._tokens = min(self.rate, self._tokens + elapsed * self.rate)
                grant = min(need, self._tokens)
                if grant > 0:
                    self._tokens -= grant
                    need -= grant
                    sleep_for = 0.0
                else:
                    # time needed to accumulate the remainder
                    sleep_for = (need - self._tokens) / self.rate
            if sleep_for > 0:
                time.sleep(min(sleep_for, 0.25))


class ThrottledReader:
    """File-like iterator that enforces the rate limiter while yielding chunks."""

    def __init__(self, fileobj, limiter=None, chunk_size=64 * 1024):
        self.f = fileobj
        self.limiter = limiter
        self.chunk_size = chunk_size

    def __iter__(self):
        return self

    def __next__(self):
        chunk = self.f.read(self.chunk_size)
        if not chunk:
            self.f.close()
            raise StopIteration
        if self.limiter:
            self.limiter.consume(len(chunk))
        return chunk
