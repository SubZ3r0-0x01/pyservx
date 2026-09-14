#!/usr/bin/env python3
"""Live statistics hub shared between request workers and the CLI dashboard."""

import threading
import time
from collections import deque


class StatsHub:
    def __init__(self, max_events=200):
        self.lock = threading.Lock()
        self.started = time.time()
        self.active_connections = 0
        self.total_requests = 0
        self.bytes_sent = 0
        self.bytes_received = 0
        self.downloads = 0
        self.uploads = 0
        self.auth_failures = 0
        self.p2p_transfers = 0
        self.scans = 0
        self.events = deque(maxlen=max_events)
        self._stop = threading.Event()

    # ------------- recorders (thread-safe) -------------
    def connect(self):
        with self.lock:
            self.active_connections += 1

    def disconnect(self):
        with self.lock:
            self.active_connections = max(0, self.active_connections - 1)

    def request(self, method, path, ip, status=None):
        with self.lock:
            self.total_requests += 1
            self.events.appendleft({
                "t": time.time(), "method": method,
                "path": path[:80], "ip": ip, "status": status,
            })

    def transfer(self, direction, n_bytes):
        with self.lock:
            if direction == "send":
                self.bytes_sent += n_bytes
            else:
                self.bytes_received += n_bytes

    def count_download(self):
        with self.lock:
            self.downloads += 1

    def count_upload(self):
        with self.lock:
            self.uploads += 1

    def count_auth_failure(self):
        with self.lock:
            self.auth_failures += 1

    def count_p2p(self):
        with self.lock:
            self.p2p_transfers += 1

    def count_scan(self):
        with self.lock:
            self.scans += 1

    def snapshot(self):
        with self.lock:
            return {
                "uptime": int(time.time() - self.started),
                "active_connections": self.active_connections,
                "total_requests": self.total_requests,
                "bytes_sent": self.bytes_sent,
                "bytes_received": self.bytes_received,
                "downloads": self.downloads,
                "uploads": self.uploads,
                "auth_failures": self.auth_failures,
                "p2p_transfers": self.p2p_transfers,
                "scans": self.scans,
                "events": list(self.events)[:15],
            }


def format_size(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024


def render_dashboard(stats, auth, ephemeral, stop_event, refresh=1.0):
    """Rich TUI if available, plain console fallback otherwise."""
    try:
        from rich.console import Console
        from rich.table import Table
        from rich.panel import Panel
        from rich.live import Live
        use_rich = True
    except ImportError:
        use_rich = False

    if not use_rich:
        _plain_dashboard(stats, stop_event, refresh)
        return

    console = Console()

    def build():
        s = stats.snapshot()
        header = Table.grid(padding=(0, 2))
        header.add_row("[bold cyan]PyServeX Live Dashboard[/]",
                       f"uptime [green]{s['uptime']}s[/]")
        grid = Table.grid(padding=(0, 4))
        grid.add_column(justify="right")
        grid.add_column()
        grid.add_row("Connections", f"[bold]{s['active_connections']}[/]")
        grid.add_row("Requests", str(s["total_requests"]))
        grid.add_row("Sent", format_size(s["bytes_sent"]))
        grid.add_row("Received", format_size(s["bytes_received"]))
        grid.add_row("Downloads / Uploads",
                     f"{s['downloads']} / {s['uploads']}")
        grid.add_row("Auth failures", f"[red]{s['auth_failures']}[/]" or "0")
        grid.add_row("P2P transfers", str(s["p2p_transfers"]))
        grid.add_row("Security scans", str(s["scans"]))

        ev = Table(expand=True)
        ev.add_column("time", style="dim", width=8)
        ev.add_column("method", width=6)
        ev.add_column("path")
        ev.add_column("ip", width=15)
        ev.add_column("status", width=6)
        for e in reversed(s["events"][-12:]):
            ts = time.strftime("%H:%M:%S", time.localtime(e["t"]))
            st = e["status"] or "-"
            color = "green" if isinstance(st, int) and st < 400 else \
                    "yellow" if isinstance(st, int) and st < 500 else "red"
            ev.add_row(ts, e["method"], e["path"], e["ip"],
                       f"[{color}]{st}[/{color}]")

        links = ephemeral.list_links()
        ep = Table(expand=True)
        ep.add_column("file")
        ep.add_column("expires in", justify="right")
        ep.add_column("uses", justify="right")
        for l in links[:8]:
            uses = f"{l['downloads']}/{l['max_downloads'] if l['max_downloads'] is not None else '∞'}"
            ep.add_row(l["file"], f"{l['expires_in']}s", uses)

        panel = Panel.fit(grid, border_style="cyan", title="stats")
        outer = Table.grid()
        outer.add_row(panel)
        outer.add_row(Panel(ev, title="recent requests", border_style="blue"))
        outer.add_row(Panel(ep, title="ephemeral links", border_style="magenta"))
        return Panel(outer, title="PyServeX — press Ctrl+C to exit")

    with Live(build(), console=console, refresh_per_second=2) as live:
        while not stop_event.wait(refresh):
            try:
                live.update(build())
            except Exception:
                break


def _plain_dashboard(stats, stop_event, refresh):
    while not stop_event.wait(refresh):
        s = stats.snapshot()
        print(f"\r[conn={s['active_connections']} req={s['total_requests']} "
              f"sent={format_size(s['bytes_sent'])} "
              f"dl={s['downloads']} ul={s['uploads']}]   ", end="", flush=True)
