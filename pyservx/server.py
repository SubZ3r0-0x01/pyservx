#!/usr/bin/env python3
# Improved Python HTTP Server Developed by Subz3r0x01
# GitHub: https://github.com/SubZ3r0-0x01

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
from . import request_handler

# Configure logging for debugging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

PORT = 8088
CONFIG_FILE = os.path.expanduser("~/.pyservx_config.json")  # Store config in user's home directory

def load_config():
    """Load shared folder path from config file if it exists."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                return config.get("shared_folder")
        except json.JSONDecodeError:
            logging.warning("Invalid config file. Ignoring.")
    return None

def save_config(folder_path):
    """Save shared folder path to config file."""
    try:
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, 'w') as f:
            json.dump({"shared_folder": folder_path}, f)
    except OSError as e:
        logging.error(f"Failed to save config: {e}")

def get_shared_folder():
    """Prompt user for shared folder path or load from config."""
    saved_folder = load_config()
    if saved_folder and os.path.isdir(saved_folder):
        print(f"Using saved shared folder: {saved_folder}")
        return os.path.abspath(saved_folder)

    while True:
        folder_path = input("Enter the path to the shared folder: ").strip()
        if os.path.isdir(folder_path):
            break
        print("Invalid folder path. Please enter a valid directory.")

    while True:
        persist = input("Do you want this choice to be persistent? (y/n): ").strip().lower()
        if persist in ('y', 'n'):
            break
        print("Please enter 'y' or 'n'.")

    folder_path = os.path.abspath(folder_path)
    if persist == 'y':
        save_config(folder_path)
        print(f"Shared folder saved for future use: {folder_path}")
    else:
        print("Shared folder will be prompted again next time.")

    return folder_path

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

def run(base_dir, no_qr=False):
    """Run the HTTP server with the specified base directory."""
    class Handler(request_handler.FileRequestHandler):
        def __init__(self, *args, **kwargs):
            self.base_dir = base_dir
            super().__init__(*args, **kwargs)

    # Create robots.txt if it doesn't exist
    robots_txt_path = os.path.join(base_dir, "robots.txt")
    if not os.path.exists(robots_txt_path):
        with open(robots_txt_path, "w") as f:
            f.write("User-agent: *\nDisallow: /\n")

    if not no_qr:
        # Print IP addresses before starting the server
        print("System IPv4 addresses (including localhost):")
        for ip in get_ip_addresses():
            print(f"  http://{ip}:{PORT}")
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
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
        print(f"Serving at http://0.0.0.0:{PORT} (accessible from network and localhost)")
        
        def shutdown_handler(signum, frame):
            print("\nShutting down server...")
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
            print("\nShutting down server...")
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
    parser = argparse.ArgumentParser(description="PyServeX: A simple HTTP server for file sharing.")
    parser.add_argument('--version', action='version', version='PyServeX 1.0.1')
    args = parser.parse_args()

    # Get the shared folder
    base_dir = get_shared_folder()
    run(base_dir)

if __name__ == "__main__":
    main()
