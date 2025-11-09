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
            <tr class="hover:bg-green-900/20">
                <td class="py-2 px-4 border-b border-green-700/50"><a href="{html.escape(parent)}" class="text-neon block">.. (Parent Directory)</a></td>
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

        # Add download folder zip link for directories
        if os.path.isdir(fullpath):
            list_rows.append(
                f"""
                <tr class="hover:bg-green-900/20">
                    <td class="py-2 px-4 border-b border-green-700/50">
                        <a href="{href}" class="text-neon block">{html.escape(displayname)}</a>
                    </td>
                    <td class="py-2 px-4 border-b border-green-700/50 text-right">{size}</td>
                    <td class="py-2 px-4 border-b border-green-700/50 text-right">{date_modified}</td>
                </tr>
                <tr class="hover:bg-green-900/20">
                    <td class="py-2 px-4 border-b border-green-700/50" colspan="3">
                        <a href="{href}download_folder" class="text-neon block">📦 Zip Download</a>
                    </td>
                </tr>
                """
            )
        else:
            list_rows.append(f"""
                <tr class="hover:bg-green-900/20">
                    <td class="py-2 px-4 border-b border-green-700/50"><a href="{href}" class="text-neon block">{html.escape(displayname)}</a></td>
                    <td class="py-2 px-4 border-b border-green-700/50 text-right">{size}</td>
                    <td class="py-2 px-4 border-b border-green-700/50 text-right">{date_modified}</td>
                    <td class="py-2 px-4 border-b border-green-700/50 text-right">{date_modified}</td>
                    <td class="py-2 px-4 border-b border-green-700/50 text-right">
                        <button onclick="previewItem('{html.escape(href)}', '{html.escape(displayname)}')" class="bg-green-700 hover:bg-green-800 text-white font-bold py-1 px-2 rounded text-xs mr-1">Preview</button>
                        {f'<button onclick="editItem(\'{html.escape(href)}\', \'{html.escape(displayname)}\')" class="bg-blue-700 hover:bg-blue-800 text-white font-bold py-1 px-2 rounded text-xs">Edit</button>' if displayname.lower().endswith(('.txt', '.py', '.js', '.html', '.css', '.json', '.xml', '.md', '.log', '.cfg', '.ini', '.yml', '.yaml')) else ''}
                    </td>
                </tr>
            """)

    list_html = '\n'.join(list_rows)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>PyServeX - Index of {displaypath}</title>
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
        body.light-theme textarea {{
            background: #f8f9fa;
            color: #000000;
            border-color: #000000;
        }}

        body.light-theme input:focus,
        body.light-theme textarea:focus {{
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

        .upload-form, .search-form {{
            margin-top: 1.5rem;
            padding: 1rem;
            border: 1px solid #00ff00;
            border-radius: 5px;
        }}

        .upload-form label, .search-form label {{
            display: block;
            margin-bottom: 0.5rem;
        }}

        .upload-form input[type="file"], .search-form input[type="text"] {{
            color: #00ff00;
            background: #000000;
            border: 1px solid #00ff00;
            padding: 0.5rem;
        }}

        .upload-form button, .search-form button {{
            background: #00ff00;
            color: #000000;
            padding: 0.5rem 1rem;
            border: none;
            cursor: pointer;
            font-family: 'VT323', monospace;
            font-size: 1.2rem;
        }}

        .upload-form button:hover, .search-form button:hover {{
            background: #00cc00;
        }}

        .drop-zone {{
            border: 2px dashed #00ff00;
            border-radius: 5px;
            padding: 20px;
            text-align: center;
            color: #00ff00;
            margin-top: 1rem;
            cursor: pointer;
        }}

        .drop-zone.highlight {{
            background: rgba(0, 255, 0, 0.1);
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 1.5rem;
        }}

        th, td {{
            text-align: left;
            padding: 0.75rem;
            border-bottom: 1px solid rgba(0, 255, 0, 0.3);
        }}

        th {{
            background-color: rgba(0, 255, 0, 0.1);
            color: #00ff00;
            font-weight: normal;
            cursor: pointer;
        }}

        th:hover {{
            background-color: rgba(0, 255, 0, 0.2);
        }}

        tr:nth-child(even) {{
            background-color: rgba(0, 255, 0, 0.05);
        }}

        /* Progress bar and popup styles */
        #progressBarContainer {{
            display: none;
            margin-top: 1rem;
            background-color: #333;
            border: 1px solid #00ff00;
            padding: 0.5rem;
            border-radius: 5px;
        }}

        #progressBar {{
            width: 0%;
            height: 20px;
            background-color: #00ff00;
            text-align: center;
            line-height: 20px;
            color: #000;
            font-size: 0.8rem;
        }}

        #progressText {{
            color: #00ff00;
            margin-top: 0.5rem;
            font-size: 0.9rem;
        }}

        #successPopup {{
            display: none;
            position: fixed;
            top: 20px;
            left: 50%;
            transform: translateX(-50%);
            background-color: #00ff00;
            color: #000;
            padding: 1rem 2rem;
            border-radius: 5px;
            font-size: 1.2rem;
            z-index: 1000;
            box-shadow: 0 0 10px rgba(0, 255, 0, 0.5);
        }}
    </style>
</head>
<body>
    <div class="scanline"></div>
    <header>
        <div class="flex justify-between items-center mb-4">
            <div></div>
            <div class="text-center">
                <h1 class="text-4xl md:text-6xl text-neon typewriter glitch">PyServeX</h1>
                <p class="text-lg text-neon mt-2">by <strong>Parth Padhiyar</strong> (<a href="https://github.com/SubZ3r0-0x01/pyservx" class="text-neon hover:underline">SubZ3r0-0x01</a>)</p>
            </div>
            <div>
                <button id="themeToggle" class="theme-toggle-btn p-2 rounded-lg border border-green-700/50 hover:bg-green-700/20 transition-colors duration-200">
                    <span id="themeIcon">🌙</span>
                </button>
            </div>
        </div>
    </header>
    <main>
        <h2 class="text-3xl mb-4 text-neon">Index of {displaypath}</h2>
        <div class="search-form mb-6 p-4 border border-green-700/50 rounded-lg">
            <form action="{html.escape(handler.path)}" method="GET" class="flex flex-col sm:flex-row items-center space-y-2 sm:space-y-0 sm:space-x-2">
                <input type="text" name="q" placeholder="Search files..." value="{html.escape(search_query)}" class="flex-grow p-2 bg-black text-neon border border-green-700/50 rounded-md focus:outline-none focus:ring-1 focus:ring-green-500 light-theme:bg-gray-100 light-theme:text-gray-800 light-theme:border-blue-300">
                <button type="submit" class="bg-green-500 text-black py-2 px-4 rounded-md hover:bg-green-600 transition-colors duration-200">Search</button>
            </form>
        </div>
        <div class="overflow-x-auto">
            <table class="min-w-full bg-black border border-green-700/50 rounded-lg light-theme:bg-white light-theme:border-gray-300">
                <thead>
                    <tr>
                        <th class="py-3 px-4 border-b border-green-700/50 text-left text-neon">
                            <a href="?sort=name&order={{'desc' if sort_by == 'name' and sort_order == 'asc' else 'asc'}}" class="block">Name</a>
                        </th>
                        <th class="py-3 px-4 border-b border-green-700/50 text-right text-neon">
                            <a href="?sort=size&order={{'desc' if sort_by == 'size' and sort_order == 'asc' else 'asc'}}" class="block">Size</a>
                        </th>
                        <th class="py-3 px-4 border-b border-green-700/50 text-right text-neon">
                            <a href="?sort=date&order={{'desc' if sort_by == 'date' and sort_order == 'asc' else 'asc'}}" class="block">Date Modified</a>
                        </th>
                        <th class="py-3 px-4 border-b border-green-700/50 text-right text-neon">Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {list_html}
                </tbody>
            </table>
        </div>
        <div class="upload-form mt-6 p-4 border border-green-700/50 rounded-lg">
            <form id="uploadForm" action="{html.escape(handler.path)}upload" method="POST" enctype="multipart/form-data" class="flex flex-col sm:flex-row items-center space-y-2 sm:space-y-0 sm:space-x-2">
                <label for="file-upload" class="text-neon">Upload files:</label>
                <input type="file" id="file-upload" name="file" multiple class="flex-grow p-2 bg-black text-neon border border-green-700/50 rounded-md focus:outline-none focus:ring-1 focus:ring-green-500" />
                <button type="submit" class="bg-green-500 text-black py-2 px-4 rounded-md hover:bg-green-600 transition-colors duration-200">Upload</button>
            </form>
            <div class="mt-4 flex space-x-2">
                <button onclick="createNewFolder()" class="bg-purple-700 hover:bg-purple-800 text-white font-bold py-2 px-4 rounded">New Folder</button>
                <button onclick="createNewFile()" class="bg-teal-700 hover:bg-teal-800 text-white font-bold py-2 px-4 rounded">New File</button>
            </div>
            <div id="progressBarContainer">
                <div id="progressBar"></div>
                <div id="progressText"></div>
            </div>
            <div id="dropZone" class="drop-zone">
                Drag & Drop Files Here or Click to Upload
            </div>
        </div>
    </main>

    <footer class="text-center py-4 text-neon text-[22px]">
    </footer>

    <div id="successPopup"></div>

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
            const xhr = new XMLHttpRequest();

            const progressBarContainer = document.getElementById('progressBarContainer');
            const progressBar = document.getElementById('progressBar');
            const progressText = document.getElementById('progressText');
            const successPopup = document.getElementById('successPopup');

            progressBarContainer.style.display = 'block';
            progressBar.style.width = '0%';
            progressText.textContent = 'Uploading...';

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
                    const response = JSON.parse(xhr.responseText);
                    successPopup.textContent = response.message;
                    successPopup.style.display = 'block';
                    setTimeout(() => {{
                        successPopup.style.display = 'none';
                        window.location.reload(); // Reload page to show new files
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

        function editItem(path, name) {{
            window.open(path + 'edit', '_blank');
        }}

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

        // Drag and Drop functionality
        const dropZone = document.getElementById('dropZone');
        const uploadForm = document.getElementById('uploadForm');

        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {{
            dropZone.addEventListener(eventName, preventDefaults, false);
            document.body.addEventListener(eventName, preventDefaults, false); // Global to prevent opening file
        }});

        ['dragenter', 'dragover'].forEach(eventName => {{
            dropZone.addEventListener(eventName, highlight, false);
        }});

        ['dragleave', 'drop'].forEach(eventName => {{
            dropZone.addEventListener(eventName, unhighlight, false);
        }});

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

        dropZone.addEventListener('drop', handleDrop, false);

        function handleDrop(e) {{
            const dt = e.dataTransfer;
            const files = dt.files;

            // Assign files to the file input
            document.getElementById('file-upload').files = files;

            // Manually trigger the form submission
            uploadForm.dispatchEvent(new Event('submit', {{ cancelable: true }}));
        }}

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

        window.onload = function() {{
            createParticles();
            initTheme();
        }};
    </script>
</body>
</html>
"""