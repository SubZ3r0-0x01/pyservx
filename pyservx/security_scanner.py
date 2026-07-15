#!/usr/bin/env python3
"""File Security Scanner for PyServeX"""

import os
import hashlib
import magic
from datetime import datetime

class FileSecurityScanner:
    def __init__(self, upload_dir="./uploads"):
        self.upload_dir = upload_dir
        self.findings = []
        self.malware_signatures = [
            b"MZ",  # PE executable
            b"\x7fELF",  # ELF executable
            b"#!/",  # Script files
        ]
    
    def scan_file(self, filepath):
        """Scan a single file for threats"""
        if not os.path.exists(filepath):
            return {"status": "error", "message": "File not found"}
        
        findings = []
        
        # Check file type
        try:
            file_type = magic.from_file(filepath)
            if "executable" in file_type.lower():
                findings.append({
                    "severity": "HIGH",
                    "type": "ExecutableFile",
                    "file": filepath,
                    "description": f"Executable file detected: {file_type}"
                })
        except:
            pass
        
        # Check file size
        size = os.path.getsize(filepath)
        if size > 100 * 1024 * 1024:  # 100MB
            findings.append({
                "severity": "MEDIUM",
                "type": "OversizedFile",
                "file": filepath,
                "description": f"File exceeds 100MB limit: {size} bytes"
            })
        
        # Calculate hash
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
            "type": file_type if 'file_type' in locals() else "unknown",
            "findings": findings
        }
    
    def scan_directory(self):
        """Scan all files in upload directory"""
        print(f"[*] Scanning directory: {self.upload_dir}")
        results = []
        
        if not os.path.exists(self.upload_dir):
            os.makedirs(self.upload_dir)
        
        for filename in os.listdir(self.upload_dir):
            filepath = os.path.join(self.upload_dir, filename)
            if os.path.isfile(filepath):
                result = self.scan_file(filepath)
                results.append(result)
                self.findings.extend(result.get("findings", []))
        
        return results
    
    def generate_report(self):
        """Generate security scan report"""
        return {
            "scanner": "FileSecurityScanner",
            "timestamp": datetime.now().isoformat(),
            "total_scanned": len(self.findings),
            "findings": self.findings
        }

if __name__ == "__main__":
    scanner = FileSecurityScanner()
    scanner.scan_directory()
    print(json.dumps(scanner.generate_report(), indent=2))
