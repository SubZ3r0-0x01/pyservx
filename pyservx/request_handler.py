#!/usr/bin/env python3

import http.server
import os
import posixpath
import urllib.parse
import shutil
import logging
import json
import time
import re
import socket
from http import cookies as http_cookies

from . import html_generator
from . import ui_shell
from . import file_operations
from . import mcp_server
from . import remote_sftp
from . import events
from . import trash as trash_module
import queue as queue_module

# ---------------------------------------------------------------------------
# Security policy tables
# ---------------------------------------------------------------------------

RISKY_EXTENSIONS = {
    ".html", ".htm", ".xhtml", ".svg", ".svgz",          # active content
    ".exe", ".msi", ".bat", ".cmd", ".com", ".scr",      # executables
    ".ps1", ".psm1", ".sh", ".bash", ".zsh",             # shell scripts
    ".vbs", ".vbe", ".wsf", ".hta", ".jar", ".apk",
    ".dll", ".so", ".bin", ".iso",
}

SAFE_INLINE_MIMES_PREFIX = ("image/", "audio/", "video/", "text/plain")

BASE_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "SAMEORIGIN",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}

PREVIEW_CSP = ("default-src 'none'; "
               "img-src 'self' data: blob:; "
               "media-src 'self' blob:; "
               "style-src 'unsafe-inline'; "
               "script-src 'unsafe-inline'; "
               "frame-src 'self'")

RAW_SANDBOX_CSP = "default-src 'none'; sandbox"

SESSION_COOKIE = "psx_session"


def guess_safe_mime(path):
    import mimetypes
    mime, _ = mimetypes.guess_type(path)
    return mime


class FileRequestHandler(http.server.SimpleHTTPRequestHandler):

    server_version = "PyServeX/4.0"

    # Class-level references wired up in server.run()
    auth = None            # auth.AuthManager
    chunk_mgr = None       # chunked_upload.ChunkedUploadManager
    ephemeral_mgr = None   # ephemeral.EphemeralLinkManager
    rate_limiter = None    # throttling.RateLimiter | None
    stats = None           # dashboard.StatsHub
    signaling = None       # webrtc_signaling.SignalingHub
    mcp = None             # mcp_server.McpBridge
    access_logger = None   # access_logger.AccessLogger | None
    events = None          # events.EventBus | None
    search = None          # search_index.SearchIndex | None
    trash = None           # trash.TrashManager | None
    auth_enabled = True
    remote_bridge_enabled = False

    # ------------------------------------------------------------------
    # plumbing
    # ------------------------------------------------------------------
    def translate_path(self, path):
        # Prevent path traversal attacks
        path = posixpath.normpath(urllib.parse.unquote(path))
        rel_path = path.lstrip('/')
        abs_path = os.path.abspath(os.path.join(self.base_dir, rel_path))
        base = os.path.abspath(self.base_dir)
        if abs_path != base and not abs_path.startswith(base + os.sep):
            logging.warning(f"Path traversal attempt detected: {path}")
            return self.base_dir
        return abs_path

    def guess_type(self, path):
        """Force octet-stream for risky extensions (prevents in-browser exec)."""
        ext = os.path.splitext(str(path))[1].lower()
        if ext in RISKY_EXTENSIONS:
            return "application/octet-stream"
        return super().guess_type(path)

    def end_headers(self):
        for k, v in BASE_SECURITY_HEADERS.items():
            self.send_header(k, v)
        super().end_headers()

    def log_access(self, action, file_path=None, file_size=None, duration=None):
        if hasattr(self, 'analytics') and getattr(self, 'config', {}).get('analytics_enabled', True):
            try:
                client_ip = self.client_address[0]
                user_agent = self.headers.get('User-Agent', '')
                self.analytics.log_file_access(
                    file_path or self.path, action, client_ip,
                    user_agent, file_size, duration)
            except Exception:
                pass

    def _log_request_stats(self, status=200):
        if self.stats:
            try:
                self.stats.request(self.command,
                                   urllib.parse.urlparse(self.path).path[:80],
                                   self.client_address[0], status)
            except Exception:
                pass

    def log_request(self, code="-", size="-"):
        """Access-log each completed request; keep the standard quiet log."""
        if self.access_logger:
            try:
                self.access_logger.log_access(
                    self.client_address[0],
                    urllib.parse.urlparse(self.path).path,
                    code, self.command)
            except Exception:
                pass
        super().log_request(code, size)

    def _csrf_ok(self):
        """CSRF defence for state-changing methods: when a browser sends an
        Origin header it must match the Host we saw. Non-browser clients
        (curl, scripts) omit Origin and are unaffected."""
        origin = self.headers.get("Origin")
        if not origin:
            return True
        host = self.headers.get("Host")
        if not host:
            return True
        try:
            return urllib.parse.urlparse(origin).netloc == host
        except ValueError:
            return False

    # ------------------------------------------------------------------
    # authentication gate
    # ------------------------------------------------------------------
    def _bearer_token(self):
        h = self.headers.get("Authorization", "")
        if h.lower().startswith("bearer "):
            return h[7:].strip()
        return None

    def _session_id(self):
        raw = self.headers.get("Cookie")
        if not raw:
            return None
        try:
            jar = http_cookies.SimpleCookie(raw)
            if SESSION_COOKIE in jar:
                return jar[SESSION_COOKIE].value
        except Exception:
            pass
        return None

    def _is_local_client(self):
        if self.auth:
            return self.auth.is_local(self.client_address[0])
        ip = self.client_address[0]
        return ip.startswith(("127.", "192.168.", "10.")) or \
            ip.startswith("172.16.") or ip == "::1"

    def authenticate(self):
        """True when allowed to proceed. Handles local-network bypass."""
        if not self.auth_enabled or self.auth is None:
            return True
        ok, _, _ = self.auth.authenticate_request(
            self.client_address[0],
            bearer_token=self._bearer_token(),
            session_cookie=self._session_id())
        if ok:
            return True
        if self.stats:
            self.stats.count_auth_failure()
        return False

    UNAUTHENTICATED_PATHS = ("/login", "/api/auth/login", "/api/auth/status")

    def _gate(self):
        """Common entry check. Sends response and returns False if blocked."""
        p = urllib.parse.urlparse(self.path).path
        if not self.auth_enabled:
            return True
        if p in self.UNAUTHENTICATED_PATHS:
            return True
        if self._is_local_client():
            return True
        if self.authenticate():
            return True
        is_api = (p.startswith("/api/") or p.startswith("/webrtc/")
                  or p == "/mcp" or p.startswith("/e/")
                  or p.startswith("/raw/"))
        if is_api:
            self.send_json({"status": "error",
                            "message": "authentication required"}, 401)
        else:
            self.serve_login_page()
        return False

    # ------------------------------------------------------------------
    # small helpers
    # ------------------------------------------------------------------
    def send_json(self, obj, code=200, extra_headers=None):
        payload = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra_headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(payload)

    def read_body(self):
        """Return the request body. In POST/DELETE the socket is drained once,
        so a handler that never reads the body cannot RST the connection."""
        if getattr(self, "_body", None) is not None:
            body = self._body
            self._body = None
            return body
        return self._read_body_raw()

    def _read_body_raw(self):
        try:
            length = int(self.headers.get('Content-Length', 0))
        except (TypeError, ValueError):
            length = 0
        if not length:
            return b""
        try:
            return self.rfile.read(length)
        except (ConnectionResetError, BrokenPipeError):
            return b""

    def body_json(self):
        try:
            return json.loads(self.read_body().decode("utf-8"))
        except Exception:
            return {}

    # ------------------------------------------------------------------
    # live events / search / trash / versions
    # ------------------------------------------------------------------
    def _publish(self, event_type, payload=None):
        if self.events:
            self.events.publish(event_type, payload)

    def serve_event_stream(self):
        if not self.events:
            return self.send_json({"status": "error",
                                   "message": "live events disabled"}, 400)
        q = self.events.subscribe()
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache, no-store")
            self.send_header("Connection", "close")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
            last_beat = time.monotonic()
            while True:
                while True:
                    try:
                        etype, payload = q.get_nowait()
                    except queue_module.Empty:
                        break
                    self.wfile.write(events.format_sse(etype, payload))
                    self.wfile.flush()
                if time.monotonic() - last_beat >= 15:
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
                    last_beat = time.monotonic()
                time.sleep(0.5)
        except (BrokenPipeError, ConnectionResetError,
                ConnectionAbortedError, OSError):
            pass
        finally:
            self.events.unsubscribe(q)

    def serve_search(self, q):
        if not self.search:
            return self.send_json({"status": "error",
                                   "message": "search disabled"}, 400)
        results = self.search.search(q, limit=50) if q.strip() else []
        self.send_json({"status": "success",
                        "ready": self.search.ready,
                        "indexed_files": self.search.indexed_files,
                        "count": len(results),
                        "results": results})

    @staticmethod
    def _rel_path_inside(base, raw_path):
        base = os.path.abspath(base)
        raw_path = (raw_path or "").replace("\\", "/")
        rel = raw_path.lstrip("/")
        abs_path = os.path.abspath(os.path.join(base, rel))
        if abs_path != base and not abs_path.startswith(base + os.sep):
            return None
        return os.path.relpath(abs_path, base)

    def _trash_rel(self, raw_path):
        rel = self._rel_path_inside(self.base_dir, raw_path)
        if rel is None or rel == ".":
            return None
        return rel

    def handle_trash_list(self):
        if not self.trash:
            return self.send_json({"status": "error",
                                   "message": "trash disabled"}, 400)
        entries = self.trash.list()
        self.send_json({"status": "success", "count": len(entries),
                        "entries": entries})

    def handle_trash_move(self):
        if not self.trash:
            return self.send_json({"status": "error",
                                   "message": "trash disabled"}, 400)
        data = self.body_json()
        rel = self._trash_rel(data.get("path", ""))
        if rel is None:
            return self.send_json({"status": "error",
                                   "message": "invalid path"}, 400)
        try:
            entry = self.trash.move(rel)
        except FileNotFoundError:
            return self.send_json({"status": "error",
                                   "message": "not found"}, 404)
        self._publish("file", {"path": "/" + rel, "action": "trashed"})
        self.log_access('trash', os.path.join(self.base_dir, rel))
        return self.send_json({"status": "success", **entry})

    def handle_trash_restore(self):
        if not self.trash:
            return self.send_json({"status": "error",
                                   "message": "trash disabled"}, 400)
        data = self.body_json()
        rel = self._trash_rel(data.get("path", ""))
        if rel is None:
            return self.send_json({"status": "error",
                                   "message": "invalid path"}, 400)
        try:
            restored = self.trash.restore(rel)
        except FileNotFoundError:
            return self.send_json({"status": "error",
                                   "message": "entry not found"}, 404)
        self._publish("file", {"path": "/" + restored,
                               "action": "restored"})
        self.log_access('restore', os.path.join(self.base_dir, restored))
        return self.send_json({"status": "success", "path": "/" + restored})

    def handle_trash_empty(self):
        if not self.trash:
            return self.send_json({"status": "error",
                                   "message": "trash disabled"}, 400)
        self.trash.empty()
        self._publish("trash", {"action": "emptied"})
        return self.send_json({"status": "success", "message": "trash emptied"})

    def handle_version_save(self):
        if not self.trash:
            return self.send_json({"status": "error",
                                   "message": "versions disabled"}, 400)
        data = self.body_json()
        rel = self._trash_rel(data.get("path", ""))
        if rel is None:
            return self.send_json({"status": "error",
                                   "message": "invalid path"}, 400)
        try:
            snap = self.trash.save_version(rel)
        except FileNotFoundError:
            return self.send_json({"status": "error",
                                   "message": "not found"}, 404)
        if not snap:
            return self.send_json({"status": "error",
                                   "message": "not a file"}, 400)
        self.log_access('version', os.path.join(self.base_dir, rel))
        return self.send_json({"status": "success", **snap})

    def handle_versions_list(self, raw_path):
        if not self.trash:
            return self.send_json({"status": "error",
                                   "message": "versions disabled"}, 400)
        rel = self._trash_rel(raw_path)
        if rel is None:
            return self.send_json({"status": "error",
                                   "message": "invalid path"}, 400)
        versions = self.trash.list_versions(rel)
        return self.send_json({"status": "success",
                               "count": len(versions), "versions": versions})

    def handle_version_restore(self):
        if not self.trash:
            return self.send_json({"status": "error",
                                   "message": "versions disabled"}, 400)
        data = self.body_json()
        rel = self._trash_rel(data.get("path", ""))
        version = str(data.get("version", ""))
        if rel is None or not version:
            return self.send_json({"status": "error",
                                   "message": "invalid request"}, 400)
        try:
            self.trash.restore_version(rel, version)
        except FileNotFoundError:
            return self.send_json({"status": "error",
                                   "message": "version not found"}, 404)
        self.save_version_snapshot(rel)
        self._publish("file", {"path": "/" + rel, "action": "updated"})
        self.log_access('restore_version', os.path.join(self.base_dir, rel))
        return self.send_json({"status": "success", "path": "/" + rel})

    def save_version_snapshot(self, rel):
        rel = rel.lstrip("/")
        if self.trash:
            try:
                return self.trash.save_version(rel)
            except (OSError, ValueError):
                return None
        return None

    # ------------------------------------------------------------------
    # GET router
    # ------------------------------------------------------------------
    def do_GET(self):
        if not self._gate():
            return
        if self.stats:
            self.stats.connect()
            try:
                self._route_get()
            finally:
                self.stats.disconnect()
                self._log_request_stats()
        else:
            self._route_get()
            self._log_request_stats()

    def _route_get(self):
        parsed = urllib.parse.urlparse(self.path)
        p = parsed.path

        # ---- special pages & apis -----------------------------------
        if p == "/login":
            self.serve_login_page()
            return
        if p == "/api/auth/status":
            local = self._is_local_client()
            self.send_json({"status": "success", "local": local,
                            "authenticated": local or bool(
                                self.auth and (self.auth.validate_session(self._session_id())
                                               or self.auth.validate_api_token(self._bearer_token())))})
            return
        if p == "/api/stats":
            snap = self.stats.snapshot() if self.stats else {}
            links = self.ephemeral_mgr.list_links() if self.ephemeral_mgr else []
            self.send_json({"status": "success", "stats": snap, "ephemeral": links})
            return
        if p == "/api/tokens":
            if self.auth is None:
                return self.send_json({"status": "error", "message": "auth disabled"}, 400)
            self.send_json({"status": "success",
                            "tokens": self.auth.list_api_tokens()})
            return
        if p == "/api/sftp/info":
            info = getattr(self.server, "sftp_info", None) or {}
            ips = set()
            try:
                for cand in socket.getaddrinfo(socket.gethostname(), None,
                                               socket.AF_INET):
                    ip = cand[4][0]
                    if not ip.startswith("127."):
                        ips.add(ip)
            except OSError:
                pass
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("10.255.255.255", 1))
                ips.add(s.getsockname()[0])
                s.close()
            except OSError:
                pass
            usernames = list(getattr(self.auth, "users", {}).keys()) \
                if self.auth else []
            self.send_json({"status": "success",
                            "enabled": bool(info.get("enabled")),
                            "port": info.get("port", 2222),
                            "hosts": sorted(ips),
                            "usernames": usernames,
                            "keys_file": "~/.pyservx_authorized_keys"})
            return
        if p == "/api/tunnel":
            tun = getattr(self.server, "tunnel_info", None) or {}
            return self.send_json({"status": "success",
                                   "active": bool(tun.get("url")),
                                   "provider": tun.get("provider", ""),
                                   "url": tun.get("url", "")})
        if p == "/api/events":
            return self.serve_event_stream()
        if p == "/api/search":
            qs = urllib.parse.parse_qs(parsed.query)
            return self.serve_search(qs.get("q", [""])[0])
        if p == "/api/trash/list":
            return self.handle_trash_list()
        if p == "/api/versions/list":
            qs = urllib.parse.parse_qs(parsed.query)
            return self.handle_versions_list(qs.get("path", [""])[0])
        if p == "/api/remote/download":
            return self.serve_remote_download(parsed.query)
        if p.startswith("/api/upload/status"):
            qs = urllib.parse.parse_qs(parsed.query)
            uid = qs.get("upload_id", [""])[0]
            stat = self.chunk_mgr.status(uid) if self.chunk_mgr else None
            if not stat:
                return self.send_json({"status": "error",
                                       "message": "unknown upload_id"}, 404)
            return self.send_json({"status": "success", **stat})
        if p == "/mcp":
            doc = {"jsonrpc": "2.0", "serverInfo":
                   {"name": "pyservx-mcp", "version": "4.0.0"},
                   "transport": "http-post", "endpoint": "/mcp",
                   "tools": [t["name"] for t in mcp_server.TOOL_DEFINITIONS]}
            self.send_json(doc)
            return
        if p == "/p2p":
            self.serve_p2p_page()
            return
        if p == "/trash":
            self.serve_trash_page()
            return
        if p == "/tokens":
            self.serve_tokens_page()
            return
        if p.startswith("/webrtc/poll"):
            qs = urllib.parse.parse_qs(parsed.query)
            room = qs.get("room", [""])[0]
            since = int(qs.get("since", ["0"])[0])
            peer = qs.get("peer", [""])[0]
            msgs, idx = self.signaling.poll(room, since, peer)
            self.send_json({"messages": msgs, "index": idx})
            return
        if p.startswith("/e/"):
            self.serve_ephemeral(p[len("/e/"):])
            return
        if p.endswith('/load_clipboard'):
            self.handle_load_clipboard()
            return
        if p.endswith('/download_folder'):
            self.handle_download_folder()
            return
        if p.endswith('/preview'):
            file_path = self.translate_path(p[:-len('/preview')])
            if os.path.isfile(file_path):
                self.serve_sandbox_preview(file_path)
                self.log_access('preview', file_path, os.path.getsize(file_path))
            else:
                self.send_error(404, "File not found for preview")
            return
        if p.endswith('/edit'):
            file_path = self.translate_path(p[:-len('/edit')])
            if os.path.isfile(file_path):
                self.serve_editor_page(file_path)
                self.log_access('edit', file_path)
            else:
                self.send_error(404, "File not found for editing")
            return
        if p.endswith('/notepad'):
            dir_path = self.translate_path(p[:-len('/notepad')])
            if os.path.isdir(dir_path):
                self.serve_notepad_page(dir_path)
                self.log_access('create_file')
            else:
                self.send_error(404, "Directory not found")
            return
        if p.startswith("/raw/"):
            file_path = self.translate_path(p[len("/raw"):])
            self.serve_raw_sandboxed(file_path)
            return

        # ---- directories ---------------------------------------------
        if os.path.isdir(self.translate_path(p)):
            self.list_directory(self.translate_path(p))
            self.log_access('browse')
            return

        # ---- plain files (range + throttle aware) ---------------------
        fparsed = urllib.parse.urlparse(self.path).path
        path = self.translate_path(fparsed)
        if os.path.isfile(path):
            self.serve_file_with_policy(path)
            return
        self.send_error(404, "File not found")

    # ------------------------------------------------------------------
    # file serving: range requests, throttling, forced-download policy
    # ------------------------------------------------------------------
    def serve_file_with_policy(self, path, force_attachment=False, filename=None):
        ext = os.path.splitext(path)[1].lower()
        risky = ext in RISKY_EXTENSIONS
        mime = self.guess_type(path)
        size = os.path.getsize(path)
        fname = filename or os.path.basename(path)
        quoted = urllib.parse.quote(fname)

        rng = self.headers.get("Range")
        start, end = 0, size - 1
        status = 200
        if rng:
            m = re.match(r"bytes=(\d*)-(\d*)$", rng.strip())
            if m and (m.group(1) or m.group(2)):
                if m.group(1):
                    start = int(m.group(1))
                    end = int(m.group(2)) if m.group(2) else size - 1
                else:  # suffix range
                    start = max(0, size - int(m.group(2)))
                end = min(end, size - 1)
                if start > end or start >= size:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{size}")
                    self.end_headers()
                    return
                status = 206

        try:
            self.send_response(status)
            self.send_header("Content-Type", mime or "application/octet-stream")
            self.send_header("Accept-Ranges", "bytes")
            if status == 206:
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            length = end - start + 1
            self.send_header("Content-Length", str(length))
            if risky or force_attachment:
                self.send_header("Content-Disposition",
                                 f"attachment; filename*=UTF-8''{quoted}")
            self.end_headers()

            with open(path, "rb") as f:
                f.seek(start)
                remaining = length
                start_time = time.time()
                while remaining > 0:
                    chunk = f.read(min(64 * 1024, remaining))
                    if not chunk:
                        break
                    if self.rate_limiter:
                        self.rate_limiter.consume(len(chunk))
                    self.wfile.write(chunk)
                    if self.stats:
                        self.stats.transfer("send", len(chunk))
                    remaining -= len(chunk)
                duration = max(time.time() - start_time, 1e-6)

            self.log_access('download', path, size, duration)
            if self.stats:
                self.stats.count_download()
            speed = length / duration
            logging.info("Sent %s (%s) in %.2fs (%s/s)",
                         fname, file_operations.format_size(size),
                         duration, file_operations.format_size(speed))
        except (BrokenPipeError, ConnectionResetError):
            logging.debug("Client aborted download: %s", fname)

    # ------------------------------------------------------------------
    # sandboxed preview & raw
    # ------------------------------------------------------------------
    def serve_raw_sandboxed(self, file_path):
        """Raw bytes inside strict sandbox; used from <iframe sandbox>. """
        if not os.path.isfile(file_path):
            return self.send_error(404, "Not found")
        ext = os.path.splitext(file_path)[1].lower()
        mime = guess_safe_mime(file_path) or "application/octet-stream"
        if ext in RISKY_EXTENSIONS:
            mime = "application/octet-stream"
        inline_ok = mime and (mime.startswith(SAFE_INLINE_MIMES_PREFIX)
                              or mime == "application/pdf")
        size = os.path.getsize(file_path)
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Security-Policy", RAW_SANDBOX_CSP)
        if not inline_ok:
            q = urllib.parse.quote(os.path.basename(file_path))
            self.send_header("Content-Disposition",
                             f"attachment; filename*=UTF-8''{q}")
        self.send_header("Content-Length", str(size))
        self.end_headers()
        with open(file_path, "rb") as f:
            shutil.copyfileobj(f, self.wfile, 64 * 1024)

    def serve_sandbox_preview(self, file_path):
        """Preview wrapper: everything risky is confined to sandboxed iframe."""
        import html as html_mod
        filename = os.path.basename(file_path)
        ext = os.path.splitext(filename)[1].lower()
        rel = '/' + os.path.relpath(file_path, self.base_dir).replace('\\', '/')
        raw_url = '/raw' + urllib.parse.quote(rel)

        if ext in ('.html', '.htm', '.xhtml', '.svg', '.svgz', '.pdf'):
            inner = (f'<div class="warn">⚠ Active content is sandboxed '
                     f'(scripts disabled).</div>'
                     f'<iframe class="framebox" sandbox src="{html_mod.escape(raw_url)}"></iframe>')
            note = "sandboxed"
        elif (guess_safe_mime(file_path) or "").startswith(SAFE_INLINE_MIMES_PREFIX):
            mime = guess_safe_mime(file_path)
            if mime.startswith("image/"):
                inner = (f'<img src="{html_mod.escape(raw_url)}" alt="{html_mod.escape(filename)}" '
                         f'style="max-width:100%;max-height:78vh;border-radius:var(--radius-btn);'
                         f'box-shadow:var(--glass-shadow)">')
            elif mime.startswith("video/"):
                inner = (f'<video controls src="{html_mod.escape(raw_url)}" '
                         f'style="max-height:70vh;border-radius:var(--radius-btn);'
                         f'box-shadow:var(--glass-shadow)"></video>')
            elif mime.startswith("audio/"):
                inner = f'<audio controls src="{html_mod.escape(raw_url)}"></audio>'
            else:
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as fh:
                        content = fh.read(10000)
                    inner = (f'<div class="codebox"><pre>{html_mod.escape(content)}'
                             f'{"\\n… truncated" if len(content) >= 10000 else ""}</pre></div>')
                except OSError:
                    inner = "<p>Unable to read file.</p>"
            note = "safe"
        else:
            inner = (f'<p>This type cannot be previewed safely.</p>'
                     f'<a class="glass-btn-accent" href="{html_mod.escape(raw_url)}" download>'
                     f'⬇ Download</a>')
            note = "download-only"

        body = f"""
<div class="preview-wrap" id="lgHero">
 <h1>🔍 Sandbox Preview <span class="badge">{note}</span></h1>
 <p class="preview-name">{html_mod.escape(filename)}</p>
 <div class="bar">
  <a class="glass-btn" href="{html_mod.escape(rel)}" download>⬇ Download</a>
 </div>
</div>
{inner}"""
        page = ui_shell.shell(
            f"Sandbox Preview: {html_mod.escape(filename)}", body,
            extra_head=("<style>"
                        ".preview-wrap{text-align:center;margin-bottom:14px;position:relative;z-index:1}"
                        ".preview-wrap h1{font-size:1.3rem;font-weight:600;margin:0 0 4px;"
                        "letter-spacing:-.01em}"
                        ".badge{display:inline-block;font-size:.72rem;font-weight:600;"
                        "padding:.15rem .6rem;border-radius:999px;vertical-align:middle;"
                        "margin-left:6px;color:var(--accent-2);border:1px solid var(--glass-border);"
                        "background:rgba(94,92,230,.12)}"
                        ".preview-name{color:var(--text-secondary);margin:0 0 10px;font-size:.9rem}"
                        ".bar{display:flex;gap:8px;justify-content:center;margin-bottom:14px}"
                        ".warn{color:var(--warning);border:1px dashed var(--glass-border);"
                        "padding:6px 10px;border-radius:var(--radius-btn);margin-bottom:10px;"
                        "text-align:center;background:rgba(255,159,10,.08)}"
                        ".framebox{width:100%;height:75vh;border:none;"
                        "border-radius:var(--radius-btn);background:rgba(0,0,0,.35)}"
                        ".codebox{max-height:72vh;overflow:auto;padding:12px;text-align:left;"
                        "border-radius:var(--radius-btn);background:rgba(120,120,128,.08);"
                        "border:1px solid var(--glass-border)}"
                        "</style>"))

        encoded = page.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Security-Policy", PREVIEW_CSP)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    # ------------------------------------------------------------------
    # ephemeral links
    # ------------------------------------------------------------------
    def serve_ephemeral(self, token):
        entry = self.ephemeral_mgr.resolve(token) if self.ephemeral_mgr else None
        if not entry:
            return self.send_json({"status": "error",
                                   "message": "link expired or unknown"}, 410)
        try:
            self.serve_file_with_policy(entry["path"], force_attachment=True)
        finally:
            self.ephemeral_mgr.finalize(token)

    # ------------------------------------------------------------------
    # POST router
    # ------------------------------------------------------------------
    def do_POST(self):
        if not self._gate():
            return
        self._body = self._read_body_raw()
        if not self._csrf_ok():
            return self.send_json({"status": "error",
                                   "message": "cross-origin request blocked"}, 403)
        parsed = urllib.parse.urlparse(self.path)
        p = parsed.path

        if p == "/api/auth/login":
            return self.handle_login()
        if p == "/api/auth/logout":
            sid = self._session_id()
            if sid and self.auth:
                self.auth.destroy_session(sid)
            self.send_json({"status": "success", "message": "logged out"},
                           extra_headers={"Set-Cookie":
                                          f"{SESSION_COOKIE}=; Max-Age=0; Path=/; HttpOnly"})
            return
        if p == "/api/tokens":
            return self.handle_token_create()
        if p == "/api/remote/connect":
            return self.handle_remote_connect()
        if p == "/api/remote/list":
            return self.handle_remote_list()
        if p == "/api/remote/close":
            return self.handle_remote_close()
        if p == "/api/ephemeral/create":
            return self.handle_ephemeral_create()
        if p == "/api/config/speed":
            return self.handle_speed_config()
        if p == "/api/upload/init":
            return self.handle_upload_init()
        if p == "/api/upload/chunk":
            return self.handle_upload_chunk()
        if p == "/api/upload/complete":
            return self.handle_upload_complete()
        if p == "/api/upload/folder":
            return self.handle_folder_upload()
        if p == "/api/remote/upload":
            return self.handle_remote_upload()
        if p == "/api/stats/ping":
            if self.stats:
                self.stats.count_p2p()
            return self.send_json({"status": "success"})
        if p == "/api/scan":
            return self.handle_scan()
        if p == "/mcp":
            body = self.read_body()
            resp = self.mcp.handle_request(body) if self.mcp else \
                {"jsonrpc": "2.0", "id": None,
                 "error": {"code": -32603, "message": "MCP unavailable"}}
            if resp is None:
                self.send_response(204)
                self.end_headers()
                return
            return self.send_json(resp)
        if p == "/webrtc/signal":
            d = self.body_json()
            try:
                seq = self.signaling.post(d.get("room", ""),
                                          d.get("from", ""),
                                          d.get("type", ""),
                                          d.get("data"),
                                          client_host=self.client_address[0])
            except Exception as e:
                status = getattr(e, "status", 400)
                return self.send_json({"status": "error",
                                       "message": str(e)}, status)
            return self.send_json({"status": "success", "seq": seq})
        if p == "/api/stats/clear":
            if self.stats:
                with self.stats.lock:
                    self.stats.events.clear()
            return self.send_json({"status": "success"})
        if p == "/api/trash/move":
            return self.handle_trash_move()
        if p == "/api/trash/restore":
            return self.handle_trash_restore()
        if p == "/api/trash/empty":
            return self.handle_trash_empty()
        if p == "/api/versions/save":
            return self.handle_version_save()
        if p == "/api/versions/restore":
            return self.handle_version_restore()
        if '/save_clipboard' in p:
            return self.handle_save_clipboard()
        if p.endswith('/create_file'):
            return self.handle_create_file()
        if p.endswith('/save_file'):
            return self.handle_save_file()
        if p.endswith('/upload'):
            return self.handle_legacy_upload()
        self.send_error(405, "Method not allowed")

    # ------------------------------------------------------------------
    # DELETE router
    # ------------------------------------------------------------------
    def do_DELETE(self):
        if not self._gate():
            return
        self._body = self._read_body_raw()
        try:
            parsed = urllib.parse.urlparse(self.path)
            p = parsed.path
            if p == "/api/tokens":
                token = self.body_json().get("token", "")
                ok = self.auth.revoke_api_token(token) if self.auth else False
                return self.send_json({"status": "success" if ok else "error"})
            if p == "/api/upload/abort":
                uid = urllib.parse.parse_qs(parsed.query).get("upload_id", [""])[0]
                return self.send_json(self.chunk_mgr.abort_upload(uid))
            if not self._csrf_ok():
                return self.send_json({"status": "error",
                                       "message": "cross-origin request blocked"}, 403)
            self.send_error(405, "Method not allowed")
        finally:
            self._log_request_stats()

    # ------------------------------------------------------------------
    # auth handlers
    # ------------------------------------------------------------------
    def handle_login(self):
        ip = self.client_address[0]
        if self.auth:
            allowed, retry = self.auth.login_status(ip)
            if not allowed:
                return self.send_json({"status": "error",
                                       "message": "too many attempts; retry in %ss"
                                       % retry}, 429)
        d = self.body_json()
        username = d.get("username", "")
        password = d.get("password", "")
        if not (self.auth and self.auth.verify_login(username, password)):
            if self.stats:
                self.stats.count_auth_failure()
            if self.auth:
                self.auth.record_login_failure(ip)
            return self.send_json({"status": "error",
                                   "message": "invalid credentials"}, 401)
        if self.auth:
            self.auth.reset_login_failures(ip)
        sid = self.auth.create_session(username)
        cookie = (f"{SESSION_COOKIE}={sid}; Path=/; HttpOnly; "
                  f"SameSite=Lax; Max-Age={12 * 3600}")
        self.send_json({"status": "success", "message": f"welcome {username}"},
                       extra_headers={"Set-Cookie": cookie})

    # ------------------------------------------------------------------
    # token management handlers
    # ------------------------------------------------------------------
    # ---- remote SFTP client bridge ---------------------------------------
    def _remote_mgr(self):
        if not self.remote_bridge_enabled:
            return None
        return getattr(self.server, "remote_sftp", None)

    def _remote_unavailable(self):
        """Consistent message when the remote bridge is off/absent."""
        if self.remote_bridge_enabled:
            return self.send_json(
                {"status": "error",
                 "message": "remote bridge unavailable (restart server)"}, 501)
        return self.send_json(
            {"status": "error",
             "message": "remote bridge disabled on this server"}, 403)

    def handle_remote_connect(self):
        mgr = self._remote_mgr()
        if mgr is None:
            return self._remote_unavailable()
        d = self.body_json()
        try:
            info = mgr.connect(d)
        except remote_sftp.RemoteSftpError as e:
            return self.send_json({"status": "error", "message": str(e)}, 400)
        except Exception as e:
            return self.send_json(
                {"status": "error",
                 "message": "connect failed: " + str(e)[:160]}, 400)
        try:
            listing = mgr.list_dir(info["sid"], info["home"])
        except Exception as e:
            mgr.close(info["sid"])
            return self.send_json({"status": "error",
                                   "message": str(e)}, 400)
        return self.send_json({"status": "success", **info,
                               **listing})

    def handle_remote_list(self):
        mgr = self._remote_mgr()
        if mgr is None:
            return self._remote_unavailable()
        d = self.body_json()
        try:
            listing = mgr.list_dir(d.get("sid", ""), d.get("path") or ".")
        except remote_sftp.RemoteSftpError as e:
            return self.send_json({"status": "error",
                                   "message": str(e)}, 404)
        return self.send_json({"status": "success", **listing})

    def handle_remote_close(self):
        mgr = self._remote_mgr()
        if mgr is None:
            return self._remote_unavailable()
        mgr.close(self.body_json().get("sid", ""))
        return self.send_json({"status": "success"})

    def serve_remote_download(self, query):
        from . import remote_sftp as rs
        mgr = self._remote_mgr()
        if mgr is None:
            return self._remote_unavailable()
        qs = urllib.parse.parse_qs(query)
        sid = qs.get("sid", [""])[0]
        path = qs.get("path", [""])[0]
        try:
            fh, size, abspath = mgr.open_download(sid, path)
        except rs.RemoteSftpError as e:
            return self.send_json({"status": "error", "message": str(e)}, 404)
        except Exception as e:
            return self.send_json({"status": "error",
                                   "message": "download failed: %s" % e}, 400)
        name = posixpath.basename(abspath.replace("\\", "/")) or "download.bin"
        safe_name = "".join(c for c in name if c not in '\r\n"') or "file"
        try:
            start, end = 0, size - 1
            status = 200
            rng = self.headers.get("Range")
            if rng:
                m = re.match(r"bytes=(\d*)-(\d*)$", rng.strip())
                if m and (m.group(1) or m.group(2)):
                    if m.group(1):
                        start = int(m.group(1))
                        end = int(m.group(2)) if m.group(2) else size - 1
                    else:
                        start = max(0, size - int(m.group(2)))
                    end = min(end, size - 1)
                    if start > end or start >= size:
                        self.send_response(416)
                        self.send_header("Content-Range", f"bytes */{size}")
                        self.end_headers()
                        return
                    status = 206
            if start:
                fh.seek(start)
            self.send_response(status)
            self.send_header("Content-Type", "application/octet-stream")
            disp = 'attachment; filename="%s"' % safe_name
            quoted = urllib.parse.quote(name)
            if quoted != safe_name:
                disp += "; filename*=UTF-8''%s" % quoted
            self.send_header("Content-Disposition", disp)
            self.send_header("Accept-Ranges", "bytes")
            if status == 206:
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            length = end - start + 1
            self.send_header("Content-Length", str(length))
            self.end_headers()
            sent = 0
            remaining = length
            while remaining > 0:
                chunk = fh.read(min(64 * 1024, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                if self.stats:
                    self.stats.transfer("send", len(chunk))
                sent += len(chunk)
                remaining -= len(chunk)
        finally:
            try:
                fh.close()
            except Exception:
                pass

    def handle_remote_upload(self):
        """Stream a raw request body to a remote SFTP path."""
        from . import remote_sftp as rs
        mgr = self._remote_mgr()
        if mgr is None:
            return self._remote_unavailable()
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        sid = qs.get("sid", [""])[0]
        path = qs.get("path", [""])[0]
        if not sid or not path:
            return self.send_json({"status": "error",
                                   "message": "sid and path required"}, 400)
        try:
            fh, abspath, existed = mgr.open_upload(sid, path)
        except rs.RemoteSftpError as e:
            return self.send_json({"status": "error", "message": str(e)}, 404)
        except Exception as e:
            return self.send_json({"status": "error",
                                   "message": "upload failed: %s" % e}, 400)
        try:
            body = self.read_body()
            fh.write(body)
            written = len(body)
        except Exception as e:
            return self.send_json({"status": "error",
                                   "message": "upload interrupted: %s" % e}, 400)
        finally:
            try:
                fh.close()
            except Exception:
                pass
        if self.stats:
            self.stats.transfer("recv", written)
            self.stats.count_upload()
        return self.send_json({"status": "success", "path": abspath,
                               "size": written, "overwritten": existed})

    def handle_scan(self):
        from .security_scanner import FileSecurityScanner
        from .integrity_checker import IntegrityChecker
        out = {}
        try:
            scanner = FileSecurityScanner(self.base_dir)
            scanned = scanner.scan_directory()
            findings = scanner.findings
            out["scanner"] = {
                "scanned": len(scanned),
                "findings": findings,
            }
        except Exception as e:
            out["scanner"] = {"error": str(e)[:200]}
        try:
            checker = IntegrityChecker(
                os.path.expanduser("~/.pyservx_integrity.json"))
            report = checker.check_integrity() if hasattr(checker, "check_integrity") \
                else checker.run() if hasattr(checker, "run") else {"note": "no report"}
            out["integrity"] = report
        except Exception as e:
            out["integrity"] = {"error": str(e)[:200]}
        if self.stats:
            self.stats.count_scan()
        return self.send_json({"status": "success", "report": out,
                               "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                          time.gmtime())})

    def handle_token_create(self):
        d = self.body_json()
        name = str(d.get("name", "api-token"))[:60]
        max_uses = d.get("max_uses")
        expires_hours = d.get("expires_hours")
        token = self.auth.create_api_token(name=name,
                                           max_uses=max_uses,
                                           expires_hours=expires_hours)
        self.log_access('token_create', name)
        self.send_json({"status": "success", "token": token})

    # ------------------------------------------------------------------
    # ephemeral link handler
    # ------------------------------------------------------------------
    def handle_ephemeral_create(self):
        d = self.body_json()
        rel = d.get("path", "")
        ttl = min(int(d.get("ttl_seconds", 3600)), 7 * 24 * 3600)
        max_dl = d.get("max_downloads", 1)
        abs_path = self.translate_path(rel)
        if not os.path.isfile(abs_path):
            return self.send_json({"status": "error",
                                   "message": "file not found"}, 404)
        token = self.ephemeral_mgr.create_link(abs_path, ttl, max_dl)
        host = self.headers.get("Host") or f"localhost:{self.server.server_address[1]}"
        url = f"http://{host}/e/{token}"
        self.log_access('ephemeral_create', abs_path)
        self.send_json({"status": "success", "url": url, "ttl_seconds": ttl,
                        "max_downloads": max_dl})

    # ------------------------------------------------------------------
    # bandwidth config
    # ------------------------------------------------------------------
    def handle_speed_config(self):
        from .throttling import parse_speed
        d = self.body_json()
        try:
            rate = parse_speed(d.get("limit"))
        except ValueError as e:
            return self.send_json({"status": "error", "message": str(e)}, 400)
        if self.rate_limiter:
            self.rate_limiter.set_rate(rate or 10 ** 9)
            shown = f"{rate} bytes/s" if rate else "unlimited"
            return self.send_json({"status": "success", "limit": shown})
        return self.send_json({"status": "success", "limit": "unlimited (no cap)"})

    # ------------------------------------------------------------------
    # chunked upload handlers
    # ------------------------------------------------------------------
    def handle_upload_init(self):
        d = self.body_json()
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        st = self.chunk_mgr.init_upload(
            upload_id=str(d.get("upload_id", ""))[:128],
            filename=d.get("filename", "upload.bin"),
            size=int(d.get("size", 0)),
            chunk_size=int(d.get("chunk_size", 1024 * 1024)),
            rel_dir=qs.get("dir", [""])[0])
        if st is None:
            return self.send_json({"status": "error",
                                   "message": "init failed"}, 400)
        self.send_json({**st, "status": "success"})

    def handle_upload_chunk(self):
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        uid = qs.get("upload_id", [""])[0]
        idx = qs.get("index", ["0"])[0]
        data = self.read_body()
        if self.stats:
            self.stats.transfer("recv", len(data))
        res = self.chunk_mgr.receive_chunk(uid, idx, data)
        code = 200 if "error" not in res else 404
        self.send_json(res, code)

    def handle_upload_complete(self):
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        uid = qs.get("upload_id", [""])[0]
        if self.chunk_mgr:
            target = self.chunk_mgr.target_path(uid)
            if target and os.path.isfile(target):
                self.save_version_snapshot(os.path.relpath(target, self.base_dir))
        res = self.chunk_mgr.complete_upload(uid)
        if res.get("status") == "success":
            if self.stats:
                self.stats.count_upload()
            self.log_access('upload', res["path"])
            self._publish("file", {"path": "/" + res["path"],
                                   "action": "updated"})
        self.send_json(res, 200 if "error" not in res else 400)

    def handle_folder_upload(self):
        """multipart: file parts + optional 'relpath' field (target subfolder)."""
        ctype = self.headers.get('Content-Type', '')
        if not ctype.startswith('multipart/form-data'):
            return self.send_error(400, "Invalid content type")
        boundary = ctype.split('boundary=')[1].encode()
        body = self.read_body()
        if self.stats:
            self.stats.transfer("recv", len(body))

        rel_dir = ""
        saved = []
        for part in body.split(b'--' + boundary):
            if b'name="' not in part:
                continue
            nstart = part.find(b'name="') + 6
            nend = part.find(b'"', nstart)
            field = part[nstart:nend].decode('utf-8', 'ignore')
            cstart = part.find(b'\r\n\r\n')
            if cstart == -1:
                continue
            value = part[cstart + 4:]
            value = re.sub(rb'\r\n--' + re.escape(boundary) + rb'--\r\n$', b'', value)
            value = value.rstrip(b'\r\n') if field != 'file' else value
            if field == 'relpath':
                rel_dir = value.decode('utf-8', 'ignore').strip().replace('\\', '/')
            elif field == 'file':
                fstart = part.find(b'filename="')
                fend = part.find(b'"', fstart + 10) if fstart != -1 else -1
                if fend == -1:
                    continue
                fname = os.path.basename(part[fstart + 10:fend].decode('utf-8', 'ignore'))
                if fname:
                    saved.append((fname, value))

        if not saved:
            return self.send_error(400, "No file provided")

        target_root = os.path.abspath(self.base_dir)
        if rel_dir:
            clean = os.path.normpath(rel_dir).lstrip('\\/')
            if clean.startswith('..'):
                return self.send_error(400, "invalid relpath")
            target_root = os.path.abspath(os.path.join(target_root, clean))
        base = os.path.abspath(self.base_dir)
        if not target_root.startswith(base + os.sep) and target_root != base:
            return self.send_error(400, "path traversal blocked")
        os.makedirs(target_root, exist_ok=True)

        written = []
        for fname, blob in saved:
            fpath = os.path.join(target_root, fname)
            try:
                if os.path.isfile(fpath):
                    self.save_version_snapshot(os.path.relpath(fpath, base))
                with open(fpath, 'wb') as f:
                    f.write(blob)
                written.append(fname)
                if self.stats:
                    self.stats.count_upload()
                    self.stats.transfer("recv", len(blob))
                self.log_access('upload', fpath, len(blob))
                self._publish("file", {"path": "/" + os.path.relpath(fpath, base),
                                       "action": "updated"})
                logging.info("Uploaded %s (%s)", fpath,
                             file_operations.format_size(len(blob)))
            except OSError:
                return self.send_error(500, "Error saving file")

        self.send_json({"status": "success", "files": written,
                        "dir": os.path.relpath(target_root, base) or "/"})

    def handle_legacy_upload(self):
        """Original single-request multipart uploader (kept for compat)."""
        content_type = self.headers.get('Content-Type', '')
        if not content_type.startswith('multipart/form-data'):
            return self.send_error(400, "Invalid content type")

        boundary = content_type.split('boundary=')[1].encode()
        body = self.read_body()
        if self.stats:
            self.stats.transfer("recv", len(body))

        parts = body.split(b'--' + boundary)
        uploaded_files = []
        target_dir = None
        for part in parts:
            if b'filename="' in part:
                start = part.find(b'filename="') + 10
                end = part.find(b'"', start)
                filename = os.path.basename(part[start:end].decode('utf-8'))
                if not filename:
                    continue
                content_start = part.find(b'\r\n\r\n') + 4
                content_end = part.rfind(b'\r\n--' + boundary)
                if content_end == -1:
                    content_end = len(part) - 2
                file_content = part[content_start:content_end]

                target_dir = self.translate_path(
                    urllib.parse.urlparse(self.path).path.replace('/upload', ''))
                if not os.path.isdir(target_dir):
                    return self.send_error(404, "Target directory not found")

                file_path = os.path.join(target_dir, filename)
                try:
                    if os.path.isfile(file_path):
                        self.save_version_snapshot(os.path.relpath(file_path,
                                                                   self.base_dir))
                    file_operations.write_file_in_chunks(file_path, file_content)
                    uploaded_files.append(filename)
                    if self.stats:
                        self.stats.count_upload()
                        self.stats.transfer("recv", len(file_content))
                    self.log_access('upload', file_path, len(file_content))
                    self._publish("file", {"path": "/" + os.path.relpath(file_path, self.base_dir),
                                           "action": "updated"})
                except OSError:
                    return self.send_error(500, "Error saving file")

        if not uploaded_files:
            return self.send_error(400, "No file provided")

        redirect_url = urllib.parse.urlparse(self.path).path.replace('/upload', '') or '/'
        logging.info(f"Files uploaded: {', '.join(uploaded_files)} -> {redirect_url}")
        self.send_json({"status": "success",
                        "files": uploaded_files,
                        "message": "Files uploaded successfully!"})

    # ------------------------------------------------------------------
    # folder zip download
    # ------------------------------------------------------------------
    def handle_download_folder(self):
        folder_path = self.translate_path(
            urllib.parse.urlparse(self.path).path.replace('/download_folder', ''))
        if os.path.isdir(folder_path):
            zip_file = file_operations.zip_folder(folder_path)
            size = zip_file.getbuffer().nbytes
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition",
                             f"attachment; filename={os.path.basename(folder_path)}.zip")
            self.send_header("Content-Length", str(size))
            self.end_headers()
            shutil.copyfileobj(zip_file, self.wfile)
            self.log_access('download_folder', folder_path)
            if self.stats:
                self.stats.transfer("send", size)
        else:
            self.send_error(404, "Folder not found")

    # ------------------------------------------------------------------
    # clipboard / editor / file-create (existing features preserved)
    # ------------------------------------------------------------------
    def handle_save_clipboard(self):
        try:
            data = json.loads(self.read_body())
            content = data.get('content', '')
            path_key = data.get('path', '/')
            clipboard_dir = os.path.join(self.base_dir, '.pyservx_clipboard')
            os.makedirs(clipboard_dir, exist_ok=True)
            safe_filename = path_key.replace('/', '_').replace('\\', '_').strip('_') or 'root'
            with open(os.path.join(clipboard_dir, f"{safe_filename}.txt"),
                      'w', encoding='utf-8') as f:
                f.write(content)
            self.send_json({"status": "success",
                            "message": "Clipboard saved successfully!"})
        except Exception as e:
            self.send_json({"status": "error", "message": str(e)}, 500)

    def handle_load_clipboard(self):
        try:
            query_params = urllib.parse.parse_qs(
                urllib.parse.urlparse(self.path).query)
            path_key = query_params.get('path', ['/'])[0]
            clipboard_dir = os.path.join(self.base_dir, '.pyservx_clipboard')
            safe_filename = path_key.replace('/', '_').replace('\\', '_').strip('_') or 'root'
            clipboard_file = os.path.join(clipboard_dir, f"{safe_filename}.txt")
            content = ""
            mtime = 0
            if os.path.exists(clipboard_file):
                with open(clipboard_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                mtime = os.path.getmtime(clipboard_file)
            self.send_json({"status": "success", "content": content,
                            "mtime": mtime})
        except Exception as e:
            self.send_json({"status": "error", "message": str(e)}, 500)

    def handle_create_file(self):
        data = self.body_json()
        filename = os.path.basename(data.get('filename', '').strip())
        content = data.get('content', '')
        if not filename:
            return self.send_json({"status": "error",
                                   "message": "Filename is required"}, 400)
        target_dir = self.translate_path(
            urllib.parse.urlparse(self.path).path.replace('/create_file', ''))
        if not os.path.isdir(target_dir):
            return self.send_error(404, "Target directory not found")
        try:
            with open(os.path.join(target_dir, filename), 'w',
                      encoding='utf-8') as f:
                f.write(content)
            full = os.path.join(target_dir, filename)
            self.log_access('create_file', full)
            self._publish("file", {"path": "/" + os.path.relpath(full, self.base_dir),
                                   "action": "created"})
            self.send_json({"status": "success",
                            "message": f"File '{filename}' created successfully!"})
        except OSError as e:
            self.send_json({"status": "error", "message": str(e)}, 500)

    def handle_save_file(self):
        data = self.body_json()
        content = data.get('content', '')
        file_path = self.translate_path(
            urllib.parse.urlparse(self.path).path.replace('/save_file', ''))
        try:
            if os.path.isfile(file_path):
                self.save_version_snapshot(os.path.relpath(file_path, self.base_dir))
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            self.log_access('save', file_path)
            self._publish("file",
                          {"path": "/" + os.path.relpath(file_path, self.base_dir),
                           "action": "updated"})
            self.send_json({"status": "success",
                            "message": f"File '{os.path.basename(file_path)}' saved!"})
        except OSError as e:
            self.send_json({"status": "error", "message": str(e)}, 500)

    # ------------------------------------------------------------------
    # MKCOL (folder creation)
    # ------------------------------------------------------------------
    def do_MKCOL(self):
        if not self._gate():
            return
        folder_path = self.translate_path(
            urllib.parse.urlparse(self.path).path)
        try:
            if os.path.exists(folder_path):
                return self.send_json({"status": "error",
                                       "message": "Folder already exists"}, 409)
            os.makedirs(folder_path)
            self.log_access('create_folder', folder_path)
            self._publish("file", {"path": "/" + os.path.relpath(folder_path,
                                                                 self.base_dir),
                                   "action": "created"})
            self.send_json({"status": "success",
                            "message": f"Folder '{os.path.basename(folder_path)}'"
                                       f" created successfully!"}, 201)
        except OSError as e:
            self.send_json({"status": "error", "message": str(e)}, 500)

    # ------------------------------------------------------------------
    # directory listing
    # ------------------------------------------------------------------
    def list_directory(self, path):
        html_content = html_generator.list_directory_page(self, path)
        encoded = html_content.encode('utf-8', 'surrogateescape')
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    # ------------------------------------------------------------------
    # generated pages: login / tokens / p2p
    # ------------------------------------------------------------------
    def serve_login_page(self):
        page = html_generator.login_page()
        encoded = page.encode('utf-8')
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def serve_tokens_page(self):
        page = html_generator.tokens_page()
        encoded = page.encode('utf-8')
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def serve_p2p_page(self):
        page = html_generator.p2p_page()
        encoded = page.encode('utf-8')
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def serve_trash_page(self):
        page = html_generator.trash_page()
        encoded = page.encode('utf-8')
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    # ------------------------------------------------------------------
    # editor / notepad pages (kept from v3)
    # ------------------------------------------------------------------
    def serve_notepad_page(self, dir_path):
        return self.serve_editor_page(None, dir_path)

    def serve_editor_page(self, file_path=None, dir_path=None):
        if file_path:
            filename = os.path.basename(file_path)
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except Exception:
                content = ""
            rel_path = os.path.relpath(file_path, self.base_dir)
            save_url = '/' + rel_path.replace('\\', '/') + '/save_file'
            title = f"Edit: {filename}"
        else:
            filename = ""
            content = ""
            rel_path = os.path.relpath(dir_path, self.base_dir)
            save_url = '/' + rel_path.replace('\\', '/') + '/create_file'
            title = "Create New File"

        editor_html = html_generator.editor_page(title, content, save_url,
                                                 include_filename=not file_path)
        encoded = editor_html.encode('utf-8')
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    # quiet default logging; dashboard handles visibility
    def log_message(self, fmt, *args):
        logging.debug("%s - %s", self.client_address[0], fmt % args)
