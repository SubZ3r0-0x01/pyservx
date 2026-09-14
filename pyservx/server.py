#!/usr/bin/env python3
# Enhanced Python HTTP Server - PyServeX v4
# Secure, resumable, P2P-ready file sharing with SSH/SFTP access.
# GitHub: https://github.com/SubZ3r0-0x01/pyservx

import os
import socketserver
import threading
import signal
import sys
import logging
import socket
import json
import argparse
import qrcode

from . import request_handler
from .auth import AuthManager
from .chunked_upload import ChunkedUploadManager
from .ephemeral import EphemeralLinkManager
from .throttling import RateLimiter, parse_speed
from .dashboard import StatsHub, render_dashboard
from .mcp_server import McpBridge
from .webrtc_signaling import SignalingHub
from .remote_sftp import RemoteSftpManager
from .tunnel import TunnelManager
from .access_logger import AccessLogger
from . import events
from . import search_index
from . import trash

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")

PORT = 8088
CONFIG_FILE = os.environ.get("PYSERVX_CONFIG",
                             os.path.expanduser("~/.pyservx_config.json"))
ANALYTICS_DB = os.path.expanduser("~/.pyservx_analytics.db")


class AnalyticsManager:
    """Manage analytics and usage statistics"""

    def __init__(self, db_path):
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS file_access (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT NOT NULL,
                action TEXT NOT NULL,
                ip_address TEXT,
                user_agent TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                file_size INTEGER,
                duration REAL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS server_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                metric_name TEXT NOT NULL,
                metric_value TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()

    def log_file_access(self, file_path, action, ip_address=None, user_agent=None,
                        file_size=None, duration=None):
        import sqlite3
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO file_access (file_path, action, ip_address, user_agent, file_size, duration)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (file_path, action, ip_address, user_agent, file_size, duration))
            conn.commit()
            conn.close()
        except Exception:
            pass

    def prune(self, keep_days=180):
        """Delete analytics rows older than keep_days, then VACUUM."""
        import sqlite3
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute("DELETE FROM file_access WHERE timestamp < "
                        "datetime('now', ?)",
                        ("-%d days" % keep_days,))
            cur.execute("DELETE FROM server_stats WHERE timestamp < "
                        "datetime('now', ?)",
                        ("-%d days" % keep_days,))
            conn.commit()
            conn.execute("VACUUM")
            conn.close()
            return True
        except Exception:
            return False

    def prune_loop(self, stop_event, interval=86400, keep_days=180):
        while not stop_event.wait(interval):
            self.prune(keep_days)


def load_config():
    default_config = {
        "shared_folder": None,
        "analytics_enabled": True,
        "thumbnail_generation": True,
        "max_file_size": 100 * 1024 * 1024,
        "allowed_extensions": [],
        "theme": "dark",
        "auth_enabled": True,
        "local_networks": [
            "127.0.0.0/8", "::1/128", "10.0.0.0/8", "172.16.0.0/12",
            "192.168.0.0/16", "169.254.0.0/16", "fe80::/10",
        ],
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                default_config.update(config)
                return default_config
        except json.JSONDecodeError:
            logging.warning("Invalid config file. Using defaults.")
    return default_config


def save_config(config):
    try:
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
    except OSError as e:
        logging.error(f"Failed to save config: {e}")


def get_shared_folder():
    """Get or create shared folder in user's Downloads directory."""
    config = load_config()
    saved_folder = config.get("shared_folder")
    if saved_folder and os.path.isdir(saved_folder):
        print(f"Using saved shared folder: {saved_folder}")
        return os.path.abspath(saved_folder)

    downloads_dir = os.path.join(os.path.expanduser("~"), "Downloads")
    shared_folder = os.path.join(downloads_dir, "PyServeX-Shared")

    try:
        os.makedirs(shared_folder, exist_ok=True)
        os.makedirs(os.path.join(shared_folder, ".thumbnails"), exist_ok=True)
        config["shared_folder"] = shared_folder
        save_config(config)
        return os.path.abspath(shared_folder)
    except OSError as e:
        logging.error(f"Failed to create shared folder: {e}")
        fallback_folder = os.path.join(os.getcwd(), "shared")
        try:
            os.makedirs(fallback_folder, exist_ok=True)
            return os.path.abspath(fallback_folder)
        except OSError:
            return os.getcwd()


def get_ip_addresses():
    ip_addresses = ["127.0.0.1"]
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if ip not in ip_addresses:
                ip_addresses.append(ip)
    except OSError:
        pass
    return ip_addresses


def _auth_maintenance(auth, stop_event, interval=300):
    """Periodic session/attempt cleanup while the server runs."""
    while not stop_event.wait(interval):
        try:
            auth.cleanup_sessions()
            auth.cleanup_login_attempts()
        except Exception:
            pass


def _shutdown(stop_dash, chunk_mgr, ephemeral_mgr, remote_sftp, tunnel,
              server, exit_code=0, events_bus=None, search=None, trash_mgr=None,
              stop_extras=None):
    """Tear down every running manager consistently (ctrl-C safe)."""
    stop_dash.set()
    if stop_extras:
        stop_extras.set()
    try:
        chunk_mgr.shutdown()
    except Exception:
        pass
    try:
        ephemeral_mgr.shutdown()
    except Exception:
        pass
    try:
        remote_sftp.shutdown()
    except Exception:
        pass
    if search:
        try:
            search.stop()
        except Exception:
            pass
    if trash_mgr:
        try:
            trash_mgr.shutdown()
        except Exception:
            pass
    if tunnel:
        try:
            tunnel.stop()
        except Exception:
            pass
    if server:
        try:
            threading.Thread(target=server.shutdown, daemon=True).start()
            server.server_close()
        except Exception:
            pass
    sys.exit(exit_code)


def run(base_dir, no_qr=False, port=None, config=None, auth=None,
        enable_ssh=False, ssh_port=2222, show_dashboard=False,
        args_username=None, args_password=None, enable_tunnel=False,
        remote_bridge=False):
    """Run the PyServeX servers (HTTP + optional SFTP + dashboard)."""
    global PORT
    if port:
        PORT = port
    config = config or load_config()

    # ---- shared services -------------------------------------------------
    analytics = AnalyticsManager(ANALYTICS_DB)
    stats = StatsHub()
    access_logger = AccessLogger()
    auth = auth or AuthManager(config)
    if args_password:
        # explicit CLI credential always (re)applies, not just on first run
        auth.set_password(args_username or config.get("admin_username") or "admin",
                          args_password)
    chunk_mgr = ChunkedUploadManager(base_dir)
    ephemeral_mgr = EphemeralLinkManager()
    signaling = SignalingHub()
    mcp_bridge = McpBridge(base_dir, stats=stats)
    remote_sftp = RemoteSftpManager()
    tunnel = TunnelManager(PORT) if enable_tunnel else None
    event_bus = events.EventBus()
    search = search_index.SearchIndex(base_dir)
    trash_mgr = trash.TrashManager(base_dir)

    speed_arg = config.get("limit_speed")
    rate_limiter = None
    if speed_arg:
        bps = parse_speed(speed_arg)
        if bps:
            rate_limiter = RateLimiter(bps)

    stop_maintenance = threading.Event()
    stop_extras = threading.Event()
    threading.Thread(target=signaling.cleanup_loop,
                     args=(stop_maintenance,), daemon=True).start()
    threading.Thread(target=remote_sftp.janitor_loop,
                     args=(stop_maintenance,), daemon=True).start()
    threading.Thread(target=analytics.prune_loop,
                     args=(stop_maintenance,), daemon=True).start()
    threading.Thread(target=_auth_maintenance, args=(auth, stop_maintenance),
                     daemon=True).start()
    search.start()
    threading.Thread(target=trash_mgr.purge_loop, args=(stop_extras,),
                     daemon=True, name="pyservx-trash-purge").start()
    threading.Thread(target=events.stats_ticker, args=(event_bus, stats, stop_extras),
                     daemon=True, name="pyservx-stats-ticker").start()

    class Handler(request_handler.FileRequestHandler):
        def __init__(self, *args, **kwargs):
            self.base_dir = base_dir
            self.config = config
            self.analytics = analytics
            super().__init__(*args, **kwargs)

    # class-level wiring shared by every request thread
    Handler.auth = auth
    Handler.chunk_mgr = chunk_mgr
    Handler.ephemeral_mgr = ephemeral_mgr
    Handler.rate_limiter = rate_limiter
    Handler.stats = stats
    Handler.signaling = signaling
    Handler.mcp = mcp_bridge
    Handler.access_logger = access_logger
    Handler.auth_enabled = bool(config.get("auth_enabled", True))
    Handler.events = event_bus
    Handler.search = search
    Handler.trash = trash_mgr
    Handler.remote_bridge_enabled = bool(remote_bridge)

    robots_txt_path = os.path.join(base_dir, "robots.txt")
    if not os.path.exists(robots_txt_path):
        with open(robots_txt_path, "w") as f:
            f.write("User-agent: *\nDisallow: /\n")

    os.makedirs(os.path.join(base_dir, ".thumbnails"), exist_ok=True)

    # ---- optional SFTP server --------------------------------------------
    sftp_server = None
    if enable_ssh:
        try:
            from .ssh_server import SshServer
            sftp_server = SshServer(auth, base_dir, port=ssh_port).start()
        except RuntimeError as e:
            print(f"[PyServeX] SSH disabled: {e}")
        except Exception as e:
            logging.error("Failed starting SSH server: %s", e)

    if not no_qr:
        print("PyServeX - System IPv4 addresses:")
        for ip in get_ip_addresses():
            print(f"  http://{ip}:{PORT}")
            try:
                qr = qrcode.QRCode(version=1,
                                   error_correction=qrcode.constants.ERROR_CORRECT_L,
                                   box_size=3, border=4)
                qr.add_data(f"http://{ip}:{PORT}")
                qr.make(fit=True)
                qr.print_tty()
            except OSError:
                pass

    server = None
    stop_dash = threading.Event()
    dash_thread = None

    try:
        class ReusableThreadingTCPServer(socketserver.ThreadingTCPServer):
            allow_reuse_address = True
            daemon_threads = True

        server = ReusableThreadingTCPServer(("0.0.0.0", PORT), Handler)
        server.sftp_info = {"enabled": sftp_server is not None, "port": ssh_port}
        server.remote_sftp = remote_sftp
        server.tunnel_info = tunnel.info() if tunnel else {}
        if tunnel:
            def _publish():
                for _ in range(60):          # up to ~2.5 min
                    time.sleep(2.5)
                    if tunnel.url:
                        server.tunnel_info = tunnel.info()
                        print(f"PyServeX public link ({tunnel.provider}): {tunnel.url}")
                        return
            threading.Thread(target=_publish, daemon=True).start()
            tunnel.start()
            print("PyServeX: requesting a public share link (tunnel)…")

        print(f"PyServeX v4.0 serving at http://0.0.0.0:{PORT}")
        print("Auth: " + ("ENABLED for remote clients "
                          "(local network needs no login)" if Handler.auth_enabled
                          else "disabled"))
        if rate_limiter:
            print(f"Bandwidth cap: {speed_arg}")
        print("Endpoints: /p2p  /tokens  /login  /mcp  /api/*  /e/<token>")

        def shutdown_handler(signum, frame):
            print("\nShutting down PyServeX...")
            _shutdown(stop_dash, chunk_mgr, ephemeral_mgr, remote_sftp,
                      tunnel, server, 0, event_bus, search, trash_mgr,
                      stop_extras)

        signal.signal(signal.SIGINT, shutdown_handler)

        if show_dashboard:
            dash_thread = threading.Thread(
                target=render_dashboard,
                args=(stats, auth, ephemeral_mgr, stop_dash),
                daemon=True, name="pyservx-dashboard")
            dash_thread.start()

        server.serve_forever()

    except KeyboardInterrupt:
        print("\nShutting down PyServeX...")
        _shutdown(stop_dash, chunk_mgr, ephemeral_mgr, remote_sftp,
                  tunnel, server, 0, event_bus, search, trash_mgr,
                  stop_extras)
    except OSError as e:
        print(f"Server error: {e}")
        if server:
            server.server_close()
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="PyServeX v4: secure file server with resumable uploads, "
                    "P2P transfers, ephemeral links, MCP bridge, SFTP access.")
    parser.add_argument('--version', action='version', version='PyServeX 4.0.0')
    parser.add_argument('--port', type=int, default=8088,
                        help='HTTP port (default: 8088)')
    parser.add_argument('--no-qr', action='store_true',
                        help='Disable QR code generation')
    parser.add_argument('--limit-speed', type=str, default=None,
                        help='Global bandwidth cap, e.g. 2M, 500K')
    parser.add_argument('--no-auth', action='store_true',
                        help='Disable authentication entirely')
    parser.add_argument('--local-only', action='store_true',
                        help='Alias: keep auth but treat everyone as local '
                             '(no login anywhere)')
    parser.add_argument('--username', type=str, default=None,
                        help='Admin username (first run)')
    parser.add_argument('--password', type=str, default=None,
                        help='Admin password (first run; else auto-generated)')
    parser.add_argument('--allowed-networks', nargs='+', default=None,
                        metavar='CIDR',
                        help='Extra networks treated as local (no auth)')
    parser.add_argument('--ssh', action='store_true',
                        help='Enable SSH/SFTP access (requires paramiko)')
    parser.add_argument('--ssh-port', type=int, default=2222)
    parser.add_argument('--tunnel', action='store_true',
                        help='Expose a public share link via tailscale funnel /'
                             ' cloudflared / ngrok (no public IP needed)')
    parser.add_argument('--remote-bridge', action='store_true',
                        help='Enable the server-side SFTP snap-in: browse and '
                             'move files between this server and a remote host '
                             '(default: off for security)')
    parser.add_argument('--dashboard', action='store_true',
                        help='Live terminal dashboard (requires rich)')
    args = parser.parse_args()

    base_dir = get_shared_folder()

    config = load_config()
    config["limit_speed"] = args.limit_speed
    if args.allowed_networks:
        nets = set(config.get("local_networks", []))
        nets.update(args.allowed_networks)
        config["local_networks"] = sorted(nets)
    if args.local_only:
        config["auth_enabled"] = False
    if args.no_auth:
        config["auth_enabled"] = False
    if args.username:
        config["admin_username"] = args.username
    if args.password:
        config["admin_password"] = args.password
    save_config({k: v for k, v in config.items()
                 if k not in ("admin_username", "admin_password", "limit_speed")})

    run(base_dir, no_qr=args.no_qr, port=args.port, config=config,
        enable_ssh=args.ssh, ssh_port=args.ssh_port,
        show_dashboard=args.dashboard,
        args_username=args.username, args_password=args.password,
        enable_tunnel=args.tunnel, remote_bridge=args.remote_bridge)


if __name__ == "__main__":
    main()
