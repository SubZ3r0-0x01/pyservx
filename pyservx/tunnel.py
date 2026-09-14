#!/usr/bin/env python3
"""Public share links without a public IP.

Tries local tunnel providers in order and publishes the resulting public
HTTPS URL so anyone on the internet can reach this server through the
host's normal internet connection:

  1. tailscale funnel   (if Tailscale is installed + logged in)
  2. cloudflared        (quick tunnels, no account needed)
  3. ngrok              (local agent + management API on :4040)

The provider binary must already be installed; PyServeX only drives it.
"""

import os
import json
import re
import subprocess
import threading
import time
import urllib.request


class TunnelManager:
    PROVIDER_ORDER = ("tailscale", "cloudflared", "ngrok")

    def __init__(self, port):
        self.port = port
        self.url = None
        self.provider = None
        self._proc = None
        self._stop = threading.Event()
        self.thread = None
        self.restarts = 0

    # ------------------------------------------------------------------
    def start(self):
        if self.thread:
            return
        self.thread = threading.Thread(target=self._run, daemon=True,
                                       name="pyservx-tunnel")
        self.thread.start()

    def stop(self):
        self._stop.set()
        if self._proc:
            try:
                self._proc.terminate()
            except OSError:
                pass

    def info(self):
        return {"url": self.url or "", "provider": self.provider or ""}

    # ------------------------------------------------------------------
    def _run(self):
        while not self._stop.is_set():
            for name in self.PROVIDER_ORDER:
                if self._stop.is_set():
                    return
                fn = getattr(self, "_try_" + name)
                try:
                    url = fn()
                except FileNotFoundError:
                    continue          # binary not installed
                except Exception:
                    continue
                if url:
                    self.url = url
                    self.provider = name
                    if self._watchdog():
                        self.restarts += 1
                        break       # process died: clear old url and retry
                    return
                if self._stop.is_set():
                    return
            self._stop.wait(15.0)    # nothing worked; back off & re-try
        # none worked: stay silent (LAN mode is fine)

    def _watchdog(self):
        """Hold the tunnel open; if the provider subprocess dies, drop the
        published URL and let _run retry the provider chain."""
        while not self._stop.is_set():
            if self._proc and self._proc.poll() is not None:
                self.url = None
                self.provider = None
                return True
            if self._stop.wait(5.0):
                break
        # stop requested or proc missing: tear down cleanly
        self.url = None
        self.provider = None
        return False

    @staticmethod
    def _which(binary):
        return subprocess.run(["where", binary] if os.name == "nt"
                              else ["which", binary],
                              capture_output=True).returncode == 0

    def _wait_for(self, pattern, stream_read, timeout=25.0, proc=None):
        rx = re.compile(pattern)
        deadline = time.time() + timeout
        buf = ""
        while time.time() < deadline and not self._stop.is_set():
            chunk = stream_read()
            if chunk:
                buf += chunk.decode("utf-8", "ignore")
                m = rx.search(buf)
                if m:
                    return m.group(0)
            elif proc and proc.poll() is not None:
                break
            time.sleep(0.4)
        return None

    # -- providers -------------------------------------------------------
    def _try_cloudflared(self):
        if not self._which("cloudflared"):
            raise FileNotFoundError("cloudflared")
        self._proc = subprocess.Popen(
            ["cloudflared", "tunnel", "--url",
             "http://127.0.0.1:%d" % self.port, "--no-autoupdate"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        return self._wait_for(r"https://[a-z0-9-]+\.trycloudflare\.com",
                              lambda: self._proc.stdout.readline(),
                              timeout=30.0, proc=self._proc)

    def _try_ngrok(self):
        if not self._which("ngrok"):
            raise FileNotFoundError("ngrok")
        self._proc = subprocess.Popen(
            ["ngrok", "http", str(self.port), "--log=stdout", "--log-format=json"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.time() + 20.0
        while time.time() < deadline and not self._stop.is_set():
            try:
                with urllib.request.urlopen(
                        "http://127.0.0.1:4040/api/tunnels", timeout=3) as r:
                    data = json.loads(r.read().decode())
                for t in data.get("tunnels", []):
                    url = t.get("public_url", "")
                    if url.startswith("https://"):
                        return url
            except Exception:
                pass
            time.sleep(0.8)
        return None

    def _try_tailscale(self):
        if not self._which("tailscale"):
            raise FileNotFoundError("tailscale")
        status = subprocess.run(["tailscale", "status"],
                                capture_output=True)
        if status.returncode != 0:
            return None                      # not logged in
        r = subprocess.run(["tailscale", "funnel", "--bg", "--https=443",
                            str(self.port)],
                           capture_output=True, text=True, timeout=60)
        out = (r.stdout or "") + "\n" + (r.stderr or "")
        m = re.search(r"https://[a-z0-9.-]+\.ts\.net", out)
        if m:
            return m.group(0)
        return None
