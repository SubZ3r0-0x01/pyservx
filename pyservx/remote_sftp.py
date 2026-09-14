#!/usr/bin/env python3
"""Outbound SFTP client bridge: lets the web UI open/browse remote machines.

Sessions live only in memory (never persisted). Credentials are used once
for the SSH handshake and then dropped; browsing streams through the server.
"""

import os
import threading
import time
import uuid

MAX_SESSIONS = 8
SESSION_IDLE_TTL = 30 * 60   # seconds before an idle session is reaped
REAP_INTERVAL = 60           # janitor cadence in seconds


class RemoteSftpError(Exception):
    pass


class RemoteSftpManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._sessions = {}

    # -- lifecycle ---------------------------------------------------------
    def _get(self, sid):
        with self._lock:
            sess = self._sessions.get(sid)
            if not sess:
                raise RemoteSftpError("unknown or closed session")
            sess["last_used"] = time.time()   # lazy touch
        return sess

    def connect(self, p):
        try:
            import paramiko
        except ImportError:
            raise RemoteSftpError(
                "paramiko not installed - run: pip install pyservx[ssh]")
        host = (p.get("host") or "").strip()
        if not host:
            raise RemoteSftpError("host required")
        port = int(p.get("port") or 22)
        user = (p.get("user") or "").strip() or None
        auth = p.get("auth") or "password"
        cli = paramiko.SSHClient()
        cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        kw = dict(hostname=host, port=port, username=user, timeout=10,
                  allow_agent=False, look_for_keys=False,
                  banner_timeout=10, auth_timeout=10)
        try:
            if auth == "password":
                if not p.get("secret"):
                    raise RemoteSftpError("password required")
                cli.connect(password=p["secret"], **kw)
            elif auth == "cert":
                kf = self._expand_key(p.get("key"))
                cli.connect(key_filename=kf, **kw)
            else:  # key | fido2 -> plain key file on the server machine
                kf = self._expand_key(p.get("key"))
                cli.connect(key_filename=kf, **kw)
        except RemoteSftpError:
            cli.close()
            raise
        except Exception as e:
            cli.close()
            msg = str(e)
            if isinstance(e, FileNotFoundError):
                msg = "key file not found on server machine: %s" % kf
            elif len(msg) > 160:
                msg = msg[:157] + "..."
            raise RemoteSftpError("connect failed: " + msg)
        try:
            sftp = cli.open_sftp()
        except Exception as e:
            cli.close()
            raise RemoteSftpError("sftp subsystem failed: %s" % e)

        with self._lock:
            if len(self._sessions) >= MAX_SESSIONS:
                oldest = min(self._sessions,
                             key=lambda s: self._sessions[s].get("last_used", 0))
                self.close(oldest)
            sid = uuid.uuid4().hex[:12]
            self._sessions[sid] = {"cli": cli, "sftp": sftp,
                                   "last_used": time.time()}
        try:
            home = sftp.normalize(".")
        except Exception:
            home = "/"
        return {"sid": sid, "home": home, "host": host, "port": port}

    @staticmethod
    def _expand_key(raw):
        kf = os.path.expanduser((raw or "").strip())
        if not kf:
            raise RemoteSftpError("key path required")
        if not os.path.isfile(kf):
            raise RemoteSftpError("key file not found on server machine: " + kf)
        return kf

    def close(self, sid):
        with self._lock:
            sess = self._sessions.pop(sid, None)
        if not sess:
            return
        try:
            sess["sftp"].close()
        except Exception:
            pass
        try:
            sess["cli"].close()
        except Exception:
            pass

    def shutdown(self):
        with self._lock:
            sids = list(self._sessions)
        for sid in sids:
            self.close(sid)

    def reap_idle(self):
        """Close sessions idle for longer than SESSION_IDLE_TTL."""
        cutoff = time.time() - SESSION_IDLE_TTL
        with self._lock:
            stale = [sid for sid, s in self._sessions.items()
                     if s.get("last_used", 0) < cutoff]
        for sid in stale:
            self.close(sid)
        return len(stale)

    def janitor_loop(self, stop_event):
        while not stop_event.wait(REAP_INTERVAL):
            try:
                self.reap_idle()
            except Exception:
                pass

    # -- operations --------------------------------------------------------
    def list_dir(self, sid, path="."):
        sftp = self._get(sid)["sftp"]
        try:
            path = sftp.normalize(path)
            entries = []
            for st in sftp.listdir_attr(path):
                entries.append({
                    "name": st.filename,
                    "isdir": __import__("stat").S_ISDIR(st.st_mode or 0),
                    "size": st.st_size or 0,
                    "mtime": st.st_mtime or 0,
                })
        except RemoteSftpError:
            raise
        except Exception as e:
            raise RemoteSftpError("listing failed: %s" % e)
        entries.sort(key=lambda x: (not x["isdir"], x["name"].lower()))
        return {"path": path, "entries": entries}

    def stat(self, sid, path):
        import stat as _stat
        sftp = self._get(sid)["sftp"]
        try:
            st = sftp.stat(sftp.normalize(path))
        except Exception as e:
            raise RemoteSftpError("stat failed: %s" % e)
        return {"size": st.st_size or 0,
                "isdir": _stat.S_ISDIR(st.st_mode or 0),
                "path": sftp.normalize(path)}

    def open_download(self, sid, path):
        """Returns (fileobj, size, abspath); caller must close fileobj."""
        sftp = self._get(sid)["sftp"]
        abspath = sftp.normalize(path)
        st = sftp.stat(abspath)
        import stat as _stat
        if _stat.S_ISDIR(st.st_mode or 0):
            raise RemoteSftpError("path is a directory")
        fh = sftp.file(abspath, "rb")
        return fh, st.st_size or 0, abspath

    def open_upload(self, sid, path):
        """Returns (fileobj_write, abspath, exists_remote); caller closes fileobj."""
        sftp = self._get(sid)["sftp"]
        abspath = sftp.normalize(path)
        exists = False
        try:
            st = sftp.stat(abspath)
            import stat as _stat
            if _stat.S_ISDIR(st.st_mode or 0):
                raise RemoteSftpError("path is a directory")
            exists = True
        except RemoteSftpError:
            raise
        except IOError:
            exists = False
        fh = sftp.file(abspath, "wb")
        return fh, abspath, exists
