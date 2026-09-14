import unittest
import os

from pyservx.throttling import parse_speed, RateLimiter
from pyservx.ephemeral import EphemeralLinkManager
from pyservx.auth import AuthManager
from pyservx.mcp_server import McpBridge
from pyservx.chunked_upload import ChunkedUploadManager
from pyservx.webrtc_signaling import SignalingHub
from pyservx.remote_sftp import RemoteSftpManager, RemoteSftpError
from pyservx.access_logger import AccessLogger
from pyservx.security_scanner import FileSecurityScanner
from pyservx.tunnel import TunnelManager
from pyservx.events import EventBus, format_sse
from pyservx.search_index import SearchIndex
from pyservx.trash import TrashManager
from pyservx.request_handler import FileRequestHandler


class TestParseSpeed(unittest.TestCase):
    def test_units(self):
        self.assertEqual(parse_speed("2M"), 2 * 1024 * 1024)
        self.assertEqual(parse_speed("500K"), 500 * 1024)
        self.assertEqual(parse_speed("1G"), 1024 ** 3)
        self.assertEqual(parse_speed("1024"), 1024)
        self.assertIsNone(parse_speed(""))
        self.assertIsNone(parse_speed(None))
        self.assertIsNone(parse_speed("0"))
        with self.assertRaises(ValueError):
            parse_speed("abc")
        with self.assertRaises(ValueError):
            parse_speed("5Z")


class TestRateLimiter(unittest.TestCase):
    def test_set_rate(self):
        rl = RateLimiter(1024)
        rl.set_rate(2048)
        self.assertEqual(rl.rate, 2048)

    def test_consume_small(self):
        rl = RateLimiter(10_000_000)  # fast enough to not stall test
        rl.consume(1000)


class TestEphemeral(unittest.TestCase):
    def setUp(self):
        import tempfile, os
        self.dir = tempfile.mkdtemp()
        self.file = os.path.join(self.dir, "secret.txt")
        with open(self.file, "w") as f:
            f.write("data")

    def test_single_use(self):
        m = EphemeralLinkManager()
        token = m.create_link(self.file, ttl_seconds=60, max_downloads=1)
        self.assertIsNotNone(token)
        first = m.resolve(token)
        self.assertIsNotNone(first)
        self.assertTrue(first["exhausted"])
        self.assertIsNone(m.resolve(token))          # second use must be gone
        m.shutdown()

    def test_expiry(self):
        import time as _t
        m = EphemeralLinkManager()
        token = m.create_link(self.file, ttl_seconds=1, max_downloads=99)
        entry = m.links[token]
        entry["expires_at"] = _t.time() - 1
        self.assertIsNone(m.resolve(token))
        m.shutdown()

    def test_missing_file(self):
        import os
        m = EphemeralLinkManager()
        self.assertIsNone(m.create_link(os.path.join(self.dir, "nope.bin")))
        m.shutdown()


class TestAuth(unittest.TestCase):
    def setUp(self):
        import tempfile, os
        self.tmp = tempfile.mkdtemp()
        from pathlib import Path
        self._old_store = AuthManager.__module__  # keep linters calm
        import pyservx.auth as auth_mod
        self.auth_mod_path = auth_mod.AUTH_STORE
        auth_mod.AUTH_STORE = os.path.join(self.tmp, "auth.json")
        self.auth = AuthManager({"tokens_db": os.path.join(self.tmp, "tok.db")})

    def tearDown(self):
        import pyservx.auth as auth_mod
        auth_mod.AUTH_STORE = self.auth_mod_path

    def test_local_bypass(self):
        for ip in ("127.0.0.1", "192.168.1.50", "10.0.0.7", "172.16.5.5",
                   "::1", "169.254.1.2"):
            ok, is_local, ident = self.auth.authenticate_request(ip)
            self.assertTrue(ok, ip)
            self.assertTrue(is_local, ip)

    def test_remote_requires_auth(self):
        ok, _, _ = self.auth.authenticate_request("203.0.113.9")
        self.assertFalse(ok)

    def test_token_flow(self):
        tok = self.auth.create_api_token(name="t", expires_hours=1)
        info = self.auth.validate_api_token(tok)
        self.assertIsNotNone(info)
        ok, is_local, ident = self.auth.authenticate_request(
            "203.0.113.9", bearer_token=tok)
        self.assertTrue(ok)
        self.assertFalse(is_local)
        self.auth.revoke_api_token(tok)
        self.assertIsNone(self.auth.validate_api_token(tok))

    def test_password_login_and_session(self):
        u = next(iter(self.auth.users))
        self.assertFalse(self.auth.verify_login(u, "wrong"))
        pw_file = open(self.auth_mod_path) if False else None
        # create known password via API
        self.auth.set_password(u, "s3cret!")
        self.assertTrue(self.auth.verify_login(u, "s3cret!"))
        sid = self.auth.create_session(u)
        ok, is_local, ident = self.auth.authenticate_request(
            "8.8.8.8", session_cookie=sid)
        self.assertTrue(ok)


class TestMcp(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.dir = tempfile.mkdtemp()
        self.bridge = McpBridge(self.dir)

    def call(self, obj):
        import json
        return json.loads(json.dumps(
            self.bridge.handle_request(__import__("json").dumps(obj).encode())))

    def test_initialize_and_tools_list(self):
        r = self.call({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        self.assertEqual(r["id"], 1)
        self.assertIn("serverInfo", r["result"])
        r = self.call({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        names = [t["name"] for t in r["result"]["tools"]]
        for n in ("list_files", "read_file", "write_file",
                  "upload_file", "search_files", "server_info"):
            self.assertIn(n, names)

    def test_write_read_search_traversal(self):
        self.call({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                   "params": {"name": "write_file",
                              "arguments": {"path": "docs/a.txt",
                                            "content": "hello"}}})
        r = self.call({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                       "params": {"name": "read_file",
                                  "arguments": {"path": "docs/a.txt"}}})
        inner = __import__("json").loads(r["result"]["content"][0]["text"])
        self.assertEqual(inner["content"], "hello")
        r = self.call({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                       "params": {"name": "search_files",
                                  "arguments": {"query": "a.txt"}}})
        self.assertTrue(any("a.txt" in m for m in
                            r["result"]["result"]["matches"]))
        bad = self.call({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                         "params": {"name": "read_file",
                                    "arguments": {"path": "../../../etc/passwd"}}})
        self.assertIn("error", bad)

    def test_unknown_method(self):
        r = self.call({"jsonrpc": "2.0", "id": 9, "method": "bogus"})
        self.assertIn("error", r)


class TestChunkedUpload(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.base = tempfile.mkdtemp()
        self.mgr = ChunkedUploadManager(self.base)

    def test_roundtrip_and_resume(self):
        payload = b"x" * (300_000)
        st = self.mgr.init_upload("u1", "big.bin", len(payload), 100_000)
        self.assertEqual(st["total"], 3)
        res = self.mgr.receive_chunk("u1", 0, payload[0:100_000])
        res = self.mgr.receive_chunk("u1", 2, payload[200_000:])
        stat = self.mgr.status("u1")
        self.assertEqual(sorted(stat["missing"]), [1])
        done = self.mgr.complete_upload("u1")
        self.assertIn("error", done)              # still missing chunk 1
        self.mgr.receive_chunk("u1", 1, payload[100_000:200_000])
        done = self.mgr.complete_upload("u1")
        self.assertEqual(done["status"], "success")
        with open(__import__("os").path.join(self.base, "big.bin"), "rb") as f:
            self.assertEqual(f.read(), payload)

    def test_abort(self):
        self.mgr.init_upload("u2", "f.txt", 10, 5)
        out = self.mgr.abort_upload("u2")
        self.assertTrue(out["aborted"])
        self.assertIsNone(self.mgr.status("u2"))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.base, ignore_errors=True)
        shutil.rmtree(self.mgr.staging_root, ignore_errors=True)


class TestLoginLockout(unittest.TestCase):
    def setUp(self):
        import tempfile, os
        self.tmp = tempfile.mkdtemp()
        self.auth = AuthManager({"tokens_db": os.path.join(self.tmp, "tok.db")})

    def test_allowed_until_threshold(self):
        for _ in range(4):
            self.auth.record_login_failure("1.2.3.4")
            allowed, _ = self.auth.login_status("1.2.3.4")
            self.assertTrue(allowed)
        self.auth.record_login_failure("1.2.3.4")
        allowed, retry = self.auth.login_status("1.2.3.4")
        self.assertFalse(allowed)
        self.assertGreater(retry, 0)

    def test_reset(self):
        self.auth.record_login_failure("5.6.7.8")
        self.auth.reset_login_failures("5.6.7.8")
        allowed, _ = self.auth.login_status("5.6.7.8")
        self.assertTrue(allowed)

    def test_ips_independent(self):
        self.auth.record_login_failure("9.9.9.9")
        self.auth.record_login_failure("9.9.9.9")
        allowed, _ = self.auth.login_status("9.9.9.9")
        self.assertTrue(allowed)          # under the cap
        allowed2, _ = self.auth.login_status("8.8.8.8")
        self.assertTrue(allowed2)         # untouched IP never affected

    def test_session_csrf(self):
        sid = self.auth.create_session("admin")
        token = self.auth.session_csrf(sid)
        self.assertTrue(token and len(token) > 16)
        self.assertIsNone(self.auth.session_csrf("bogus"))


class TestSignaling(unittest.TestCase):
    def setUp(self):
        self.hub = SignalingHub()

    def test_offer_poll_roundtrip(self):
        self.hub.post("r1", "alice", "offer", {"sdp": "v=0"})
        msgs, _ = self.hub.poll("r1", 0, "alice")
        self.assertEqual(len(msgs), 0)    # sender doesn't see own message
        msgs, _ = self.hub.poll("r1", 0, "bob")
        self.assertEqual(msgs[0]["type"], "offer")
        self.assertEqual(msgs[0]["data"], {"sdp": "v=0"})

    def test_join_peer_cap(self):
        from unittest import mock
        with mock.patch("pyservx.webrtc_signaling.MAX_PEERS_PER_ROOM", 2):
            self.hub.post("r2", "p1", "join", {})
            self.hub.post("r2", "p2", "join", {})
            with self.assertRaises(Exception) as ctx:
                self.hub.post("r2", "p3", "join", {})
            self.assertEqual(ctx.exception.status, 503)

    def test_room_cap(self):
        from unittest import mock
        with mock.patch("pyservx.webrtc_signaling.MAX_ROOMS", 3):
            for i in range(3):
                self.hub.post("room%d" % i, "x", "join", {})
            with self.assertRaises(Exception) as ctx:
                self.hub.post("room3", "x", "join", {})
            self.assertEqual(ctx.exception.status, 503)

    def test_rate_limit(self):
        from unittest import mock
        with mock.patch("pyservx.webrtc_signaling.MSG_RATE_LIMIT", 2):
            self.hub.post("r3", "alice", "offer", {})
            self.hub.post("r3", "alice", "answer", {})
            with self.assertRaises(Exception) as ctx:
                self.hub.post("r3", "alice", "candidate", {"candidate": "x"})
            self.assertEqual(ctx.exception.status, 429)

    def test_payload_size_cap(self):
        from unittest import mock
        with mock.patch("pyservx.webrtc_signaling.MAX_MSG_BYTES", 8):
            with self.assertRaises(Exception) as ctx:
                self.hub.post("r4", "alice", "offer", {"sdp": "x" * 50})
            self.assertEqual(ctx.exception.status, 413)

    def test_relay_candidate_rewrite(self):
        self.hub.post("r5", "carol", "candidate",
                      {"candidate":
                       "candidate:1 1 udp 2122260223 192.168.1.50 60000 typ host",
                       "sdpMid": "0", "sdpMLineIndex": 0},
                      client_host="203.0.113.7")
        msgs, _ = self.hub.poll("r5", 0, "alice")
        self.assertIn("203.0.113.7 60000", msgs[0]["data"]["candidate"])

    def test_public_candidate_untouched(self):
        self.hub.post("r6", "carol", "candidate",
                      {"candidate":
                       "candidate:1 1 udp 2122260223 8.8.8.8 60000 typ host"},
                      client_host="203.0.113.7")
        msgs, _ = self.hub.poll("r6", 0, "alice")
        self.assertIn("8.8.8.8 60000", msgs[0]["data"]["candidate"])

    def test_invalid_ids_rejected(self):
        with self.assertRaises(Exception):
            self.hub.post("r", "x" * 200, "join", {})


class TestAccessLogger(unittest.TestCase):
    def test_rotation(self):
        import tempfile, os
        tmp = tempfile.mkdtemp()
        try:
            path = os.path.join(tmp, "access.jsonl")
            logger = AccessLogger(path)
            logger.log_access("1.1.1.1", "/a", 200)
            self.assertEqual(logger.get_stats()["total_requests"], 1)
            logger.rotate()
            self.assertTrue(any(f.startswith("access.") and f.endswith(".jsonl")
                                for f in os.listdir(tmp)))
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)


class TestSecurityScanner(unittest.TestCase):
    def test_script_and_magic_detection(self):
        import tempfile, os
        tmp = tempfile.mkdtemp()
        try:
            sh = os.path.join(tmp, "run.sh")
            with open(sh, "w") as f:
                f.write("#!/bin/sh\necho hi\n")
            dll = os.path.join(tmp, "payload.bin")
            with open(dll, "wb") as f:
                f.write(b"MZ\x90\x00fakepe")
            txt = os.path.join(tmp, "notes.txt")
            with open(txt, "w") as f:
                f.write("plain text")
            s = FileSecurityScanner(tmp)
            res_sh = s.scan_file(sh)
            res_dll = s.scan_file(dll)
            res_txt = s.scan_file(txt)
            self.assertTrue(res_sh["findings"], res_sh)
            self.assertTrue(any(f["type"] == "ExecutableFile"
                                for f in res_dll["findings"]) or
                            res_dll["findings"])
            self.assertEqual(res_txt["findings"], [])
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)


class TestRemoteSftpManager(unittest.TestCase):
    class _FakeStat:
        def __init__(self, mode, size):
            self.st_mode = mode
            self.st_size = size

    class _FakeSftp:
        def __init__(self):
            self.files = {}

        def normalize(self, path):
            return path

        def stat(self, path):
            if path == "/remote/file.txt":
                return TestRemoteSftpManager._FakeStat(
                    __import__("stat").S_IFREG, 1024)
            if path == "/remote/dir":
                return TestRemoteSftpManager._FakeStat(
                    __import__("stat").S_IFDIR, 0)
            raise IOError("no such file: %s" % path)

        def file(self, path, mode):
            if path == "/remote/file.txt":
                return None   # read handle simulated by caller
            buf = b""
            fh = TestRemoteSftpManager._FakeFile(buf if mode == "rb" else None)
            self.files.setdefault(path, []).append(fh)
            return fh

        def close(self):
            pass

    class _FakeFile:
        def __init__(self, data=None):
            self.data = data

        def write(self, b):
            pass

        def close(self):
            pass

    def _mgr_with_session(self):
        mgr = RemoteSftpManager()
        fake = self._FakeSftp()
        mgr._sessions["s1"] = {"cli": object(), "sftp": fake,
                               "last_used": 0}
        return mgr, fake

    def test_open_download_rejects_dir(self):
        mgr, _ = self._mgr_with_session()
        with self.assertRaises(RemoteSftpError):
            mgr.open_download("s1", "/remote/dir")

    def test_unknown_session(self):
        mgr = RemoteSftpManager()
        with self.assertRaises(RemoteSftpError):
            mgr.open_download("nope", "/x")

    def test_reap_idle_closes_stale(self):
        import time
        mgr, _ = self._mgr_with_session()
        mgr._sessions["s1"]["last_used"] = 0   # stale
        mgr._sessions["s2"] = {"cli": object(), "sftp": self._FakeSftp(),
                               "last_used": time.time() + 1000}  # fresh
        reaped = mgr.reap_idle()
        self.assertEqual(reaped, 1)
        self.assertNotIn("s1", mgr._sessions)
        self.assertIn("s2", mgr._sessions)


class TestTunnelWatchdog(unittest.TestCase):
    def test_drops_url_when_process_dies(self):
        tun = TunnelManager(9999)
        tun.url = "https://x.trycloudflare.com"
        tun.provider = "cloudflared"
        tun._proc = type("P", (), {"poll": lambda self: 0})()  # dead
        exited = tun._watchdog()
        self.assertTrue(exited)
        self.assertIsNone(tun.url)

    def test_stop_releases_cleanly(self):
        tun = TunnelManager(9999)
        tun.url = "https://live.trycloudflare.com"
        tun._proc = type("P", (), {"poll": lambda self: None})()
        tun._stop.set()
        exited = tun._watchdog()   # returns fast, proc still "alive"
        self.assertFalse(exited)
        self.assertIsNone(tun.url)  # url cleared because loop ended


class TestHandlerHardening(unittest.TestCase):
    def setUp(self):
        import tempfile, threading, http.server, http.client
        self.tmp = tempfile.mkdtemp()
        FileRequestHandler.base_dir = self.tmp
        FileRequestHandler.auth = None
        FileRequestHandler.auth_enabled = False
        FileRequestHandler.remote_bridge_enabled = False
        FileRequestHandler.stats = None
        FileRequestHandler.signaling = None
        FileRequestHandler.ephemeral_mgr = None
        FileRequestHandler.chunk_mgr = None
        FileRequestHandler.rate_limiter = None
        from pyservx.events import EventBus
        from pyservx.search_index import SearchIndex
        FileRequestHandler.events = EventBus()
        FileRequestHandler.search = SearchIndex(self.tmp)
        FileRequestHandler.search.force_reindex()
        FileRequestHandler.trash = TrashManager(
            self.tmp,
            data_dir=os.path.join(self.tmp, "..", ".trash_test_" + str(os.getpid())),
            versions_root=os.path.join(self.tmp, "..", ".vers_test_" + str(os.getpid())))
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0),
                                                 FileRequestHandler)
        self.server = server
        self.port = server.server_address[1]
        threading.Thread(target=server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)
        shutil.rmtree(os.path.join(self.tmp, "..", ".trash_test_" + str(os.getpid())),
                      ignore_errors=True)
        shutil.rmtree(os.path.join(self.tmp, "..", ".vers_test_" + str(os.getpid())),
                      ignore_errors=True)

    def _request(self, method, path, body=b"", headers=None):
        import http.client
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        c.request(method, path, body=body, headers=headers or {})
        r = c.getresponse()
        data = r.read()
        c.close()
        return r.status, data, dict(r.getheaders())

    def test_stats_ping(self):
        st, body, _ = self._request("POST", "/api/stats/ping", b"{}",
                                    {"Content-Type": "application/json"})
        self.assertEqual(st, 200)

    def test_cross_origin_post_blocked(self):
        st, _, _ = self._request("POST", "/api/stats/ping", b"{}",
                                 {"Origin": "https://evil.example",
                                  "Host": "127.0.0.1"})
        self.assertEqual(st, 403)

    def test_same_origin_post_allowed(self):
        st, _, _ = self._request("POST", "/api/stats/ping", b"{}",
                                 {"Origin": "http://127.0.0.1",
                                  "Host": "127.0.0.1"})
        self.assertEqual(st, 200)

    def test_remote_bridge_off_by_default(self):
        st, body, _ = self._request("GET", "/api/remote/download?sid=1&path=/")
        self.assertEqual(st, 403)

    def test_scan_endpoint(self):
        import json
        st, body, _ = self._request("POST", "/api/scan", b"{}")
        self.assertEqual(st, 200)
        d = json.loads(body)
        self.assertEqual(d["status"], "success")
        self.assertIn("scanner", d["report"])

    def test_search_endpoint(self):
        import json, io
        io.open(os.path.join(self.tmp, "needle.test"), "w").write("quasar needle")
        FileRequestHandler.search.force_reindex()
        st, body, _ = self._request("GET", "/api/search?q=quasar")
        self.assertEqual(st, 200)
        d = json.loads(body)
        self.assertEqual(d["status"], "success")
        self.assertTrue(any(r["name"] == "needle.test" for r in d["results"]))

    def test_trash_move_list_restore_via_api(self):
        import json, io
        io.open(os.path.join(self.tmp, "doomed.txt"), "w").write("bye")
        st, body, _ = self._request(
            "POST", "/api/trash/move",
            json.dumps({"path": "/doomed.txt"}).encode(),
            {"Content-Type": "application/json"})
        self.assertEqual(st, 200)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "doomed.txt")))
        st, body, _ = self._request("GET", "/api/trash/list")
        d = json.loads(body)
        self.assertEqual(d["count"], 1)
        self.assertEqual(d["entries"][0]["name"], "doomed.txt")
        st, body, _ = self._request(
            "POST", "/api/trash/restore",
            json.dumps({"path": "/doomed.txt"}).encode(),
            {"Content-Type": "application/json"})
        self.assertEqual(st, 200)
        self.assertTrue(os.path.exists(os.path.join(self.tmp, "doomed.txt")))

    def test_trash_move_traversal_rejected(self):
        import json
        st, body, _ = self._request(
            "POST", "/api/trash/move",
            json.dumps({"path": "/../../etc/passwd"}).encode(),
            {"Content-Type": "application/json"})
        self.assertEqual(st, 400)

    def test_version_save_list_restore_via_api(self):
        import json, io
        fpath = os.path.join(self.tmp, "doc.txt")
        io.open(fpath, "w").write("v0")
        st, body, _ = self._request(
            "POST", "/api/versions/save",
            json.dumps({"path": "/doc.txt"}).encode(),
            {"Content-Type": "application/json"})
        self.assertEqual(st, 200)
        io.open(fpath, "w").write("v1")
        st, body, _ = self._request("GET", "/api/versions/list?path=/doc.txt")
        d = json.loads(body)
        self.assertEqual(d["status"], "success")
        self.assertGreaterEqual(d["count"], 1)
        st, body, _ = self._request(
            "POST", "/api/versions/restore",
            json.dumps({"path": "/doc.txt",
                        "version": d["versions"][0]["version"]}).encode(),
            {"Content-Type": "application/json"})
        self.assertEqual(st, 200)
        with open(fpath) as f:
            self.assertEqual(f.read(), "v0")

    def test_event_stream_endpoint_sends_frames(self):
        FileRequestHandler.events.publish("file", {"path": "/x",
                                                   "action": "created"})
        import http.client
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        c.request("GET", "/api/events")
        r = c.getresponse()
        self.assertEqual(r.status, 200)
        self.assertEqual(r.getheader("Content-Type"),
                         "text/event-stream; charset=utf-8")
        head = r.read(1)
        head += r.fp.readline()
        head += r.fp.readline()
        c.close()
        self.assertIn(b"event: file", head)
        self.assertIn(b"action", head)


class TestEventBus(unittest.TestCase):
    def test_publish_subscribe(self):
        import queue as q
        bus = EventBus(max_history=0)
        sub = bus.subscribe()
        bus.publish("file", {"path": "/x", "action": "created"})
        etype, payload = sub.get_nowait()
        self.assertEqual((etype, payload),
                         ("file", {"path": "/x", "action": "created"}))
        bus.unsubscribe(sub)
        self.assertEqual(bus.subscriber_count(), 0)

    def test_history_replay_for_late_subscriber(self):
        bus = EventBus(max_history=2)
        bus.publish("file", {"path": "/a", "action": "created"})
        bus.publish("stats", {"requests": 3})
        bus.publish("file", {"path": "/b", "action": "deleted"})
        sub = bus.subscribe()
        events = []
        while True:
            try:
                events.append(sub.get_nowait())
            except Exception:
                break
        self.assertEqual(len(events), 2)          # oldest dropped, 2 replayed
        self.assertEqual(events[0][0], "stats")
        self.assertEqual(events[1][1]["path"], "/b")
        bus.unsubscribe(sub)

    def test_sse_format(self):
        frame = format_sse("file", {"path": "/x", "action": "created"})
        self.assertTrue(frame.startswith(b"event: file\n"))
        self.assertIn(b"data:", frame)
        self.assertTrue(frame.endswith(b"\n\n"))
        big = format_sse("stats", {"blob": "x" * 12000})
        self.assertTrue(big.endswith(b"\n\n"))

    def test_slow_consumer_drops_instead_of_blocking(self):
        bus = EventBus(max_history=0)
        sub = bus.subscribe(maxsize=1)
        for i in range(5):
            bus.publish("file", {"n": i})
        # queue keeps at most maxsize items; publisher never blocked
        self.assertLessEqual(sub.qsize(), 1)
        bus.unsubscribe(sub)


class TestSearchIndex(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.dir = tempfile.mkdtemp()
        with open(os.path.join(self.dir, "alpha_report.txt"), "w") as f:
            f.write("The quick brown fox jumps over the lazy zodiacal quasar.")
        with open(os.path.join(self.dir, "notes.md"), "w") as f:
            f.write("shopping list: milk, eggs, quasar bread")
        os.makedirs(os.path.join(self.dir, "sub"))
        with open(os.path.join(self.dir, "sub", "deep.py"), "w") as f:
            f.write("def quasar_helper():\n    pass\n")
        self.idx = SearchIndex(self.dir)
        self.idx.force_reindex()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_name_search(self):
        hits = self.idx.search("alpha")
        self.assertTrue(any(h["name"] == "alpha_report.txt" for h in hits))
        self.assertTrue(self.idx.ready)
        self.assertGreaterEqual(self.idx.indexed_files, 3)

    def test_content_search_with_snippet(self):
        hits = self.idx.search("zodiacal")
        self.assertTrue(hits)
        top = hits[0]
        self.assertIn("zodiacal", top["snippet"].lower())

    def test_deep_content_search(self):
        hits = self.idx.search("helper")
        self.assertTrue(any(h["path"].endswith("sub/deep.py") for h in hits))

    def test_empty_query_returns_nothing(self):
        self.assertEqual(self.idx.search(""), [])
        self.assertEqual(self.idx.search("   "), [])

    def test_deleted_file_pruned(self):
        import shutil
        hits = self.idx.search("eggs")
        self.assertTrue(hits)
        os.remove(os.path.join(self.dir, "notes.md"))
        self.idx.force_reindex()
        self.assertEqual(self.idx.search("eggs"), [])

    def test_searches_are_thread_safe_from_start(self):
        self.idx.start()          # bg thread running while we query
        try:
            for _ in range(30):
                self.idx.search("quasar")
        finally:
            self.idx.stop()


class TestTrashManager(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.dir = tempfile.mkdtemp()
        self.trash_dir = tempfile.mkdtemp()
        self.vers_dir = tempfile.mkdtemp()
        self.mg = TrashManager(self.dir, data_dir=self.trash_dir,
                               versions_root=self.vers_dir)
        self.fpath = os.path.join(self.dir, "victim.txt")
        with open(self.fpath, "w") as f:
            f.write("original")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.dir, ignore_errors=True)
        shutil.rmtree(self.trash_dir, ignore_errors=True)
        shutil.rmtree(self.vers_dir, ignore_errors=True)

    def test_move_restore_roundtrip(self):
        self.mg.move("victim.txt")
        self.assertFalse(os.path.exists(self.fpath))
        self.assertEqual(len(self.mg.list()), 1)
        self.mg.restore("victim.txt")
        self.assertTrue(os.path.exists(self.fpath))
        with open(self.fpath) as f:
            self.assertEqual(f.read(), "original")
        self.assertEqual(self.mg.list(), [])

    def test_traversal_rejected(self):
        with self.assertRaises(ValueError):
            self.mg._resolve("../../etc/passwd")
        with self.assertRaises(ValueError):
            self.mg._resolve(os.path.abspath(os.path.join(self.dir, "..")))

    def test_empty(self):
        self.mg.move("victim.txt")
        self.mg.empty()
        self.assertEqual(self.mg.list(), [])

    def test_versions_pruned_to_limit(self):
        for i in range(5):
            with open(self.fpath, "w") as f:
                f.write(f"v{i}")
            self.mg.save_version("victim.txt", max_copies=3)
        versions = self.mg.list_versions("victim.txt")
        self.assertEqual(len(versions), 3)

    def test_version_save_and_restore(self):
        self.mg.save_version("victim.txt")
        with open(self.fpath, "w") as f:
            f.write("changed")
        versions = self.mg.list_versions("victim.txt")
        self.assertTrue(versions)
        self.mg.restore_version("victim.txt", versions[0]["version"])
        with open(self.fpath) as f:
            self.assertEqual(f.read(), "original")

    def test_purge_expired(self):
        self.mg.move("victim.txt")
        tid = next(iter(self.mg._entries))
        self.mg._entries[tid]["trashed_at"] = "2000-01-01T00:00:00"
        self.mg._purge_expired(3600)
        self.assertEqual(self.mg.list(), [])


if __name__ == '__main__':
    unittest.main()
