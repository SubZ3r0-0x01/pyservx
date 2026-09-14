# Changelog

All notable changes to PyServeX are documented here.

## [4.0.0] - 2026-09-14

### Added
- Authentication: PBKDF2 user store, cookie sessions, SQLite API tokens,
  local-network bypass, per-IP login lockout (5 fails -> 5 min).
- Resumable chunked uploads (1 MiB chunks) with idempotent resume and
  full folder drag-and-drop upload.
- P2P WebRTC file transfers with server-side SDP/ICE signaling relay.
- Ephemeral self-destructing links (`/e/<token>`) with TTL + download caps.
- Full-share instant search (`/api/search`) with background index.
- Trash bin and version history (`/api/trash/*`, `/api/versions/*`).
- Live server-sent event stream (`/api/events`) with auto-refreshing UI.
- MCP JSON-RPC bridge (`/mcp`) for AI coding agents.
- Inbound SSH/SFTP server (paramiko), jailed to the shared folder.
- Outbound remote SFTP bridge (opt-in) for browsing other hosts.
- Public tunnel support: Tailscale Funnel -> cloudflared -> ngrok.
- Optional rich terminal dashboard and rotating JSONL access log.
- Security scanner and SHA-256 integrity checks.
- Liquid Glass UI reskin (dependency-free WebGL2 backdrop, theme picker),
  browser file editor, live clipboard sync.

### Changed
- Directory listing hardened against path-traversal fallthrough.
- Risky file types force-downloaded; previews served in sandboxed iframes.
- Deprecated v3-era docs and changelog removed; product documentation
  rewritten for first-time users.

## [3.0.0]
Prior releases are archived in git history.