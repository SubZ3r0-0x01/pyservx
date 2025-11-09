#!/usr/bin/env python3
# Enhanced Request Handler with Advanced Features

import http.server
import os
import posixpath
import urllib.parse
import shutil
import logging
import json
import time
import mimetypes
from datetime import datetime

from . import html_generator
from . import file_operations

class EnhancedFileRequestHandler(http.server.SimpleHTTPRequestHandler):
    
    def translate_path(self, path):
        # Prevent path traversal attacks
        path = posixpath.normpath(urllib.parse.unquote(path))
        rel_path = path.lstrip('/')
        abs_path = os.path.abspath(os.path.join(self.base_dir, rel_path))
        if not abs_path.startswith(self.base_dir):
            logging.warning(f"Path traversal attempt detected: {path}")
            return self.base_dir
        return abs_path

    def log_access(self, action, file_path=None, file_size=None, duration=None):
        """Log file access for analytics"""
        if hasattr(self, 'analytics') and self.config.get('analytics_enabled', True):
            client_ip = self.client_address[0]
            user_agent = self.headers.get('User-Agent', '')
            self.analytics.log_file_access(
                file_path or self.path,
                action,
                client_ip,
                user_agent,
                file_size,
                duration
            )

    def do_GET(self):
        start_time = time.time()
        
        # Handle special endpoints
        if self.path.endswith('/analytics'):
            self.serve_analytics()
            return
        elif self.path.endswith('/find_duplicates'):
            self.serve_duplicates()
            return
        elif self.path.endswith('/preview'):
            file_path = self.translate_path(self.path.replace('/preview', ''))
            if os.path.isfile(file_path):
                self.serve_preview_page(file_path)
                self.log_access('preview', file_path, os.path.getsize(file_path))
            else:
                self.send_error(404, "File not found for preview")
            return
        elif self.path.endswith('/edit'):
            file_path = self.translate_path(self.path.replace('/edit', ''))
            if os.path.isfile(file_path):
                self.serve_editor_page(file_path)
                self.log_access('edit', file_path)
            else:
                self.send_error(404, "File not found for editing")
            return
        elif self.path.endswith('/notepad'):
            dir_path = self.translate_path(self.path.replace('/notepad', ''))
            if os.path.isdir(dir_path):
                self.serve_notepad_page(dir_path)
                self.log_access('create_file')
            else:
                self.send_error(404, "Directory not found")
            return
        elif self.path.startswith('/.thumbnails/'):
            # Serve thumbnail files
            thumbnail_path = self.translate_path(self.path)
            if os.path.isfile(thumbnail_path):
                self.serve_file(thumbnail_path)
            else:
                self.send_error(404, "Thumbnail not found")
            return

        # Handle directory listing or file download
        if self.path.endswith('/download_folder'):
            folder_path = self.translate_path(self.path.replace('/download_folder', ''))
            if os.path.isdir(folder_path):
                zip_file = file_operations.zip_folder(folder_path)
                self.send_response(200)
                self.send_header("Content-Type", "application/zip")
                self.send_header("Content-Disposition", f"attachment; filename={os.path.basename(folder_path)}.zip")
                self.end_headers()
                shutil.copyfileobj(zip_file, self.wfile)
                self.log_access('download_folder', folder_path)
            else:
                self.send_error(404, "Folder not found")
            return

        if os.path.isdir(self.translate_path(self.path)):
            self.list_directory(self.translate_path(self.path))
            self.log_access('browse')
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
                    
                    self.log_access('download', path, file_size, duration)

                except OSError:
                    self.send_error(404, "File not found")
            else:
                super().do_GET()

    def do_POST(self):
        if self.path.endswith('/create_file'):
            self.handle_create_file()
            return
        elif self.path.endswith('/save_file'):
            self.handle_save_file()
            return
        elif self.path.endswith('/copy'):
            self.handle_copy_file()
            return
        elif self.path.endswith('/move'):
            self.handle_move_file()
            return
        elif self.path.endswith('/generate_thumbnails'):
            self.handle_generate_thumbnails()
            return
        elif self.path.endswith('/upload'):
            self.handle_upload()
            return
        else:
            self.send_error(405, "Method not allowed")

    def do_MKCOL(self):
        """Handle MKCOL method for creating directories"""
        folder_path = self.translate_path(self.path)
        
        try:
            if os.path.exists(folder_path):
                self.send_response(409)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                response_data = {"status": "error", "message": "Folder already exists"}
                self.wfile.write(json.dumps(response_data).encode('utf-8'))
                return
            
            os.makedirs(folder_path)
            folder_name = os.path.basename(folder_path)
            logging.info(f"Created folder: {folder_path}")
            
            self.send_response(201)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            response_data = {"status": "success", "message": f"Folder '{folder_name}' created successfully!"}
            self.wfile.write(json.dumps(response_data).encode('utf-8'))
            
            self.log_access('create_folder', folder_path)
            
        except OSError as e:
            logging.error(f"Error creating folder {folder_path}: {e}")
            self.send_response(500)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            response_data = {"status": "error", "message": f"Error creating folder: {e}"}
            self.wfile.write(json.dumps(response_data).encode('utf-8'))

    def serve_file(self, file_path):
        """Serve a file with proper headers"""
        try:
            with open(file_path, 'rb') as f:
                self.send_response(200)
                self.send_header("Content-type", self.guess_type(file_path))
                self.send_header("Content-Length", str(os.path.getsize(file_path)))
                self.end_headers()
                shutil.copyfileobj(f, self.wfile)
        except OSError:
            self.send_error(404, "File not found")

    def serve_analytics(self):
        """Serve analytics data"""
        try:
            popular_files = self.analytics.get_popular_files(10)
            usage_stats = self.analytics.get_usage_stats(7)
            
            analytics_data = {
                'popular_files': popular_files,
                'usage_stats': usage_stats
            }
            
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(analytics_data).encode('utf-8'))
            
        except Exception as e:
            logging.error(f"Error serving analytics: {e}")
            self.send_error(500, "Error loading analytics")

    def serve_duplicates(self):
        """Find and serve duplicate files"""
        try:
            duplicates = file_operations.find_duplicates(self.base_dir)
            
            # Format duplicates for display
            formatted_duplicates = []
            for dup in duplicates:
                formatted_duplicates.append({
                    'original': os.path.relpath(dup['original'], self.base_dir),
                    'duplicate': os.path.relpath(dup['duplicate'], self.base_dir),
                    'size': file_operations.format_size(dup['size'])
                })
            
            response_data = {'duplicates': formatted_duplicates}
            
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response_data).encode('utf-8'))
            
        except Exception as e:
            logging.error(f"Error finding duplicates: {e}")
            self.send_error(500, "Error finding duplicates")

    def handle_copy_file(self):
        """Handle file copy operation"""
        content_length = int(self.headers.get('Content-Length', 0))
        request_body = self.rfile.read(content_length)
        
        try:
            data = json.loads(request_body)
            source = data.get('source')
            destination = data.get('destination')
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON payload")
            return

        if not source or not destination:
            self.send_response(400)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            response_data = {"status": "error", "message": "Source and destination required"}
            self.wfile.write(json.dumps(response_data).encode('utf-8'))
            return

        try:
            source_path = self.translate_path('/' + source.lstrip('/'))
            dest_dir = self.translate_path('/' + destination.lstrip('/'))
            dest_path = os.path.join(dest_dir, os.path.basename(source_path))
            
            if not os.path.exists(dest_dir):
                os.makedirs(dest_dir)
            
            if os.path.isfile(source_path):
                file_operations.copy_file(source_path, dest_path)
            elif os.path.isdir(source_path):
                shutil.copytree(source_path, dest_path)
            
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            response_data = {"status": "success", "message": f"Copied successfully to {destination}"}
            self.wfile.write(json.dumps(response_data).encode('utf-8'))
            
            self.log_access('copy', source_path)
            
        except Exception as e:
            logging.error(f"Error copying file: {e}")
            self.send_response(500)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            response_data = {"status": "error", "message": f"Copy failed: {e}"}
            self.wfile.write(json.dumps(response_data).encode('utf-8'))

    def handle_move_file(self):
        """Handle file move operation"""
        content_length = int(self.headers.get('Content-Length', 0))
        request_body = self.rfile.read(content_length)
        
        try:
            data = json.loads(request_body)
            source = data.get('source')
            destination = data.get('destination')
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON payload")
            return

        try:
            source_path = self.translate_path('/' + source.lstrip('/'))
            dest_dir = self.translate_path('/' + destination.lstrip('/'))
            dest_path = os.path.join(dest_dir, os.path.basename(source_path))
            
            if not os.path.exists(dest_dir):
                os.makedirs(dest_dir)
            
            shutil.move(source_path, dest_path)
            
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            response_data = {"status": "success", "message": f"Moved successfully to {destination}"}
            self.wfile.write(json.dumps(response_data).encode('utf-8'))
            
            self.log_access('move', source_path)
            
        except Exception as e:
            logging.error(f"Error moving file: {e}")
            self.send_response(500)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            response_data = {"status": "error", "message": f"Move failed: {e}"}
            self.wfile.write(json.dumps(response_data).encode('utf-8'))

    def handle_generate_thumbnails(self):
        """Generate thumbnails for images in current directory"""
        try:
            current_dir = self.translate_path(self.path.replace('/generate_thumbnails', ''))
            thumbnail_dir = os.path.join(self.base_dir, '.thumbnails')
            
            generated_count = 0
            for filename in os.listdir(current_dir):
                file_path = os.path.join(current_dir, filename)
                if os.path.isfile(file_path):
                    ext = os.path.splitext(filename)[1].lower()
                    if ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']:
                        thumbnail_path = file_operations.generate_thumbnail(file_path, thumbnail_dir)
                        if thumbnail_path:
                            generated_count += 1
            
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            response_data = {"status": "success", "message": f"Generated {generated_count} thumbnails"}
            self.wfile.write(json.dumps(response_data).encode('utf-8'))
            
            self.log_access('generate_thumbnails')
            
        except Exception as e:
            logging.error(f"Error generating thumbnails: {e}")
            self.send_response(500)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            response_data = {"status": "error", "message": f"Thumbnail generation failed: {e}"}
            self.wfile.write(json.dumps(response_data).encode('utf-8'))

    def handle_upload(self):
        """Enhanced file upload with better error handling"""
        content_length = int(self.headers.get('Content-Length', 0))
        
        # Check file size limit
        max_size = self.config.get('max_file_size', 100 * 1024 * 1024)  # 100MB default
        if content_length > max_size:
            self.send_response(413)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            response_data = {"status": "error", "message": f"File too large. Max size: {file_operations.format_size(max_size)}"}
            self.wfile.write(json.dumps(response_data).encode('utf-8'))
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

                # Check allowed extensions
                allowed_extensions = self.config.get('allowed_extensions', [])
                if allowed_extensions:
                    ext = os.path.splitext(filename)[1].lower()
                    if ext not in allowed_extensions:
                        continue

                # Extract file content
                content_start = part.find(b'\\r\\n\\r\\n') + 4
                content_end = part.rfind(b'\\r\\n--' + boundary)
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
                    
                    self.log_access('upload', file_path, file_size_bytes, duration)
                    
                except OSError as e:
                    logging.error(f"Error saving file {filename}: {e}")
                    self.send_error(500, f"Error saving file: {e}")
                    return

        if not uploaded_files:
            self.send_error(400, "No valid files provided")
            return

        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        response_data = {"status": "success", "message": f"Uploaded {len(uploaded_files)} files successfully!"}
        self.wfile.write(json.dumps(response_data).encode('utf-8'))

    def serve_preview_page(self, file_path):
        """Enhanced preview with better file type support"""
        import mimetypes
        
        filename = os.path.basename(file_path)
        file_ext = os.path.splitext(filename)[1].lower()
        mime_type, _ = mimetypes.guess_type(file_path)
        
        # Get relative path for the file URL
        rel_path = os.path.relpath(file_path, self.base_dir)
        file_url = '/' + rel_path.replace('\\\\', '/')
        
        try:
            if mime_type and mime_type.startswith('image/'):
                preview_html = self.generate_image_preview(filename, file_url)
            elif mime_type == 'application/pdf':
                preview_html = self.generate_pdf_preview(filename, file_url)
            elif mime_type and mime_type.startswith('video/'):
                preview_html = self.generate_video_preview(filename, file_url)
            elif mime_type and mime_type.startswith('audio/'):
                preview_html = self.generate_audio_preview(filename, file_url)
            elif mime_type and mime_type.startswith('text/') or file_ext in ['.txt', '.md', '.py', '.js', '.html', '.css', '.json', '.xml']:
                preview_html = self.generate_text_preview(filename, file_path)
            else:
                preview_html = self.generate_download_preview(filename, file_url)
            
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(preview_html.encode('utf-8'))
            
        except OSError:
            self.send_error(404, "File not found for preview")

    def generate_image_preview(self, filename, file_url):
        content = f"""
    <div class="max-w-4xl mx-auto">
        <h1 class="text-2xl mb-4 text-center">🖼️ Image Preview: {filename}</h1>
        <div class="text-center mb-4">
            <img src="{file_url}" alt="{filename}" class="max-w-full h-auto border border-green-700/50 light-theme:border-gray-300 rounded-lg mx-auto" style="max-height: 80vh;">
        </div>
        <div class="text-center">
            <a href="{file_url}" download class="bg-green-700 hover:bg-green-800 text-white font-bold py-2 px-4 rounded mr-2">📥 Download</a>
            <button onclick="window.close()" class="bg-gray-700 hover:bg-gray-800 text-white font-bold py-2 px-4 rounded">❌ Close</button>
        </div>
    </div>
"""
        return self.get_preview_page_template(f"Preview: {filename}", content, filename, file_url)

    def generate_pdf_preview(self, filename, file_url):
        content = f"""
    <div class="max-w-6xl mx-auto">
        <h1 class="text-2xl mb-4 text-center">📄 PDF Preview: {filename}</h1>
        <div class="mb-4">
            <embed src="{file_url}" type="application/pdf" width="100%" height="600px" class="border border-green-700/50 light-theme:border-gray-300 rounded-lg">
        </div>
        <div class="text-center">
            <a href="{file_url}" download class="bg-green-700 hover:bg-green-800 text-white font-bold py-2 px-4 rounded mr-2">📥 Download</a>
            <button onclick="window.close()" class="bg-gray-700 hover:bg-gray-800 text-white font-bold py-2 px-4 rounded">❌ Close</button>
        </div>
    </div>
"""
        return self.get_preview_page_template(f"Preview: {filename}", content, filename, file_url)

    def generate_video_preview(self, filename, file_url):
        content = f"""
    <div class="max-w-4xl mx-auto">
        <h1 class="text-2xl mb-4 text-center">🎥 Video Preview: {filename}</h1>
        <div class="text-center mb-4">
            <video controls class="max-w-full h-auto border border-green-700/50 light-theme:border-gray-300 rounded-lg mx-auto" style="max-height: 70vh;">
                <source src="{file_url}" type="video/mp4">
                <source src="{file_url}" type="video/webm">
                <source src="{file_url}" type="video/ogg">
                Your browser does not support the video tag.
            </video>
        </div>
        <div class="text-center">
            <a href="{file_url}" download class="bg-green-700 hover:bg-green-800 text-white font-bold py-2 px-4 rounded mr-2">📥 Download</a>
            <button onclick="window.close()" class="bg-gray-700 hover:bg-gray-800 text-white font-bold py-2 px-4 rounded">❌ Close</button>
        </div>
    </div>
"""
        return self.get_preview_page_template(f"Preview: {filename}", content, filename, file_url)

    def generate_audio_preview(self, filename, file_url):
        content = f"""
    <div class="max-w-2xl mx-auto">
        <h1 class="text-2xl mb-4 text-center">🎵 Audio Preview: {filename}</h1>
        <div class="text-center mb-4">
            <audio controls class="w-full border border-green-700/50 light-theme:border-gray-300 rounded-lg p-2">
                <source src="{file_url}" type="audio/mpeg">
                <source src="{file_url}" type="audio/ogg">
                <source src="{file_url}" type="audio/wav">
                Your browser does not support the audio element.
            </audio>
        </div>
        <div class="text-center">
            <a href="{file_url}" download class="bg-green-700 hover:bg-green-800 text-white font-bold py-2 px-4 rounded mr-2">📥 Download</a>
            <button onclick="window.close()" class="bg-gray-700 hover:bg-gray-800 text-white font-bold py-2 px-4 rounded">❌ Close</button>
        </div>
    </div>
"""
        return self.get_preview_page_template(f"Preview: {filename}", content, filename, file_url)

    def generate_text_preview(self, filename, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Limit content size for preview
            if len(content) > 10000:
                content = content[:10000] + "\\n\\n... (file truncated for preview)"
            
            # Escape HTML characters
            import html
            content = html.escape(content)
            
            page_content = f"""
    <div class="max-w-4xl mx-auto">
        <h1 class="text-2xl mb-4 text-center">📝 Text Preview: {filename}</h1>
        <div class="mb-4 p-4 border border-green-700/50 light-theme:border-gray-300 rounded-lg bg-gray-900 light-theme:bg-gray-50 overflow-auto" style="max-height: 70vh;">
            <pre class="text-sm whitespace-pre-wrap text-green-400 light-theme:text-gray-800">{content}</pre>
        </div>
        <div class="text-center">
            <button onclick="window.open('{os.path.relpath(file_path, self.base_dir).replace(chr(92), '/')}/edit', '_blank')" class="bg-blue-700 hover:bg-blue-800 text-white font-bold py-2 px-4 rounded mr-2">✏️ Edit</button>
            <button onclick="window.close()" class="bg-gray-700 hover:bg-gray-800 text-white font-bold py-2 px-4 rounded">❌ Close</button>
        </div>
    </div>
"""
            return self.get_preview_page_template(f"Preview: {filename}", page_content, filename, f"/{os.path.relpath(file_path, self.base_dir).replace(chr(92), '/')}")
        except Exception:
            return self.generate_download_preview(filename, f"/{os.path.relpath(file_path, self.base_dir).replace(chr(92), '/')}")

    def generate_download_preview(self, filename, file_url):
        content = f"""
    <div class="max-w-2xl mx-auto text-center">
        <h1 class="text-2xl mb-4">📋 File: {filename}</h1>
        <p class="mb-4">This file type cannot be previewed in the browser.</p>
        <div>
            <a href="{file_url}" download class="bg-green-700 hover:bg-green-800 text-white font-bold py-2 px-4 rounded mr-2">📥 Download File</a>
            <button onclick="window.close()" class="bg-gray-700 hover:bg-gray-800 text-white font-bold py-2 px-4 rounded">❌ Close</button>
        </div>
    </div>
"""
        return self.get_preview_page_template(f"Preview: {filename}", content, filename, file_url)

    def get_preview_page_template(self, title, content, filename, file_url):
        """Generate enhanced preview page template with theme support"""
        return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - PyServeX Enhanced</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body {{ 
            background: #000000; 
            color: #00ff00;
            font-family: 'Courier New', monospace; 
            transition: background-color 0.3s ease, color 0.3s ease;
        }}
        .text-neon {{ 
            color: #00ff00; 
            transition: color 0.3s ease;
        }}
        body.light-theme {{ 
            background: #ffffff; 
            color: #000000; 
        }}
        body.light-theme .text-neon {{ 
            color: #000000; 
        }}
        .theme-toggle-btn {{
            background: transparent;
            border: 1px solid;
            cursor: pointer;
            font-size: 1.2rem;
            padding: 0.5rem;
            border-radius: 0.5rem;
            transition: all 0.3s ease;
            position: fixed;
            top: 1rem;
            right: 1rem;
            z-index: 1000;
        }}
        body:not(.light-theme) .theme-toggle-btn {{
            border-color: #00ff00;
            color: #00ff00;
        }}
        body.light-theme .theme-toggle-btn {{
            border-color: #000000;
            color: #000000;
        }}
        body.light-theme .border-green-700 {{
            border-color: #d1d5db !important;
        }}
        body.light-theme .bg-green-700 {{
            background-color: #000000 !important;
        }}
        body.light-theme .bg-blue-700 {{
            background-color: #000000 !important;
        }}
        body.light-theme .bg-gray-700 {{
            background-color: #6b7280 !important;
        }}
    </style>
</head>
<body class="bg-black text-neon p-4">
    <button id="themeToggle" class="theme-toggle-btn">
        <span id="themeIcon">🌙</span>
    </button>
    {content}
    
    <script>
        // Theme Toggle Functionality
        function initTheme() {{
            const themeToggle = document.getElementById('themeToggle');
            const themeIcon = document.getElementById('themeIcon');
            const body = document.body;
            
            const savedTheme = localStorage.getItem('pyservx-theme') || 'dark';
            
            if (savedTheme === 'light') {{
                body.classList.add('light-theme');
                themeIcon.textContent = '☀️';
            }} else {{
                body.classList.remove('light-theme');
                themeIcon.textContent = '🌙';
            }}
            
            themeToggle.addEventListener('click', function() {{
                if (body.classList.contains('light-theme')) {{
                    body.classList.remove('light-theme');
                    themeIcon.textContent = '🌙';
                    localStorage.setItem('pyservx-theme', 'dark');
                }} else {{
                    body.classList.add('light-theme');
                    themeIcon.textContent = '☀️';
                    localStorage.setItem('pyservx-theme', 'light');
                }}
            }});
        }}
        
        window.onload = initTheme;
    </script>
</body>
</html>
"""

    # Include all the editor functionality from the original
    def serve_notepad_page(self, dir_path):
        """Serve a notepad page for creating new files"""
        return self.serve_editor_page(None, dir_path)

    def serve_editor_page(self, file_path=None, dir_path=None):
        """Enhanced text editor with syntax highlighting support"""
        if file_path:
            filename = os.path.basename(file_path)
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except Exception:
                content = ""
            
            rel_path = os.path.relpath(file_path, self.base_dir)
            save_url = '/' + rel_path.replace('\\\\', '/') + '/save_file'
            title = f"✏️ Edit: {filename}"
        else:
            filename = ""
            content = ""
            rel_path = os.path.relpath(dir_path, self.base_dir)
            save_url = '/' + rel_path.replace('\\\\', '/') + '/create_file'
            title = "📄 Create New File"

        editor_html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - PyServeX Enhanced</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.2/codemirror.min.css">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.2/codemirror.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.2/mode/javascript/javascript.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.2/mode/python/python.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.2/mode/xml/xml.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.2/mode/css/css.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.2/mode/markdown/markdown.min.js"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.2/theme/monokai.min.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.2/theme/default.min.css">
    <style>
        body {{ 
            background: #000000; 
            color: #00ff00;
            font-family: 'Courier New', monospace; 
            transition: background-color 0.3s ease, color 0.3s ease;
        }}
        .text-neon {{ 
            color: #00ff00; 
            transition: color 0.3s ease;
        }}
        .editor-container {{ min-height: 70vh; }}
        
        /* Light Theme */
        body.light-theme {{ 
            background: #ffffff; 
            color: #000000; 
        }}
        body.light-theme .text-neon {{ 
            color: #000000; 
        }}
        body.light-theme .CodeMirror {{
            background: #f8f9fa;
            color: #000000;
        }}
        
        .filename-input {{ 
            background: #111111; 
            color: #00ff00; 
            border: 1px solid #00ff00;
            font-family: 'Courier New', monospace;
            transition: all 0.3s ease;
        }}
        .filename-input:focus {{ outline: none; border-color: #00ff00; box-shadow: 0 0 5px rgba(0, 255, 0, 0.5); }}
        
        body.light-theme .filename-input {{ 
            background: #f8f9fa; 
            color: #000000; 
            border-color: #000000;
        }}
        body.light-theme .filename-input:focus {{ 
            border-color: #000000; 
            box-shadow: 0 0 5px rgba(0, 0, 0, 0.3); 
        }}
        
        .theme-toggle-btn {{
            background: transparent;
            border: 1px solid;
            cursor: pointer;
            font-size: 1.2rem;
            padding: 0.5rem;
            border-radius: 0.5rem;
            transition: all 0.3s ease;
            position: fixed;
            top: 1rem;
            right: 1rem;
            z-index: 1000;
        }}
        body:not(.light-theme) .theme-toggle-btn {{
            border-color: #00ff00;
            color: #00ff00;
        }}
        body.light-theme .theme-toggle-btn {{
            border-color: #000000;
            color: #000000;
        }}
        
        .CodeMirror {{
            height: 500px;
            font-family: 'Courier New', monospace;
            font-size: 14px;
        }}
    </style>
</head>
<body class="bg-black text-neon p-4">
    <button id="themeToggle" class="theme-toggle-btn">
        <span id="themeIcon">🌙</span>
    </button>
    
    <div class="max-w-6xl mx-auto">
        <div class="mb-4 flex justify-between items-center">
            <h1 class="text-2xl">{title}</h1>
            <div class="flex space-x-2">
                <button onclick="saveFile()" class="bg-green-700 hover:bg-green-800 text-white font-bold py-2 px-4 rounded">💾 Save</button>
                <button onclick="window.close()" class="bg-gray-700 hover:bg-gray-800 text-white font-bold py-2 px-4 rounded">❌ Close</button>
            </div>
        </div>
        
        {"" if file_path else '''
        <div class="mb-4">
            <label for="filename" class="block text-sm font-bold mb-2">📄 Filename:</label>
            <input type="text" id="filename" class="filename-input w-full p-2 rounded" placeholder="Enter filename (e.g., myfile.txt)" value="">
        </div>
        '''}
        
        <div class="editor-container">
            <textarea id="editor" class="w-full h-full p-4 rounded" placeholder="Start typing your content here...">{content}</textarea>
        </div>
        
        <div id="status" class="mt-4 text-center"></div>
    </div>

    <script>
        let editor;
        
        function initEditor() {{
            editor = CodeMirror.fromTextArea(document.getElementById('editor'), {{
                lineNumbers: true,
                mode: 'text/plain',
                theme: 'monokai',
                indentUnit: 4,
                lineWrapping: true,
                autoCloseBrackets: true,
                matchBrackets: true
            }});
            
            // Set mode based on filename
            {"" if not file_path else f'''
            const filename = "{filename}";
            setEditorMode(filename);
            '''}
        }}
        
        function setEditorMode(filename) {{
            const ext = filename.split('.').pop().toLowerCase();
            let mode = 'text/plain';
            
            switch(ext) {{
                case 'js': mode = 'javascript'; break;
                case 'py': mode = 'python'; break;
                case 'html': mode = 'xml'; break;
                case 'css': mode = 'css'; break;
                case 'md': mode = 'markdown'; break;
                case 'json': mode = 'javascript'; break;
            }}
            
            editor.setOption('mode', mode);
        }}
        
        function saveFile() {{
            const content = editor.getValue();
            {"const filename = document.getElementById('filename').value;" if not file_path else f"const filename = '{filename}';"}
            
            {"" if file_path else '''
            if (!filename.trim()) {
                alert('Please enter a filename');
                return;
            }
            
            setEditorMode(filename);
            '''}
            
            const payload = {{
                {"filename: filename," if not file_path else ""}
                content: content
            }};
            
            fetch('{save_url}', {{
                method: 'POST',
                headers: {{
                    'Content-Type': 'application/json',
                }},
                body: JSON.stringify(payload)
            }})
            .then(response => response.json())
            .then(data => {{
                const status = document.getElementById('status');
                if (data.status === 'success') {{
                    status.innerHTML = '<span class="text-green-500">✓ ' + data.message + '</span>';
                    setTimeout(() => {{
                        status.innerHTML = '';
                    }}, 3000);
                }} else {{
                    status.innerHTML = '<span class="text-red-500">✗ ' + data.message + '</span>';
                }}
            }})
            .catch(error => {{
                console.error('Error:', error);
                document.getElementById('status').innerHTML = '<span class="text-red-500">✗ Save failed due to network error</span>';
            }});
        }}
        
        // Theme Toggle Functionality
        function initTheme() {{
            const themeToggle = document.getElementById('themeToggle');
            const themeIcon = document.getElementById('themeIcon');
            const body = document.body;
            
            const savedTheme = localStorage.getItem('pyservx-theme') || 'dark';
            
            if (savedTheme === 'light') {{
                body.classList.add('light-theme');
                themeIcon.textContent = '☀️';
                if (editor) editor.setOption('theme', 'default');
            }} else {{
                body.classList.remove('light-theme');
                themeIcon.textContent = '🌙';
                if (editor) editor.setOption('theme', 'monokai');
            }}
            
            themeToggle.addEventListener('click', function() {{
                if (body.classList.contains('light-theme')) {{
                    body.classList.remove('light-theme');
                    themeIcon.textContent = '🌙';
                    localStorage.setItem('pyservx-theme', 'dark');
                    editor.setOption('theme', 'monokai');
                }} else {{
                    body.classList.add('light-theme');
                    themeIcon.textContent = '☀️';
                    localStorage.setItem('pyservx-theme', 'light');
                    editor.setOption('theme', 'default');
                }}
            }});
        }}
        
        // Initialize everything
        window.onload = function() {{
            initEditor();
            initTheme();
        }};
        
        // Keyboard shortcuts
        document.addEventListener('keydown', function(e) {{
            if (e.ctrlKey && e.key === 's') {{
                e.preventDefault();
                saveFile();
            }}
        }});
    </script>
</body>
</html>
"""
        
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(editor_html.encode('utf-8'))

    def handle_create_file(self):
        """Handle creating a new file"""
        content_length = int(self.headers.get('Content-Length', 0))
        request_body = self.rfile.read(content_length)
        
        try:
            data = json.loads(request_body)
            filename = data.get('filename', '').strip()
            content = data.get('content', '')
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON payload")
            return

        if not filename:
            self.send_response(400)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            response_data = {"status": "error", "message": "Filename is required"}
            self.wfile.write(json.dumps(response_data).encode('utf-8'))
            return

        target_dir = self.translate_path(self.path.replace('/create_file', ''))
        if not os.path.isdir(target_dir):
            self.send_error(404, "Target directory not found")
            return

        filename = os.path.basename(filename)
        file_path = os.path.join(target_dir, filename)

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logging.info(f"Created file: {file_path}")
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            response_data = {"status": "success", "message": f"File '{filename}' created successfully!"}
            self.wfile.write(json.dumps(response_data).encode('utf-8'))
            
            self.log_access('create_file', file_path)
            
        except OSError as e:
            logging.error(f"Error creating file {file_path}: {e}")
            self.send_response(500)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            response_data = {"status": "error", "message": f"Error creating file: {e}"}
            self.wfile.write(json.dumps(response_data).encode('utf-8'))

    def handle_save_file(self):
        """Handle saving an existing file"""
        content_length = int(self.headers.get('Content-Length', 0))
        request_body = self.rfile.read(content_length)
        
        try:
            data = json.loads(request_body)
            content = data.get('content', '')
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON payload")
            return

        file_path = self.translate_path(self.path.replace('/save_file', ''))
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            filename = os.path.basename(file_path)
            logging.info(f"Saved file: {file_path}")
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            response_data = {"status": "success", "message": f"File '{filename}' saved successfully!"}
            self.wfile.write(json.dumps(response_data).encode('utf-8'))
            
            self.log_access('save_file', file_path)
            
        except OSError as e:
            logging.error(f"Error saving file {file_path}: {e}")
            self.send_response(500)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            response_data = {"status": "error", "message": f"Error saving file: {e}"}
            self.wfile.write(json.dumps(response_data).encode('utf-8'))

    def list_directory(self, path):
        html_content = html_generator.list_directory_page(self, path)
        encoded = html_content.encode('utf-8', 'surrogateescape')
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)
        return