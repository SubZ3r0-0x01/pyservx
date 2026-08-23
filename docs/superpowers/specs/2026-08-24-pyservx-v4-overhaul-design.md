# PyServeX v4.0 Overhaul — Design Spec

Status: approved-to-build (user directive: "develop everything, wire it, deal with details later")
Owner defaults below are explicit decisions made in place of further Q&A, per that directive. Flag any to override.

## Ground rules

- Stay stdlib-first (`http.server` + `socketserver.ThreadingTCPServer`). No framework migration — the existing server works; ponytail rung 2 says reuse it, not replace it.
- New third-party deps, justified, nothing else:
  - `paramiko` — SSH/SFTP server (Phase 2) and nothing does this in stdlib.
  - `rich` — CLI dashboard (Phase 6) rendering only.
  - No new dep for auth hashing (`hashlib.pbkdf2_hmac`, stdlib), no new dep for MCP (raw JSON-RPC over the existing handler, stdlib `json`), no new dep for WebRTC signaling (plain HTTP long-poll on the existing server).
- One shared UI shell module (`pyservx/ui_shell.py`) replaces the 3x-duplicated theme CSS/JS currently copy-pasted across `html_generator.py`, and the preview/editor templates in `request_handler.py`. Liquid Glass tokens get defined once. This is a pre-existing DRY problem in the path we're touching for Phase 0 anyway — fixed as part of it, not a separate task.
- All new server-side state (auth users, API tokens, ephemeral links, chunked-upload sessions) lives in small SQLite files under `~/.pyservx_*` next to the existing `~/.pyservx_analytics.db` / `~/.pyservx_config.json`, same pattern already in `server.py`.

## Phase 0 — Liquid Glass UI overhaul

**What changes:** `html_generator.py` (directory listing) and the preview/editor templates in `request_handler.py` move off the flat black/neon-green Tailwind-CDN look onto a Liquid Glass material system, per `apple-design-skill`'s Liquid Glass reference (functional layer vs. content layer separation, blur/opacity tokens, light+dark semantic colors, sparing color emphasis, scroll-edge effects).

**Architecture:**
- `pyservx/ui_shell.py` exports `shell(title, body_html, extra_head="")` — the single `<head>`+CSS-tokens+theme-toggle-JS wrapper. `html_generator.list_directory_page`, and every `generate_*_preview`/`serve_editor_page` in `request_handler.py`, call this instead of inlining their own copy.
- CSS tokens (`:root` custom properties): `--glass-bg`, `--glass-border`, `--glass-blur`, `--text-primary`, `--text-secondary`, `--accent` — light values on `:root`, dark overrides under `prefers-color-scheme: dark` and `[data-theme="dark"]`, matching the existing localStorage theme-toggle behavior (kept, just re-skinned).
- Surfaces (file rows, buttons, modals, the future login screen, token panel, throttle slider, drag-drop zone) become glass panels: `background: var(--glass-bg); backdrop-filter: blur(var(--glass-blur)); border: 1px solid var(--glass-border);`
- Still Tailwind CDN for layout utilities (unchanged dependency) — Liquid Glass is a CSS-token layer on top, not a rewrite of the grid/flex structure.

**Data flow / error handling:** none — pure presentation layer, no new endpoints.

**Testing:** manual pass via `run` skill launching the server and checking directory listing, preview (image/pdf/video/audio/text), editor, in both light and dark, at mobile and desktop widths. No unit tests for HTML string output (ponytail: not worth it for template strings); a smoke test that `ui_shell.shell()` returns non-empty string with both theme tokens present is the one cheap regression check.

## Phase 1 — Access Control Foundation

**Components (`pyservx/auth.py`):**
- Single local account: username + PBKDF2-SHA256 hash (stdlib `hashlib.pbkdf2_hmac`, 260k iterations, random salt), stored in `~/.pyservx_config.json` alongside existing config keys. Set via `pyservx --set-password` CLI flag on first run (auto-prompted if unset and non-LAN binding requested).
- Session cookie: signed opaque token (`hmac.new(secret, session_id, sha256)`), issued on `POST /login`, checked on every request via a guard called at the top of `do_GET`/`do_POST` in `FileRequestHandler`.
- **LAN-bypass rule:** `is_local_request(client_ip)` uses stdlib `ipaddress` to check `client_ip` is loopback or in a private range (RFC1918 + RFC4193). If true, the auth guard short-circuits to allowed — no cookie, no prompt — and access is still logged via existing `log_access`. Config flag `require_auth_on_lan: false` (default) governs this; settable to `true` to force auth everywhere, in case the network is untrusted despite being "local" (e.g., shared coworking wifi).
- **API tokens:** `secrets.token_hex(32)`, stored hashed (sha256) in a `tokens` table in a new `~/.pyservx_tokens.db` SQLite file, with a label and created_at. Checked via `Authorization: Bearer <token>` header — this is what MCP (Phase 5) and CLI/agent callers use instead of the cookie flow. Token management gets a small glass panel UI (create/list/revoke) built on the Phase 0 shell.
- **Ephemeral URLs** (`pyservx/ephemeral.py`): `ephemeral` table in the same tokens DB — `token, file_path, expires_at, max_uses, uses`. `create_ephemeral_link(path, ttl_seconds, max_uses=1)` returns a `/e/<token>` URL. Validated and consumed (uses incremented, row deleted once expired or exhausted) lazily at request time — no background sweep thread, ponytail: a cron/thread for this is overkill at file-server scale, add one only if the table measurably grows unbounded. Generation gets a button next to each file (glass panel) issuing a single-use, 24h-default link.

**Error handling:** unauthenticated non-LAN request → glass-styled login page (302 redirect preserving target path). Expired/exhausted ephemeral token → 410 Gone. Bad/missing bearer token on `/mcp` or token-gated API → 401 JSON error.

**Testing:** unit tests for `is_local_request` (loopback/private/public IPs), PBKDF2 round-trip, ephemeral token expiry/max-uses logic — these are pure functions, cheap to test directly without spinning up the HTTP server.

## Phase 2 — Remote SSH File Access

**Decision (default, since ambiguity wasn't resolved before the "build everything" directive):** Option (a) — PyServeX **runs** an SFTP server. Anyone with an SSH/SFTP client provides the host's IP, a username, and a password-or-key to connect and browse the same `base_dir` the web UI serves. Reasoning: it's the natural reading of "we can connect via ssh... provide ip, username, password or key to connect and access file," it reuses a well-trodden protocol instead of building a bespoke remote-browsing web UI (ponytail rung 4: native/standard protocol over custom), and every OS already ships an SFTP client.
- If this is wrong and you actually meant "pyservx reaches out to *another* machine over SSH and shows its files in our browser UI" — that's a different, larger feature (an SSH-client-backed virtual filesystem mounted into the web UI); say so and it becomes its own Phase 2b.

**Components (`pyservx/ssh_server.py`):**
- `paramiko.SFTPServer` subclass rooted at `base_dir`, reusing `FileRequestHandler.translate_path`'s traversal-prevention logic (extracted to a shared `pyservx/path_guard.py` so both HTTP and SFTP enforce identical confinement — one guard, both callers, per the root-cause-fix rule).
- Auth: same account as Phase 1's web login (password) plus optional authorized-keys file (`~/.pyservx_authorized_keys`, standard OpenSSH format) for key-based login.
- Started as a daemon thread from `server.run()` when `--ssh-port <port>` is passed (opt-in, off by default — the HTTP server doesn't imply an SSH server exists).
- LAN-bypass does **not** apply to SSH — SSH always requires credentials; the bypass is a convenience for the web UI's browser cookie flow only, not a blanket "skip auth" rule.

**Testing:** integration test using `paramiko.SSHClient` against a locally-started test instance, asserting: correct password logs in, wrong password rejected, path traversal (`../../etc`) blocked, and a file written over SFTP appears via the HTTP listing (proves shared `base_dir`).

## Phase 3 — Transfer & Upload

**One upload pipeline, not two** (chunked-resumable and drag-drop-folder are the same mechanism plus a relative-path field — ponytail: don't build parallel systems):
- Client (`Blob.slice()`) computes an MD5 (via WebCrypto `crypto.subtle.digest` client-side or a small JS MD5 fallback) as `upload_id`, slices into e.g. 4MB chunks, POSTs each to `/<dir>/upload_chunk` with headers `X-Upload-Id`, `X-Chunk-Index`, `X-Chunk-Total`, `X-Rel-Path` (empty for flat uploads, `sub/dir/file.ext` when dragged in from a folder via `webkitGetAsEntry()` recursion).
- Server (`pyservx/upload_manager.py`) writes each chunk to `.pyservx_uploads/<upload_id>/<index>.part`; on receiving the final chunk, checks all parts present, streams-concatenates into `target_dir/<rel_path>` (creating subdirectories as needed), verifies against the MD5, deletes the temp folder.
- Resume: `GET /<dir>/upload_status?upload_id=X` returns which chunk indices already exist, so a resumed client skips them.
- Existing flat `/upload` endpoint (whole-file multipart) stays as-is for small files / non-JS clients — no breaking change, ponytail: don't rip out a working simple path.

**Bandwidth throttle (`pyservx/throttle.py`):** a generator wrapper around `file_operations.read_file_in_chunks` — computes `sleep_for = chunk_size / limit_bytes_per_sec` and `time.sleep()`s between yields. Applied per-connection in `do_GET`'s download path. CLI flag `--limit-speed 2M` (parsed via a small regex `^\d+[KMG]?$`) sets the default; the directory-listing UI gets a glass slider that POSTs a per-session override stored in the connection's handler instance.

**Testing:** unit test for chunk reassembly + MD5 verification with deliberately out-of-order chunk arrival; unit test for the throttle generator's timing (mock `time.sleep`, assert call count/args, not wall-clock).

## Phase 4 — Security Hardening (sandboxed preview)

- `serve_preview_page` in `request_handler.py`: for `text/html`, `image/svg+xml`, and `application/xhtml+xml`, render inside `<iframe sandbox="allow-same-origin" srcdoc="...">` (no `allow-scripts`) instead of the current direct embed, and send `Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'; img-src 'self'` on that response.
- Any MIME type not in the existing preview allowlist (image/pdf/video/audio/text) is forced to `Content-Disposition: attachment` — never rendered inline, closing the "unknown risky type gets embedded anyway" gap implicit in today's `generate_download_preview` fallback (that fallback already offers download-only, this phase just makes sure html/svg/xhtml don't sneak into the "renderable" branches above it).

**Testing:** request an uploaded `.svg` with an embedded `<script>` through `/preview`, assert response contains the CSP header and the script does not execute (iframe sandbox without `allow-scripts` — assert statically that `allow-scripts` is absent from the sandbox attribute, real execution isn't testable headlessly without a browser).

## Phase 5 — AI-Agent Compatibility

- `/mcp` JSON-RPC 2.0 endpoint (`pyservx/mcp_server.py`) added to `do_POST`, gated by the Phase 1 bearer-token auth (LAN-bypass still applies — an agent running on the same machine/network doesn't need a token either). Exposes three tools: `list_files(path)`, `read_file(path)`, `upload_file(path, content_base64)`, all routed through the existing `translate_path`/`path_guard` confinement.
- `AGENTS.md` at repo root: architecture map (module list + one-line purpose each), the path-traversal/base_dir-confinement invariant, and how the security-scanner hooks (`security_scanner.py`, `integrity_checker.py`) fit the request lifecycle — so an LLM editing this repo doesn't reinvent or bypass them.

**Testing:** JSON-RPC round trip for each of the 3 tools against a temp `base_dir`, plus a path-traversal attempt (`../../../etc/passwd`) asserting a JSON-RPC error, not a leak.

## Phase 6 — CLI Dashboard

- `pyservx watch` subcommand: `rich.live.Live` dashboard reading from a thread-safe `queue.Queue` (or a simple lock-guarded counter dict) that `do_GET`/`do_POST` push events into (connect, download start/progress/done, upload start/done). Terminal-only — HIG/Liquid Glass doesn't apply here; flag if you actually want a browser-based admin dashboard instead, that would live in Phase 0/1's glass UI.

**Testing:** unit test that the event queue receives one entry per simulated request (mock the `Live` render, don't assert terminal pixels).

## Phase 7 — WebRTC P2P Fallback (lowest priority, most complex)

- Signaling reuses the existing HTTP server: `POST /webrtc/offer` and `GET /webrtc/answer?id=` against an in-memory dict (no new dependency, no WebSocket). Client uses Google's public STUN (`stun:stun.l.google.com:19302`). This only activates when the user explicitly toggles "P2P mode" in the UI — it is not a silent fallback, since detecting "server unreachable due to NAT" reliably from the browser is unreliable; an explicit toggle avoids building failure-detection heuristics that don't work.

**Testing:** deferred — this phase is explicitly last and most likely to shift; a design nod now, detailed plan when we get there.

## Cross-cutting: `pyservx/path_guard.py`

Extracted from `FileRequestHandler.translate_path`'s existing traversal-prevention logic so Phase 1 (login-redirect target), Phase 2 (SFTP), and Phase 5 (MCP tools) all call one function instead of three copies of the same `abspath`/`startswith` check. This is the one piece of "existing code has a problem that affects the work" — today the guard lives inline in the HTTP handler only; every new entry point needs it too, so it moves to a shared module once, not copy-pasted three more times.

## Release

- `pyproject.toml` version → `4.0.0`, add `paramiko` and `rich` to `dependencies`.
- README/CHANGELOG updated per existing "Auto-updated by development automation" convention already in the repo.
