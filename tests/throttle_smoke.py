"""One-shot throttle check: global token bucket caps download speed."""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

SHARED = os.path.join(os.path.expanduser("~"), "Downloads", "PyServeX-Shared")
TAG = os.urandom(3).hex()
FNAME = f"throttle-{TAG}.bin"
RATE = 200 * 1024          # bytes/sec
SIZE = RATE * 3            # bucket(1x) + 2 seconds of refill

probe = socket.socket(); probe.bind(("127.0.0.1", 0))
PORT = probe.getsockname()[1]; probe.close()

with open(os.path.join(SHARED, FNAME), "wb") as f:
    f.write(os.urandom(SIZE))

env = dict(os.environ, PYTHONUNBUFFERED="1")
proc = subprocess.Popen(
    [sys.executable, "-m", "pyservx.server", "--port", str(PORT),
     "--no-qr", "--limit-speed", "200K"],
    cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)

ok = False
try:
    t0 = time.time()
    while time.time() - t0 < 15 and not ok:
        try:
            with socket.create_connection(("127.0.0.1", PORT), timeout=1):
                ok = True
        except OSError:
            time.sleep(0.2)
    assert ok, "server did not start"

    t0 = time.time()
    body = urllib.request.urlopen(
        f"http://127.0.0.1:{PORT}/{FNAME}", timeout=60).read()
    elapsed = time.time() - t0

    print(f"downloaded {len(body)} B in {elapsed:.2f}s "
          f"(avg {len(body)/max(elapsed, 0.001)/1024:.0f} KB/s)")
    assert len(body) == SIZE, "content mismatch"
    # unthrottled loopback would be <0.3s; bucket allows RATE instantly,
    # remaining 2*RATE must take >= ~1.7s even with scheduling slop
    assert elapsed >= 1.5, f"throttle not effective ({elapsed:.2f}s)"
    assert elapsed <= 12, f"throttle too slow ({elapsed:.2f}s)"
    print("PASS throttle caps speed")
finally:
    proc.terminate()
    try:
        os.remove(os.path.join(SHARED, FNAME))
    except OSError:
        pass
print("THROTTLE SMOKE OK")
