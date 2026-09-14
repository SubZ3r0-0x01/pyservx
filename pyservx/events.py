#!/usr/bin/env python3

import json
import queue
import threading
import time

EVENT_FILE = "file"        # payload: {"path", "action": created|updated|deleted|
                           #           |moved|trashed|restored}
EVENT_UPLOAD = "upload"    # payload: {"path", "status", "received", "total"}
EVENT_STATS = "stats"      # payload: stats snapshot dict from StatsHub
EVENT_SEARCH = "search"    # payload: {"ready", "files", "tokens", "indexed_at"}
EVENT_SCAN = "scan"        # payload: {"scan_id", "status", "findings"}

MAX_SSE_CHUNK = 8192


class EventBus:
    """Thread-safe publish/subscribe bus for live (SSE) updates.

    Subscribers receive (event_type, payload) tuples from a bounded queue;
    slow consumers drop the oldest event instead of blocking the publisher.
    A short recent-history replay lets a subscriber that connects late still
    see the current state."""

    def __init__(self, max_history=128):
        self._subs = set()
        self._history = []
        self._max_history = max_history
        self._lock = threading.Lock()

    def subscribe(self, maxsize=512):
        q = queue.Queue(maxsize=maxsize)
        with self._lock:
            self._subs.add(q)
            for item in list(self._history):
                self._put(q, item)
        return q

    def unsubscribe(self, q):
        with self._lock:
            self._subs.discard(q)

    def publish(self, event_type, payload=None):
        item = (event_type, payload)
        with self._lock:
            self._history.append(item)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]
            for q in list(self._subs):
                self._put(q, item)

    def subscriber_count(self):
        with self._lock:
            return len(self._subs)

    @staticmethod
    def _put(q, item):
        try:
            q.put_nowait(item)
        except queue.Full:
            try:
                q.get_nowait()
                q.put_nowait(item)
            except (queue.Empty, queue.Full):
                pass


def format_sse(event_type, payload):
    """Format one SSE frame, chunking oversized payloads (as data: lines)."""
    data = json.dumps(payload if payload is not None else {},
                      ensure_ascii=False)
    body = (f"event: {event_type}\ndata: {data}\n\n").encode("utf-8")
    if len(body) > MAX_SSE_CHUNK:
        out = []
        while data:
            out.append(f"event: {event_type}\ndata: {data[:MAX_SSE_CHUNK]}\n\n")
            data = data[MAX_SSE_CHUNK:]
        body = "".join(out).encode("utf-8")
    return body


def stats_ticker(bus, stats, stop_event, interval=5.0):
    """Background loop publishing periodic stats snapshots so connected
    EventSource clients see live counters without polling."""
    while not stop_event.is_set():
        try:
            if stats is not None:
                bus.publish(EVENT_STATS, stats.snapshot())
        except Exception:
            pass
        if stop_event.wait(interval):
            break