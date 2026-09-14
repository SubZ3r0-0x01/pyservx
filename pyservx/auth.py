#!/usr/bin/env python3
"""Authentication & authorization for PyServeX.

Rules:
- Clients on the local network NEVER require login.
- Remote clients must authenticate via session cookie (web login)
  or Authorization: Bearer <api-token> header.
- API tokens are persistent (SQLite) and can be created/revoked
  via the UI or REST endpoints.
"""

import hashlib
import ipaddress
import json
import logging
import os
import secrets
import sqlite3
import threading
import time

DEFAULT_LOCAL_NETWORKS = [
    "127.0.0.0/8",
    "::1/128",
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "169.254.0.0/16",
    "fe80::/10",
]

AUTH_STORE = os.path.expanduser("~/.pyservx_auth.json")
TOKEN_DB = os.path.expanduser("~/.pyservx_tokens.db")
SESSION_TTL = 12 * 3600  # seconds
LOGIN_MAX_ATTEMPTS = 5     # failed attempts before a temporary IP lockout
LOGIN_LOCKOUT_SECONDS = 300
LOGIN_ATTEMPT_TTL = 3600   # forget remembered failures after this long


def _pbkdf2(password, salt, iterations=120_000):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), iterations).hex()


class AuthManager:
    def __init__(self, config=None):
        self.config = config or {}
        self.lock = threading.RLock()
        self.sessions = {}  # sid -> {user, expires, csrf}
        # ip -> {"fails": int, "locked_until": ts}
        self._login_attempts = {}
        self.max_attempts = int(self.config.get("login_max_attempts",
                                                LOGIN_MAX_ATTEMPTS))
        self.lockout_seconds = int(self.config.get("login_lockout_seconds",
                                                   LOGIN_LOCKOUT_SECONDS))
        self.local_networks = [ipaddress.ip_network(n, strict=False)
                               for n in self.config.get("local_networks", DEFAULT_LOCAL_NETWORKS)]
        self.token_db_path = self.config.get("tokens_db", TOKEN_DB)
        self._init_token_db()
        self.users = self._load_users()

    # ---------- users ----------
    def _load_users(self):
        """Load user db; bootstrap admin account on first run."""
        data = {}
        if os.path.exists(AUTH_STORE):
            try:
                with open(AUTH_STORE, "r") as f:
                    data = json.load(f)
            except Exception:
                data = {}
        if not data.get("users"):
            username = self.config.get("admin_username") or "admin"
            password = self.config.get("admin_password") or secrets.token_urlsafe(12)
            salt = secrets.token_hex(16)
            data["users"] = {username: {"salt": salt,
                                        "hash": _pbkdf2(password, salt)}}
            try:
                with open(AUTH_STORE, "w") as f:
                    json.dump(data, f, indent=2)
                logging.info("[auth] Created admin user '%s' with password: %s "
                             "(stored hashed; change it via /tokens page)", username, password)
                print(f"[PyServeX] First run: admin user '{username}' created.")
                print(f"[PyServeX] Admin password (remote login): {password}")
            except OSError as e:
                logging.error("Failed to persist auth store: %s", e)
        return data["users"]

    def set_password(self, username, password):
        salt = secrets.token_hex(16)
        with self.lock:
            self.users[username] = {"salt": salt, "hash": _pbkdf2(password, salt)}
            self._save_users()

    def _save_users(self):
        try:
            with open(AUTH_STORE, "w") as f:
                json.dump({"users": self.users}, f, indent=2)
        except OSError as e:
            logging.error("Failed to save auth store: %s", e)

    def verify_login(self, username, password):
        rec = self.users.get(username)
        if not rec:
            # constant-ish time
            _pbkdf2(password or "", secrets.token_hex(16))
            return False
        return secrets.compare_digest(_pbkdf2(password or "", rec["salt"]), rec["hash"])

    # ---------- local network ----------
    def is_local(self, ip):
        try:
            addr = ipaddress.ip_address(ip.split("%")[0])
        except ValueError:
            return False
        return any(addr in net for net in self.local_networks)

    # ---------- sessions ----------
    def create_session(self, username):
        sid = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(32)
        with self.lock:
            self.sessions[sid] = {"user": username,
                                  "expires": time.time() + SESSION_TTL,
                                  "csrf": csrf}
        return sid

    def validate_session(self, sid):
        if not sid:
            return None
        with self.lock:
            sess = self.sessions.get(sid)
            if not sess:
                return None
            if sess["expires"] < time.time():
                del self.sessions[sid]
                return None
            return sess["user"]

    def session_csrf(self, sid):
        """Return the CSRF token bound to a live session (None if invalid)."""
        with self.lock:
            sess = self.sessions.get(sid)
            if not sess or sess["expires"] < time.time():
                return None
            return sess.get("csrf")

    def destroy_session(self, sid):
        with self.lock:
            self.sessions.pop(sid, None)

    def cleanup_sessions(self):
        now = time.time()
        with self.lock:
            for sid in [s for s, v in self.sessions.items() if v["expires"] < now]:
                del self.sessions[sid]

    # ---------- brute-force protection ----------
    def login_status(self, ip):
        """Return (allowed: bool, retry_after_seconds: int) for this IP."""
        now = time.time()
        with self.lock:
            rec = self._login_attempts.get(ip)
            if rec and rec["locked_until"] and rec["locked_until"] > now:
                return False, int(rec["locked_until"] - now) + 1
        return True, 0

    def record_login_failure(self, ip):
        with self.lock:
            now = time.time()
            rec = self._login_attempts.setdefault(
                ip, {"fails": 0, "locked_until": 0, "first": now})
            if rec["locked_until"] and rec["locked_until"] > now:
                return              # already locked out
            if now - rec.get("first", now) > LOGIN_ATTEMPT_TTL:
                rec.update(fails=0, first=now)
            rec["fails"] += 1
            if rec["fails"] >= self.max_attempts:
                rec["locked_until"] = now + self.lockout_seconds
                rec["fails"] = 0

    def reset_login_failures(self, ip):
        with self.lock:
            self._login_attempts.pop(ip, None)

    def cleanup_login_attempts(self):
        now = time.time()
        with self.lock:
            stale = [ip for ip, r in self._login_attempts.items()
                     if r["locked_until"] < now
                     and now - r.get("first", now) > LOGIN_ATTEMPT_TTL]
            for ip in stale:
                del self._login_attempts[ip]

    # ---------- api tokens ----------
    def _init_token_db(self):
        conn = sqlite3.connect(self.token_db_path)
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS api_tokens (
                        token TEXT PRIMARY KEY,
                        name TEXT,
                        created_at REAL,
                        expires_at REAL,
                        max_uses INTEGER,
                        uses INTEGER DEFAULT 0,
                        active INTEGER DEFAULT 1)""")
        conn.commit()
        conn.close()

    def create_api_token(self, name="default", max_uses=None, expires_hours=None):
        token = "psx_" + secrets.token_hex(24)
        now = time.time()
        expires = now + expires_hours * 3600 if expires_hours else None
        conn = sqlite3.connect(self.token_db_path)
        c = conn.cursor()
        c.execute("INSERT INTO api_tokens (token,name,created_at,expires_at,max_uses,uses,active)"
                  " VALUES (?,?,?,?,?,?,1)",
                  (token, name, now, expires, max_uses, 0))
        conn.commit()
        conn.close()
        return token

    def validate_api_token(self, token):
        """Returns dict(token info) when valid else None."""
        if not token:
            return None
        conn = sqlite3.connect(self.token_db_path)
        c = conn.cursor()
        c.execute("SELECT token,name,created_at,expires_at,max_uses,uses,active"
                  " FROM api_tokens WHERE token=?", (token,))
        row = c.fetchone()
        conn.close()
        if not row or not row[6]:
            return None
        _, name, created, expires, max_uses, uses, _ = row
        if expires and time.time() > expires:
            return None
        if max_uses is not None and uses >= max_uses:
            return None
        return {"name": name, "created": created, "expires": expires,
                "max_uses": max_uses, "uses": uses}

    def touch_api_token(self, token):
        conn = sqlite3.connect(self.token_db_path)
        c = conn.cursor()
        c.execute("UPDATE api_tokens SET uses = uses + 1 WHERE token=?", (token,))
        conn.commit()
        conn.close()

    def revoke_api_token(self, token):
        conn = sqlite3.connect(self.token_db_path)
        c = conn.cursor()
        c.execute("UPDATE api_tokens SET active=0 WHERE token=?", (token,))
        changed = c.rowcount
        conn.commit()
        conn.close()
        return bool(changed)

    def list_api_tokens(self, include_revoked=False):
        q = "SELECT token,name,created_at,expires_at,max_uses,uses,active FROM api_tokens"
        if not include_revoked:
            q += " WHERE active=1"
        conn = sqlite3.connect(self.token_db_path)
        c = conn.cursor()
        c.execute(q)
        rows = c.fetchall()
        conn.close()
        out = []
        for tok, name, created, expires, max_uses, uses, active in rows:
            out.append({
                "token": tok[:12] + "...",
                "full_token": tok,
                "name": name,
                "created_at": created,
                "expires_at": expires,
                "max_uses": max_uses,
                "uses": uses,
                "active": bool(active),
            })
        return out

    # ---------- main gate ----------
    def authenticate_request(self, client_ip, bearer_token=None, session_cookie=None):
        """Return (authenticated: bool, is_local: bool, identity: str|None)."""
        if self.is_local(client_ip):
            return True, True, f"local:{client_ip}"
        if bearer_token:
            info = self.validate_api_token(bearer_token)
            if info:
                self.touch_api_token(bearer_token)
                return True, False, f"token:{info['name']}"
        user = self.validate_session(session_cookie)
        if user:
            return True, False, f"user:{user}"
        return False, False, None
