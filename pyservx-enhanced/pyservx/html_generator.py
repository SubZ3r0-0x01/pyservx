#!/usr/bin/env python3
# Enhanced HTML Generator with Advanced Features

import html
import os
import urllib.parse
import datetime
import json
from . import file_operations

def format_size(size):
    if size < 1024:
        return f"{size} B"
    elif size < 1024**2:
        return f"{size / 1024:.2f} KB"
    elif size < 1024**3:
        return f"{size / (1024**2):.2f} MB"
    else:
        return f"{size / (1024**3):.2f} GB"

def get_file_icon(filename, is_dir=False):
    """Get appropriate icon for file type"""
    if is_dir:
        return "📁"
    
    ext = os.path.splitext(filename)[1].lower()
    
    # Image files
    if ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp']:
        return "🖼️"
    # Video files
    elif ext in ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm']:
        return "🎥"
    # Audio files
    elif ext in ['.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a']:
        return "🎵"
    # Document files
    elif ext in ['.pdf', '.doc', '.docx', '.txt', '.rtf']:
        return "📄"
    # Code files
    elif ext in ['.py', '.js', '.html', '.css', '.java', '.cpp', '.c', '.php']:
        return "💻"
    # Archive files
    elif ext in ['.zip', '.rar', '.7z', '.tar', '.gz']:
        return "📦"
    # Excel/Spreadsheet
    elif ext in ['.xls', '.xlsx', '.csv']:
        return "📊"
    # PowerPoint
    elif ext in ['.ppt', '.pptx']:
        return "📈"
    else:
        return "📋"

def generate_breadcrumb(path, handler_path):
    """Generate breadcrumb navigation"""
    parts = path.strip('/').split('/') if path.strip('/') else []
    breadcrumbs = ['<a href="/" class="text-neon hover:underline">🏠 Home</a>']
    
    current_path = ""
    for part in parts:
        if part:
            current_path += "/" + part
            breadcrumbs.append(f'<a href="{current_path}" class="text-neon hover:underline">{html.escape(part)}</a>')
    
    return " / ".join(breadcrumbs)

def list_directory_page(handler, path):
    try:
        entries = os.listdir(path)
    except OSError:
        handler.send_error(404, "Cannot list directory")
        return None

    query_params = urllib.parse.parse_qs(urllib.parse.urlparse(handler.path).query)
    search_query = query_params.get('q', [''])[0]
    sort_by = query_params.get('sort', ['name'])[0]
    sort_order = query_params.get('order', ['asc'])[0]
    view_mode = query_params.get('view', ['list'])[0]  # list or grid
    file_type_filter = query_params.get('type', [''])[0]

    if search_query:
        entries = [e for e in entries if search_query.lower() in e.lower()]

    # Filter by file type
    if file_type_filter:
        filtered_entries = []
        for entry in entries:
            fullpath = os.path.join(path, entry)
            if file_type_filter == 'folder' and os.path.isdir(fullpath):
                filtered_entries.append(entry)
            elif file_type_filter == 'image' and not os.path.isdir(fullpath):
                ext = os.path.splitext(entry)[1].lower()
                if ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp']:
                    filtered_entries.append(entry)
            elif file_type_filter == 'video' and not os.path.isdir(fullpath):
                ext = os.path.splitext(entry)[1].lower()
                if ext in ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm']:
                    filtered_entries.append(entry)
            elif file_type_filter == 'audio' and not os.path.isdir(fullpath):
                ext = os.path.splitext(entry)[1].lower()
                if ext in ['.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a']:
                    filtered_entries.append(entry)
            elif file_type_filter == 'document' and not os.path.isdir(fullpath):
                ext = os.path.splitext(entry)[1].lower()
                if ext in ['.pdf', '.doc', '.docx', '.txt', '.rtf', '.xls', '.xlsx', '.ppt', '.pptx']:
                    filtered_entries.append(entry)
        entries = filtered_entries

    # Sort entries
    def sort_key(entry):
        fullpath = os.path.join(path, entry)
        if sort_by == 'name':
            return entry.lower()
        elif sort_by == 'size':
            return os.path.getsize(fullpath) if os.path.isfile(fullpath) else 0
        elif sort_by == 'modified':
            return os.path.getmtime(fullpath)
        return entry.lower()

    entries.sort(key=sort_key, reverse=(sort_order == 'desc'))
    
    # Separate directories and files
    directories = [e for e in entries if os.path.isdir(os.path.join(path, e))]
    files = [e for e in entries if os.path.isfile(os.path.join(path, e))]
    
    # Always show directories first
    entries = directories + files

    displaypath = html.escape(urllib.parse.unquote(handler.path))
    list_rows = []

    # Parent directory link if not root
    if handler.path != '/':
        parent = os.path.dirname(handler.path.rstrip('/'))
        if not parent.endswith('/'):
            parent += '/'
        list_rows.append(f"""
            <tr class="hover:bg-green-900/20 light-theme:hover:bg-gray-100">
                <td class="py-2 px-4 border-b border-green-700/50 light-theme:border-gray-300">
                    <a href="{html.escape(parent)}" class="text-neon flex items-center">
                        📁 <span class="ml-2">.. (Parent Directory)</span>
                    </a>
                </td>
                <td class="py-2 px-4 border-b border-green-700/50 light-theme:border-gray-300 text-right">-</td>
                <td class="py-2 px-4 border-b border-green-700/50 light-theme:border-gray-300 text-right">-</td>
                <td class="py-2 px-4 border-b border-green-700/50 light-theme:border-gray-300 text-right">-</td>
            </tr>
        """)

    for name in entries:
        fullpath = os.path.join(path, name)
        displayname = name + '/' if os.path.isdir(fullpath) else name
        href = urllib.parse.quote(name)
        if os.path.isdir(fullpath):
            href += '/'
        
        size = "-"
        date_modified = "-"
        file_icon = get_file_icon(name, os.path.isdir(fullpath))
        
        if os.path.isfile(fullpath):
            size = format_size(os.path.getsize(fullpath))
            date_modified = datetime.datetime.fromtimestamp(os.path.getmtime(fullpath)).strftime('%Y-%m-%d %H:%M:%S')

        # Check if thumbnail exists for images
        thumbnail_path = None
        if os.path.isfile(fullpath):
            ext = os.path.splitext(name)[1].lower()
            if ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']:
                thumbnail_dir = os.path.join(handler.base_dir, '.thumbnails')
                thumbnail_name = f"{os.path.splitext(name)[0]}_thumb{ext}"
                thumbnail_full_path = os.path.join(thumbnail_dir, thumbnail_name)
                if os.path.exists(thumbnail_full_path):
                    thumbnail_path = f"/.thumbnails/{thumbnail_name}"

        if view_mode == 'grid':
            # Grid view for images and files
            card_content = f"""
                <div class="bg-gray-900 light-theme:bg-white border border-green-700/50 light-theme:border-gray-300 rounded-lg p-4 hover:bg-green-900/20 light-theme:hover:bg-gray-50 transition-colors">
                    <div class="text-center mb-2">
                        {f'<img src="{thumbnail_path}" alt="{name}" class="w-20 h-20 object-cover mx-auto rounded">' if thumbnail_path else f'<div class="text-4xl">{file_icon}</div>'}
                    </div>
                    <div class="text-sm">
                        <a href="{href}" class="text-neon hover:underline block truncate" title="{html.escape(displayname)}">{html.escape(displayname)}</a>
                        <div class="text-xs text-gray-400 light-theme:text-gray-600 mt-1">{size}</div>
                        <div class="text-xs text-gray-400 light-theme:text-gray-600">{date_modified}</div>
                    </div>
                    <div class="mt-2 flex justify-center space-x-1">
                        <button onclick="previewItem('{html.escape(href)}', '{html.escape(displayname)}')" class="bg-green-700 hover:bg-green-800 text-white font-bold py-1 px-2 rounded text-xs">Preview</button>
                        {f'<button onclick="editItem(\'{html.escape(href)}\', \'{html.escape(displayname)}\')" class="bg-blue-700 hover:bg-blue-800 text-white font-bold py-1 px-2 rounded text-xs">Edit</button>' if displayname.lower().endswith(('.txt', '.py', '.js', '.html', '.css', '.json', '.xml', '.md', '.log', '.cfg', '.ini', '.yml', '.yaml')) else ''}
                    </div>
                </div>
            """
            list_rows.append(card_content)
        else:
            # List view (table)
            list_rows.append(f"""
                <tr class="hover:bg-green-900/20 light-theme:hover:bg-gray-100">
                    <td class="py-2 px-4 border-b border-green-700/50 light-theme:border-gray-300">
                        <div class="flex items-center">
                            {f'<img src="{thumbnail_path}" alt="{name}" class="w-8 h-8 object-cover rounded mr-2">' if thumbnail_path else f'<span class="text-lg mr-2">{file_icon}</span>'}
                            <a href="{href}" class="text-neon hover:underline">{html.escape(displayname)}</a>
                        </div>
                    </td>
                    <td class="py-2 px-4 border-b border-green-700/50 light-theme:border-gray-300 text-right">{size}</td>
                    <td class="py-2 px-4 border-b border-green-700/50 light-theme:border-gray-300 text-right">{date_modified}</td>
                    <td class="py-2 px-4 border-b border-green-700/50 light-theme:border-gray-300 text-right">
                        <button onclick="previewItem('{html.escape(href)}', '{html.escape(displayname)}')" class="bg-green-700 hover:bg-green-800 text-white font-bold py-1 px-2 rounded text-xs mr-1">Preview</button>
                        {f'<button onclick="editItem(\'{html.escape(href)}\', \'{html.escape(displayname)}\')" class="bg-blue-700 hover:bg-blue-800 text-white font-bold py-1 px-2 rounded text-xs mr-1">Edit</button>' if displayname.lower().endswith(('.txt', '.py', '.js', '.html', '.css', '.json', '.xml', '.md', '.log', '.cfg', '.ini', '.yml', '.yaml')) else ''}
                        <button onclick="copyFile('{html.escape(href)}', '{html.escape(displayname)}')" class="bg-purple-700 hover:bg-purple-800 text-white font-bold py-1 px-2 rounded text-xs mr-1">Copy</button>
                        <button onclick="moveFile('{html.escape(href)}', '{html.escape(displayname)}')" class="bg-orange-700 hover:bg-orange-800 text-white font-bold py-1 px-2 rounded text-xs">Move</button>
                    </td>
                </tr>
            """)

    if view_mode == 'grid':
        list_html = f'<div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">{"".join(list_rows)}</div>'
    else:
        list_html = '\n'.join(list_rows)

    breadcrumb = generate_breadcrumb(displaypath, handler.path)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>PyServeX Enhanced - Index of {displaypath}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=VT323&display=swap');

        /* Dark Theme (Default) */
        body {{
            font-family: 'VT323', monospace;
            background: #000000;
            color: #00ff00;
            min-height: 100vh;
            margin: 0;
            overflow-x: hidden;
            transition: background-color 0.3s ease, color 0.3s ease;
        }}

        .text-neon {{
            color: #00ff00;
            transition: color 0.3s ease;
        }}

        /* Light Theme */
        body.light-theme {{
            background: #ffffff;
            color: #000000;
        }}

        body.light-theme .text-neon {{
            color: #000000;
        }}

        body.light-theme .scanline {{
            background: linear-gradient(
                to bottom,
                rgba(0, 0, 0, 0),
                rgba(0, 0, 0, 0.05) 50%,
                rgba(0, 0, 0, 0)
            );
        }}

        /* Theme Toggle Button */
        .theme-toggle-btn {{
            background: transparent;
            color: inherit;
            border: 1px solid;
            cursor: pointer;
            font-size: 1.2rem;
            transition: all 0.3s ease;
        }}

        .theme-toggle-btn:hover {{
            transform: scale(1.1);
        }}

        /* Dark theme styles */
        body:not(.light-theme) .theme-toggle-btn {{
            border-color: #00ff00;
            color: #00ff00;
        }}

        body:not(.light-theme) .theme-toggle-btn:hover {{
            background: rgba(0, 255, 0, 0.1);
        }}

        /* Light theme styles */
        body.light-theme .theme-toggle-btn {{
            border-color: #000000;
            color: #000000;
        }}

        body.light-theme .theme-toggle-btn:hover {{
            background: rgba(0, 0, 0, 0.1);
        }}

        /* Update table and form styles for light theme */
        body.light-theme table {{
            background: #f8f9fa;
            border-color: #000000;
        }}

        body.light-theme th,
        body.light-theme td {{
            border-color: #000000;
        }}

        body.light-theme tr:hover {{
            background: rgba(0, 0, 0, 0.05) !important;
        }}

        body.light-theme input,
        body.light-theme textarea,
        body.light-theme select {{
            background: #f8f9fa;
            color: #000000;
            border-color: #000000;
        }}

        body.light-theme input:focus,
        body.light-theme textarea:focus,
        body.light-theme select:focus {{
            border-color: #000000;
            box-shadow: 0 0 5px rgba(0, 0, 0, 0.3);
        }}

        body.light-theme button {{
            transition: all 0.3s ease;
        }}

        /* Update glitch animation for light theme */
        body.light-theme .glitch {{
            color: #000000;
        }}

        body.light-theme @keyframes blink-caret {{
            from, to {{ border-right: 2px solid #000000; }}
            50% {{ border-right: 2px solid transparent; }}
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
            100% {{ transform: translateY(100vh); }}
        }}

        .particle {{
            position: absolute;
            width: 2px;
            height: 2px;
            background: #00ff00;
            animation: float 6s ease-in-out infinite;
        }}

        @keyframes float {{
            0%, 100% {{ transform: translateY(0px) rotate(0deg); }}
            50% {{ transform: translateY(-20px) rotate(180deg); }}
        }}

        #successPopup {{
            position: fixed;
            top: 20px;
            right: 20px;
            background: #00ff00;
            color: #000000;
            padding: 10px 20px;
            border-radius: 5px;
            display: none;
            z-index: 1000;
            box-shadow: 0 0 10px rgba(0, 255, 0, 0.5);
        }}

        .filter-bar {{
            background: rgba(0, 255, 0, 0.1);
            border: 1px solid #00ff00;
            border-radius: 8px;
            padding: 1rem;
            margin-bottom: 1rem;
        }}

        body.light-theme .filter-bar {{
            background: rgba(0, 0, 0, 0.05);
            border-color: #000000;
        }}

        .stats-bar {{
            background: rgba(0, 255, 0, 0.05);
            border: 1px solid #00ff00;
            border-radius: 8px;
            padding: 0.5rem 1rem;
            margin-bottom: 1rem;
            font-size: 0.9rem;
        }}

        body.light-theme .stats-bar {{
            background: rgba(0, 0, 0, 0.02);
            border-color: #000000;
        }}
    </style>
</head>
<body>
    <div class="scanline"></div>
    <header>
        <div class="flex justify-between items-center mb-4">
            <div></div>
            <div class="text-center">
                <h1 class="text-4xl md:text-6xl text-neon typewriter glitch">PyServeX Enhanced</h1>
                <p class="text-lg text-neon mt-2">by <strong>Parth Padhiyar</strong> (<a href="https://github.com/SubZ3r0-0x01/pyservx" class="text-neon hover:underline">SubZ3r0-0x01</a>)</p>
                <p class="text-sm text-neon mt-1">v2.0.0 - Enhanced with Analytics & Advanced Features</p>
            </div>
            <div>
                <button id="themeToggle" class="theme-toggle-btn p-2 rounded-lg border border-green-700/50 hover:bg-green-700/20 transition-colors duration-200">
                    <span id="themeIcon">🌙</span>
                </button>
            </div>
        </div>
    </header>
    <main>
        <!-- Breadcrumb Navigation -->
        <div class="mb-4 p-2 bg-gray-900 light-theme:bg-gray-100 rounded">
            <nav class="text-sm">{breadcrumb}</nav>
        </div>

        <!-- Statistics Bar -->
        <div class="stats-bar">
            <div class="flex justify-between items-center text-sm">
                <span>📁 {len(directories)} folders, 📄 {len(files)} files</span>
                <span>💾 Total: {format_size(sum(os.path.getsize(os.path.join(path, f)) for f in files if os.path.isfile(os.path.join(path, f))))}</span>
            </div>
        </div>

        <!-- Enhanced Search and Filter Bar -->
        <div class="filter-bar">
            <form action="{html.escape(handler.path)}" method="GET" class="space-y-4">
                <div class="flex flex-col md:flex-row gap-4">
                    <div class="flex-1">
                        <input type="text" name="q" placeholder="🔍 Search files and folders..." value="{html.escape(search_query)}" 
                               class="w-full p-2 bg-black text-neon border border-green-700/50 rounded-md focus:outline-none focus:ring-1 focus:ring-green-500 light-theme:bg-gray-100 light-theme:text-gray-800 light-theme:border-gray-300">
                    </div>
                    <div class="flex gap-2">
                        <select name="type" class="p-2 bg-black text-neon border border-green-700/50 rounded-md light-theme:bg-gray-100 light-theme:text-gray-800 light-theme:border-gray-300">
                            <option value="">All Types</option>
                            <option value="folder" {'selected' if file_type_filter == 'folder' else ''}>📁 Folders</option>
                            <option value="image" {'selected' if file_type_filter == 'image' else ''}>🖼️ Images</option>
                            <option value="video" {'selected' if file_type_filter == 'video' else ''}>🎥 Videos</option>
                            <option value="audio" {'selected' if file_type_filter == 'audio' else ''}>🎵 Audio</option>
                            <option value="document" {'selected' if file_type_filter == 'document' else ''}>📄 Documents</option>
                        </select>
                        <select name="view" class="p-2 bg-black text-neon border border-green-700/50 rounded-md light-theme:bg-gray-100 light-theme:text-gray-800 light-theme:border-gray-300">
                            <option value="list" {'selected' if view_mode == 'list' else ''}>📋 List</option>
                            <option value="grid" {'selected' if view_mode == 'grid' else ''}>⊞ Grid</option>
                        </select>
                        <button type="submit" class="bg-green-500 text-black py-2 px-4 rounded-md hover:bg-green-600 transition-colors duration-200">Search</button>
                    </div>
                </div>
            </form>
        </div>

        <!-- File Listing -->
        <div class="overflow-x-auto">
            {f'<table class="min-w-full bg-black border border-green-700/50 rounded-lg light-theme:bg-white light-theme:border-gray-300"><thead><tr><th class="py-3 px-4 border-b border-green-700/50 light-theme:border-gray-300 text-left text-neon"><a href="?sort=name&order={{"desc" if sort_by == "name" and sort_order == "asc" else "asc"}}" class="block">📄 Name</a></th><th class="py-3 px-4 border-b border-green-700/50 light-theme:border-gray-300 text-right text-neon"><a href="?sort=size&order={{"desc" if sort_by == "size" and sort_order == "asc" else "asc"}}" class="block">📏 Size</a></th><th class="py-3 px-4 border-b border-green-700/50 light-theme:border-gray-300 text-right text-neon"><a href="?sort=modified&order={{"desc" if sort_by == "modified" and sort_order == "asc" else "asc"}}" class="block">📅 Modified</a></th><th class="py-3 px-4 border-b border-green-700/50 light-theme:border-gray-300 text-right text-neon">⚡ Actions</th></tr></thead><tbody>{list_html}</tbody></table>' if view_mode == 'list' else list_html}
        </div>

        <!-- Enhanced Upload and Actions -->
        <div class="upload-form mt-6 p-4 border border-green-700/50 light-theme:border-gray-300 rounded-lg">
            <form id="uploadForm" action="{html.escape(handler.path)}upload" method="POST" enctype="multipart/form-data" class="space-y-4">
                <div class="flex flex-col md:flex-row gap-4">
                    <div class="flex-1">
                        <label for="file-upload" class="text-neon block mb-2">📤 Upload files:</label>
                        <input type="file" id="file-upload" name="file" multiple 
                               class="w-full p-2 bg-black text-neon border border-green-700/50 rounded-md focus:outline-none focus:ring-1 focus:ring-green-500 light-theme:bg-gray-100 light-theme:text-gray-800 light-theme:border-gray-300" />
                    </div>
                    <div class="flex items-end">
                        <button type="submit" class="bg-green-500 text-black py-2 px-4 rounded-md hover:bg-green-600 transition-colors duration-200">Upload</button>
                    </div>
                </div>
            </form>
            
            <div class="mt-4 flex flex-wrap gap-2">
                <button onclick="createNewFolder()" class="bg-purple-700 hover:bg-purple-800 text-white font-bold py-2 px-4 rounded">📁 New Folder</button>
                <button onclick="createNewFile()" class="bg-teal-700 hover:bg-teal-800 text-white font-bold py-2 px-4 rounded">📄 New File</button>
                <button onclick="generateThumbnails()" class="bg-blue-700 hover:bg-blue-800 text-white font-bold py-2 px-4 rounded">🖼️ Generate Thumbnails</button>
                <button onclick="findDuplicates()" class="bg-yellow-700 hover:bg-yellow-800 text-white font-bold py-2 px-4 rounded">🔍 Find Duplicates</button>
                <button onclick="showAnalytics()" class="bg-indigo-700 hover:bg-indigo-800 text-white font-bold py-2 px-4 rounded">📊 Analytics</button>
            </div>
            
            <div id="progressBarContainer" style="display: none;" class="mt-4">
                <div class="bg-gray-700 rounded-full h-2">
                    <div id="progressBar" class="bg-green-500 h-2 rounded-full" style="width: 0%"></div>
                </div>
                <p id="progressText" class="text-neon mt-2">Uploading...</p>
            </div>
        </div>
    </main>

    <footer class="text-center py-4 text-neon text-[22px]">
    </footer>

    <div id="successPopup"></div>

    <!-- Enhanced Modals -->
    <div id="analyticsModal" class="fixed inset-0 bg-black bg-opacity-50 hidden z-50">
        <div class="flex items-center justify-center min-h-screen p-4">
            <div class="bg-gray-900 light-theme:bg-white border border-green-700 light-theme:border-gray-300 rounded-lg p-6 max-w-4xl w-full max-h-96 overflow-y-auto">
                <div class="flex justify-between items-center mb-4">
                    <h3 class="text-xl text-neon">📊 Analytics Dashboard</h3>
                    <button onclick="closeModal('analyticsModal')" class="text-neon hover:text-red-500">✕</button>
                </div>
                <div id="analyticsContent">Loading analytics...</div>
            </div>
        </div>
    </div>

    <div id="duplicatesModal" class="fixed inset-0 bg-black bg-opacity-50 hidden z-50">
        <div class="flex items-center justify-center min-h-screen p-4">
            <div class="bg-gray-900 light-theme:bg-white border border-green-700 light-theme:border-gray-300 rounded-lg p-6 max-w-4xl w-full max-h-96 overflow-y-auto">
                <div class="flex justify-between items-center mb-4">
                    <h3 class="text-xl text-neon">🔍 Duplicate Files</h3>
                    <button onclick="closeModal('duplicatesModal')" class="text-neon hover:text-red-500">✕</button>
                </div>
                <div id="duplicatesContent">Scanning for duplicates...</div>
            </div>
        </div>
    </div>

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

        // Handle file uploads with progress bar
        document.getElementById('uploadForm').addEventListener('submit', function(e) {{
            e.preventDefault();
            
            const formData = new FormData(this);
            const progressBarContainer = document.getElementById('progressBarContainer');
            const progressBar = document.getElementById('progressBar');
            const progressText = document.getElementById('progressText');
            
            progressBarContainer.style.display = 'block';
            progressBar.style.width = '0%';
            progressText.textContent = 'Uploading...';

            const xhr = new XMLHttpRequest();
            
            xhr.upload.addEventListener('progress', function(event) {{
                if (event.lengthComputable) {{
                    const percent = (event.loaded / event.total) * 100;
                    progressBar.style.width = percent.toFixed(2) + '%';
                    progressText.textContent = `Uploading: ${{percent.toFixed(2)}}%`;
                }}
            }});

            xhr.addEventListener('load', function() {{
                progressBarContainer.style.display = 'none';
                if (xhr.status === 200) {{
                    const successPopup = document.getElementById('successPopup');
                    successPopup.textContent = 'Files uploaded successfully!';
                    successPopup.style.display = 'block';
                    setTimeout(() => {{
                        successPopup.style.display = 'none';
                        window.location.reload();
                    }}, 2000);
                }} else {{
                    progressText.textContent = 'Upload failed!';
                    alert('Upload failed: ' + xhr.statusText);
                }}
            }});

            xhr.addEventListener('error', function() {{
                progressBarContainer.style.display = 'none';
                progressText.textContent = 'Upload failed!';
                alert('Upload failed due to a network error.');
            }});

            xhr.open('POST', this.action);
            xhr.send(formData);
        }});

        function previewItem(path, name) {{
            const currentPath = window.location.pathname;
            const fullPath = currentPath.endsWith('/') ? currentPath + path : currentPath + '/' + path;
            window.open(fullPath + '/preview', '_blank');
        }}

        function editItem(path, name) {{
            const currentPath = window.location.pathname;
            const fullPath = currentPath.endsWith('/') ? currentPath + path : currentPath + '/' + path;
            window.open(fullPath + '/edit', '_blank');
        }}

        function createNewFolder() {{
            const folderName = prompt("Enter new folder name:");
            if (folderName) {{
                fetch(window.location.pathname + folderName, {{
                    method: 'MKCOL',
                }})
                .then(response => response.json())
                .then(data => {{
                    const successPopup = document.getElementById('successPopup');
                    if (data.status === 'success') {{
                        successPopup.textContent = data.message;
                        successPopup.style.display = 'block';
                        setTimeout(() => {{
                            successPopup.style.display = 'none';
                            window.location.reload();
                        }}, 2000);
                    }} else {{
                        alert('Create folder failed: ' + data.message);
                    }}
                }})
                .catch(error => {{
                    console.error('Error:', error);
                    alert('Create folder failed due to a network error.');
                }});
            }}
        }}

        function createNewFile() {{
            window.open(window.location.pathname + 'notepad', '_blank');
        }}

        function copyFile(path, name) {{
            const destination = prompt(`Copy "${{name}}" to (relative path):`, './');
            if (destination) {{
                fetch(window.location.pathname + 'copy', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ source: path, destination: destination }})
                }})
                .then(response => response.json())
                .then(data => {{
                    if (data.status === 'success') {{
                        showSuccess(data.message);
                        setTimeout(() => window.location.reload(), 1000);
                    }} else {{
                        alert('Copy failed: ' + data.message);
                    }}
                }})
                .catch(error => alert('Copy failed: ' + error));
            }}
        }}

        function moveFile(path, name) {{
            const destination = prompt(`Move "${{name}}" to (relative path):`, './');
            if (destination) {{
                fetch(window.location.pathname + 'move', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ source: path, destination: destination }})
                }})
                .then(response => response.json())
                .then(data => {{
                    if (data.status === 'success') {{
                        showSuccess(data.message);
                        setTimeout(() => window.location.reload(), 1000);
                    }} else {{
                        alert('Move failed: ' + data.message);
                    }}
                }})
                .catch(error => alert('Move failed: ' + error));
            }}
        }}

        function generateThumbnails() {{
            fetch(window.location.pathname + 'generate_thumbnails', {{ method: 'POST' }})
            .then(response => response.json())
            .then(data => {{
                if (data.status === 'success') {{
                    showSuccess(data.message);
                    setTimeout(() => window.location.reload(), 2000);
                }} else {{
                    alert('Thumbnail generation failed: ' + data.message);
                }}
            }})
            .catch(error => alert('Thumbnail generation failed: ' + error));
        }}

        function findDuplicates() {{
            document.getElementById('duplicatesModal').classList.remove('hidden');
            fetch(window.location.pathname + 'find_duplicates')
            .then(response => response.json())
            .then(data => {{
                const content = document.getElementById('duplicatesContent');
                if (data.duplicates && data.duplicates.length > 0) {{
                    let html = '<div class="space-y-2">';
                    data.duplicates.forEach(dup => {{
                        html += `<div class="p-2 border border-gray-600 rounded">
                            <div class="font-bold">${{dup.original}}</div>
                            <div class="text-sm text-gray-400">Duplicate: ${{dup.duplicate}}</div>
                            <div class="text-xs">Size: ${{dup.size}} bytes</div>
                        </div>`;
                    }});
                    html += '</div>';
                    content.innerHTML = html;
                }} else {{
                    content.innerHTML = '<p class="text-center text-gray-400">No duplicates found! 🎉</p>';
                }}
            }})
            .catch(error => {{
                document.getElementById('duplicatesContent').innerHTML = 'Error loading duplicates: ' + error;
            }});
        }}

        function showAnalytics() {{
            document.getElementById('analyticsModal').classList.remove('hidden');
            fetch(window.location.pathname + 'analytics')
            .then(response => response.json())
            .then(data => {{
                const content = document.getElementById('analyticsContent');
                let html = '<div class="grid grid-cols-1 md:grid-cols-2 gap-4">';
                
                // Popular files
                if (data.popular_files && data.popular_files.length > 0) {{
                    html += '<div><h4 class="font-bold mb-2">📈 Most Popular Files</h4><ul class="space-y-1">';
                    data.popular_files.forEach(file => {{
                        html += `<li class="text-sm">${{file[0]}} (accessed ${{file[1]}} times)</li>`;
                    }});
                    html += '</ul></div>';
                }}
                
                // Usage stats
                if (data.usage_stats && data.usage_stats.length > 0) {{
                    html += '<div><h4 class="font-bold mb-2">📊 Usage Statistics</h4><ul class="space-y-1">';
                    data.usage_stats.forEach(stat => {{
                        html += `<li class="text-sm">${{stat[0]}}: ${{stat[1]}} requests, ${{stat[2]}} visitors</li>`;
                    }});
                    html += '</ul></div>';
                }}
                
                html += '</div>';
                content.innerHTML = html;
            }})
            .catch(error => {{
                document.getElementById('analyticsContent').innerHTML = 'Error loading analytics: ' + error;
            }});
        }}

        function closeModal(modalId) {{
            document.getElementById(modalId).classList.add('hidden');
        }}

        function showSuccess(message) {{
            const popup = document.getElementById('successPopup');
            popup.textContent = message;
            popup.style.display = 'block';
            setTimeout(() => popup.style.display = 'none', 3000);
        }}

        // Drag and Drop functionality
        const dropZone = document.getElementById('dropZone');
        const uploadForm = document.getElementById('uploadForm');

        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {{
            dropZone.addEventListener(eventName, preventDefaults, false);
            document.body.addEventListener(eventName, preventDefaults, false);
        }});

        ['dragenter', 'dragover'].forEach(eventName => {{
            dropZone.addEventListener(eventName, highlight, false);
        }});

        ['dragleave', 'drop'].forEach(eventName => {{
            dropZone.addEventListener(eventName, unhighlight, false);
        }});

        dropZone.addEventListener('drop', handleDrop, false);

        function preventDefaults(e) {{
            e.preventDefault();
            e.stopPropagation();
        }}

        function highlight() {{
            dropZone.classList.add('highlight');
        }}

        function unhighlight() {{
            dropZone.classList.remove('highlight');
        }}

        function handleDrop(e) {{
            const dt = e.dataTransfer;
            const files = dt.files;

            document.getElementById('file-upload').files = files;
            uploadForm.dispatchEvent(new Event('submit', {{ cancelable: true }}));
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

        window.onload = function() {{
            createParticles();
            initTheme();
        }};
    </script>
</body>
</html>
"""