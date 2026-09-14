import hashlib
import os
import sys

import paramiko

HOST = os.environ.get("PSX_VPS_HOST", "")
USER = os.environ.get("PSX_VPS_USER", "admin")
PASSWORD = os.environ.get("PSX_VPS_PASSWORD", "")

ok = True


def check(name, cond, extra=""):
    global ok
    ok = ok and cond
    print(("PASS " if cond else "FAIL ") + name + (" | " + str(extra) if not cond else ""))


cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    cli.connect(HOST, 2222, username=USER, password=PASSWORD,
                allow_agent=False, look_for_keys=False, timeout=15)
    check("sftp login from VPS", True)
except Exception as e:
    check("sftp login from VPS", False, repr(e))
    sys.exit(1)

sftp = cli.open_sftp()

payload = os.urandom(256_000)
local = "/tmp/psx-vps-up.bin"
with open(local, "wb") as f:
    f.write(payload)
remote_name = f"from-{HOST}-vps.bin"
sftp.put(local, remote_name)

back = "/tmp/psx-vps-down.bin"
sftp.get(remote_name, back)
same = hashlib.sha256(payload).hexdigest() == \
    hashlib.sha256(open(back, "rb").read()).hexdigest()
check("put/get round-trip sha256", same)

st = sftp.stat(remote_name)
check("stat size", st.st_size == len(payload))

names = sftp.listdir(".")
check("listdir sees file", remote_name in names)

try:
    sftp.stat("/../../../../etc/passwd")
    check("traversal blocked", False, "escaped!")
except IOError:
    check("traversal blocked", True)

sftp.remove(remote_name)
check("cleanup remove", remote_name not in sftp.listdir("."))

sftp.close()
cli.close()
print("VPS-SFTP", "OK" if ok else "FAILED")
sys.exit(0 if ok else 1)
