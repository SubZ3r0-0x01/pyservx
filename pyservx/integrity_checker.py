#!/usr/bin/env python3
"""File Integrity Checker for PyServeX"""

import os
import hashlib
import json
from datetime import datetime

class IntegrityChecker:
    def __init__(self, check_file="./integrity.json"):
        self.check_file = check_file
        self.baselines = {}
        self.load_baseline()
    
    def load_baseline(self):
        """Load baseline hashes"""
        if os.path.exists(self.check_file):
            with open(self.check_file, "r") as f:
                self.baselines = json.load(f)
    
    def save_baseline(self):
        """Save baseline hashes"""
        with open(self.check_file, "w") as f:
            json.dump(self.baselines, f, indent=2)
    
    def calculate_hash(self, filepath):
        """Calculate SHA256 hash of file"""
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def add_to_baseline(self, filepath):
        """Add file to baseline"""
        if os.path.exists(filepath):
            self.baselines[filepath] = {
                "hash": self.calculate_hash(filepath),
                "added": datetime.now().isoformat()
            }
            self.save_baseline()
            return True
        return False
    
    def check_integrity(self):
        """Check integrity of all baselined files"""
        changes = []
        
        for filepath, baseline in self.baselines.items():
            if os.path.exists(filepath):
                current_hash = self.calculate_hash(filepath)
                if current_hash != baseline["hash"]:
                    changes.append({
                        "file": filepath,
                        "type": "MODIFIED",
                        "expected": baseline["hash"],
                        "actual": current_hash
                    })
            else:
                changes.append({
                    "file": filepath,
                    "type": "DELETED",
                    "expected": baseline["hash"]
                })
        
        return changes

if __name__ == "__main__":
    checker = IntegrityChecker()
    # Add a test file
    checker.add_to_baseline("./test.txt")
    print(json.dumps(checker.check_integrity(), indent=2))
