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

    def serve_preview_page(self, file_path):
        """Serve a preview page for different file types"""
        import mimetypes
        
        filename = os.path.basename(file_path)
        file_ext = os.path.splitext(filename)[1].lower()
        mime_type, _ = mimetypes.guess_type(file_path)
        
        # Get relative path for the file URL
        rel_path = os.path.relpath(file_path, self.base_dir)
        file_url = '/' + rel_path.replace('\\', '/')
        
        try:
            if mime_type and mime_type.startswith('image/'):
                # Image preview
                preview_html = self.generate_image_preview(filename, file_url)
            elif mime_type == 'application/pdf':
                # PDF preview
                preview_html = self.generate_pdf_preview(filename, file_url)
            elif mime_type and mime_type.startswith('video/'):
                # Video preview
                preview_html = self.generate_video_preview(filename, file_url)
            elif mime_type and mime_type.startswith('audio/'):
                # Audio preview
                preview_html = self.generate_audio_preview(filename, file_url)
            elif mime_type and mime_type.startswith('text/') or file_ext in ['.txt', '.md', '.py', '.js', '.html', '.css', '.json', '.xml']:
                # Text file preview
                preview_html = self.generate_text_preview(filename, file_path)
            else:
                # Unsupported file type - offer download
                preview_html = self.generate_download_preview(filename, file_url)
            
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(preview_html.encode('utf-8'))
            
        except OSError:
            self.send_error(404, "File not found for preview")

    def get_preview_page_template(self, title, content, filename, file_url):
        """Generate a common template for preview pages with theme support"""
        return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
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
            border-color: #000000 !important;
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
            
            // Load saved theme or default to dark
            const savedTheme = localStorage.getItem('pyservx-theme') || 'dark';
            
            if (savedTheme === 'light') {{
                body.classList.add('light-theme');
                themeIcon.textContent = '☀️';
            }} else {{
                body.classList.remove('light-theme');
                themeIcon.textContent = '🌙';
            }}
            
            // Theme toggle event listener
            themeToggle.addEventListener('click', function() {{
                if (body.classList.contains('light-theme')) {{
                    // Switch to dark theme
                    body.classList.remove('light-theme');
                    themeIcon.textContent = '🌙';
                    localStorage.setItem('pyservx-theme', 'dark');
                }} else {{
                    // Switch to light theme
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

    def generate_image_preview(self, filename, file_url):
        content = f"""
    <div class="max-w-4xl mx-auto">
        <h1 class="text-2xl mb-4 text-center">Image Preview: {filename}</h1>
        <div class="text-center mb-4">
            <img src="{file_url}" alt="{filename}" class="max-w-full h-auto border border-green-700/50 rounded-lg mx-auto" style="max-height: 80vh;">
        </div>
        <div class="text-center">
            <a href="{file_url}" download class="bg-green-700 hover:bg-green-800 text-white font-bold py-2 px-4 rounded mr-2">Download</a>
            <button onclick="window.close()" class="bg-gray-700 hover:bg-gray-800 text-white font-bold py-2 px-4 rounded">Close</button>
        </div>
    </div>
"""
        return self.get_preview_page_template(f"Preview: {filename}", content, filename, file_url)

    def generate_pdf_preview(self, filename, file_url):
        content = f"""
    <div class="max-w-6xl mx-auto">
        <h1 class="text-2xl mb-4 text-center">PDF Preview: {filename}</h1>
        <div class="mb-4">
            <embed src="{file_url}" type="application/pdf" width="100%" height="600px" class="border border-green-700/50 rounded-lg">
        </div>
        <div class="text-center">
            <a href="{file_url}" download class="bg-green-700 hover:bg-green-800 text-white font-bold py-2 px-4 rounded mr-2">Download</a>
            <button onclick="window.close()" class="bg-gray-700 hover:bg-gray-800 text-white font-bold py-2 px-4 rounded">Close</button>
        </div>
    </div>
"""
        return self.get_preview_page_template(f"Preview: {filename}", content, filename, file_url)

    def generate_video_preview(self, filename, file_url):
        content = f"""
    <div class="max-w-4xl mx-auto">
        <h1 class="text-2xl mb-4 text-center">Video Preview: {filename}</h1>
        <div class="text-center mb-4">
            <video controls class="max-w-full h-auto border border-green-700/50 rounded-lg mx-auto" style="max-height: 70vh;">
                <source src="{file_url}" type="video/mp4">
                <source src="{file_url}" type="video/webm">
                <source src="{file_url}" type="video/ogg">
                Your browser does not support the video tag.
            </video>
        </div>
        <div class="text-center">
            <a href="{file_url}" download class="bg-green-700 hover:bg-green-800 text-white font-bold py-2 px-4 rounded mr-2">Download</a>
            <button onclick="window.close()" class="bg-gray-700 hover:bg-gray-800 text-white font-bold py-2 px-4 rounded">Close</button>
        </div>
    </div>
"""
        return self.get_preview_page_template(f"Preview: {filename}", content, filename, file_url)

    def generate_audio_preview(self, filename, file_url):
        content = f"""
    <div class="max-w-2xl mx-auto">
        <h1 class="text-2xl mb-4 text-center">Audio Preview: {filename}</h1>
        <div class="text-center mb-4">
            <audio controls class="w-full border border-green-700/50 rounded-lg p-2">
                <source src="{file_url}" type="audio/mpeg">
                <source src="{file_url}" type="audio/ogg">
                <source src="{file_url}" type="audio/wav">
                Your browser does not support the audio element.
            </audio>
        </div>
        <div class="text-center">
            <a href="{file_url}" download class="bg-green-700 hover:bg-green-800 text-white font-bold py-2 px-4 rounded mr-2">Download</a>
            <button onclick="window.close()" class="bg-gray-700 hover:bg-gray-800 text-white font-bold py-2 px-4 rounded">Close</button>
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
        <h1 class="text-2xl mb-4 text-center">Text Preview: {filename}</h1>
        <div class="mb-4 p-4 border border-green-700/50 rounded-lg bg-gray-900 overflow-auto" style="max-height: 70vh;">
            <pre class="text-sm whitespace-pre-wrap">{content}</pre>
        </div>
        <div class="text-center">
            <button onclick="window.open('{file_url}edit', '_blank')" class="bg-blue-700 hover:bg-blue-800 text-white font-bold py-2 px-4 rounded mr-2">Edit</button>
            <button onclick="window.close()" class="bg-gray-700 hover:bg-gray-800 text-white font-bold py-2 px-4 rounded">Close</button>
        </div>
    </div>
"""
            return self.get_preview_page_template(f"Preview: {filename}", page_content, filename, f"/{os.path.relpath(file_path, self.base_dir).replace(chr(92), '/')}")
        except Exception:
            return self.generate_download_preview(filename, f"/{os.path.relpath(file_path, self.base_dir).replace(chr(92), '/')}")

    def generate_download_preview(self, filename, file_url):
        content = f"""
    <div class="max-w-2xl mx-auto text-center">
        <h1 class="text-2xl mb-4">File: {filename}</h1>
        <p class="mb-4">This file type cannot be previewed in the browser.</p>
        <div>
            <a href="{file_url}" download class="bg-green-700 hover:bg-green-800 text-white font-bold py-2 px-4 rounded mr-2">Download File</a>
            <button onclick="window.close()" class="bg-gray-700 hover:bg-gray-800 text-white font-bold py-2 px-4 rounded">Close</button>
        </div>
    </div>
"""
        return self.get_preview_page_template(f"Preview: {filename}", content, filename, file_url)

    def serve_notepad_page(self, dir_path):
        """Serve a notepad page for creating new files"""
        return self.serve_editor_page(None, dir_path)

    def serve_editor_page(self, file_path=None, dir_path=None):
        """Serve a text editor page for creating or editing files"""
        if file_path:
            # Editing existing file
            filename = os.path.basename(file_path)
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except Exception:
                content = ""
            
            rel_path = os.path.relpath(file_path, self.base_dir)
            save_url = '/' + rel_path.replace('\\', '/') + '/save_file'
            title = f"Edit: {filename}"
        else:
            # Creating new file
            filename = ""
            content = ""
            rel_path = os.path.relpath(dir_path, self.base_dir)
            save_url = '/' + rel_path.replace('\\', '/') + '/create_file'
            title = "Create New File"

        editor_html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
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
        .editor-container {{ min-height: 70vh; }}
        #editor {{ 
            background: #111111; 
            color: #00ff00; 
            font-family: 'Courier New', monospace; 
            font-size: 14px;
            line-height: 1.5;
            border: 1px solid #00ff00;
            resize: none;
            transition: all 0.3s ease;
        }}
        #editor:focus {{ outline: none; border-color: #00ff00; box-shadow: 0 0 5px rgba(0, 255, 0, 0.5); }}
        .filename-input {{ 
            background: #111111; 
            color: #00ff00; 
            border: 1px solid #00ff00;
            font-family: 'Courier New', monospace;
            transition: all 0.3s ease;
        }}
        .filename-input:focus {{ outline: none; border-color: #00ff00; box-shadow: 0 0 5px rgba(0, 255, 0, 0.5); }}
        
        /* Light Theme */
        body.light-theme {{ 
            background: #ffffff; 
            color: #000000; 
        }}
        body.light-theme .text-neon {{ 
            color: #000000; 
        }}
        body.light-theme #editor {{ 
            background: #f8f9fa; 
            color: #000000; 
            border-color: #000000;
        }}
        body.light-theme #editor:focus {{ 
            border-color: #000000; 
            box-shadow: 0 0 5px rgba(0, 0, 0, 0.3); 
        }}
        body.light-theme .filename-input {{ 
            background: #f8f9fa; 
            color: #000000; 
            border-color: #000000;
        }}
        body.light-theme .filename-input:focus {{ 
            border-color: #000000; 
            box-shadow: 0 0 5px rgba(0, 0, 0, 0.3); 
        }}
        body.light-theme .bg-green-700 {{
            background-color: #000000 !important;
        }}
        body.light-theme .bg-gray-700 {{
            background-color: #6b7280 !important;
        }}
        
        /* Theme Toggle Button */
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
                <button onclick="saveFile()" class="bg-green-700 hover:bg-green-800 text-white font-bold py-2 px-4 rounded">Save</button>
                <button onclick="window.close()" class="bg-gray-700 hover:bg-gray-800 text-white font-bold py-2 px-4 rounded">Close</button>
            </div>
        </div>
        
        {"" if file_path else '''
        <div class="mb-4">
            <label for="filename" class="block text-sm font-bold mb-2">Filename:</label>
            <input type="text" id="filename" class="filename-input w-full p-2 rounded" placeholder="Enter filename (e.g., myfile.txt)" value="">
        </div>
        '''}
        
        <div class="editor-container">
            <textarea id="editor" class="w-full h-full p-4 rounded" placeholder="Start typing your content here...">{content}</textarea>
        </div>
        
        <div id="status" class="mt-4 text-center"></div>
    </div>

    <script>
        function saveFile() {{
            const content = document.getElementById('editor').value;
            {"const filename = document.getElementById('filename').value;" if not file_path else f"const filename = '{filename}';"}
            
            {"" if file_path else '''
            if (!filename.trim()) {
                alert('Please enter a filename');
                return;
            }
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
        
        // Auto-resize textarea
        const editor = document.getElementById('editor');
        editor.style.height = 'auto';
        editor.style.height = Math.max(500, editor.scrollHeight) + 'px';
        
        editor.addEventListener('input', function() {{
            this.style.height = 'auto';
            this.style.height = Math.max(500, this.scrollHeight) + 'px';
        }});
        
        // Theme Toggle Functionality
        function initTheme() {{
            const themeToggle = document.getElementById('themeToggle');
            const themeIcon = document.getElementById('themeIcon');
            const body = document.body;
            
            // Load saved theme or default to dark
            const savedTheme = localStorage.getItem('pyservx-theme') || 'dark';
            
            if (savedTheme === 'light') {{
                body.classList.add('light-theme');
                themeIcon.textContent = '☀️';
            }} else {{
                body.classList.remove('light-theme');
                themeIcon.textContent = '🌙';
            }}
            
            // Theme toggle event listener
            themeToggle.addEventListener('click', function() {{
                if (body.classList.contains('light-theme')) {{
                    // Switch to dark theme
                    body.classList.remove('light-theme');
                    themeIcon.textContent = '🌙';
                    localStorage.setItem('pyservx-theme', 'dark');
                }} else {{
                    // Switch to light theme
                    body.classList.add('light-theme');
                    themeIcon.textContent = '☀️';
                    localStorage.setItem('pyservx-theme', 'light');
                }}
            }});
        }}
        
        // Initialize theme on page load
        initTheme();
        
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

        # Get target directory
        target_dir = self.translate_path(self.path.replace('/create_file', ''))
        if not os.path.isdir(target_dir):
            self.send_error(404, "Target directory not found")
            return

        # Sanitize filename
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

        # Get file path
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
            
        except OSError as e:
            logging.error(f"Error saving file {file_path}: {e}")
            self.send_response(500)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            response_data = {"status": "error", "message": f"Error saving file: {e}"}
            self.wfile.write(json.dumps(response_data).encode('utf-8'))

    def handle_save_clipboard(self):
        """Handle saving clipboard content to server-side storage"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            request_body = self.rfile.read(content_length)
            
            data = json.loads(request_body)
            content = data.get('content', '')
            path_key = data.get('path', '/')
            
            logging.info(f"Saving clipboard for path: {path_key}, content length: {len(content)}")
            
            # Create clipboard storage directory
            clipboard_dir = os.path.join(self.base_dir, '.pyservx_clipboard')
            os.makedirs(clipboard_dir, exist_ok=True)
            
            # Use path as filename (sanitized)
            safe_filename = path_key.replace('/', '_').replace('\\', '_').strip('_') or 'root'
            clipboard_file = os.path.join(clipboard_dir, f"{safe_filename}.txt")
            
            logging.info(f"Saving to clipboard file: {clipboard_file}")
            
            with open(clipboard_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logging.info(f"Successfully saved clipboard for path: {path_key}")
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            response_data = {"status": "success", "message": "Clipboard saved successfully!"}
            self.wfile.write(json.dumps(response_data).encode('utf-8'))
            
        except json.JSONDecodeError as e:
            logging.error(f"JSON decode error in save_clipboard: {e}")
            self.send_response(400)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            response_data = {"status": "error", "message": "Invalid JSON payload"}
            self.wfile.write(json.dumps(response_data).encode('utf-8'))
        except Exception as e:
            logging.error(f"Error saving clipboard: {e}")
            self.send_response(500)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            response_data = {"status": "error", "message": f"Error saving clipboard: {e}"}
            self.wfile.write(json.dumps(response_data).encode('utf-8'))

    def handle_load_clipboard(self):
        """Handle loading clipboard content from server-side storage"""
        try:
            query_params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            path_key = query_params.get('path', ['/'])[0]
            
            logging.info(f"Loading clipboard for path: {path_key}")
            
            # Create clipboard storage directory
            clipboard_dir = os.path.join(self.base_dir, '.pyservx_clipboard')
            os.makedirs(clipboard_dir, exist_ok=True)
            
            # Use path as filename (sanitized)
            safe_filename = path_key.replace('/', '_').replace('\\', '_').strip('_') or 'root'
            clipboard_file = os.path.join(clipboard_dir, f"{safe_filename}.txt")
            
            logging.info(f"Looking for clipboard file: {clipboard_file}")
            
            if os.path.exists(clipboard_file):
                with open(clipboard_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                logging.info(f"Loaded clipboard content: {len(content)} characters")
            else:
                content = ""
                logging.info("No clipboard file found, returning empty content")
            
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            response_data = {"status": "success", "content": content}
            self.wfile.write(json.dumps(response_data).encode('utf-8'))
            
        except Exception as e:
            logging.error(f"Error loading clipboard: {e}")
            self.send_response(500)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            response_data = {"status": "error", "message": f"Error loading clipboard: {e}"}
            self.wfile.write(json.dumps(response_data).encode('utf-8'))

    def do_GET(self):
        # Handle load_clipboard before other checks
        if '/load_clipboard' in self.path:
            self.handle_load_clipboard()
            return
        elif self.path.endswith('/download_folder'):
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

        # Parse the path without query parameters for directory/file checks
        parsed_path = urllib.parse.urlparse(self.path).path
        
        if os.path.isdir(self.translate_path(parsed_path)):
            self.list_directory(self.translate_path(parsed_path))
            self.log_access('browse')
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
            # New file creation via notepad
            dir_path = self.translate_path(self.path.replace('/notepad', ''))
            if os.path.isdir(dir_path):
                self.serve_notepad_page(dir_path)
                self.log_access('create_file')
            else:
                self.send_error(404, "Directory not found")
            return
        else:
            # Handle file downloads with progress tracking
            # Parse the path without query parameters
            parsed_path = urllib.parse.urlparse(self.path).path
            path = self.translate_path(parsed_path)
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
        # Handle save_clipboard before other checks
        if '/save_clipboard' in self.path:
            self.handle_save_clipboard()
            return
        elif self.path.endswith('/create_file'):
            self.handle_create_file()
            return
        elif self.path.endswith('/save_file'):
            self.handle_save_file()
            return
        elif self.path.endswith('/upload'):
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
            
            # Log analytics for each uploaded file
            for filename in uploaded_files:
                file_path = os.path.join(target_dir, filename)
                if os.path.exists(file_path):
                    self.log_access('upload', file_path, os.path.getsize(file_path))

            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            response_data = {"status": "success", "message": "Files uploaded successfully!"}
            self.wfile.write(json.dumps(response_data).encode('utf-8'))
            return
        else:
            self.send_error(405, "Method not allowed")



    def do_MKCOL(self):
        """Handle MKCOL method for creating directories (WebDAV standard)"""
        # Extract folder name from the path
        folder_path = self.translate_path(self.path)
        
        try:
            if os.path.exists(folder_path):
                self.send_response(409)  # Conflict - folder already exists
                self.send_header("Content-type", "application/json")
                self.end_headers()
                response_data = {"status": "error", "message": "Folder already exists"}
                self.wfile.write(json.dumps(response_data).encode('utf-8'))
                return
            
            os.makedirs(folder_path)
            folder_name = os.path.basename(folder_path)
            logging.info(f"Created folder: {folder_path}")
            
            self.log_access('create_folder', folder_path)
            
            self.send_response(201)  # Created
            self.send_header("Content-type", "application/json")
            self.end_headers()
            response_data = {"status": "success", "message": f"Folder '{folder_name}' created successfully!"}
            self.wfile.write(json.dumps(response_data).encode('utf-8'))
            
        except OSError as e:
            logging.error(f"Error creating folder {folder_path}: {e}")
            self.send_response(500)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            response_data = {"status": "error", "message": f"Error creating folder: {e}"}
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