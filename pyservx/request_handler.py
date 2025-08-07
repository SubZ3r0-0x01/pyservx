#!/usr/bin/env python3

import http.server
import os
import posixpath
import urllib.parse
import shutil
import logging
import json
import time
from . import html_generator
from . import file_operations

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
                zip_file = file_operations.zip_folder(folder_path)
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
            # Handle file downloads with progress tracking
            path = self.translate_path(self.path)
            if os.path.isfile(path):
                try:
                    file_size = os.path.getsize(path)
                    self.send_response(200)
                    self.send_header("Content-type", self.guess_type(path))
                    self.send_header("Content-Length", str(file_size))
                    self.end_headers()

                    start_time = time.time()
                    for chunk in file_operations.read_file_in_chunks(path):
                        self.wfile.write(chunk)
                    end_time = time.time()
                    duration = end_time - start_time
                    speed_bps = file_size / duration if duration > 0 else 0
                    logging.info(f"Downloaded {os.path.basename(path)} ({file_operations.format_size(file_size)}) in {duration:.2f}s at {file_operations.format_size(speed_bps)}/s")

                except OSError:
                    self.send_error(404, "File not found")
            else:
                super().do_GET()

    def do_POST(self):
        if self.path.endswith('/upload'):
            content_length = int(self.headers.get('Content-Length', 0))
            
            # Parse multipart form data
            content_type = self.headers.get('Content-Type', '')
            if not content_type.startswith('multipart/form-data'):
                self.send_error(400, "Invalid content type")
                return

            boundary = content_type.split('boundary=')[1].encode()
            body = self.rfile.read(content_length)
            
            # Simple parsing of multipart form data
            parts = body.split(b'--' + boundary)
            uploaded_files = []
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
                        start_time = time.time()
                        file_operations.write_file_in_chunks(file_path, file_content)
                        end_time = time.time()
                        duration = end_time - start_time
                        file_size_bytes = len(file_content)
                        speed_bps = file_size_bytes / duration if duration > 0 else 0
                        
                        logging.info(f"Uploaded {filename} ({file_operations.format_size(file_size_bytes)}) in {duration:.2f}s at {file_operations.format_size(speed_bps)}/s")
                        uploaded_files.append(filename)
                    except OSError:
                        self.send_error(500, "Error saving file")
                        return

            if not uploaded_files:
                self.send_error(400, "No file provided")
                return

            # Log the upload and redirect URL
            redirect_url = self.path.replace('/upload', '') or '/'
            logging.info(f"Files uploaded: {', '.join(uploaded_files)} to {target_dir}")
            logging.info(f"Redirecting to: {redirect_url}")

            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            response_data = {"status": "success", "message": "Files uploaded successfully!"}
            self.wfile.write(json.dumps(response_data).encode('utf-8'))
            return
        else:
            self.send_error(405, "Method not allowed")

    def list_directory(self, path):
        html_content = html_generator.list_directory_page(self, path)
        encoded = html_content.encode('utf-8', 'surrogateescape')
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)
        return