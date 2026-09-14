#!/usr/bin/env python3
"""Access Logger for PyServeX (JSONL with size-based rotation)."""

import json
import os
import threading
import time
from datetime import datetime
from collections import defaultdict

DEFAULT_LOG_DIR = os.path.join(os.path.expanduser("~"), ".pyservx_logs")
LOG_ROTATE_BYTES = 10 * 1024 * 1024  # rotate the JSONL when it crosses 10 MiB
LOG_KEEP_ROTATIONS = 5               # how many old rotated files to retain
_RING = 0


def _next_log_path(log_dir):
    """Plain 'access.jsonl' lives in log_dir; rotated copies get a suffix."""
    return os.path.join(log_dir, "access.jsonl")


class AccessLogger:
    def __init__(self, log_file=None):
        self.log_file = log_file or _next_log_path(
            os.environ.get("PYSERVX_LOGS_DIR", DEFAULT_LOG_DIR))
        self._lock = threading.Lock()
        self.logs = []
        self.stats = defaultdict(int)

        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)

    def log_access(self, ip, path, status_code, method="GET"):
        """Log a file access, appending a JSON line; returns the entry."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "ip": ip,
            "path": path,
            "method": method,
            "status": status_code,
        }
        with self._lock:
            self.logs.append(entry)
            self.stats[f"{method} {status_code}"] += 1
            try:
                with open(self.log_file, "a") as f:
                    f.write(json.dumps(entry) + "\n")
            except OSError:
                pass
            if os.path.getsize(self.log_file) > LOG_ROTATE_BYTES:
                self.rotate()
        return entry

    def rotate(self):
        """Move the current JSONL aside (up to LOG_KEEP_ROTATIONS) and start fresh."""
        global _RING
        base = os.path.dirname(self.log_file)
        try:
            os.makedirs(base, exist_ok=True)
            stamp = time.strftime("%Y%m%d-%H%M%S")
            dest = os.path.join(base, "access.%s.%d.jsonl" % (stamp, _RING))
            _RING = (_RING + 1) % 10000
            os.replace(self.log_file, dest)
        except OSError:
            return
        kept = sorted(p for p in os.listdir(base) if p.startswith("access."))
        for stale in kept[:-LOG_KEEP_ROTATIONS]:
            try:
                os.remove(os.path.join(base, stale))
            except OSError:
                pass

    def get_stats(self):
        """Get access statistics."""
        with self._lock:
            return {
                "total_requests": len(self.logs),
                "by_status": dict(self.stats),
                "unique_ips": len(set(log["ip"] for log in self.logs)),
            }

    def get_recent(self, limit=10):
        """Get recent access logs."""
        with self._lock:
            return self.logs[-limit:]


if __name__ == "__main__":
    logger = AccessLogger()
    # Simulate some access
    logger.log_access("192.168.1.100", "/files/test.txt", 200)
    logger.log_access("192.168.1.101", "/files/secret.pdf", 403)
    print(json.dumps(logger.get_stats(), indent=2))