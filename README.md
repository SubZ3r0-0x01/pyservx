# PyServeX v4.0.0

A secure, pure-stdlib Python HTTP(S) file server with resumable chunked
uploads, P2P WebRTC transfers, ephemeral links, token auth, an MCP bridge,
SSH/SFTP access, and a live terminal dashboard.

## Features

- **HTTP file serving** — streaming downloads with `Range`/resume support and
  optional global bandwidth throttling (`--limit-speed 2M`)
- **Resumable chunked uploads** — `>8 MB` files upload in 1 MiB chunks via
  `/api/upload/init → chunk → complete`; a stalled upload resumes by re-running
  `init` (missing indexes come back in the status payload)
- **P2P WebRTC transfers** — file bytes go device-to-device over an encrypted
  data channel; the server only relays SDP/ICE through `/webrtc/signal` +
  `/webrtc/poll` (room UI at `/p2p`)
- **Ephemeral links** — self-destructing `/e/<token>` downloads with TTL and
  max-download counts
- **Auth** — local-network clients are never asked to log in; remote clients
  use a session cookie or `Authorization: Bearer <token>` (SQLite token store).
  Failed logins are rate-limited per-IP (5 attempts → 5-minute lockout)
- **MCP bridge** — `POST /mcp` exposes `list_files` / `read_file` /
  `write_file` / `upload_file` / `search_files` / `server_info` over JSON-RPC 2.0
- **SSH/SFTP** — optional inbound server jail (`--ssh`, port 2222, paramiko)
- **Remote SFTP bridge** — optional outbound snap-in (`--remote-bridge`) that
  browses/downloads/uploads files on another host from the web UI
- **Tunnels** — `--tunnel` publishes a public HTTPS link via
  tailscale funnel → cloudflared → ngrok, with a watchdog that restarts the
  provider if the process dies
- **Hardening** — CSRF rejection via Origin/Host match, risky files sandboxed
  (`/raw` iframe CSP), security headers on every response, magic-byte +
  extension scanning (`/api/scan` + integrity checks), JSONL access log with
  rotation (`~/.pyservx_logs/`)

## Quick start

```bash
pip install .                 # or: pip install pyservx[ssh,dashboard]
pyservx --port 8088
# open http://<this-machine-ip>:8088
```

Useful flags:

```bash
pyservx --ssh               # also expose SFTP on :2222 (needs paramiko)
pyservx --tunnel            # public share link (needs cloudflared/ngrok/tailscale)
pyservx --remote-bridge     # enable server-side remote SFTP browsing (OFF by default)
pyservx --limit-speed 2M    # cap download throughput
pyservx --dashboard         # rich live stats TUI
pyservx --no-auth           # disable auth entirely (LAN demos only)
pyservx --username admin --password "change-me"   # set the admin login
```

## Authentication model

Clients on the local network (RFC1918 / loopback / link-local) bypass the
login gate. Everything else must present a session cookie or a bearer token
(`/tokens` page). This keeps LAN use frictionless while any remote client —
including a tunneled public URL — is protected by default.

## Endpoints

| Path | Purpose |
|---|---|
| `/` | directory listing |
| `/login`, `/tokens` | auth pages |
| `/p2p` | WebRTC peer-to-peer file transfer UI |
| `/notepad`, `<file>/edit` | create / edit text files |
| `/api/stats`, `/api/stats/ping` | live counters |
| `/api/scan` | security scanner + integrity report |
| `/api/upload/*` | chunked upload lifecycle |
| `/api/remote/*` | remote SFTP bridge (only when `--remote-bridge`) |
| `/api/ephemeral/*` | one-time download links |
| `/api/tokens` | bearer-token lifecycle |
| `/e/<token>` | ephemeral download |
| `/webrtc/signal`, `/webrtc/poll` | P2P signaling |
| `/mcp` | MCP JSON-RPC tool bridge |

## Tests

```bash
python -m pytest tests -q                        # 39+ unit tests
python -m pytest tests/integration_smoke.py -q   # boots a real server (53 checks)
```

## Docs

- `AGENTS.md` — architecture map and the invariants agents must not break
- `CONTRIBUTING.md` — PR workflow
- `VAPT_INTEGRATION.md` — vulnerability-assessment hooks (scan → fix → verify)