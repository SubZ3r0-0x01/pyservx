# PyServeX

**Share a folder with anyone — on your LAN or anywhere on Earth — from one
pure-Python server.**

PyServeX is a secure, zero-config file-sharing server. Point it at a folder,
and you get an instant web file manager with resumable uploads, peer-to-peer
transfers, one-time links, SFTP access, a public tunnel URL, and even hooks for
AI agents (MCP). Local devices on your network never see a login screen;
everyone outside your network is asked to authenticate first.

One Python script, no databases to install, no account portals, no JavaScript
build step.

---

## What you get

| Capability | What it does | Best for |
|---|---|---|
| **Web file manager** | Stream downloads with `Range`/resume, thumbnails, in-browser previews, folder browsing | Sharing a directory over your LAN |
| **Resumable uploads** | Files of any size upload in 1 MiB chunks; a stalled transfer resumes where it left off | Moving large files across flaky connections |
| **Drag-and-drop folders** | Drop a folder onto the page and the whole tree uploads preserving structure | Backing up a project or photo album |
| **Peer-to-peer transfers** | File bytes travel device-to-device over an encrypted WebRTC channel; the server only relays connection metadata | Big files between two people without hitting your server's bandwidth |
| **One-time links** | Self-destructing `/e/<token>` URLs with a TTL and download count | Sending a file once, then forgetting it |
| **Instant search** | Background index of every filename and text file's contents; type and get hits as you type | Finding a needle in a huge share |
| **Trash + versions** | Deleted files land in a trash bin; edited files keep a version history you can restore | Recovering from mistakes |
| **Live updates** | The page refreshes itself in real time via a server-sent event stream when files change | Watching an upload/folder sync live |
| **SSH / SFTP server** | Access the same folder over SFTP/SCP with standard tools, jailed to the share | Connecting `FileZilla`, `rsync`, or your terminal |
| **Public tunnel** | A public `https://…` link without a public IP (Tailscale Funnel → cloudflared → ngrok) | Sharing with the world from behind NAT |
| **MCP bridge** | A JSON-RPC endpoint (`list_files`, `read_file`, `write_file`, …) for AI coding agents | Letting an agent browse/edit your files |
| **API tokens** | Issue scoped bearer tokens for scripts and integrations | Automating access without a browser login |
| **Web editor & notepad** | Create and edit text files in the browser | Quick edits from any device |

---

## Quick start

You need [Python 3.8+](https://python.org). No database, no Node, no build step.

```bash
pip install pyservx            # or: git clone, then  pip install .
pyservx                        # HTTP server starts on :8088
```

That's it. Open the printed URL (a QR code is shown for phone access):

- Browser URL: **http://\<this-machine-ip\>:8088** (port `--port`; default `8088`)
- Shared folder: **`~/Downloads/PyServeX-Shared`** on Linux/macOS, or `%USERPROFILE%\Downloads\PyServeX-Shared` on Windows (created for you on first run, and changeable — see Configuration).

On your own network you won't be asked to log in. Anyone outside your
network gets the login page — create your admin account on first run with
`--username` / `--password`, or let PyServeX generate a password and print it
at startup (auth is [LAN-only by default](#authentication-model)).

> Python 3.8+ works out of the box. For the optional extras install
> `pip install "pyservx[ssh,dashboard]"` (adds SFTP via *paramiko* and the
> live terminal dashboard via *rich*).

### Start with the more useful flags

```bash
pyservx --username admin --password "change-me"   # pick your own admin login
pyservx --port 9000                               # different HTTP port
pyservx --limit-speed 2M                          # cap every download at 2 MB/s
pyservx --ssh --ssh-port 2222                     # also expose SFTP/SCP
pyservx --tunnel                                  # public https:// link, no public IP
pyservx --remote-bridge                           # browse files on ANOTHER machine
pyservx --dashboard                               # live stats terminal dashboard
pyservx --local-only                              # trust everyone (no logins anywhere)
```

Find the full flag table near the bottom of this page.

---

## How to use it

### Browse and download
Open the root URL to see the shared folder. Click any file to stream it
(partial downloads resume thanks to `Range` support), click images/videos for
in-browser previews, and use the breadcrumbs to navigate.

Risky files (scripts, executables, HTML, PDFs...) never run in your browser —
they open in a sandboxed viewer or download as attachments, and every response
carries hardening headers.

### Upload files
Drag and drop files or whole folders onto the page. Large files are cut into
1 MiB chunks; if the connection drops, refresh and re-select the file and the
upload **resumes** from the missing chunk automatically — no restart, no
corruption.

### Share one file, one time
Every file row has an "ephemeral link" action. It creates an `/e/<token>` URL
that self-destructs after its TTL or download limit. Hand it out once and move
on — the link is dead for good afterward.

### Transfer device-to-device
Choose *Share with QR / P2P* in the UI (`/p2p`). The file bytes flow
**directly between two browsers** on an encrypted WebRTC channel. The server
only brokers the connection — it never holds your file bytes. Great for bypassing
your server's bandwidth.

### Find anything
Use the search box in the header. It queries a background index of every
filename **and** the text contents of readable files, so a search for a
snippet inside a `.md` or `.txt` finds it instantly — even while the index is
still warming up.

### Undo mistakes
- **Trash**: deleted files go to `/trash` (underlying `~/.pyservx_trash`) and
  can be restored from there. Older trash auto-purges.
- **Versions**: edited files keep snapshots (up to three); open the file's
  history and restore any of them from the server's version store.

### Edit files
Any text file gets an *Edit* button that opens the built-in editor; the
notepad page (`/notepad`) gives you a scratch pad. Saved edits are versioned,
so you can always roll back.

### Connect over SSH/SFTP
Start with `--ssh`. Then `sftp://<ip>:2222` works with FileZilla, WinSCP,
`scp`, or `rsync`:

```bash
sftp -P 2222 admin@<this-machine-ip>
# or mounted over sshfs if you like
```

SFTP sessions are **jailed** to the shared folder — users can never walk up to
`/etc` or anything outside the share. Login uses the same user store: a
username + password pair, or an authorized public key
(`~/.pyservx_authorized_keys`).

### Browse another machine (remote bridge)
With `--remote-bridge` you can connect the web UI **out** to a different
machine's SFTP service and browse, download, or upload across the two. This is
a power feature and stays **off by default** so your server is never an open
relay.

### Put it on the public internet
Pass `--tunnel` and PyServeX tries, in order, **Tailscale Funnel**,
**cloudflared**, then **ngrok** — publishing a public `https://…` URL that is
printed to the console and shown in the UI. A watchdog restarts the tunnel
provider if it dies. No public IP, no router config needed. (You need one of
the three tools installed; the URL always requires authentication unless you
choose otherwise.)

### Let an AI agent in (MCP)
PyServeX speaks the **Model Context Protocol** at `POST /mcp`. Point Claude,
Cursor, or any MCP client at it and an agent can `list_files`, `read_file`,
`write_file`, `upload_file`, `search_files`, and query `server_info` against
your share — the same sandboxed paths the web UI uses.

### Automate with tokens
The `/tokens` page issues bearer API tokens (stored in a SQLite database).
Scripts that live outside your network authenticate with:

```bash
curl -H "Authorization: Bearer <token>" http://host:8088/api/stats
```

Failed logins are throttled per IP (5 wrong attempts → 5-minute lockout).

---

## Authentication model

PyServeX is secure **by default** but frictionless **where it matters**:

| Where the client is | What happens |
|---|---|
| On your LAN (RFC1918 / loopback / link-local) | Never asked to log in |
| On an extra network you trust | Add it with `--allowed-networks 10.1.0.0/16` |
| Outside your network (incl. the tunnel URL) | Must present a session cookie or `Authorization: Bearer <token>` |

This means your family and LAN devices open the share instantly, while the
same URL exposed to the internet is protected. `--no-auth` disables login
everywhere (LAN demos only) and `--local-only` keeps auth on but trusts every
client.

## Security posture

- **Auth gate on every route** — no unauthenticated way around it; any new
  feature route must pass the same gate.
- **Path traversal is blocked** at every surface (HTTP, MCP, SFTP) — user input
  is never joined raw onto the share root.
- **Risky files never execute** — scripts/executables become
  `application/octet-stream` attachments; web-y files load inside a sandboxed
  iframe with `default-src 'none'; sandbox`.
- **Hardening headers on every response** — `nosniff`, `SAMEORIGIN`, referrer
  policy, and a locked-down permissions policy.
- **CSRF protection** — any state-changing request whose `Origin` host doesn't
  match the `Host` header is rejected (browser-borne attacks), while simple
  scripts (which send no `Origin`) are unaffected.
- **Login brute-force throttling** — per-IP lockout after repeated failures.
- **File scanning & integrity** — a magic-byte security scanner
  (`/api/scan`) and SHA-256 baseline checks (`integrity_checker`) ship in-repo
  to pair with vulnerability-assessment workflow.
- **Uploads land only when whole** — chunks stage outside the served tree and
  assemble only at completion, so a half-upload is never visible/served.

## Command-line reference

| Flag | Effect | Default |
|---|---|---|
| `--port PORT` | HTTP port | `8088` |
| `--no-qr` | Disable the printed LAN QR code | QR shown |
| `--limit-speed 2M` | Global download cap (`2M`, `500K`, `1G`) | unlimited |
| `--no-auth` | Turn authentication off entirely (LAN demos) | auth on |
| `--local-only` | Keep auth but trust every client (no logins anywhere) | off |
| `--username NAME` | Admin username | generates a user |
| `--password PASS` | Admin password (set it; otherwise a random one is shown once) | auto-generated |
| `--allowed-networks CIDR ...` | Extra subnets treated as local (no login) | none |
| `--ssh` | Enable the SFTP/SSH server | off |
| `--ssh-port PORT` | SFTP port when `--ssh` | `2222` |
| `--tunnel` | Public link via Tailscale Funnel → cloudflared → ngrok | off |
| `--remote-bridge` | Let the UI browse another host's SFTP | off (security) |
| `--dashboard` | Live rich terminal dashboard | off |

Settings chosen at startup persist to `~/.pyservx_config.json`, so later
`pyservx` runs reuse them (override with the `PYSERVX_CONFIG` env var).

## Where your data lives

| Item | Location |
|---|---|
| Shared folder | `~/Downloads/PyServeX-Shared` |
| Runtime config | `~/.pyservx_config.json` |
| API tokens (SQLite) | `~/.pyservx_tokens.db` |
| In-flight upload chunks | `~/.pyservx_uploads/` |
| Trash bin | `~/.pyservx_trash/` |
| File version history | `~/.pyservx_versions/` |
| Access log (JSONL, rotated) | `~/.pyservx_logs/` |

## API endpoints

| Path | Purpose |
|---|---|
| `/` | Directory listing + the full file manager |
| `/login`, `/tokens` | Auth pages; token manager |
| `/trash` | Trash bin UI |
| `/p2p` | Peer-to-peer transfer room |
| `/notepad`, `<file>/edit` | Scratch pad / file editor |
| `/api/stats`, `/api/stats/ping` | Live counters |
| `/api/search?q=…` | Full-share instant search |
| `/api/events` | Server-sent live event stream (heartbeat 15 s) |
| `/api/upload/*` | Chunked/resumable upload lifecycle |
| `/api/ephemeral/*`, `/e/<token>` | One-time download links |
| `/api/trash/*`, `/api/versions/*` | Trash + version history |
| `/api/scan` | Security scanner + integrity report |
| `/api/remote/*` | Remote SFTP bridge (only with `--remote-bridge`) |
| `/webrtc/signal`, `/webrtc/poll` | P2P signaling relay |
| `/mcp` | MCP JSON-RPC tools for AI agents |

## MCP tools (for AI agents)

| Tool | Purpose |
|---|---|
| `list_files` | List a directory |
| `read_file` | Read a file's contents |
| `write_file` | Create/overwrite a file |
| `upload_file` | Write binary data |
| `search_files` | Full-share text search |
| `server_info` | Settings & status |

## Development

```bash
git clone https://github.com/SubZ3r0-0x01/pyservx.git
cd pyservx
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .[ssh,dashboard]
python -m pytest tests -q                        # unit suite
python tests/integration_smoke.py                # boots a real server (53 checks)
python -m pyservx.server --help                  # CLI smoke test
```

Before committing changes, read `AGENTS.md` — it maps the architecture and
lists the invariants (auth gate, path jail, security headers, CSRF, threading)
that every contribution must preserve.

## License

MIT — see [LICENSE](LICENSE). Built with the Python standard library; optional
extras are [paramiko](https://www.paramiko.org/) (SSH) and
[rich](https://github.com/Textualize/rich) (dashboard).

**Homepage & issues:** https://github.com/SubZ3r0-0x01/pyservx