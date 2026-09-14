#!/usr/bin/env python3
"""SSH (SFTP) access to the PyServeX shared folder.

Users connect with any SSH/SFTP client:
    sftp -P 2222 user@server-ip
and land in a chroot-style view of the shared directory.

Auth options per user:
  - username + password  (same account store as the web UI)
  - public key           (append lines to ~/.pyservx_authorized_keys)

Requires: pip install pyservx[ssh]   (paramiko)
"""

import logging
import os
import socket
import socketserver
import threading

try:
    import paramiko
    HAS_PARAMIKO = True
except ImportError:  # pragma: no cover
    paramiko = None
    HAS_PARAMIKO = False

HOST_KEY_PATH = os.path.expanduser("~/.pyservx_ssh_host_key")
AUTHORIZED_KEYS = os.path.expanduser("~/.pyservx_authorized_keys")


def _ensure_host_key():
    """Load or generate the server host key (RSA; loads legacy Ed25519)."""
    io = __import__("io")
    if os.path.exists(HOST_KEY_PATH):
        with open(HOST_KEY_PATH, "r") as f:
            data = f.read()
        for loader in (paramiko.Ed25519Key.from_private_key,
                       paramiko.RSAKey.from_private_key):
            try:
                return loader(io.StringIO(data))
            except Exception:
                pass
    key = paramiko.RSAKey.generate(3072)
    buf = io.StringIO()
    key.write_private_key(buf)
    with open(HOST_KEY_PATH, "w") as f:
        f.write(buf.getvalue())
    return key


class _SshServerInterface(paramiko.ServerInterface):
    def __init__(self, auth_manager, base_dir):
        self.auth = auth_manager
        self.base_dir = base_dir
        self._load_authorized_keys()

    def _load_authorized_keys(self):
        self.allowed_pubkeys = []
        if os.path.exists(AUTHORIZED_KEYS):
            with open(AUTHORIZED_KEYS, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    try:
                        parts = line.split()
                        key_cls = {"ssh-rsa": paramiko.RSAKey,
                                   "ssh-ed25519": paramiko.Ed25519Key}.get(parts[0])
                        if key_cls:
                            import base64 as b64
                            self.allowed_pubkeys.append(
                                paramiko.RSAKey(data=b64.b64decode(parts[1]))
                                if parts[0] == "ssh-rsa"
                                else paramiko.Ed25519Key(data=b64.b64decode(parts[1])))
                    except Exception:
                        logging.warning("Bad authorized_keys line skipped")

    # --- paramiko hooks ---
    def get_allowed_auths(self, username):
        return "password,publickey"

    def check_auth_password(self, username, password):
        if self.auth.verify_login(username, password):
            return paramiko.AUTH_SUCCESSFUL
        return paramiko.AUTH_FAILED

    def check_auth_publickey(self, username, key):
        for allowed in self.allowed_pubkeys:
            if key.get_fingerprint() == allowed.get_fingerprint():
                return paramiko.AUTH_SUCCESSFUL
        return paramiko.AUTH_FAILED

    def check_channel_request(self, kind, chanid):
        return paramiko.OPEN_SUCCEEDED

    def check_channel_shell_request(self, channel):
        return False


class _ThreadedSshHandler(socketserver.BaseRequestHandler):
    def handle(self):
        transport = None
        try:
            transport = paramiko.Transport(self.request)
            # paramiko >= 4 dropped GSS support; older versions need moduli
            if hasattr(transport, "set_gss_host"):
                transport.set_gss_host(socket.getfqdn(""))
            try:
                transport.load_server_moduli()
            except Exception:
                pass
            transport.add_server_key(self.server.host_key)
            interface = _SshServerInterface(self.server.auth_manager,
                                            self.server.base_dir)
            transport.set_subsystem_handler(
                "sftp", paramiko.SFTPServer,
                sftp_si=_PyServeXSftp, root=self.server.base_dir)
            transport.start_server(server=interface)

            while transport.is_active():
                chan = transport.accept(60)
                if chan is None:
                    break
        except Exception as e:
            logging.debug("SSH handler ended: %s", e)
        finally:
            if transport:
                transport.close()


# Minimal SFTP server rooted at base_dir
from paramiko import SFTP_NO_SUCH_FILE, SFTP_PERMISSION_DENIED, SFTP_OK  # noqa: E402
from paramiko.sftp_handle import SFTPHandle  # noqa: E402
from paramiko.sftp_server import SFTPServerInterface  # noqa: E402

class _PyServeXSftp(SFTPServerInterface):
    """Maps every requested path into the shared root (jail)."""

    ROOT_LABEL = "/pyservx-shared"

    def __init__(self, server, root=None, *largs, **kwargs):
        super().__init__(server)
        self.sftp_server = server
        self.root = os.path.abspath(root or os.getcwd())

    def _map(self, server_path):
        p = server_path
        if p.startswith(_PyServeXSftp.ROOT_LABEL):
            rel = p[len(_PyServeXSftp.ROOT_LABEL):]
        else:
            rel = p.replace("\\", "/")
        rel = rel.lstrip("/")
        abs_path = os.path.abspath(os.path.join(self.root, rel))
        if not abs_path.startswith(self.root + os.sep) and abs_path != self.root:
            raise IOError(SFTP_PERMISSION_DENIED)
        return abs_path

    def list_folder(self, path):
        d = self._map(path)
        try:
            out = []
            for name in os.listdir(d):
                full = os.path.join(d, name)
                st = os.stat(full)
                out.append(paramiko.SFTPAttributes.from_stat(st, name))
            return out
        except OSError:
            return SFTP_NO_SUCH_FILE

    def stat(self, path):
        try:
            return paramiko.SFTPAttributes.from_stat(os.stat(self._map(path)))
        except OSError:
            return SFTP_NO_SUCH_FILE

    def lstat(self, path):
        try:
            return paramiko.SFTPAttributes.from_stat(os.lstat(self._map(path)))
        except OSError:
            return SFTP_NO_SUCH_FILE

    def open(self, path, flags, attr):
        p = self._map(path)
        try:
            flags |= getattr(os, "O_BINARY", 0)
            write = bool(flags & (os.O_WRONLY | os.O_RDWR))
            append = bool(flags & os.O_APPEND)
            if write:
                fmode = "ab" if append else ("r+b" if flags & os.O_RDWR
                                             and not (flags & os.O_TRUNC)
                                             else "wb")
            else:
                fmode = "rb"
            f = open(p, fmode)
        except OSError:
            return SFTP_NO_SUCH_FILE
        fobj = SFTPHandle(flags)
        fobj.filename = p
        fobj.readfile = f if (flags & os.O_WRONLY) == 0 else None
        fobj.writefile = f if (flags & (os.O_WRONLY | os.O_RDWR)) else None
        return fobj

    def remove(self, path):
        try:
            os.remove(self._map(path))
        except OSError:
            return SFTP_NO_SUCH_FILE
        return SFTP_OK

    def rename(self, oldpath, newpath):
        try:
            os.rename(self._map(oldpath), self._map(newpath))
        except OSError:
            return SFTP_NO_SUCH_FILE
        return SFTP_OK

    def mkdir(self, path, attr):
        try:
            os.mkdir(self._map(path))
        except OSError:
            return SFTP_FAILURE
        return SFTP_OK

    def rmdir(self, path):
        try:
            os.rmdir(self._map(path))
        except OSError:
            return SFTP_NO_SUCH_FILE
        return SFTP_OK

    def readlink(self, path):
        try:
            return os.readlink(self._map(path))
        except OSError:
            return SFTP_NO_SUCH_FILE


class _ReusableThreadingTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class SshServer:
    def __init__(self, auth_manager, base_dir, port=2222, bind="0.0.0.0"):
        if not HAS_PARAMIKO:
            raise RuntimeError("paramiko is required for SSH support: "
                               "pip install pyservx[ssh]")
        self.auth_manager = auth_manager
        self.base_dir = base_dir
        self.port = port
        self.bind = bind
        self.host_key = _ensure_host_key()

    def start(self):
        srv = _ReusableThreadingTCPServer((self.bind, self.port),
                                          _ThreadedSshHandler)
        srv.auth_manager = self.auth_manager
        srv.base_dir = self.base_dir
        srv.host_key = self.host_key
        t = threading.Thread(target=srv.serve_forever, daemon=True,
                             name="pyservx-ssh")
        t.start()
        logging.info("SFTP server listening on %s:%d (root=%s)",
                     self.bind, self.port, self.base_dir)
        print(f"[PyServeX] SSH/SFTP enabled: sftp -P {self.port} <user>@<host>")
        return srv
