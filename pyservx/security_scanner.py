#!/usr/bin/env python3
"""File Security Scanner for PyServeX.

Detection is stdlib-only: executable content is flagged via magic bytes
(MZ / ELF / shebang) and risky extensions. The optional `python-magic`
package upgrades type detection when installed.
"""

import hashlib
import json
import os
from datetime import datetime

try:
    import magic as _magic
except ImportError:
    _magic = None

RISKY_EXTENSIONS = {
    ".exe", ".msi", ".dll", ".scr", ".com", ".bat", ".cmd",
    ".sh", ".bash", ".zsh", ".ps1", ".psm1", ".vbs", ".vbe",
    ".wsf", ".hta", ".jar", ".apk", ".pyc", ".so", ".bin",
}

EXEC_MAGIC = ((b"MZ", "PE executable"), (b"\x7fELF", "ELF executable"),
              (b"#!", "script"))


class FileSecurityScanner:
    def __init__(self, upload_dir="./uploads"):
        self.upload_dir = upload_dir
        self.findings = []

    def _magic_type(self, filepath):
        if _magic is not None:
            try:
                return _magic.from_file(filepath)
            except Exception:
                return ""
        with open(filepath, "rb") as f:
            head = f.read(4)
        for sig, name in EXEC_MAGIC:
            if head.startswith(sig):
                return name
        return ""

    def scan_file(self, filepath):
        """Scan a single file for threats, returning a findings dict."""
        if not os.path.exists(filepath):
            return {"status": "error", "message": "File not found"}

        findings = []
        file_type = self._magic_type(filepath)
        if file_type:
            findings.append({
                "severity": "HIGH",
                "type": "ExecutableFile",
                "file": filepath,
                "description": "Executable content detected: %s" % file_type,
            })

        ext = os.path.splitext(filepath)[1].lower()
        if ext in RISKY_EXTENSIONS:
            findings.append({
                "severity": "MEDIUM",
                "type": "RiskyExtension",
                "file": filepath,
                "description": "Risky file extension served as download-only: %s" % ext,
            })

        size = os.path.getsize(filepath)
        if size > 100 * 1024 * 1024:  # 100MB
            findings.append({
                "severity": "MEDIUM",
                "type": "OversizedFile",
                "file": filepath,
                "description": "File exceeds 100MB limit: %d bytes" % size,
            })

        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        file_hash = sha256_hash.hexdigest()

        return {
            "status": "scanned",
            "file": filepath,
            "hash": file_hash,
            "size": size,
            "type": file_type or "unknown",
            "findings": findings,
        }

    def scan_directory(self, max_files=500):
        """Scan all files in the upload directory (non-recursive)."""
        results = []
        if not os.path.exists(self.upload_dir):
            return results
        for i, filename in enumerate(os.listdir(self.upload_dir)):
            if i >= max_files:
                break
            filepath = os.path.join(self.upload_dir, filename)
            if os.path.isfile(filepath):
                result = self.scan_file(filepath)
                results.append(result)
                self.findings.extend(result.get("findings", []))
        return results

    def generate_report(self):
        """Generate security scan report."""
        return {
            "scanner": "FileSecurityScanner",
            "timestamp": datetime.now().isoformat(),
            "total_scanned": len(self.findings),
            "findings": self.findings,
        }


if __name__ == "__main__":
    scanner = FileSecurityScanner()
    scanner.scan_directory()
    print(json.dumps(scanner.generate_report(), indent=2))