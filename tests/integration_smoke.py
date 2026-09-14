#!/usr/bin/env python3
"""One-shot integration harness: boots PyServeX, exercises every endpoint, exits."""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import io

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import socket as _socket
_probe = _socket.socket()
_probe.bind(("127.0.0.1", 0))
PORT = _probe.getsockname()[1]
_probe.close()
BASE = f"http://127.0.0.1:{PORT}"
RUN_TAG = os.urandom(4).hex()
PASS, FAIL = [], []


def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name + (" | " + str(extra) if extra and not cond else ""))


def req(path, method="GET", data=None, headers=None, raw=False):
    r = urllib.request.Request(BASE + path, data=data, method=method,
                               headers=headers or {})
    try:
        resp = urllib.request.urlopen(r, timeout=15)
        body = resp.read()
        return resp.status, dict(resp.headers), (body if raw else body)
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def jreq(path, method="GET", obj=None, headers=None):
    data = json.dumps(obj).encode() if obj is not None else None
    h = {"Content-Type": "application/json"}
    h.update(headers or {})
    st, hd, body = req(path, method, data, h)
    try:
        return st, hd, json.loads(body)
    except Exception:
        return st, hd, body[:200]


def wait_port(port, timeout=20):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return True
        except OSError:
            time.sleep(0.3)
    return False


def main():
    sys.path.insert(0, ROOT)
    from pyservx.auth import AuthManager
    am = AuthManager({})
    am.set_password("admin", "knowntest123")

    env = dict(os.environ, PYTHONUNBUFFERED="1")
    proc = subprocess.Popen(
        [sys.executable, "-m", "pyservx.server", "--port", str(PORT), "--no-qr"],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
    try:
        if not wait_port(PORT):
            time.sleep(0.5)
            out = b""
            try:
                os.set_blocking(proc.stdout.fileno(), False)
                out = proc.stdout.read() or b""
            except Exception:
                pass
            print("SERVER FAILED TO START:\n" +
                  out.decode(errors="replace")[-2000:])
            sys.exit(2)
        run_tests()
        print(f"\n===== {len(PASS)} passed, {len(FAIL)} failed =====")
        if FAIL:
            print("FAILED:", *FAIL, sep="\n  ")
        err = proc.stdout.read().decode(errors="replace") if proc.poll() is not None else ""
        if err.strip():
            print("--- server log tail ---\n" + "\n".join(err.splitlines()[-25:]))
    finally:
        proc.terminate()
    sys.exit(1 if FAIL else 0)


def run_tests():
    # ---- basics ----
    st, hd, body = req("/")
    check("directory page renders", st == 200 and b"PyServeX" in body)

    st, _, d = jreq("/api/stats")
    check("api stats", st == 200 and d.get("status") == "success")

    # security headers present everywhere
    st, hd, _ = req("/api/stats")
    check("security headers",
          hd.get("X-Content-Type-Options") == "nosniff" and
          hd.get("X-Frame-Options") == "SAMEORIGIN")

    # ---- MCP ----
    st, _, d = jreq("/mcp", "POST", {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    names = [t["name"] for t in d["result"]["tools"]]
    check("mcp tools/list", st == 200 and "read_file" in names, names)
    st, _, d = jreq("/mcp", "POST", {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                                     "params": {"name": "write_file",
                                                "arguments": {"path": "it/mcp.txt",
                                                              "content": "hi"}}})
    check("mcp write_file", st == 200 and b"written" in json.dumps(d.get("result", {})).encode())
    st, _, d = jreq("/mcp", "POST", {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                                     "params": {"name": "read_file",
                                                "arguments": {"path": "../secret"}}})
    check("mcp traversal blocked", "error" in d, d)

    # ---- chunked upload with resume semantics ----
    payload = bytes(range(256)) * 8192          # 2 MiB exactly
    uid = f"integration-upload-{RUN_TAG}"
    fname = f"int-test-{RUN_TAG}.bin"
    st, _, d = jreq("/api/upload/init", "POST",
                    {"upload_id": uid, "filename": fname,
                     "size": len(payload), "chunk_size": 262144})
    total = d["total"]
    check("upload init", st == 200 and total == len(payload) // 262144, d)
    ok_all = True
    for i in range(total):
        st, _, _ = req(f"/api/upload/chunk?upload_id={uid}&index={i}", "POST",
                       payload[i * 262144:(i + 1) * 262144])
        ok_all &= st == 200
    check("chunks accepted", ok_all)
    st, _, d = jreq(f"/api/upload/status?upload_id={uid}")
    check("status complete", d.get("complete") is True, d)
    st, _, d = jreq(f"/api/upload/complete?upload_id={uid}", "POST", {})
    check("upload complete", d.get("status") == "success", d)
    st, hd, body = req(f"/int-test-{RUN_TAG}.bin", raw=False)
    check("uploaded file round-trips", st == 200 and body == payload,
          f"len={len(body)} want={len(payload)}")

    # range request
    st, hd, body = req(f"/int-test-{RUN_TAG}.bin", headers={"Range": "bytes=1000-1099"}, raw=True)
    check("range request 206", st == 206 and len(body) == 100 and
          body == payload[1000:1100] and hd.get("Content-Range", "").startswith("bytes 1000-1099/"),
          hd.get("Content-Range"))

    # resume: init again returns missing=[]
    st, _, d = jreq("/api/upload/init", "POST",
                    {"upload_id": uid, "filename": fname,
                     "size": len(payload), "chunk_size": 262144})
    check("resume init reports complete", d.get("missing") == [], d)

    # ---- ephemeral links ----
    st, _, d = jreq("/api/ephemeral/create", "POST",
                    {"path": f"/int-test-{RUN_TAG}.bin", "ttl_seconds": 600, "max_downloads": 1})
    url = d.get("url", "")
    path = url.replace(BASE, "") if url else ""
    check("ephemeral create", st == 200 and path.startswith("/e/"), d)
    st, hd, body = req(path, raw=True)
    check("ephemeral dl#1", st == 200 and body == payload and
          "attachment" in hd.get("Content-Disposition", ""))
    st, _, _ = req(path)
    check("ephemeral dl#2 -> 410", st == 410, st)

    # ---- risky files & sandbox preview ----
    boundary = "----psxboundary42"
    parts = []
    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"relpath\"\r\n\r\nsub/dir\r\n".encode())
    file_content = b"<script>alert(1)</script><h1>evil</h1>"
    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"page.html\"\r\n\r\n".encode()
                 + file_content + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    mp = b"".join(parts)
    st, hd, body = req("/api/upload/folder", "POST", mp,
                       {"Content-Type": f"multipart/form-data; boundary={boundary}"})
    d = json.loads(body)
    check("folder upload w/ relpath", st == 200 and d.get("files") == ["page.html"]
          and d.get("dir").replace("\\", "/") == "sub/dir", d)
    # direct GET must be octet-stream + attachment (never inline html)
    st, hd, _ = req("/sub/dir/page.html")
    check("risky ext forced attachment",
          hd.get("Content-Type") == "application/octet-stream" and
          "attachment" in hd.get("Content-Disposition", ""),
          f"{hd.get('Content-Type')} {hd.get('Content-Disposition')}")
    # preview wrapper + sandboxed raw
    st, hd, body = req("/sub/dir/page.html/preview")
    check("preview wrapper", st == 200 and b"<iframe" in body and b"sandbox" in body)
    csp = hd.get("Content-Security-Policy", "")
    check("preview CSP", "default-src 'none'" in csp, csp)
    st, hd, body = req("/raw/sub/dir/page.html")
    rcsp = hd.get("Content-Security-Policy", "")
    check("raw sandboxed CSP+attachment",
          "sandbox" in rcsp and "default-src 'none'" in rcsp and
          "attachment" in hd.get("Content-Disposition", ""), rcsp)

    # safe image preview stays inline in raw
    png = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000") + b"\x1f\x15\xc4\x89" + \
        bytes.fromhex("0000000d49444154789c626001000000ffff03000006000557bfabd40000000049454e44ae426082")
    mp2 = f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"px.png\"\r\n\r\n".encode() + png + b"\r\n" + f"--{boundary}--\r\n".encode()
    req("/api/upload/folder", "POST", mp2,
        {"Content-Type": f"multipart/form-data; boundary={boundary}"})
    st, hd, _ = req("/raw/px.png")
    check("safe image inline in /raw",
          st == 200 and hd.get("Content-Type") == "image/png" and
          "attachment" not in hd.get("Content-Disposition", ""))

    # ---- legacy upload + MKCOL + editor endpoints ----
    mpl = f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"old.txt\"\r\n\r\nhello old\r\n--{boundary}--\r\n".encode()
    st, _, body = req("/upload", "POST", mpl,
                      {"Content-Type": f"multipart/form-data; boundary={boundary}"})
    check("legacy upload", st == 200 and b"success" in body, body[:120])
    import uuid as _uuid
    unique_dir = "mkcol-" + _uuid.uuid4().hex[:8]
    st, _, body = req("/" + unique_dir, "MKCOL")
    d = json.loads(body)
    check("MKCOL create folder", st in (201,) and d["status"] == "success", d)
    st, _, body = req("/", "GET")
    check("new folder visible", unique_dir.encode() in body)

    # clipboard
    st, _, d = jreq("/save_clipboard", "POST", {"content": "clip-data", "path": "/"})
    check("clipboard save", d.get("status") == "success")
    st, _, d = jreq("/load_clipboard?path=%2F")
    check("clipboard load", d.get("content") == "clip-data", d)

    # create/save file endpoints
    st, _, d = jreq("/create_file", "POST", {"filename": "made.txt", "content": "abc"})
    check("create_file endpoint", d.get("status") == "success", d)
    st, _, d = jreq("/made.txt/save_file", "POST", {"content": "xyz"})
    check("save_file endpoint", d.get("status") == "success", d)
    st, _, body = req("/made.txt")
    check("saved content visible", body == b"xyz")

    # ---- tokens API ----
    st, _, d = jreq("/api/tokens", "POST", {"name": "ci", "max_uses": 5, "expires_hours": 1})
    tok = d.get("token", "")
    check("token create", st == 200 and tok.startswith("psx_"), d)
    st, _, d = jreq("/api/tokens")
    check("token list", any(t["full_token"] == tok for t in d.get("tokens", [])))
    st, _, d = jreq("/api/tokens", "DELETE", {"token": tok})
    check("token revoke", d.get("status") == "success")
    st, _, d = jreq("/api/tokens")
    check("revoked token gone", not any(t["full_token"] == tok for t in d.get("tokens", [])))

    # ---- auth login flow (local client bypasses, but endpoint must work) ----
    authfile = os.path.join(os.path.expanduser("~"), ".pyservx_auth.json")
    admin_pw = None
    st, hd, body = req("/login")
    check("login page renders", st == 200 and b"Login" in body)
    st, _, d = jreq("/api/auth/login", "POST", {"username": "admin", "password": "definitely-wrong"})
    check("bad login rejected", st == 401, (st, d))
    st, hd, d = jreq("/api/auth/login", "POST", {"username": "admin", "password": "knowntest123"})
    cookie = hd.get("Set-Cookie", "")
    check("good login sets cookie", st == 200 and "psx_session=" in cookie, (st, d))
    sid = cookie.split("psx_session=")[1].split(";")[0] if "psx_session=" in cookie else ""
    st, _, d = jreq("/api/auth/status", headers={"Cookie": f"psx_session={sid}"})
    check("session cookie accepted", d.get("authenticated") is True, d)
    st, _, d = jreq("/api/auth/logout", "POST", {}, headers={"Cookie": f"psx_session={sid}"})
    check("logout succeeds", d.get("status") == "success", d)

    # ---- REMOTE client simulation -----------------------------------
    # Second instance whose only 'local' network is documentation space,
    # so this loopback client is treated as REMOTE: full auth flow.
    run_remote_tests(tok_name="remote-test")

    # ---- bandwidth config endpoint ----
    st, _, d = jreq("/api/config/speed", "POST", {"limit": "64K"})
    check("speed limit set", d.get("status") == "success", d)
    st, _, d = jreq("/api/config/speed", "POST", {"limit": ""})
    check("speed limit cleared", d.get("status") == "success", d)

    # ---- webrtc signaling ----
    st, _, d = jreq("/webrtc/signal", "POST", {"room": "itest", "from": "peerA",
                                               "type": "offer", "data": {"sdp": "v=0"}})
    seq = d.get("seq")
    check("signal post", d.get("status") == "success", d)
    st, _, d = jreq("/webrtc/poll?room=itest&since=0&peer=peerB")
    check("signal poll", any(m["type"] == "offer" for m in d.get("messages", [])), d)
    st, _, body = req("/p2p")
    check("p2p page", st == 200 and b"RTCPeerConnection" in body)

    # ---- pages ----
    st, _, body = req("/tokens")
    check("tokens page", st == 200 and b"API Token" in body)
    st, _, body = req("/made.txt/edit")
    check("editor page", st == 200 and b"saveFile" in body)
    st, _, body = req("/notepad")
    check("notepad page", st == 200 and b"filename" in body)


def run_remote_tests(tok_name="remote"):
    """Boot a second instance where 127.0.0.1 counts as REMOTE."""
    global BASE
    old_base = BASE
    cfg_path = os.path.join(ROOT, ".pyservx_test_config.json")
    with open(cfg_path, "w") as f:
        json.dump({"local_networks": ["203.0.113.0/24"],
                   "shared_folder": os.path.join(os.path.expanduser("~"),
                                                 "Downloads", "PyServeX-Shared")}, f)
    env = dict(os.environ, PYTHONUNBUFFERED="1", PYSERVX_CONFIG=cfg_path)
    _p2 = _socket.socket(); _p2.bind(("127.0.0.1", 0))
    port2 = _p2.getsockname()[1]; _p2.close()
    proc = subprocess.Popen(
        [sys.executable, "-m", "pyservx.server", "--port", str(port2), "--no-qr"],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
    try:
        base2 = f"http://127.0.0.1:{port2}"
        if not wait_port(port2):
            time.sleep(0.5)
            try:
                os.set_blocking(proc.stdout.fileno(), False)
                out = proc.stdout.read() or b""
            except Exception:
                out = b""
            print("REMOTE-SIM SERVER FAILED:\n" + out.decode(errors="replace")[-1500:])
            sys.exit(2)

        def rreq(path, method="GET", data=None, headers=None):
            r = urllib.request.Request(base2 + path, data=data, method=method,
                                       headers=headers or {})
            try:
                resp = urllib.request.urlopen(r, timeout=15)
                return resp.status, dict(resp.headers), resp.read()
            except urllib.error.HTTPError as e:
                return e.code, dict(e.headers), e.read()

        st, hd, body = rreq("/")
        check("remote: login page served", st == 200 and b"Login" in body
              and "text/html" in hd.get("Content-Type", ""), st)

        st, _, body = rreq("/api/stats")
        d = json.loads(body) if st != 200 else {}
        check("remote: api blocked without auth", st == 401, (st, body[:120]))

        # bearer token path
        from pyservx.auth import AuthManager
        am2 = AuthManager({})
        tok = am2.create_api_token(name=tok_name, expires_hours=1)
        st, _, body = rreq("/api/stats",
                           headers={"Authorization": f"Bearer {tok}"})
        check("remote: bearer token grants access", st == 200, (st, body[:120]))

        # session cookie path
        st, hd, body = rreq("/api/auth/login", "POST",
                            json.dumps({"username": "admin",
                                        "password": "knowntest123"}).encode(),
                            {"Content-Type": "application/json"})
        cookie = hd.get("Set-Cookie", "")
        sid = cookie.split("psx_session=")[1].split(";")[0] \
            if "psx_session=" in cookie else ""
        check("remote: login works", st == 200 and sid, (st, body[:120]))
        st, _, body = rreq("/", headers={"Cookie": f"psx_session={sid}"})
        check("remote: session grants UI", st == 200 and b"PyServeX" in body, st)
        st, _, body = rreq("/api/stats", headers={"Cookie": "psx_session=bogus"})
        check("remote: bogus session rejected", st == 401, st)
    finally:
        proc.terminate()
        try:
            os.remove(cfg_path)
        except OSError:
            pass
    BASE = old_base


if __name__ == "__main__":
    main()
