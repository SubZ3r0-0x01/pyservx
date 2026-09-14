#!/usr/bin/env python3
"""Ephemeral (self-destructing) download links for PyServeX.

token -> {abs_path, expires_at, max_downloads, downloads}
Links vanish automatically once expired or fully consumed.
A janitor thread purges expired entries every minute.
"""

import logging
import os
import secrets
import threading
import time


class EphemeralLinkManager:
    def __init__(self):
        self.lock = threading.RLock()
        self.links = {}
        self._stop = threading.Event()
        self._janitor = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._janitor.start()

    def create_link(self, abs_path, ttl_seconds=3600, max_downloads=1):
        if not os.path.isfile(abs_path):
            return None
        token = secrets.token_urlsafe(24)
        with self.lock:
            self.links[token] = {
                "path": os.path.abspath(abs_path),
                "expires_at": time.time() + int(ttl_seconds),
                "max_downloads": max_downloads,
                "downloads": 0,
                "created": time.time(),
            }
        return token

    def resolve(self, token):
        """Return file path & consume one use; None when invalid/expired/exhausted."""
        now = time.time()
        with self.lock:
            entry = self.links.get(token)
            if not entry:
                return None
            if entry["expires_at"] < now:
                del self.links[token]
                return None
            if entry["max_downloads"] is not None and entry["downloads"] >= entry["max_downloads"]:
                del self.links[token]
                return None
            entry["downloads"] += 1
            path = entry["path"]
            exhausted = (entry["max_downloads"] is not None
                         and entry["downloads"] >= entry["max_downloads"])
            if exhausted or not os.path.isfile(path):
                # keep until response served: caller deletes via finalize()
                pass
        return {"path": path, "exhausted": exhausted}

    def finalize(self, token):
        """Delete link record after a successful exhausted transfer."""
        with self.lock:
            entry = self.links.get(token)
            if entry and entry["max_downloads"] is not None \
                    and entry["downloads"] >= entry["max_downloads"]:
                del self.links[token]

    def revoke(self, token):
        with self.lock:
            return self.links.pop(token, None) is not None

    def list_links(self):
        now = time.time()
        with self.lock:
            return [{"token": t[:8] + "...",
                     "expires_in": max(0, int(e["expires_at"] - now)),
                     "downloads": e["downloads"],
                     "max_downloads": e["max_downloads"],
                     "file": os.path.basename(e["path"])}
                    for t, e in self.links.items()]

    def _cleanup_loop(self):
        while not self._stop.wait(60):
            now = time.time()
            with self.lock:
                dead = [t for t, e in self.links.items()
                        if e["expires_at"] < now]
                for t in dead:
                    del self.links[t]
            if dead:
                logging.info("Ephemeral links expired: %d", len(dead))

    def shutdown(self):
        self._stop.set()
