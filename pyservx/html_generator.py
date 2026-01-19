#!/usr/bin/env python3

import html
import os
import urllib.parse
import datetime

def format_size(size):
    if size < 1024:
        return f"{size} B"
    elif size < 1024**2:
        return f"{size / 1024:.2f} KB"
    elif size < 1024**3:
        return f"{size / (1024**2):.2f} MB"
    else:
        return f"{size / (1024**3):.2f} GB"

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

    if search_query:
        entries = [e for e in entries if search_query.lower() in e.lower()]

    def sort_key(item):
        item_path = os.path.join(path, item)
        if os.path.isdir(item_path):
            return (0, item.lower()) # Directories first
        if sort_by == 'size':
            return (1, os.path.getsize(item_path))
        elif sort_by == 'date':
            return (1, os.path.getmtime(item_path))
        else:
            return (1, item.lower())

    entries.sort(key=sort_key, reverse=sort_order == 'desc')
    
    displaypath = html.escape(urllib.parse.unquote(handler.path))

    # Build list items for directories and files
    list_rows = []
    # Parent directory link if not root
    if handler.path != '/':
        parent = os.path.dirname(handler.path.rstrip('/'))
        if not parent.endswith('/'):
            parent += '/'
        list_rows.append(f"""
            <tr class="hover:bg-green-900/20 cursor-pointer" onclick="navigateToPath('{html.escape(parent)}')">
                <td class="py-2 px-4 border-b border-green-700/50">
                    <span class="text-neon">📁 .. (Parent Directory)</span>
                </td>
                <td class="py-2 px-4 border-b border-green-700/50 text-right">-</td>
                <td class="py-2 px-4 border-b border-green-700/50 text-right">-</td>
                <td class="py-2 px-4 border-b border-green-700/50 text-right">-</td>
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
        if os.path.isfile(fullpath):
            size = format_size(os.path.getsize(fullpath))
            date_modified = datetime.datetime.fromtimestamp(os.path.getmtime(fullpath)).strftime('%Y-%m-%d %H:%M:%S')

        # Determine file type for direct download
        file_ext = os.path.splitext(name)[1].lower()
        is_media = file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.mkv', '.mp3', '.wav', '.ogg', '.flac', '.aac']
        
        # Add download folder zip link for directories
        if os.path.isdir(fullpath):
            list_rows.append(
                f"""
                <tr class="hover:bg-green-900/20 cursor-pointer" onclick="navigateToPath('{href}')">
                    <td class="py-2 px-4 border-b border-green-700/50">
                        <span class="text-neon">📁 {html.escape(displayname)}</span>
                    </td>
                    <td class="py-2 px-4 border-b border-green-700/50 text-right">{size}</td>
                    <td class="py-2 px-4 border-b border-green-700/50 text-right">{date_modified}</td>
                    <td class="py-2 px-4 border-b border-green-700/50 text-right">
                        <button onclick="event.stopPropagation(); downloadFolder('{href}')" class="bg-purple-700 hover:bg-purple-800 text-white font-bold py-1 px-2 rounded text-xs">📦 Zip</button>
                    </td>
                </tr>
                """
            )
        else:
            # For files, determine action based on type
            if is_media:
                # Direct download for media files
                action_onclick = f"event.stopPropagation(); downloadFile('{href}', '{html.escape(displayname)}')"
                file_icon = "🎬" if file_ext in ['.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.mkv'] else "🎵" if file_ext in ['.mp3', '.wav', '.ogg', '.flac', '.aac'] else "🖼️"
            else:
                # Regular file click behavior
                action_onclick = f"previewFile('{href}', '{html.escape(displayname)}')"
                file_icon = "📄"
            
            list_rows.append(f"""
                <tr class="hover:bg-green-900/20 cursor-pointer" onclick="{action_onclick}">
                    <td class="py-2 px-4 border-b border-green-700/50">
                        <span class="text-neon">{file_icon} {html.escape(displayname)}</span>
                    </td>
                    <td class="py-2 px-4 border-b border-green-700/50 text-right">{size}</td>
                    <td class="py-2 px-4 border-b border-green-700/50 text-right">{date_modified}</td>
                    <td class="py-2 px-4 border-b border-green-700/50 text-right">
                        <button onclick="event.stopPropagation(); previewFile('{href}', '{html.escape(displayname)}')" class="bg-green-700 hover:bg-green-800 text-white font-bold py-1 px-2 rounded text-xs mr-1">👁️</button>
                        {f'<button onclick="event.stopPropagation(); editFile(\'{href}\', \'{html.escape(displayname)}\')" class="bg-blue-700 hover:bg-blue-800 text-white font-bold py-1 px-2 rounded text-xs mr-1">✏️</button>' if displayname.lower().endswith(('.txt', '.py', '.js', '.html', '.css', '.json', '.xml', '.md', '.log', '.cfg', '.ini', '.yml', '.yaml')) else ''}
                        <button onclick="event.stopPropagation(); downloadFile('{href}', '{html.escape(displayname)}')" class="bg-orange-700 hover:bg-orange-800 text-white font-bold py-1 px-2 rounded text-xs">⬇️</button>
                    </td>
                </tr>
            """)

    list_html = '\n'.join(list_rows)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>PyServeX v3.0 - {displaypath}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=VT323&display=swap');

        /* Fixed Layout - No Scrolling */
        html, body {{
            height: 100vh;
            overflow: hidden;
            margin: 0;
            padding: 0;
            font-family: 'VT323', monospace;
            background: #000000;
            color: #00ff00;
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
            position: fixed;
            top: 1rem;
            right: 1rem;
            z-index: 1000;
            padding: 0.5rem;
            border-radius: 0.5rem;
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

        /* Main Layout Container */
        .main-container {{
            display: flex;
            height: 100vh;
            flex-direction: column;
        }}

        /* Header */
        .header {{
            height: 80px;
            flex-shrink: 0;
            display: flex;
            align-items: center;
            justify-content: center;
            border-bottom: 1px solid #00ff00;
            position: relative;
        }}

        body.light-theme .header {{
            border-bottom-color: #000000;
        }}

        /* Content Area */
        .content-area {{
            flex: 1;
            display: flex;
            overflow: hidden;
        }}

        /* File Explorer Panel */
        .file-explorer {{
            width: 60%;
            border-right: 1px solid #00ff00;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }}

        body.light-theme .file-explorer {{
            border-right-color: #000000;
        }}

        /* Search and Controls */
        .search-controls {{
            padding: 1rem;
            border-bottom: 1px solid #00ff00;
            flex-shrink: 0;
        }}

        body.light-theme .search-controls {{
            border-bottom-color: #000000;
        }}

        /* File List Container */
        .file-list-container {{
            flex: 1;
            overflow-y: auto;
            overflow-x: hidden;
        }}

        /* Text Panel */
        .text-panel {{
            width: 40%;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }}

        /* Text Area */
        .text-area {{
            flex: 1;
            display: flex;
            flex-direction: column;
            padding: 1rem;
            overflow: hidden;
        }}

        .text-content {{
            flex: 1;
            overflow-y: auto;
            border: 1px solid #00ff00;
            padding: 1rem;
            background: rgba(0, 255, 0, 0.05);
            font-family: 'Courier New', monospace;
            font-size: 14px;
            line-height: 1.5;
            resize: none;
        }}

        body.light-theme .text-content {{
            border-color: #000000;
            background: rgba(0, 0, 0, 0.05);
        }}

        /* Scrollbar Styling */
        .file-list-container::-webkit-scrollbar,
        .text-content::-webkit-scrollbar {{
            width: 8px;
        }}

        .file-list-container::-webkit-scrollbar-track,
        .text-content::-webkit-scrollbar-track {{
            background: rgba(0, 255, 0, 0.1);
        }}

        .file-list-container::-webkit-scrollbar-thumb,
        .text-content::-webkit-scrollbar-thumb {{
            background: #00ff00;
            border-radius: 4px;
        }}

        body.light-theme .file-list-container::-webkit-scrollbar-track,
        body.light-theme .text-content::-webkit-scrollbar-track {{
            background: rgba(0, 0, 0, 0.1);
        }}

        body.light-theme .file-list-container::-webkit-scrollbar-thumb,
        body.light-theme .text-content::-webkit-scrollbar-thumb {{
            background: #000000;
        }}

        /* Table Styles */
        table {{
            width: 100%;
            border-collapse: collapse;
        }}

        th, td {{
            text-align: left;
            padding: 0.5rem;
            border-bottom: 1px solid rgba(0, 255, 0, 0.3);
        }}

        body.light-theme th,
        body.light-theme td {{
            border-bottom-color: rgba(0, 0, 0, 0.3);
        }}

        th {{
            background-color: rgba(0, 255, 0, 0.1);
            color: #00ff00;
            font-weight: normal;
            cursor: pointer;
            position: sticky;
            top: 0;
            z-index: 10;
        }}

        body.light-theme th {{
            background-color: rgba(0, 0, 0, 0.1);
            color: #000000;
        }}

        th:hover {{
            background-color: rgba(0, 255, 0, 0.2);
        }}

        body.light-theme th:hover {{
            background-color: rgba(0, 0, 0, 0.2);
        }}

        tr:nth-child(even) {{
            background-color: rgba(0, 255, 0, 0.05);
        }}

        body.light-theme tr:nth-child(even) {{
            background-color: rgba(0, 0, 0, 0.05);
        }}

        /* Input Styles */
        input, textarea, button {{
            background: #111111;
            color: #00ff00;
            border: 1px solid #00ff00;
            padding: 0.5rem;
            font-family: 'VT323', monospace;
            transition: all 0.3s ease;
        }}

        body.light-theme input,
        body.light-theme textarea,
        body.light-theme button {{
            background: #f8f9fa;
            color: #000000;
            border-color: #000000;
        }}

        input:focus, textarea:focus {{
            outline: none;
            box-shadow: 0 0 5px rgba(0, 255, 0, 0.5);
        }}

        body.light-theme input:focus,
        body.light-theme textarea:focus {{
            box-shadow: 0 0 5px rgba(0, 0, 0, 0.3);
        }}

        button:hover {{
            background: rgba(0, 255, 0, 0.1);
            transform: scale(1.05);
        }}

        body.light-theme button:hover {{
            background: rgba(0, 0, 0, 0.1);
        }}

        /* Glitch Animation */
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

        /* Scanline Effect */
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

        /* Upload Progress */
        .upload-progress {{
            margin-top: 1rem;
            padding: 0.5rem;
            border: 1px solid #00ff00;
            border-radius: 4px;
            display: none;
        }}

        body.light-theme .upload-progress {{
            border-color: #000000;
        }}

        .progress-bar {{
            width: 0%;
            height: 20px;
            background-color: #00ff00;
            text-align: center;
            line-height: 20px;
            color: #000;
            font-size: 0.8rem;
            transition: width 0.3s ease;
        }}

        body.light-theme .progress-bar {{
            background-color: #000000;
            color: #fff;
        }}

        /* Responsive Design */
        @media (max-width: 768px) {{
            .content-area {{
                flex-direction: column;
            }}
            
            .file-explorer {{
                width: 100%;
                height: 60%;
                border-right: none;
                border-bottom: 1px solid #00ff00;
            }}
            
            body.light-theme .file-explorer {{
                border-bottom-color: #000000;
            }}
            
            .text-panel {{
                width: 100%;
                height: 40%;
            }}
        }}
    </style>
</head>
<body>
    <div class="scanline"></div>
    <button id="themeToggle" class="theme-toggle-btn">
        <span id="themeIcon">🌙</span>
    </button>

    <div class="main-container">
        <!-- Header -->
        <div class="header">
            <div class="text-center">
                <h1 class="text-3xl md:text-4xl text-neon glitch">PyServeX v3.0</h1>
                <p class="text-sm text-neon">Enhanced File Server by <strong>Parth Padhiyar</strong></p>
            </div>
        </div>

        <!-- Content Area -->
        <div class="content-area">
            <!-- File Explorer Panel -->
            <div class="file-explorer">
                <!-- Search and Controls -->
                <div class="search-controls">
                    <div class="mb-4">
                        <h2 class="text-xl mb-2 text-neon">📁 {displaypath}</h2>
                        <div class="flex flex-col sm:flex-row gap-2">
                            <input type="text" id="searchInput" placeholder="🔍 Real-time search..." 
                                   value="{html.escape(search_query)}" 
                                   class="flex-grow p-2 rounded-md focus:outline-none focus:ring-1 focus:ring-green-500">
                            <button onclick="clearSearch()" class="bg-red-700 hover:bg-red-800 text-white py-2 px-4 rounded-md">Clear</button>
                        </div>
                    </div>
                    
                    <!-- Upload Section -->
                    <div class="mb-4">
                        <form id="uploadForm" class="flex flex-col sm:flex-row gap-2">
                            <input type="file" id="fileUpload" multiple class="flex-grow p-2 rounded-md">
                            <button type="submit" class="bg-green-700 hover:bg-green-800 text-white py-2 px-4 rounded-md">Upload</button>
                        </form>
                        <div class="flex gap-2 mt-2">
                            <button onclick="createNewFolder()" class="bg-purple-700 hover:bg-purple-800 text-white py-1 px-3 rounded text-sm">📁 New Folder</button>
                            <button onclick="createNewFile()" class="bg-teal-700 hover:bg-teal-800 text-white py-1 px-3 rounded text-sm">📄 New File</button>
                        </div>
                        <div id="uploadProgress" class="upload-progress">
                            <div id="progressBar" class="progress-bar"></div>
                            <div id="progressText" class="text-center mt-1 text-sm"></div>
                        </div>
                    </div>
                </div>

                <!-- File List Container -->
                <div class="file-list-container">
                    <table>
                        <thead>
                            <tr>
                                <th onclick="sortFiles('name')" class="cursor-pointer">
                                    📄 Name {('↓' if sort_by == 'name' and sort_order == 'desc' else '↑' if sort_by == 'name' else '')}
                                </th>
                                <th onclick="sortFiles('size')" class="cursor-pointer text-right">
                                    📏 Size {('↓' if sort_by == 'size' and sort_order == 'desc' else '↑' if sort_by == 'size' else '')}
                                </th>
                                <th onclick="sortFiles('date')" class="cursor-pointer text-right">
                                    📅 Modified {('↓' if sort_by == 'date' and sort_order == 'desc' else '↑' if sort_by == 'date' else '')}
                                </th>
                                <th class="text-right">⚡ Actions</th>
                            </tr>
                        </thead>
                        <tbody id="fileTableBody">
                            {list_html}
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Text Panel -->
            <div class="text-panel">
                <div class="text-area">
                    <div class="mb-4 flex justify-between items-center">
                        <h3 class="text-lg text-neon">📝 Text Clipboard</h3>
                        <div class="flex gap-2">
                            <button onclick="saveTextClipboard()" class="bg-green-700 hover:bg-green-800 text-white py-1 px-3 rounded text-sm">💾 Save</button>
                            <button onclick="clearTextClipboard()" class="bg-red-700 hover:bg-red-800 text-white py-1 px-3 rounded text-sm">🗑️ Clear</button>
                            <button onclick="copyToClipboard()" class="bg-blue-700 hover:bg-blue-800 text-white py-1 px-3 rounded text-sm">📋 Copy</button>
                        </div>
                    </div>
                    <textarea id="textClipboard" class="text-content resize-none" 
                              placeholder="📝 Your permanent text clipboard...&#10;&#10;• Copy/paste text here&#10;• Click Save to persist&#10;• Survives page refreshes&#10;• Perfect for notes, code snippets, etc."></textarea>
                    <div id="clipboardStatus" class="mt-2 text-center text-sm"></div>
                </div>
            </div>
        </div>
    </div>

    <script>
        let currentPath = '{displaypath}';
        let searchTimeout;

        // Initialize on page load
        window.onload = function() {{
            initTheme();
            loadTextClipboard();
            setupRealTimeSearch();
            setupUploadHandling();
        }};

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

        // Real-time Search
        function setupRealTimeSearch() {{
            const searchInput = document.getElementById('searchInput');
            searchInput.addEventListener('input', function() {{
                clearTimeout(searchTimeout);
                searchTimeout = setTimeout(() => {{
                    performSearch(this.value);
                }}, 300);
            }});
        }}

        function performSearch(query) {{
            const rows = document.querySelectorAll('#fileTableBody tr');
            rows.forEach(row => {{
                const nameCell = row.querySelector('td:first-child');
                if (nameCell) {{
                    const fileName = nameCell.textContent.toLowerCase();
                    if (query === '' || fileName.includes(query.toLowerCase())) {{
                        row.style.display = '';
                    }} else {{
                        row.style.display = 'none';
                    }}
                }}
            }});
        }}

        function clearSearch() {{
            document.getElementById('searchInput').value = '';
            performSearch('');
        }}

        // Navigation
        function navigateToPath(path) {{
            window.location.href = path;
        }}

        function sortFiles(sortBy) {{
            const url = new URL(window.location);
            const currentSort = url.searchParams.get('sort');
            const currentOrder = url.searchParams.get('order');
            let newOrder = 'asc';
            
            if (currentSort === sortBy && currentOrder === 'asc') {{
                newOrder = 'desc';
            }}
            
            url.searchParams.set('sort', sortBy);
            url.searchParams.set('order', newOrder);
            window.location.href = url.toString();
        }}

        // File Operations
        function downloadFile(path, filename) {{
            const link = document.createElement('a');
            link.href = path;
            link.download = filename;
            link.click();
        }}

        function downloadFolder(path) {{
            window.location.href = path + 'download_folder';
        }}

        function previewFile(path, filename) {{
            window.open(path + '/preview', '_blank');
        }}

        function editFile(path, filename) {{
            window.open(path + '/edit', '_blank');
        }}

        function createNewFolder() {{
            const folderName = prompt("📁 Enter new folder name:");
            if (folderName) {{
                fetch(window.location.pathname + folderName, {{
                    method: 'MKCOL',
                }})
                .then(response => response.json())
                .then(data => {{
                    if (data.status === 'success') {{
                        showStatus('✅ ' + data.message, 'success');
                        setTimeout(() => window.location.reload(), 1500);
                    }} else {{
                        showStatus('❌ ' + data.message, 'error');
                    }}
                }})
                .catch(error => {{
                    showStatus('❌ Network error creating folder', 'error');
                }});
            }}
        }}

        function createNewFile() {{
            window.open(window.location.pathname + 'notepad', '_blank');
        }}

        // Upload Handling
        function setupUploadHandling() {{
            const uploadForm = document.getElementById('uploadForm');
            const fileUpload = document.getElementById('fileUpload');
            const uploadProgress = document.getElementById('uploadProgress');
            const progressBar = document.getElementById('progressBar');
            const progressText = document.getElementById('progressText');

            uploadForm.addEventListener('submit', function(e) {{
                e.preventDefault();
                
                const files = fileUpload.files;
                if (files.length === 0) {{
                    showStatus('❌ Please select files to upload', 'error');
                    return;
                }}

                const formData = new FormData();
                for (let i = 0; i < files.length; i++) {{
                    formData.append('file', files[i]);
                }}

                const xhr = new XMLHttpRequest();
                
                uploadProgress.style.display = 'block';
                progressBar.style.width = '0%';
                progressText.textContent = 'Uploading...';

                xhr.upload.addEventListener('progress', function(event) {{
                    if (event.lengthComputable) {{
                        const percent = (event.loaded / event.total) * 100;
                        progressBar.style.width = percent.toFixed(2) + '%';
                        progressText.textContent = `Uploading: ${{percent.toFixed(1)}}%`;
                    }}
                }});

                xhr.addEventListener('load', function() {{
                    uploadProgress.style.display = 'none';
                    if (xhr.status === 200) {{
                        const response = JSON.parse(xhr.responseText);
                        showStatus('✅ ' + response.message, 'success');
                        setTimeout(() => window.location.reload(), 1500);
                    }} else {{
                        showStatus('❌ Upload failed', 'error');
                    }}
                }});

                xhr.addEventListener('error', function() {{
                    uploadProgress.style.display = 'none';
                    showStatus('❌ Upload failed due to network error', 'error');
                }});

                xhr.open('POST', window.location.pathname + 'upload');
                xhr.send(formData);
            }});

            // Drag and drop
            const fileExplorer = document.querySelector('.file-explorer');
            
            ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {{
                fileExplorer.addEventListener(eventName, preventDefaults, false);
            }});

            ['dragenter', 'dragover'].forEach(eventName => {{
                fileExplorer.addEventListener(eventName, highlight, false);
            }});

            ['dragleave', 'drop'].forEach(eventName => {{
                fileExplorer.addEventListener(eventName, unhighlight, false);
            }});

            function preventDefaults(e) {{
                e.preventDefault();
                e.stopPropagation();
            }}

            function highlight() {{
                fileExplorer.style.background = 'rgba(0, 255, 0, 0.1)';
            }}

            function unhighlight() {{
                fileExplorer.style.background = '';
            }}

            fileExplorer.addEventListener('drop', function(e) {{
                const dt = e.dataTransfer;
                const files = dt.files;
                fileUpload.files = files;
                uploadForm.dispatchEvent(new Event('submit', {{ cancelable: true }}));
            }});
        }}

        // Text Clipboard Functions
        function loadTextClipboard() {{
            // Try to load from server first, fallback to localStorage
            fetch(window.location.pathname + 'load_clipboard?path=' + encodeURIComponent(window.location.pathname))
                .then(response => response.json())
                .then(data => {{
                    if (data.status === 'success' && data.content) {{
                        document.getElementById('textClipboard').value = data.content;
                    }} else {{
                        // Fallback to localStorage
                        const saved = localStorage.getItem('pyservx-clipboard-' + window.location.pathname);
                        if (saved) {{
                            document.getElementById('textClipboard').value = saved;
                        }}
                    }}
                }})
                .catch(error => {{
                    // Fallback to localStorage on error
                    const saved = localStorage.getItem('pyservx-clipboard-' + window.location.pathname);
                    if (saved) {{
                        document.getElementById('textClipboard').value = saved;
                    }}
                }});
        }}

        function saveTextClipboard() {{
            const content = document.getElementById('textClipboard').value;
            
            // Save to server
            fetch(window.location.pathname + 'save_clipboard', {{
                method: 'POST',
                headers: {{
                    'Content-Type': 'application/json',
                }},
                body: JSON.stringify({{
                    content: content,
                    path: window.location.pathname
                }})
            }})
            .then(response => response.json())
            .then(data => {{
                if (data.status === 'success') {{
                    // Also save to localStorage as backup
                    localStorage.setItem('pyservx-clipboard-' + window.location.pathname, content);
                    showClipboardStatus('💾 Text saved successfully!', 'success');
                }} else {{
                    showClipboardStatus('❌ Save failed: ' + data.message, 'error');
                }}
            }})
            .catch(error => {{
                // Fallback to localStorage only
                localStorage.setItem('pyservx-clipboard-' + window.location.pathname, content);
                showClipboardStatus('💾 Saved locally (server unavailable)', 'info');
            }});
        }}

        function clearTextClipboard() {{
            if (confirm('🗑️ Clear all text in clipboard?')) {{
                document.getElementById('textClipboard').value = '';
                localStorage.removeItem('pyservx-clipboard-' + window.location.pathname);
                showClipboardStatus('🗑️ Clipboard cleared', 'info');
            }}
        }}

        function copyToClipboard() {{
            const textArea = document.getElementById('textClipboard');
            textArea.select();
            textArea.setSelectionRange(0, 99999);
            
            try {{
                document.execCommand('copy');
                showClipboardStatus('📋 Copied to system clipboard!', 'success');
            }} catch (err) {{
                // Fallback for modern browsers
                navigator.clipboard.writeText(textArea.value).then(() => {{
                    showClipboardStatus('📋 Copied to system clipboard!', 'success');
                }}).catch(() => {{
                    showClipboardStatus('❌ Copy failed', 'error');
                }});
            }}
        }}

        // Status Functions
        function showStatus(message, type) {{
            // You can implement a toast notification here
            console.log(type + ': ' + message);
        }}

        function showClipboardStatus(message, type) {{
            const status = document.getElementById('clipboardStatus');
            status.textContent = message;
            status.className = `mt-2 text-center text-sm ${{type === 'success' ? 'text-green-500' : type === 'error' ? 'text-red-500' : 'text-blue-500'}}`;
            setTimeout(() => {{
                status.textContent = '';
                status.className = 'mt-2 text-center text-sm';
            }}, 3000);
        }}

        // Auto-save clipboard content
        document.getElementById('textClipboard').addEventListener('input', function() {{
            clearTimeout(window.clipboardSaveTimeout);
            window.clipboardSaveTimeout = setTimeout(() => {{
                const content = document.getElementById('textClipboard').value;
                // Only auto-save if there's content and it's different from what's saved
                if (content.trim()) {{
                    // Save to localStorage immediately for responsiveness
                    localStorage.setItem('pyservx-clipboard-' + window.location.pathname, content);
                    
                    // Save to server
                    fetch(window.location.pathname + 'save_clipboard', {{
                        method: 'POST',
                        headers: {{
                            'Content-Type': 'application/json',
                        }},
                        body: JSON.stringify({{
                            content: content,
                            path: window.location.pathname
                        }})
                    }})
                    .then(response => response.json())
                    .then(data => {{
                        if (data.status === 'success') {{
                            showClipboardStatus('💾 Auto-saved', 'success');
                        }}
                    }})
                    .catch(error => {{
                        // Silent fail for auto-save
                        console.log('Auto-save failed, using localStorage only');
                    }});
                }}
            }}, 2000);
        }});
    </script>
</body>
</html>
"""