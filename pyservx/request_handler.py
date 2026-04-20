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

    def _safe_write_response(self, status_code, headers_dict, content):
        """Safely write response with client disconnect handling"""
        try:
            self.send_response(status_code)
            for header, value in headers_dict.items():
                self.send_header(header, value)
            self.end_headers()
            if content:
                self.wfile.write(content)
        except (ConnectionResetError, BrokenPipeError):
            # Client disconnected - this is normal, stop processing
            logging.debug("Client disconnected during response")
            return False
        return True

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
            
            self._safe_write_response(200, {"Content-type": "text/html; charset=utf-8"}, preview_html.encode('utf-8'))
            
        except OSError:
            self.send_error(404, "File not found for preview")

    def get_preview_page_template(self, title, content, filename, file_url):
        """Generate a common template for preview pages with theme support"""
        return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=5.0, user-scalable=yes">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <title>{title}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

        /* Apple iOS Glass Theme Variables */
        :root {{
            --bg-primary: #000000;
            --bg-secondary: #1c1c1e;
            --bg-tertiary: #2c2c2e;
            --text-primary: #ffffff;
            --text-secondary: rgba(255, 255, 255, 0.6);
            --accent-color: #007aff;
            --accent-hover: #0051d5;
            --glass-bg: rgba(28, 28, 30, 0.7);
            --glass-border: rgba(255, 255, 255, 0.1);
            --shadow-color: rgba(0, 0, 0, 0.3);
            --blur-strong: 40px;
            --blur-medium: 20px;
            --radius-small: 10px;
            --radius-medium: 16px;
            --radius-large: 20px;
            --spacing-sm: 12px;
            --spacing-md: 16px;
            --spacing-lg: 24px;
        }}

        body.light-theme {{
            --bg-primary: #f2f2f7;
            --bg-secondary: #ffffff;
            --bg-tertiary: #e5e5ea;
            --text-primary: #000000;
            --text-secondary: rgba(0, 0, 0, 0.6);
            --glass-bg: rgba(255, 255, 255, 0.7);
            --glass-border: rgba(0, 0, 0, 0.1);
            --shadow-color: rgba(0, 0, 0, 0.1);
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{ 
            background: var(--bg-primary);
            color: var(--text-primary);
            font-family: -apple-system, BlinkMacSystemFont, 'Inter', 'Segoe UI', sans-serif;
            transition: background-color 0.3s cubic-bezier(0.4, 0, 0.2, 1), color 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
            padding: var(--spacing-md);
            min-height: 100vh;
        }}

        .text-neon {{ 
            color: var(--text-primary);
        }}

        .theme-toggle-btn {{
            background: var(--glass-bg);
            backdrop-filter: blur(var(--blur-medium)) saturate(180%);
            -webkit-backdrop-filter: blur(var(--blur-medium)) saturate(180%);
            color: var(--text-primary);
            border: 1px solid var(--glass-border);
            cursor: pointer;
            font-size: 1.2rem;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            position: fixed;
            top: var(--spacing-md);
            right: var(--spacing-md);
            z-index: 1000;
            padding: var(--spacing-sm);
            border-radius: var(--radius-medium);
            box-shadow: 0 4px 16px var(--shadow-color), 0 0 0 1px var(--glass-border);
            width: 44px;
            height: 44px;
            display: flex;
            align-items: center;
            justify-content: center;
        }}

        .theme-toggle-btn:hover {{
            transform: scale(1.05);
            opacity: 0.85;
            box-shadow: 0 8px 24px var(--shadow-color);
        }}

        .theme-toggle-btn:active {{
            transform: scale(0.95);
        }}

        .preview-container {{
            max-width: 1200px;
            margin: 0 auto;
            background: var(--glass-bg);
            backdrop-filter: blur(var(--blur-strong)) saturate(180%);
            -webkit-backdrop-filter: blur(var(--blur-strong)) saturate(180%);
            border-radius: var(--radius-large);
            border: 1px solid var(--glass-border);
            box-shadow: 0 8px 32px var(--shadow-color), 
                        0 0 0 1px var(--glass-border),
                        inset 0 1px 0 rgba(255, 255, 255, 0.1);
            padding: var(--spacing-lg);
            margin-top: 60px;
        }}

        .preview-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: var(--spacing-lg);
            padding-bottom: var(--spacing-md);
            border-bottom: 1px solid var(--glass-border);
        }}

        .preview-header h1 {{
            font-size: 1.5rem;
            font-weight: 600;
            color: var(--text-primary);
        }}

        .preview-actions {{
            display: flex;
            gap: var(--spacing-sm);
        }}

        button {{
            background: var(--accent-color);
            color: white;
            border: none;
            border-radius: var(--radius-medium);
            padding: var(--spacing-sm) var(--spacing-lg);
            font-family: inherit;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
        }}

        button:hover {{
            background: var(--accent-hover);
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(0, 122, 255, 0.3);
        }}

        button:active {{
            transform: translateY(0);
        }}

        .btn-secondary {{
            background: var(--bg-secondary);
            color: var(--text-primary);
            border: 1px solid var(--glass-border);
        }}

        .btn-secondary:hover {{
            background: var(--bg-tertiary);
            box-shadow: 0 4px 12px var(--shadow-color);
        }}

        .preview-content {{
            background: var(--bg-secondary);
            border-radius: var(--radius-medium);
            padding: var(--spacing-md);
            border: 1px solid var(--glass-border);
        }}

        @media (max-width: 768px) {{
            .preview-header {{
                flex-direction: column;
                gap: var(--spacing-md);
                align-items: flex-start;
            }}

            .preview-actions {{
                width: 100%;
                flex-direction: column;
            }}

            button {{
                width: 100%;
            }}
        }}
    </style>
</head>
<body>
    <button id="themeToggle" class="theme-toggle-btn">
        <span id="themeIcon">🌙</span>
    </button>
    
    <div class="preview-container">
        {content}
    </div>
    
    <script>
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

    def generate_image_preview(self, filename, file_url):
        content = f"""
        <div class="preview-header">
            <h1>🖼️ {filename}</h1>
            <div class="preview-actions">
                <a href="{file_url}" download><button>Download</button></a>
                <button onclick="window.close()" class="btn-secondary">Close</button>
            </div>
        </div>
        <div class="preview-content" style="text-align: center;">
            <img src="{file_url}" alt="{filename}" style="max-width: 100%; height: auto; max-height: 70vh; border-radius: var(--radius-medium);">
        </div>
"""
        return self.get_preview_page_template(f"Preview: {filename}", content, filename, file_url)

    def generate_pdf_preview(self, filename, file_url):
        content = f"""
        <div class="preview-header">
            <h1>📄 {filename}</h1>
            <div class="preview-actions">
                <a href="{file_url}" download><button>Download</button></a>
                <button onclick="window.close()" class="btn-secondary">Close</button>
            </div>
        </div>
        <div class="preview-content">
            <embed src="{file_url}" type="application/pdf" width="100%" height="600px" style="border-radius: var(--radius-medium);">
        </div>
"""
        return self.get_preview_page_template(f"Preview: {filename}", content, filename, file_url)

    def generate_video_preview(self, filename, file_url):
        content = f"""
        <div class="preview-header">
            <h1>🎬 {filename}</h1>
            <div class="preview-actions">
                <a href="{file_url}" download><button>Download</button></a>
                <button onclick="window.close()" class="btn-secondary">Close</button>
            </div>
        </div>
        <div class="preview-content" style="text-align: center;">
            <video controls style="max-width: 100%; height: auto; max-height: 70vh; border-radius: var(--radius-medium);">
                <source src="{file_url}" type="video/mp4">
                <source src="{file_url}" type="video/webm">
                <source src="{file_url}" type="video/ogg">
                Your browser does not support the video tag.
            </video>
        </div>
"""
        return self.get_preview_page_template(f"Preview: {filename}", content, filename, file_url)

    def generate_audio_preview(self, filename, file_url):
        content = f"""
        <div class="preview-header">
            <h1>🎵 {filename}</h1>
            <div class="preview-actions">
                <a href="{file_url}" download><button>Download</button></a>
                <button onclick="window.close()" class="btn-secondary">Close</button>
            </div>
        </div>
        <div class="preview-content">
            <audio controls style="width: 100%; border-radius: var(--radius-medium);">
                <source src="{file_url}" type="audio/mpeg">
                <source src="{file_url}" type="audio/ogg">
                <source src="{file_url}" type="audio/wav">
                Your browser does not support the audio element.
            </audio>
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
        <div class="preview-header">
            <h1>📝 {filename}</h1>
            <div class="preview-actions">
                <button onclick="window.open('{file_url}edit', '_blank')">Edit</button>
                <button onclick="window.close()" class="btn-secondary">Close</button>
            </div>
        </div>
        <div class="preview-content" style="max-height: 70vh; overflow-y: auto;">
            <pre style="margin: 0; font-family: 'SF Mono', Monaco, Menlo, monospace; font-size: 13px; line-height: 1.6; white-space: pre-wrap; word-wrap: break-word;">{content}</pre>
        </div>
"""
            return self.get_preview_page_template(f"Preview: {filename}", page_content, filename, f"/{os.path.relpath(file_path, self.base_dir).replace(chr(92), '/')}")
        except Exception:
            return self.generate_download_preview(filename, f"/{os.path.relpath(file_path, self.base_dir).replace(chr(92), '/')}")

    def generate_download_preview(self, filename, file_url):
        content = f"""
        <div class="preview-header">
            <h1>📦 {filename}</h1>
            <div class="preview-actions">
                <a href="{file_url}" download><button>Download</button></a>
                <button onclick="window.close()" class="btn-secondary">Close</button>
            </div>
        </div>
        <div class="preview-content" style="text-align: center; padding: var(--spacing-xl);">
            <p style="font-size: 3rem; margin-bottom: var(--spacing-md);">📄</p>
            <p style="color: var(--text-secondary); margin-bottom: var(--spacing-lg);">This file type cannot be previewed in the browser.</p>
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
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=5.0, user-scalable=yes">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <title>{title}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

        :root {{
            --bg-primary: #000000;
            --bg-secondary: #1c1c1e;
            --bg-tertiary: #2c2c2e;
            --text-primary: #ffffff;
            --text-secondary: rgba(255, 255, 255, 0.6);
            --accent-color: #007aff;
            --accent-hover: #0051d5;
            --glass-bg: rgba(28, 28, 30, 0.7);
            --glass-border: rgba(255, 255, 255, 0.1);
            --shadow-color: rgba(0, 0, 0, 0.3);
            --blur-strong: 40px;
            --blur-medium: 20px;
            --radius-small: 10px;
            --radius-medium: 16px;
            --radius-large: 20px;
            --spacing-sm: 12px;
            --spacing-md: 16px;
            --spacing-lg: 24px;
        }}

        body.light-theme {{
            --bg-primary: #f2f2f7;
            --bg-secondary: #ffffff;
            --bg-tertiary: #e5e5ea;
            --text-primary: #000000;
            --text-secondary: rgba(0, 0, 0, 0.6);
            --glass-bg: rgba(255, 255, 255, 0.7);
            --glass-border: rgba(0, 0, 0, 0.1);
            --shadow-color: rgba(0, 0, 0, 0.1);
        }}

        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        body {{ 
            background: var(--bg-primary);
            color: var(--text-primary);
            font-family: -apple-system, BlinkMacSystemFont, 'Inter', sans-serif;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            -webkit-font-smoothing: antialiased;
            padding: var(--spacing-md);
            min-height: 100vh;
        }}

        .theme-toggle-btn {{
            background: var(--glass-bg);
            backdrop-filter: blur(var(--blur-medium)) saturate(180%);
            -webkit-backdrop-filter: blur(var(--blur-medium)) saturate(180%);
            color: var(--text-primary);
            border: 1px solid var(--glass-border);
            cursor: pointer;
            font-size: 1.2rem;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            position: fixed;
            top: var(--spacing-md);
            right: var(--spacing-md);
            z-index: 1000;
            padding: var(--spacing-sm);
            border-radius: var(--radius-medium);
            box-shadow: 0 4px 16px var(--shadow-color);
            width: 44px;
            height: 44px;
            display: flex;
            align-items: center;
            justify-content: center;
        }}

        .theme-toggle-btn:hover {{ transform: scale(1.05); opacity: 0.85; }}
        .theme-toggle-btn:active {{ transform: scale(0.95); }}

        .editor-container {{
            max-width: 1200px;
            margin: 0 auto;
            background: var(--glass-bg);
            backdrop-filter: blur(var(--blur-strong)) saturate(180%);
            -webkit-backdrop-filter: blur(var(--blur-strong)) saturate(180%);
            border-radius: var(--radius-large);
            border: 1px solid var(--glass-border);
            box-shadow: 0 8px 32px var(--shadow-color), 0 0 0 1px var(--glass-border), inset 0 1px 0 rgba(255, 255, 255, 0.1);
            padding: var(--spacing-lg);
            margin-top: 60px;
        }}

        .editor-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: var(--spacing-lg);
            padding-bottom: var(--spacing-md);
            border-bottom: 1px solid var(--glass-border);
        }}

        .editor-header h1 {{ font-size: 1.5rem; font-weight: 600; }}

        .editor-actions {{ display: flex; gap: var(--spacing-sm); }}

        button {{
            background: var(--accent-color);
            color: white;
            border: none;
            border-radius: var(--radius-medium);
            padding: var(--spacing-sm) var(--spacing-lg);
            font-family: inherit;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
        }}

        button:hover {{ background: var(--accent-hover); transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0, 122, 255, 0.3); }}
        button:active {{ transform: translateY(0); }}

        .btn-secondary {{
            background: var(--bg-secondary);
            color: var(--text-primary);
            border: 1px solid var(--glass-border);
        }}

        .btn-secondary:hover {{ background: var(--bg-tertiary); box-shadow: 0 4px 12px var(--shadow-color); }}

        .filename-input {{
            background: var(--bg-secondary);
            color: var(--text-primary);
            border: 1px solid var(--glass-border);
            border-radius: var(--radius-medium);
            padding: var(--spacing-sm) var(--spacing-md);
            font-family: inherit;
            font-size: 14px;
            width: 100%;
            transition: all 0.2s;
        }}

        .filename-input:focus {{
            outline: none;
            border-color: var(--accent-color);
            box-shadow: 0 0 0 4px rgba(0, 122, 255, 0.1);
        }}

        #editor {{
            background: var(--bg-secondary);
            color: var(--text-primary);
            border: 1px solid var(--glass-border);
            border-radius: var(--radius-medium);
            padding: var(--spacing-md);
            font-family: 'SF Mono', Monaco, Menlo, monospace;
            font-size: 14px;
            line-height: 1.6;
            width: 100%;
            min-height: 500px;
            resize: vertical;
            transition: all 0.2s;
        }}

        #editor:focus {{
            outline: none;
            border-color: var(--accent-color);
            box-shadow: 0 0 0 4px rgba(0, 122, 255, 0.1);
        }}

        #status {{
            margin-top: var(--spacing-md);
            text-align: center;
            font-weight: 500;
        }}

        @media (max-width: 768px) {{
            .editor-header {{ flex-direction: column; gap: var(--spacing-md); align-items: flex-start; }}
            .editor-actions {{ width: 100%; flex-direction: column; }}
            button {{ width: 100%; }}
        }}
    </style>
</head>
<body>
    <button id="themeToggle" class="theme-toggle-btn">
        <span id="themeIcon">🌙</span>
    </button>
    
    <div class="editor-container">
        <div class="editor-header">
            <h1>✏️ {title}</h1>
            <div class="editor-actions">
                <button onclick="saveFile()">💾 Save</button>
                <button onclick="window.close()" class="btn-secondary">Close</button>
            </div>
        </div>
        
        {"" if file_path else '''
        <div style="margin-bottom: var(--spacing-lg);">
            <label for="filename" style="display: block; font-weight: 500; margin-bottom: var(--spacing-sm); color: var(--text-secondary); font-size: 14px;">Filename:</label>
            <input type="text" id="filename" class="filename-input" placeholder="Enter filename (e.g., myfile.txt)" value="">
        </div>
        '''}
        
        <div>
            <textarea id="editor" placeholder="Start typing your content here...">{content}</textarea>
        </div>
        
        <div id="status"></div>
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
                    status.innerHTML = '<span style="color: #34c759;">✓ ' + data.message + '</span>';
                    setTimeout(() => {{ status.innerHTML = ''; }}, 3000);
                }} else {{
                    status.innerHTML = '<span style="color: #ff3b30;">✗ ' + data.message + '</span>';
                }}
            }})
            .catch(error => {{
                console.error('Error:', error);
                document.getElementById('status').innerHTML = '<span style="color: #ff3b30;">✗ Save failed</span>';
            }});
        }}
        
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
        
        self._safe_write_response(200, {"Content-type": "text/html; charset=utf-8"}, editor_html.encode('utf-8'))

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
            self._safe_write_response(400, {"Content-type": "application/json"}, 
                json.dumps({"status": "error", "message": "Filename is required"}).encode('utf-8'))
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
            self._safe_write_response(200, {"Content-type": "application/json"}, 
                json.dumps({"status": "success", "message": f"File '{filename}' created successfully!"}).encode('utf-8'))
            
        except OSError as e:
            logging.error(f"Error creating file {file_path}: {e}")
            self._safe_write_response(500, {"Content-type": "application/json"}, 
                json.dumps({"status": "error", "message": f"Error creating file: {e}"}).encode('utf-8'))

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
            self._safe_write_response(200, {"Content-type": "application/json"}, 
                json.dumps({"status": "success", "message": f"File '{filename}' saved successfully!"}).encode('utf-8'))
            
        except OSError as e:
            logging.error(f"Error saving file {file_path}: {e}")
            self._safe_write_response(500, {"Content-type": "application/json"}, 
                json.dumps({"status": "error", "message": f"Error saving file: {e}"}).encode('utf-8'))

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
            self._safe_write_response(200, {"Content-type": "application/json", "Access-Control-Allow-Origin": "*"}, 
                json.dumps({"status": "success", "message": "Clipboard saved successfully!"}).encode('utf-8'))
            
        except json.JSONDecodeError as e:
            logging.error(f"JSON decode error in save_clipboard: {e}")
            self._safe_write_response(400, {"Content-type": "application/json", "Access-Control-Allow-Origin": "*"}, 
                json.dumps({"status": "error", "message": "Invalid JSON payload"}).encode('utf-8'))
        except Exception as e:
            logging.error(f"Error saving clipboard: {e}")
            self._safe_write_response(500, {"Content-type": "application/json", "Access-Control-Allow-Origin": "*"}, 
                json.dumps({"status": "error", "message": f"Error saving clipboard: {e}"}).encode('utf-8'))

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
            
            self._safe_write_response(200, {"Content-type": "application/json", "Access-Control-Allow-Origin": "*"}, 
                json.dumps({"status": "success", "content": content}).encode('utf-8'))
            
        except Exception as e:
            logging.error(f"Error loading clipboard: {e}")
            self._safe_write_response(500, {"Content-type": "application/json", "Access-Control-Allow-Origin": "*"}, 
                json.dumps({"status": "error", "message": f"Error loading clipboard: {e}"}).encode('utf-8'))

    def do_GET(self):
        # Handle load_clipboard before other checks
        if '/load_clipboard' in self.path:
            self.handle_load_clipboard()
            return
        elif self.path.endswith('/download_folder'):
            folder_path = self.translate_path(self.path.replace('/download_folder', ''))
            if os.path.isdir(folder_path):
                zip_file = file_operations.zip_folder(folder_path)
                try:
                    self.send_response(200)
                    self.send_header("Content-Type", "application/zip")
                    self.send_header("Content-Disposition", f"attachment; filename={os.path.basename(folder_path)}.zip")
                    self.end_headers()
                    shutil.copyfileobj(zip_file, self.wfile)
                    self.log_access('download_folder', folder_path)
                except (ConnectionResetError, BrokenPipeError):
                    # Client disconnected during folder download - this is normal
                    logging.debug(f"Client disconnected during folder download of {os.path.basename(folder_path)}")
                    return
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
                    try:
                        for chunk in file_operations.read_file_in_chunks(path):
                            self.wfile.write(chunk)
                        end_time = time.time()
                        duration = end_time - start_time
                        speed_bps = file_size / duration if duration > 0 else 0
                        logging.info(f"Downloaded {os.path.basename(path)} ({file_operations.format_size(file_size)}) in {duration:.2f}s at {file_operations.format_size(speed_bps)}/s")
                        
                        self.log_access('download', path, file_size, duration)
                    except (ConnectionResetError, BrokenPipeError):
                        # Client disconnected during file transfer - this is normal
                        logging.debug(f"Client disconnected during download of {os.path.basename(path)}")
                        return

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
        try:
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
        except (ConnectionResetError, BrokenPipeError):
            # Client disconnected during directory listing - this is normal
            logging.debug("Client disconnected during directory listing")
            return
        return