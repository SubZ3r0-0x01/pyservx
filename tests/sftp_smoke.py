"""One-shot SFTP smoke test: password auth, upload/download, path jail."""
import os
import sys
import time
import socket
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pyservx.auth import AuthManager
from pyservx.ssh_server import SshServer

PASS, FAIL = [], []


def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name +
          (" | " + str(extra) if not cond and extra else ""))


def wait_port(port, timeout=15):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return True
        except OSError:
            time.sleep(0.2)
    return False


def main():
    am = AuthManager({})
    am.set_password("admin", "knowntest123")
    base = am.base_dir if hasattr(am, "base_dir") else \
        os.path.expanduser("~/Downloads/PyServeX-Shared")

    probe = socket.socket(); probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]; probe.close()

    srv = SshServer(am, base, port=port)
    real = srv.start()
    check("sftp server started", wait_port(port))

    import paramiko
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    # wrong password must fail
    try:
        cli.connect("127.0.0.1", port, username="admin",
                    password="wrongpw", allow_agent=False,
                    look_for_keys=False, timeout=10)
        check("bad sftp password rejected", False)
        cli.close()
    except paramiko.ssh_exception.AuthenticationException:
        check("bad sftp password rejected", True)
    except Exception as e:
        check("bad sftp password rejected", False, repr(e))

    # good password
    try:
        cli.connect("127.0.0.1", port, username="admin",
                    password="knowntest123", allow_agent=False,
                    look_for_keys=False, timeout=10)
        check("sftp password login ok", True)
    except Exception as e:
        check("sftp password login ok", False, repr(e))
        sys.exit(1)

    tag = os.urandom(4).hex()
    try:
        sftp = cli.open_sftp()
        names = sftp.listdir(".")
        check("listdir works", isinstance(names, list), names[:5])

        local = os.path.join(os.environ["TEMP"], f"sftp-up-{tag}.bin")
        payload = os.urandom(700_000)
        with open(local, "wb") as f:
            f.write(payload)
        remote_name = f"sftp-test-{tag}.bin"
        sftp.put(local, remote_name)

        back = os.path.join(os.environ["TEMP"], f"sftp-down-{tag}.bin")
        sftp.get(remote_name, back)
        same = open(back, "rb").read() == payload
        check("sftp put/get round-trip", same)

        st = sftp.stat(remote_name)
        check("stat size matches", st.st_size == len(payload),
              (st.st_size, len(payload)))

        dname = f"sftp-dir-{tag}"
        sftp.mkdir(dname)
        subs = sftp.listdir(".")
        check("mkdir visible", dname in subs)

        # traversal attempt: /../.. must stay jailed to base_dir
        escaped = None
        try:
            st = sftp.stat("/../../../../Windows/win.ini")
            escaped = st
        except IOError:
            pass
        check("traversal blocked in sftp", escaped is None,
              f"escaped={escaped is not None}")

        sftp.remove(remote_name)
        sftp.rmdir(dname)
        left = sftp.listdir(".")
        check("cleanup remove/rmdir", remote_name not in left
              and dname not in left)
        sftp.close()
    except Exception as e:
        import traceback; traceback.print_exc()
        check("sftp operations", False, repr(e))
    finally:
        cli.close()
        real.shutdown(); real.server_close()

    print(f"\n===== {len(PASS)} passed, {len(FAIL)} failed =====")
    if FAIL:
        print("FAILED:", *FAIL, sep="\n  ")
        sys.exit(1)


if __name__ == "__main__":
    main()
