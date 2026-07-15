#!/usr/bin/env python3
"""Access Logger for PyServeX"""

import json
import os
from datetime import datetime
from collections import defaultdict

class AccessLogger:
    def __init__(self, log_file="./logs/access.json"):
        self.log_file = log_file
        self.logs = []
        self.stats = defaultdict(int)
        
        # Create log directory
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    def log_access(self, ip, path, status_code, method="GET"):
        """Log a file access"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "ip": ip,
            "path": path,
            "method": method,
            "status": status_code
        }
        
        self.logs.append(entry)
        self.stats[f"{method} {status_code}"] += 1
        
        # Write to file
        with open(self.log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
        
        return entry
    
    def get_stats(self):
        """Get access statistics"""
        return {
            "total_requests": len(self.logs),
            "by_status": dict(self.stats),
            "unique_ips": len(set(log["ip"] for log in self.logs))
        }
    
    def get_recent(self, limit=10):
        """Get recent access logs"""
        return self.logs[-limit:]

if __name__ == "__main__":
    logger = AccessLogger()
    # Simulate some access
    logger.log_access("192.168.1.100", "/files/test.txt", 200)
    logger.log_access("192.168.1.101", "/files/secret.pdf", 403)
    print(json.dumps(logger.get_stats(), indent=2))
