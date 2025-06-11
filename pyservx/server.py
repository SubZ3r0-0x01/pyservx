#!/usr/bin/env python3
# Improved Python HTTP Server Developed by Subz3r0x01
# GitHub: https://github.com/SubZ3r0-0x01

import os
import posixpath
import urllib.parse
import http.server
import socketserver
import shutil
import mimetypes
from io import BytesIO
import zipfile
import threading
import signal
import sys
import html
import logging
import socket
import json
import argparse

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

def zip_folder(folder_path):
    memory_file = BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(folder_path):
            for file in files:
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, folder_path)
                zipf.write(abs_path, rel_path)
    memory_file.seek(0)
    return memory_file

class FileRequestHandler(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        # Prevent path traversal attacks
        path = posixpath.normpath(urllib.parse.unquote(path))
        rel_path = path.lstrip('/')
        abs_path = os.path.abspath(os.path.join(self.base_dir, rel_path))
        if not abs_path.startswith(self.base_dir):
            logging.warning(f"Path traversal attempt detected: {path}")
            return self.base_dir  # Prevent access outside the base directory
        return abs_path

    def do_GET(self):
        if self.path.endswith('/download_folder'):
            folder_path = self.translate_path(self.path.replace('/download_folder', ''))
            if os.path.isdir(folder_path):
                zip_file = zip_folder(folder_path)
                self.send_response(200)
                self.send_header("Content-Type", "application/zip")
                self.send_header("Content-Disposition", f"attachment; filename={os.path.basename(folder_path)}.zip")
                self.end_headers()
                shutil.copyfileobj(zip_file, self.wfile)
            else:
                self.send_error(404, "Folder not found")
            return

        if os.path.isdir(self.translate_path(self.path)):
            self.list_directory(self.translate_path(self.path))
        else:
            super().do_GET()

    def do_POST(self):
        if self.path.endswith('/upload'):
            content_length = int(self.headers.get('Content-Length', 0))
            # Limit file size to prevent abuse (e.g., 100MB)
            max_file_size = 100 * 1024 * 1024
            if content_length > max_file_size:
                self.send_error(413, "File too large")
                return

            # Parse multipart form data
            content_type = self.headers.get('Content-Type', '')
            if not content_type.startswith('multipart/form-data'):
                self.send_error(400, "Invalid content type")
                return

            boundary = content_type.split('boundary=')[1].encode()
            body = self.rfile.read(content_length)
            
            # Simple parsing of multipart form data
            parts = body.split(b'--' + boundary)
            for part in parts:
                if b'filename="' in part:
                    # Extract filename
                    start = part.find(b'filename="') + 10
                    end = part.find(b'"', start)
                    filename = part[start:end].decode('utf-8')
                    # Sanitize filename
                    filename = os.path.basename(filename)
                    if not filename:
                        continue

                    # Extract file content
                    content_start = part.find(b'\r\n\r\n') + 4
                    content_end = part.rfind(b'\r\n--' + boundary)
                    if content_end == -1:
                        content_end = len(part) - 2
                    file_content = part[content_start:content_end]

                    # Save file to the target directory
                    target_dir = self.translate_path(self.path.replace('/upload', ''))
                    if not os.path.isdir(target_dir):
                        self.send_error(404, "Target directory not found")
                        return

                    file_path = os.path.join(target_dir, filename)
                    try:
                        with open(file_path, 'wb') as f:
                            f.write(file_content)
                    except OSError:
                        self.send_error(500, "Error saving file")
                        return

                    # Log the upload and redirect URL
                    redirect_url = self.path.replace('/upload', '') or '/'
                    logging.info(f"File uploaded: {filename} to {target_dir}")
                    logging.info(f"Redirecting to: {redirect_url}")

                    # Serve success page with redirect
                    html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>PyServeX - Upload Success</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=VT323&display=swap');

        body {{
            font-family: 'VT323', monospace;
            background: #000000;
            min-height: 100vh;
            margin: 0;
            overflow-x: hidden;
        }}

        .text-neon {{
            color: #00ff00;
        }}

        .typewriter h1 {{
            overflow: hidden;
            white-space: nowrap;
            animation: typing 3s steps(40, end), blink-caret 0.5s step-end infinite;
            margin: 0 auto;
            text-align: center;
        }}

        @keyframes typing {{
            from {{ width: 0; }}
            to {{ width: 100%; }}
        }}

        @keyframes blink-caret {{
            from, to {{ border-right: 2px solid #00ff00; }}
            50% {{ border-right: 2px solid transparent; }}
        }}

        .glitch {{
            position: relative.
            animation: glitch 2s infinite;
        }}

        @keyframes glitch {{
            0% {{ transform: translate(0); }}
            10% {{ transform: translate(-2px, 2px); }}
            20% {{ transform: translate(2px, -2px); }}
            30% {{ transform: translate(-2px, 2px); }}
            40% {{ transform: translate(0); }}
            100% {{ transform: translate(0); }}
        }}

        .scanline {{
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: linear-gradient(
                to bottom,
                rgba(255, 255, 255, 0),
                rgba(255, 255, 255, 0.1) 50%,
                rgba(255, 255, 255, 0)
            );
            animation: scan 4s linear infinite;
            pointer-events: none;
        }}

        @keyframes scan {{
            0% {{ transform: translateY(-100%); }}
            100% {{ transform: translateY(100%); }}
        }}

        .particle {{
            position: absolute;
            width: 3px;
            height: 3px;
            background: #00ff00;
            opacity: 0.5;
            animation: flicker 3s infinite;
        }}

        @keyframes flicker {{
            0% {{ opacity: 0.5; }}
            50% {{ opacity: 0.1; }}
            100% {{ opacity: 0.5; }}
        }}

        main {{
            margin-top: 100px;
            padding: 2rem;
            color: #00ff00;
            text-align: center;
            max-width: 900px;
            margin-left: auto;
            margin-right: auto;
        }}
    </style>
</head>
<body>
    <div class="scanline"></div>
    <main>
        <h1 class="text-4xl md:text-6xl text-neon typewriter glitch">File Uploaded Successfully!</h1>
        <p class="text-neon text-2xl mt-4">Redirecting to directory in 3 seconds...</p>
    </main>
    <script>
        // Generate random particles for hacker effect
        function createParticles() {{
            const numParticles = 30;
            for (let i = 0; i < numParticles; i++) {{
                const particle = document.createElement('div');
                particle.classList.add('particle');
                particle.style.left = `${{Math.random() * 100}}vw`;
                particle.style.top = `${{Math.random() * 100}}vh`;
                particle.style.animationDelay = `${{Math.random() * 3}}s`;
                document.body.appendChild(particle);
            }}
        }}

        // Auto-redirect after 3 seconds
        setTimeout(() => {{
            window.location.href = "{html.escape(redirect_url)}";
        }}, 3000);

        window.onload = createParticles;
    </script>
</body>
</html>
'''
                    encoded = html_content.encode('utf-8', 'surrogateescape')
                    self.send_response(200)
                    self.send_header("Content-type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(encoded)))
                    self.end_headers()
                    self.wfile.write(encoded)
                    return
            self.send_error(400, "No file provided")
            return
        else:
            self.send_error(405, "Method not allowed")

    def list_directory(self, path):
        try:
            entries = os.listdir(path)
        except OSError:
            self.send_error(404, "Cannot list directory")
            return None

        entries.sort(key=lambda a: a.lower())
        displaypath = html.escape(urllib.parse.unquote(self.path))

        # Build list items for directories and files
        list_items = []
        # Parent directory link if not root
        if self.path != '/':
            parent = os.path.dirname(self.path.rstrip('/'))
            if not parent.endswith('/'):
                parent += '/'
            list_items.append(f'<li><a href="{html.escape(parent)}" class="text-neon">.. (Parent Directory)</a></li>')

        for name in entries:
            fullpath = os.path.join(path, name)
            displayname = name + '/' if os.path.isdir(fullpath) else name
            href = urllib.parse.quote(name)
            if os.path.isdir(fullpath):
                href += '/'
            # Add download folder zip link for directories
            if os.path.isdir(fullpath):
                list_items.append(
                    f'<li>'
                    f'<a href="{href}" class="text-neon">{html.escape(displayname)}</a> '
                    f' |  <a href="{href}download_folder" class="text-neon">📦 Zip Download</a>'
                    f'</li>'
                )
            else:
                list_items.append(f'<li><a href="{href}" class="text-neon">{html.escape(displayname)}</a></li>')

        list_html = '\n'.join(list_items)

        html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>PyServeX - Index of {displaypath}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=VT323&display=swap');

        body {{
            font-family: 'VT323', monospace;
            background: #000000;
            min-height: 100vh;
            margin: 0;
            overflow-x: hidden;
        }}

        header {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            padding: 1rem 0;
            background: rgba(0, 0,0, 0.9);
            box-shadow: 0 2px 5px rgba(0, 255, 0, 0.2);
            z-index: 1000;
        }}

        .text-neon {{
            color: #00ff00;
        }}

        .typewriter h1 {{
            overflow: hidden;
            white-space: nowrap;
            animation: typing 3s steps(40, end), blink-caret 0.5s step-end infinite;
            margin: 0 auto;
            text-align: center;
        }}

        @keyframes typing {{
            from {{ width: 0; }}
            to {{ width: 100%; }}
        }}

        @keyframes blink-caret {{
            from, to {{ border-right: 2px solid #00ff00; }}
            50% {{ border-right: 2px solid transparent; }}
        }}

        .glitch {{
            position: relative;
            animation: glitch 2s infinite;
        }}

        @keyframes glitch {{
            0% {{ transform: translate(0); }}
            10% {{ transform: translate(-2px, 2px); }}
            20% {{ transform: translate(2px, -2px); }}
            30% {{ transform: translate(-2px, 2px); }}
            40% {{ transform: translate(0); }}
            100% {{ transform: translate(0); }}
        }}

        .scanline {{
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: linear-gradient(
                to bottom,
                rgba(255, 255, 255, 0),
                rgba(255, 255, 255, 0.1) 50%,
                rgba(255, 255, 255, 0)
            );
            animation: scan 4s linear infinite;
            pointer-events: none;
        }}

        @keyframes scan {{
            0% {{ transform: translateY(-100%); }}
            100% {{ transform: translateY(100%); }}
        }}

        .particle {{
            position: absolute;
            width: 3px;
            height: 3px;
            background: #00ff00;
            opacity: 0.5;
            animation: flicker 3s infinite;
        }}

        @keyframes flicker {{
            0% {{ opacity: 0.5; }}
            50% {{ opacity: 0.1; }}
            100% {{ opacity: 0.5; }}
        }}

        main {{
            margin-top: 100px; /* Adjust based on header height */
            padding: 2rem;
            color: #00ff00;
            text-align: left;
            max-width: 900px;
            margin-left: auto;
            margin-right: auto;
        }}

        ul {{
            list-style-type: none;
            padding-left: 0;
        }}

        li {{
            margin-bottom: 0.7rem;
            font-size: 1.2rem;
        }}

        a {{
            text-decoration: none;
        }}

        a:hover {{
            text-decoration: underline;
        }}

        .upload-form {{
            margin-top: 1.5rem;
            padding: 1rem;
            border: 1px solid #00ff00;
            border-radius: 5px;
        }}

        .upload-form label {{
            display: block;
            margin-bottom: 0.5rem;
        }}

        .upload-form input[type="file"] {{
            color: #00ff00;
            background: #000000;
            border: 1px solid #00ff00;
            padding: 0.5rem;
        }}

        .upload-form button {{
            background: #00ff00;
            color: #000000;
            padding: 0.5rem 1rem;
            border: none;
            cursor: pointer;
            font-family: 'VT323', monospace;
            font-size: 1.2rem;
        }}

        .upload-form button:hover {{
            background: #00cc00;
        }}
    </style>
</head>
<body>
    <div class="scanline"></div>
    <header>
        <div class="text-center">
            <h1 class="text-4xl md:text-6xl text-neon typewriter glitch">PyServeX</h1>
        </div>
    </header>
    <main>
        <h2>Index of {displaypath}</h2>
        <ul>
            {list_html}
        </ul>
        <div class="upload-form">
            <form action="{html.escape(self.path)}upload" method="POST" enctype="multipart/form-data">
                <label for="file-upload" class="text-neon">Upload a file:</label>
                <input type="file" id="file-upload" name="file" />
                <button type="submit">Upload</button>
            </form>
        </div>
    </main>

    <script>
        // Generate random particles for hacker effect
        function createParticles() {{
            const numParticles = 30;
            for (let i = 0; i < numParticles; i++) {{
                const particle = document.createElement('div');
                particle.classList.add('particle');
                particle.style.left = `${{Math.random() * 100}}vw`;
                particle.style.top = `${{Math.random() * 100}}vh`;
                particle.style.animationDelay = `${{Math.random() * 3}}s`;
                document.body.appendChild(particle);
            }}
        }}

        window.onload = createParticles;
    </script>
</body>
</html>
'''

        encoded = html_content.encode('utf-8', 'surrogateescape')
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)
        return

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

def run(base_dir):
    """Run the HTTP server with the specified base directory."""
    class Handler(FileRequestHandler):
        def __init__(self, *args, **kwargs):
            self.base_dir = base_dir
            super().__init__(*args, **kwargs)

    # Print IP addresses before starting the server
    print("System IPv4 addresses (including localhost):")
    for ip in get_ip_addresses():
        print(f"  http://{ip}:{PORT}")
    
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