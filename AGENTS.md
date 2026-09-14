# AGENTS.md ÔÇö PyServeX

Instructions for AI coding agents (Claude, Cursor, Copilot, ÔÇª) working in this
repository. Read this before generating patches; it prevents most wrong-code
mistakes seen in this project.

## Project overview

PyServeX is a **pure-stdlib Python HTTP(S) file server** with optional extras
(`paramiko` for SSH/SFTP, `rich` for the dashboard). It shares one folder
(`~/Downloads/PyServeX-Shared` by default) over:

| Surface | Where |
|---|---|
| Web UI + REST | `http://0.0.0.0:8088` (`--port`) |
| SFTP/SSH | port 2222 when started with `--ssh` (`pyservx/ssh_server.py`) |
| MCP JSON-RPC | `POST /mcp` (`pyservx/mcp_server.py`) |
| P2P WebRTC signaling | `/webrtc/signal`, `/webrtc/poll`, UI at `/p2p` |

## Architecture (module map)

```
pyservx/
Ôö£ÔöÇÔöÇ server.py            # entry point, CLI, wires all managers into the handler
Ôö£ÔöÇÔöÇ request_handler.py   # http.server handler: routing, auth gate, uploads,
Ôöé                        # downloads (Range+throttle), previews, security headers
Ôö£ÔöÇÔöÇ html_generator.py    # ALL HTML/JS/CSS pages are Python f-string templates here:
Ôöé                        # directory listing, login, tokens, p2p, editor
Ôö£ÔöÇÔöÇ auth.py              # AuthManager: local-network bypass, sessions (cookie),
Ôöé                        # API tokens (SQLite ~/.pyservx_tokens.db), PBKDF2 users
Ôö£ÔöÇÔöÇ chunked_upload.py    # ChunkedUploadManager: init/chunk/status/complete/abort,
Ôöé                        # staging dir ~/.pyservx_uploads/<upload_id>/chunk_N
Ôö£ÔöÇÔöÇ ephemeral.py         # EphemeralLinkManager: /e/<token> self-destructing links
Ôö£ÔöÇÔöÇ throttling.py        # parse_speed("2M"), global RateLimiter token bucket,
Ôöé                        # ThrottledReader iterator
Ôö£ÔöÇÔöÇ mcp_server.py        # MCP tools: list_files/read_file/write_file/upload_file/
Ôöé                        # search_files/server_info over JSON-RPC 2.0
Ôö£ÔöÇÔöÇ webrtc_signaling.py  # SignalingHub room relay: SDP/ICE polling with room/
Ôöé                        # peer caps, per-peer rate limits, payload bound,
Ôöé                        # and ICE relay-candidate rewrite to the sender's
Ôöé                        # server-observed address
Ôö£ÔöÇÔöÇ ssh_server.py        # paramiko SFTP server jailing users to base_dir;
Ôöé                        # passwords from auth store, keys from ~/.pyservx_authorized_keys
Ôö£ÔöÇÔöÇ dashboard.py         # StatsHub counters + rich TUI (--dashboard)
Ôö£ÔöÇÔöÇ file_operations.py   # zip_folder, chunked read/write, hashing helpers
Ôö£ÔöÇÔöÇ tunnel.py            # TunnelManager: tailscale funnel ÔåÆ cloudflared ÔåÆ ngrok
Ôöé                        # with an in-thread watchdog that drops the URL and
Ôöé                        # retries the provider chain if the process dies
Ôö£ÔöÇÔöÇ remote_sftp.py       # RemoteSftpManager: outbound paramiko bridge for the
Ôöé                        # web UI (browse/download/upload); sessions are
Ôöé                        # in-memory + idle-reaped (SESSION_IDLE_TTL)
Ôö£ÔöÇÔöÇ access_logger.py     # AccessLogger: JSONL access trail with size-based
Ôöé                        # rotation (10 MiB), default ~/.pyservx_logs/
Ôö£ÔöÇÔöÇ events.py            # EventBus publish/subscribe + SSE formatting; live
Ôöé                        # events stream at GET /api/events (heartbeat 15 s)
Ôö£ÔöÇÔöÇ search_index.py      # bg full-share index; GET /api/search?q= instant hits
Ôö£ÔöÇÔöÇ trash.py             # TrashManager + version history; /api/trash/* and
Ôöé                        # /api/versions/* (data dirs ~/.pyservx_trash,
Ôöé                        # ~/.pyservx_versions)
Ôö£ÔöÇÔöÇ security_scanner.py  # magic-byte (bundled) + optional python-magic scanner
ÔööÔöÇÔöÇ integrity_checker.py # SHA-256 baseline integrity checks
```

## Critical rules (do not break)

1. **Auth invariant**: clients on the local network (RFC1918/loopback/link-local)
   must *never* be asked to log in. Remote clients need a session cookie or
   `Authorization: Bearer <token>`. The single gate is
   `FileRequestHandler._gate()` ÔåÆ `AuthManager.authenticate_request()`.
   Any new route must pass through `_gate()` or be added to
   `UNAUTHENTICATED_PATHS` deliberately.
2. **Path traversal**: every user-supplied path goes through
   `translate_path()` (HTTP) or `McpBridge.resolve()` (MCP) or
   `_PyServeXSftp._map()` (SFTP). Never join raw user input with `base_dir`.
3. **Risky files never execute**: `.html/.svg/.pdf/ÔÇª` are served inside a
   sandboxed `<iframe>` from `/raw/...` which sets
   `Content-Security-Policy: default-src 'none'; sandbox`. Executable/scripty
   extensions get `Content-Type: application/octet-stream` +
   `Content-Disposition: attachment` via `guess_type()` override and
   `serve_file_with_policy()`.
4. **Security headers** are appended for every response in `end_headers()`
   (`nosniff`, `SAMEORIGIN`, `Referrer-Policy`). Don't remove them.
5. **Threading**: server is `ThreadingTCPServer`; every shared structure
   (`RateLimiter`, `StatsHub`, `SignalingHub`, upload session dicts) must stay
   lock-protected.
6. **Frontend has no build step**: pages live as templates in
   `html_generator.py`. The LAN is served over plain HTTP, so `crypto.subtle`
   is unavailable ÔÇö file identity hashes use the FNV-1a fallback in JS
   (`fileIdOf`). Keep both branches working.
7. **Chunk protocol**: client picks `upload_id = sha256/fnv(name:size:mtime)`,
   POSTs `/api/upload/init`, then chunks of exactly the negotiated
   `chunk_size` to `/api/upload/chunk?upload_id&index`, finally
   `/api/upload/complete`. Resume = re-run init; missing indexes come back in
   the status payload. Do not change these field names casually ÔÇö the browser
   code in `_DIRECTORY_TEMPLATE` mirrors them.
8. **CSRF**: state-changing methods (POST/DELETE/ÔÇª) reject requests whose
   `Origin` header host does not match the `Host` header. Non-browser clients
   (`curl`, scripts) omit `Origin` and are unaffected. Do not widen this.
9. **Login brute force**: failed logins are counted per-IP; after
   `LOGIN_MAX_ATTEMPTS` (5) the IP is locked for `LOGIN_LOCKOUT_SECONDS` (300).
   Use `auth.login_status()` / `record_login_failure()` /
   `reset_login_failures()` in any new auth path.
10. **Remote SFTP bridge defaults OFF**: `--remote-bridge` flips
    `Handler.remote_bridge_enabled`. Every `/api/remote/*` handler must go
    through `_remote_mgr()` so a disabled bridge answers 403, never an open door.
11. **Sessions carry a CSRF nonce**: `AuthManager.create_session()` stores
    `csrf` alongside the user; read it with `session_csrf(sid)` if a route ever
    moves off the Origin check.
12. **Live events are close-delimited**: `GET /api/events` streams SSE frames
    with no `Content-Length`. `http.client.read(amt)` blocks until `amt` bytes
    OR EOF arrive ÔÇö tests/clients must read small chunks (`read(1)`/`readline`),
    not a big buffer. Browser `EventSource` handles this natively.
13. **Trash restore / version restore must jail paths**: `/api/trash/*` and
    `/api/versions/*` resolve relative paths through `_rel_path_inside()`
    (never `os.path.join(base, user_input)`), matching the `translate_path()`
    traversal rule.
14. **Search skips system dirs**: `search_index` never walks `.thumbnails`,
    `.psx_events`, `.git`, `__pycache__`, `.psx_versions`. Keep that list in
    sync if new dot-dirs appear alongside the shared folder.

## Conventions

- Python ÔëÑ3.8, stdlib-first; optional deps only behind try/import with a
  graceful message (`ssh_server.py`, `dashboard.py`).
- No comments unless explaining non-obvious security/threading decisions.
- Version lives in two places: `pyproject.toml` and `pyservx/__init__.py`.
- CLI flags are defined once in `server.main()`; runtime config persists to
  `~/.pyservx_config.json`.
- Maintainers-style lifecycle: every manager that owns threads/resources gets
  a `shutdown()` (and stale-state loop) called from `server._shutdown()` on
  SIGINT/KeyboardInterrupt ÔÇö keep the teardown list in that helper in sync.

## Testing & verification

```bash
python -m pytest tests -q          # unit tests (39+)
python -m pytest tests/integration_smoke.py -q   # boots a real server, 53 checks
python -m pyservx.server --help    # CLI smoke test
python -m pyservx.server --port 8099 --no-auth --no-qr &
curl -s localhost:8099/api/stats | head -c 200   # expect {"status": "success"...
```

Manual checks after touching uploads/downloads: upload >8 MB file (chunked
path), refresh mid-upload and retry (resume), drag a folder onto the page,
create an ephemeral link and open it twice (second must 410), fetch `/mcp`
with `tools/list`.

## VAPT hooks

Uploads land in the shared dir only after full assembly (chunk staging keeps
partial data out of the served tree). `security_scanner.FileSecurityScanner`
can be run against the shared folder post-upload; findings feed the same
severity vocabulary used in `VAPT_INTEGRATION.md`.
