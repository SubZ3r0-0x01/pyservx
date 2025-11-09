#!/usr/bin/env python3
# Enhanced Python HTTP Server Developed by Subz3r0x01
# GitHub: https://github.com/SubZ3r0-0x01/pyservx
# Unified Version with All Features

import os
import socketserver
import threading
import signal
import sys
import logging
import socket
import json
import argparse
import qrcode
import sqlite3
from datetime import datetime
from . import request_handler

# Configure logging for debugging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

PORT = 8088
CONFIG_FILE = os.path.expanduser("~/.pyservx_config.json")
ANALYTICS_DB = os.path.expanduser("~/.pyservx_analytics.db")

class AnalyticsManager:
    """Manage analytics and usage statistics"""
    
    def __init__(self, db_path):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize analytics database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # File access logs
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS file_access (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT NOT NULL,
                action TEXT NOT NULL,
                ip_address TEXT,
                user_agent TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                file_size INTEGER,
                duration REAL
            )
        ''')
        
        # Server statistics
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS server_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                metric_name TEXT NOT NULL,
                metric_value TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def log_file_access(self, file_path, action, ip_address=None, user_agent=None, file_size=None, duration=None):
        """Log file access for analytics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO file_access (file_path, action, ip_address, user_agent, file_size, duration)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (file_path, action, ip_address, user_agent, file_size, duration))
        
        conn.commit()
        conn.close()
    
    def get_popular_files(self, limit=10):
        """Get most accessed files"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT file_path, COUNT(*) as access_count
            FROM file_access
            WHERE action IN ('download', 'preview')
            GROUP BY file_path
            ORDER BY access_count DESC
            LIMIT ?
        ''', (limit,))
        
        results = cursor.fetchall()
        conn.close()
        return results
    
    def get_usage_stats(self, days=7):
        """Get usage statistics for the last N days"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                DATE(timestamp) as date,
                COUNT(*) as total_requests,
                COUNT(DISTINCT ip_address) as unique_visitors,
                SUM(CASE WHEN action = 'upload' THEN 1 ELSE 0 END) as uploads,
                SUM(CASE WHEN action = 'download' THEN 1 ELSE 0 END) as downloads
            FROM file_access
            WHERE timestamp >= datetime('now', '-{} days')
            GROUP BY DATE(timestamp)
            ORDER BY date DESC
        '''.format(days))
        
        results = cursor.fetchall()
        conn.close()
        return results



def load_config():
    """Load configuration from file."""
    default_config = {
        "shared_folder": None,
        "analytics_enabled": True,
        "thumbnail_generation": True,
        "max_file_size": 100 * 1024 * 1024,  # 100MB
        "allowed_extensions": [],  # Empty means all allowed
        "theme": "dark"
    }
    
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                # Merge with defaults
                default_config.update(config)
                return default_config
        except json.JSONDecodeError:
            logging.warning("Invalid config file. Using defaults.")
    
    return default_config

def save_config(config):
    """Save configuration to file."""
    try:
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
    except OSError as e:
        logging.error(f"Failed to save config: {e}")

def get_shared_folder():
    """Get or create shared folder in user's Downloads directory."""
    config = load_config()
    
    # Check if there's a saved custom folder first
    saved_folder = config.get("shared_folder")
    if saved_folder and os.path.isdir(saved_folder):
        print(f"Using saved shared folder: {saved_folder}")
        return os.path.abspath(saved_folder)

    # Get user's Downloads directory
    import platform
    system = platform.system()
    
    if system == "Windows":
        downloads_dir = os.path.join(os.path.expanduser("~"), "Downloads")
    elif system == "Darwin":  # macOS
        downloads_dir = os.path.join(os.path.expanduser("~"), "Downloads")
    else:  # Linux and other Unix-like systems
        downloads_dir = os.path.join(os.path.expanduser("~"), "Downloads")
    
    # Create PyServeX shared folder in Downloads
    shared_folder = os.path.join(downloads_dir, "PyServeX-Shared")
    
    try:
        if not os.path.exists(shared_folder):
            os.makedirs(shared_folder)
            print(f"Created shared folder: {shared_folder}")
        else:
            print(f"Using existing shared folder: {shared_folder}")
        
        # Create thumbnails directory
        thumbnails_dir = os.path.join(shared_folder, ".thumbnails")
        os.makedirs(thumbnails_dir, exist_ok=True)
        
        # Save this as the default for future use
        config["shared_folder"] = shared_folder
        save_config(config)
        
        return os.path.abspath(shared_folder)
        
    except OSError as e:
        logging.error(f"Failed to create shared folder: {e}")
        print(f"Error creating shared folder in Downloads. Using current directory instead.")
        
        # Fallback to current directory
        fallback_folder = os.path.join(os.getcwd(), "shared")
        try:
            if not os.path.exists(fallback_folder):
                os.makedirs(fallback_folder)
            return os.path.abspath(fallback_folder)
        except OSError:
            # Last resort - use current directory
            return os.getcwd()

def get_ip_addresses():
    """Retrieve all non-loopback and loopback IPv4 addresses of the system."""
    ip_addresses = ["127.0.0.1"]  # Explicitly include localhost
    try:
        # Get all network interfaces, filter for IPv4 (AF_INET)
        for interface in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = interface[4][0]
            # Filter out link-local (169.254.x.x) but keep 127.x.x.x
            if not ip.startswith("169.254.") and ip not in ip_addresses:
                ip_addresses.append(ip)
        return ip_addresses if ip_addresses else ["127.0.0.1", "No other IPv4 addresses found"]
    except socket.gaierror:
        return ["127.0.0.1", "Unable to resolve hostname"]

def run(base_dir, no_qr=False, port=None):
    """Run the HTTP server with the specified base directory."""
    global PORT
    if port:
        PORT = port
    
    # Initialize analytics
    analytics = AnalyticsManager(ANALYTICS_DB)
    
    class Handler(request_handler.FileRequestHandler):
        def __init__(self, *args, **kwargs):
            self.base_dir = base_dir
            self.config = load_config()
            self.analytics = analytics
            super().__init__(*args, **kwargs)

    # Create necessary directories and files
    robots_txt_path = os.path.join(base_dir, "robots.txt")
    if not os.path.exists(robots_txt_path):
        with open(robots_txt_path, "w") as f:
            f.write("User-agent: *\nDisallow: /\n")
    
    # Create thumbnails directory
    thumbnails_dir = os.path.join(base_dir, ".thumbnails")
    os.makedirs(thumbnails_dir, exist_ok=True)

    if not no_qr:
        # Print IP addresses before starting the server
        print("PyServeX - System IPv4 addresses:")
        for ip in get_ip_addresses():
            print(f"  http://{ip}:{PORT}")
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=3,
                border=4,
            )
            qr.add_data(f"http://{ip}:{PORT}")
            qr.make(fit=True)
            try:
                qr.print_tty()
            except OSError:
                print("Not a TTY. Cannot print QR code.")

    server = None
    
    try:
        server = socketserver.ThreadingTCPServer(("0.0.0.0", PORT), Handler)
        print(f"PyServeX v2.0.0 serving at http://0.0.0.0:{PORT}")
        print("Features: Dark/Light Theme, Notepad, Analytics, Thumbnails, File Operations")
        
        def shutdown_handler(signum, frame):
            print("\nShutting down PyServeX...")
            if server:
                # Run shutdown in a separate thread to avoid blocking
                threading.Thread(target=server.shutdown, daemon=True).start()
                server.server_close()
            sys.exit(0)

        # Register signal handler for SIGINT (Ctrl+C)
        signal.signal(signal.SIGINT, shutdown_handler)
        
        # Start the server
        server.serve_forever()
    
    except KeyboardInterrupt:
        # Handle Ctrl+C explicitly to ensure clean shutdown
        if server:
            print("\nShutting down PyServeX...")
            server.shutdown()
            server.server_close()
        sys.exit(0)
    except Exception as e:
        print(f"Server error: {e}")
        if server:
            server.server_close()
        sys.exit(1)

def main():
    """Main entry point for the command-line tool."""
    parser = argparse.ArgumentParser(description="PyServeX: Advanced HTTP server for file sharing with dark/light themes, notepad, analytics, and enhanced features.")
    parser.add_argument('--version', action='version', version='PyServeX 2.0.0')
    parser.add_argument('--port', type=int, default=8088, help='Port to run the server on (default: 8088)')
    parser.add_argument('--no-qr', action='store_true', help='Disable QR code generation')
    args = parser.parse_args()

    # Get the shared folder
    base_dir = get_shared_folder()
    run(base_dir, no_qr=args.no_qr, port=args.port)

if __name__ == "__main__":
    main()
