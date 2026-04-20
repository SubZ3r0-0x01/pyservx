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
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=5.0, user-scalable=yes" />
    <meta name="apple-mobile-web-app-capable" content="yes" />
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />
    <meta name="theme-color" content="#000000" media="(prefers-color-scheme: dark)" />
    <meta name="theme-color" content="#f2f2f7" media="(prefers-color-scheme: light)" />
    <title>PyServeX v3.0.1 - {displaypath}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

        /* CSS Variables for Apple iOS Glass Theme */
        :root {{
            /* Apple iOS Colors - Dark Mode */
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
            
            /* Opacity Levels */
            --opacity-glass: 0.7;
            --opacity-hover: 0.85;
            
            /* Blur Strength */
            --blur-strong: 20px;
            --blur-medium: 12px;
            --blur-light: 8px;
            
            /* Border Radius - Apple Style */
            --radius-small: 10px;
            --radius-medium: 16px;
            --radius-large: 20px;
            --radius-xl: 28px;
            
            /* Spacing */
            --spacing-xs: 8px;
            --spacing-sm: 12px;
            --spacing-md: 16px;
            --spacing-lg: 24px;
            --spacing-xl: 32px;
        }}

        /* Light Theme Variables */
        body.light-theme {{
            --bg-primary: #f2f2f7;
            --bg-secondary: #ffffff;
            --bg-tertiary: #e5e5ea;
            --text-primary: #000000;
            --text-secondary: rgba(0, 0, 0, 0.6);
            --accent-color: #007aff;
            --accent-hover: #0051d5;
            --glass-bg: rgba(255, 255, 255, 0.7);
            --glass-border: rgba(0, 0, 0, 0.1);
            --shadow-color: rgba(0, 0, 0, 0.1);
        }}

        /* Fixed Layout - No Scrolling */
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        html, body {{
            height: 100vh;
            overflow: hidden;
            font-family: -apple-system, BlinkMacSystemFont, 'Inter', 'Segoe UI', 'Roboto', sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            transition: background-color 0.3s cubic-bezier(0.4, 0, 0.2, 1), color 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
            position: relative;
        }}

        /* Animated Background Canvas */
        #backgroundCanvas {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: 0;
            pointer-events: none;
            background: #000000;
        }}

        body.light-theme #backgroundCanvas {{
            background: #ffffff;
        }}

        /* Ensure content is above background */
        .main-container {{
            position: relative;
            z-index: 1;
        }}

        .text-neon {{
            color: var(--text-primary);
            transition: color 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }}

        /* Remove scanline effect for Apple theme */
        body.light-theme .scanline {{
            display: none;
        }}

        /* Theme Toggle Button - Apple Style */
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
            background: var(--glass-bg);
            opacity: var(--opacity-hover);
            box-shadow: 0 8px 24px var(--shadow-color), 0 0 0 1px var(--glass-border);
        }}

        .theme-toggle-btn:active {{
            transform: scale(0.95);
        }}

        /* Main Layout Container */
        .main-container {{
            display: flex;
            height: 100vh;
            flex-direction: column;
            padding: var(--spacing-sm);
            gap: var(--spacing-sm);
        }}

        /* Header - Apple Style */
        .header {{
            flex-shrink: 0;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: var(--spacing-md) var(--spacing-lg);
            background: rgba(28, 28, 30, 0.3);
            backdrop-filter: blur(var(--blur-strong)) saturate(180%);
            -webkit-backdrop-filter: blur(var(--blur-strong)) saturate(180%);
            border-radius: var(--radius-large);
            border: 1px solid var(--glass-border);
            box-shadow: 0 8px 32px var(--shadow-color), 
                        0 0 0 1px var(--glass-border),
                        inset 0 1px 0 rgba(255, 255, 255, 0.1);
        }}

        body.light-theme .header {{
            background: rgba(255, 255, 255, 0.3);
        }}

        /* Content Area */
        .content-area {{
            flex: 1;
            display: flex;
            gap: 0;
            overflow: hidden;
            position: relative;
        }}

        /* File Explorer Panel - Apple Glass Style */
        .file-explorer {{
            flex: 1;
            display: flex;
            flex-direction: column;
            overflow: hidden;
            background: rgba(28, 28, 30, 0.3);
            backdrop-filter: blur(var(--blur-strong)) saturate(180%);
            -webkit-backdrop-filter: blur(var(--blur-strong)) saturate(180%);
            border-radius: var(--radius-large);
            border: 1px solid var(--glass-border);
            box-shadow: 0 8px 32px var(--shadow-color), 
                        0 0 0 1px var(--glass-border),
                        inset 0 1px 0 rgba(255, 255, 255, 0.1);
            margin-right: var(--spacing-sm);
        }}

        body.light-theme .file-explorer {{
            background: rgba(255, 255, 255, 0.3);
        }}

        /* Resizer Handle */
        .resizer {{
            width: 8px;
            cursor: col-resize;
            background: transparent;
            position: relative;
            flex-shrink: 0;
            transition: background 0.2s;
        }}

        .resizer:hover {{
            background: var(--accent-color);
        }}

        .resizer::before {{
            content: '';
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 4px;
            height: 40px;
            background: var(--glass-border);
            border-radius: 2px;
            transition: all 0.2s;
        }}

        .resizer:hover::before {{
            background: white;
            height: 60px;
        }}

        .resizer.resizing {{
            background: var(--accent-color);
        }}

        /* Search and Controls */
        .search-controls {{
            padding: var(--spacing-md);
            border-bottom: 1px solid var(--glass-border);
            flex-shrink: 0;
            background: rgba(28, 28, 30, 0.2);
        }}

        body.light-theme .search-controls {{
            background: rgba(255, 255, 255, 0.2);
        }}

        /* File List Container */
        .file-list-container {{
            flex: 1;
            overflow-y: auto;
            overflow-x: hidden;
            padding: var(--spacing-sm);
        }}

        /* Text Panel - Apple Glass Style */
        .text-panel {{
            width: 400px;
            display: flex;
            flex-direction: column;
            overflow: hidden;
            background: rgba(28, 28, 30, 0.3);
            backdrop-filter: blur(var(--blur-strong)) saturate(180%);
            -webkit-backdrop-filter: blur(var(--blur-strong)) saturate(180%);
            border-radius: var(--radius-large);
            border: 1px solid var(--glass-border);
            box-shadow: 0 8px 32px var(--shadow-color), 
                        0 0 0 1px var(--glass-border),
                        inset 0 1px 0 rgba(255, 255, 255, 0.1);
            flex-shrink: 0;
        }}

        body.light-theme .text-panel {{
            background: rgba(255, 255, 255, 0.3);
        }}

        /* Text Area */
        .text-area {{
            flex: 1;
            display: flex;
            flex-direction: column;
            padding: var(--spacing-md);
            overflow: hidden;
        }}

        .text-content {{
            flex: 1;
            overflow-y: auto;
            border: 1px solid var(--glass-border);
            border-radius: var(--radius-medium);
            padding: var(--spacing-md);
            background: rgba(28, 28, 30, 0.4);
            font-family: 'SF Mono', 'Monaco', 'Menlo', 'Courier New', monospace;
            font-size: 14px;
            line-height: 1.6;
            resize: none;
            color: var(--text-primary);
            box-shadow: inset 0 2px 8px var(--shadow-color);
        }}

        body.light-theme .text-content {{
            background: rgba(255, 255, 255, 0.4);
        }}

        .text-content::placeholder {{
            color: var(--text-secondary);
        }}

        /* Scrollbar Styling - Apple Style */
        .file-list-container::-webkit-scrollbar,
        .text-content::-webkit-scrollbar {{
            width: 8px;
        }}

        .file-list-container::-webkit-scrollbar-track,
        .text-content::-webkit-scrollbar-track {{
            background: transparent;
        }}

        .file-list-container::-webkit-scrollbar-thumb,
        .text-content::-webkit-scrollbar-thumb {{
            background: var(--text-secondary);
            border-radius: 10px;
        }}

        .file-list-container::-webkit-scrollbar-thumb:hover,
        .text-content::-webkit-scrollbar-thumb:hover {{
            background: var(--text-primary);
        }}

        /* Table Styles - Apple iOS Style */
        table {{
            width: 100%;
            border-collapse: separate;
            border-spacing: 0 4px;
        }}

        th, td {{
            text-align: left;
            padding: var(--spacing-sm) var(--spacing-md);
        }}

        th {{
            background: rgba(28, 28, 30, 0.3);
            color: var(--text-secondary);
            font-weight: 600;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            cursor: pointer;
            border-radius: var(--radius-small);
        }}

        body.light-theme th {{
            background: rgba(255, 255, 255, 0.3);
        }}

        th:hover {{
            background: rgba(28, 28, 30, 0.5);
        }}

        body.light-theme th:hover {{
            background: rgba(255, 255, 255, 0.5);
        }}

        tr {{
            background: rgba(28, 28, 30, 0.2);
            border-radius: var(--radius-medium);
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
        }}

        body.light-theme tr {{
            background: rgba(255, 255, 255, 0.2);
        }}

        tr:hover {{
            background: rgba(28, 28, 30, 0.4);
            transform: scale(1.01);
            box-shadow: 0 4px 12px var(--shadow-color);
        }}

        body.light-theme tr:hover {{
            background: rgba(255, 255, 255, 0.4);
        }}

        td {{
            border-top: 1px solid var(--glass-border);
            border-bottom: 1px solid var(--glass-border);
        }}

        td:first-child {{
            border-left: 1px solid var(--glass-border);
            border-top-left-radius: var(--radius-medium);
            border-bottom-left-radius: var(--radius-medium);
        }}

        td:last-child {{
            border-right: 1px solid var(--glass-border);
            border-top-right-radius: var(--radius-medium);
            border-bottom-right-radius: var(--radius-medium);
        }}

        /* Input Styles - Apple iOS Style */
        input, textarea, button {{
            background: var(--bg-secondary);
            color: var(--text-primary);
            border: 1px solid var(--glass-border);
            border-radius: var(--radius-medium);
            padding: var(--spacing-sm) var(--spacing-md);
            font-family: -apple-system, BlinkMacSystemFont, 'Inter', sans-serif;
            font-size: 14px;
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
            outline: none;
        }}

        input:focus, textarea:focus {{
            border-color: var(--accent-color);
            box-shadow: 0 0 0 4px rgba(0, 122, 255, 0.1);
        }}

        button {{
            cursor: pointer;
            font-weight: 500;
            background: var(--accent-color);
            color: white;
            border: none;
            padding: var(--spacing-sm) var(--spacing-lg);
        }}

        button:hover {{
            background: var(--accent-hover);
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(0, 122, 255, 0.3);
        }}

        button:active {{
            transform: translateY(0);
        }}

        /* Button Variants */
        .bg-green-700 {{
            background: #34c759;
        }}

        .bg-green-700:hover {{
            background: #2fb350;
        }}

        .bg-red-700 {{
            background: #ff3b30;
        }}

        .bg-red-700:hover {{
            background: #e6342a;
        }}

        .bg-blue-700 {{
            background: #007aff;
        }}

        .bg-blue-700:hover {{
            background: #0051d5;
        }}

        .bg-orange-700 {{
            background: #ff9500;
        }}

        .bg-orange-700:hover {{
            background: #e68600;
        }}

        .bg-purple-700 {{
            background: #af52de;
        }}

        .bg-purple-700:hover {{
            background: #9c47c5;
        }}

        .bg-teal-700 {{
            background: #5ac8fa;
        }}

        .bg-teal-700:hover {{
            background: #51b3e1;
        }}

        /* Remove Glitch Animation - Not Apple Style */
        .glitch {{
            position: relative;
        }}

        /* Subtle Scanline Effect - Only Dark Mode */
        .scanline {{
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: linear-gradient(
                to bottom,
                rgba(255, 255, 255, 0),
                rgba(255, 255, 255, 0.02) 50%,
                rgba(255, 255, 255, 0)
            );
            animation: scan 8s linear infinite;
            pointer-events: none;
            opacity: 0.3;
        }}

        body.light-theme .scanline {{
            display: none;
        }}

        @keyframes scan {{
            0% {{ transform: translateY(-100%); }}
            100% {{ transform: translateY(100%); }}
        }}

        /* Upload Progress - Apple Style */
        .upload-progress {{
            margin-top: var(--spacing-md);
            padding: var(--spacing-md);
            border: 1px solid var(--glass-border);
            border-radius: var(--radius-medium);
            display: none;
            background: var(--bg-secondary);
            box-shadow: 0 2px 8px var(--shadow-color);
        }}

        .progress-bar {{
            width: 0%;
            height: 6px;
            background: var(--accent-color);
            border-radius: 3px;
            transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            box-shadow: 0 0 8px rgba(0, 122, 255, 0.5);
        }}

        /* Responsive Design - Multi-Device Support */
        
        /* Large Desktop (1920px+) */
        @media (min-width: 1920px) {{
            .main-container {{
                max-width: 1800px;
                margin: 0 auto;
            }}
            
            .text-panel {{
                width: 500px;
            }}
        }}

        /* Desktop (1200px - 1919px) */
        @media (min-width: 1200px) and (max-width: 1919px) {{
            .text-panel {{
                width: 400px;
            }}
        }}

        /* Laptop / Small Desktop (992px - 1199px) */
        @media (min-width: 992px) and (max-width: 1199px) {{
            .main-container {{
                padding: var(--spacing-sm);
            }}
            
            .text-panel {{
                width: 350px;
            }}
            
            .header {{
                padding: var(--spacing-md);
            }}
            
            h1 {{
                font-size: 1.75rem !important;
            }}
        }}

        /* Tablet Landscape (768px - 991px) */
        @media (min-width: 768px) and (max-width: 991px) {{
            .main-container {{
                padding: var(--spacing-sm);
                gap: var(--spacing-sm);
            }}
            
            .content-area {{
                flex-direction: column;
                gap: var(--spacing-sm);
            }}
            
            .resizer {{
                display: none;
            }}
            
            .file-explorer {{
                height: 55%;
                width: 100% !important;
                margin-right: 0;
            }}
            
            .text-panel {{
                width: 100% !important;
                height: 45%;
            }}
            
            .header {{
                padding: var(--spacing-md);
            }}
            
            h1 {{
                font-size: 1.5rem !important;
            }}
            
            .search-controls {{
                padding: var(--spacing-md);
            }}
            
            .text-area {{
                padding: var(--spacing-md);
            }}
            
            /* Adjust button sizes */
            button {{
                padding: var(--spacing-xs) var(--spacing-md);
                font-size: 13px;
            }}
        }}

        /* Tablet Portrait / Large Phone (576px - 767px) */
        @media (min-width: 576px) and (max-width: 767px) {{
            .main-container {{
                padding: var(--spacing-xs);
                gap: var(--spacing-xs);
            }}
            
            .content-area {{
                flex-direction: column;
                gap: var(--spacing-xs);
            }}
            
            .resizer {{
                display: none;
            }}
            
            .file-explorer {{
                height: 60%;
                width: 100% !important;
                margin-right: 0;
            }}
            
            .text-panel {{
                width: 100% !important;
                height: 40%;
            }}
            
            .header {{
                padding: var(--spacing-sm);
            }}
            
            h1 {{
                font-size: 1.25rem !important;
            }}
            
            .header p {{
                font-size: 11px !important;
            }}
            
            .search-controls {{
                padding: var(--spacing-sm);
            }}
            
            .text-area {{
                padding: var(--spacing-sm);
            }}
            
            /* Stack buttons vertically */
            .search-controls .flex {{
                flex-direction: column;
            }}
            
            /* Smaller buttons */
            button {{
                padding: var(--spacing-xs) var(--spacing-sm);
                font-size: 12px;
                width: 100%;
            }}
            
            /* Adjust table */
            th, td {{
                padding: var(--spacing-xs) var(--spacing-sm);
                font-size: 12px;
            }}
            
            th {{
                font-size: 10px;
            }}
            
            /* Hide some columns on smaller tablets */
            table th:nth-child(3),
            table td:nth-child(3) {{
                display: none;
            }}
        }}

        /* Mobile / Small Phone (320px - 575px) */
        @media (max-width: 575px) {{
            :root {{
                --spacing-xs: 6px;
                --spacing-sm: 8px;
                --spacing-md: 12px;
                --spacing-lg: 16px;
            }}
            
            .main-container {{
                padding: 6px;
                gap: 6px;
            }}
            
            .content-area {{
                flex-direction: column;
                gap: 6px;
            }}
            
            .resizer {{
                display: none;
            }}
            
            .file-explorer {{
                height: 65%;
                width: 100% !important;
                margin-right: 0;
            }}
            
            .text-panel {{
                width: 100% !important;
                height: 35%;
            }}
            
            .header {{
                padding: var(--spacing-sm);
            }}
            
            h1 {{
                font-size: 1.1rem !important;
            }}
            
            .header p {{
                font-size: 10px !important;
                margin-top: 2px !important;
            }}
            
            .search-controls {{
                padding: var(--spacing-sm);
            }}
            
            .text-area {{
                padding: var(--spacing-sm);
            }}
            
            /* Stack all controls vertically */
            .search-controls .flex,
            .text-area .flex {{
                flex-direction: column;
                gap: var(--spacing-xs);
            }}
            
            /* Full width buttons */
            button {{
                padding: var(--spacing-xs);
                font-size: 11px;
                width: 100%;
            }}
            
            /* Compact inputs */
            input, textarea {{
                padding: var(--spacing-xs);
                font-size: 12px;
            }}
            
            /* Simplified table */
            th, td {{
                padding: 6px 8px;
                font-size: 11px;
            }}
            
            th {{
                font-size: 9px;
            }}
            
            /* Hide size and date columns on mobile */
            table th:nth-child(2),
            table td:nth-child(2),
            table th:nth-child(3),
            table td:nth-child(3) {{
                display: none;
            }}
            
            /* Compact action buttons */
            table button {{
                padding: 4px 6px;
                font-size: 10px;
                margin: 0 2px;
            }}
            
            /* Theme toggle button */
            .theme-toggle-btn {{
                width: 36px;
                height: 36px;
                top: 8px;
                right: 8px;
                font-size: 1rem;
            }}
            
            /* Smaller text content */
            .text-content {{
                font-size: 12px;
                padding: var(--spacing-xs);
            }}
            
            /* Adjust border radius for mobile */
            .header,
            .file-explorer,
            .text-panel {{
                border-radius: var(--radius-medium);
            }}
        }}

        /* Extra Small Mobile (< 375px) */
        @media (max-width: 374px) {{
            h1 {{
                font-size: 1rem !important;
            }}
            
            .header p {{
                font-size: 9px !important;
            }}
            
            button {{
                font-size: 10px;
                padding: 6px;
            }}
            
            th, td {{
                padding: 4px 6px;
                font-size: 10px;
            }}
            
            .theme-toggle-btn {{
                width: 32px;
                height: 32px;
                font-size: 0.9rem;
            }}
        }}

        /* Landscape Mode Adjustments for Mobile */
        @media (max-height: 500px) and (orientation: landscape) {{
            .main-container {{
                padding: 6px;
                gap: 6px;
            }}
            
            .header {{
                padding: 8px;
            }}
            
            h1 {{
                font-size: 1rem !important;
            }}
            
            .header p {{
                display: none;
            }}
            
            .content-area {{
                flex-direction: row;
                gap: 0;
            }}
            
            .resizer {{
                display: block;
            }}
            
            .file-explorer {{
                width: 60% !important;
                height: auto;
                margin-right: 0;
            }}
            
            .text-panel {{
                width: 40% !important;
                height: auto;
            }}
            
            .search-controls,
            .text-area {{
                padding: 8px;
            }}
        }}

        /* High DPI / Retina Display Optimization */
        @media (-webkit-min-device-pixel-ratio: 2), (min-resolution: 192dpi) {{
            body {{
                -webkit-font-smoothing: antialiased;
                -moz-osx-font-smoothing: grayscale;
            }}
            
            .glass-bg {{
                backdrop-filter: blur(var(--blur-strong)) saturate(200%);
                -webkit-backdrop-filter: blur(var(--blur-strong)) saturate(200%);
            }}
        }}

        /* Touch Device Optimizations */
        @media (hover: none) and (pointer: coarse) {{
            /* Larger touch targets */
            button {{
                min-height: 44px;
            }}
            
            input, textarea {{
                min-height: 44px;
            }}
            
            th {{
                min-height: 44px;
            }}
            
            /* Remove hover effects on touch devices */
            tr:hover {{
                transform: none;
            }}
            
            button:hover {{
                transform: none;
            }}
            
            /* Add active states instead */
            button:active {{
                transform: scale(0.95);
                opacity: 0.8;
            }}
            
            tr:active {{
                background: var(--bg-tertiary);
            }}
        }}

        /* Print Styles */
        @media print {{
            .theme-toggle-btn,
            .search-controls,
            .text-panel,
            .scanline {{
                display: none !important;
            }}
            
            .main-container {{
                padding: 0;
            }}
            
            .file-explorer {{
                width: 100%;
                box-shadow: none;
                border: 1px solid #000;
            }}
            
            body {{
                background: white;
                color: black;
            }}
        }}
    </style>
</head>
<body>
    <!-- Animated Background Canvas -->
    <canvas id="backgroundCanvas"></canvas>

    <div class="scanline"></div>
    <button id="themeToggle" class="theme-toggle-btn">
        <span id="themeIcon">🌙</span>
    </button>

    <div class="main-container">
        <!-- Header -->
        <div class="header">
            <div class="text-center">
                <h1 class="text-3xl md:text-4xl text-neon" style="font-weight: 600; letter-spacing: -0.5px;">PyServeX v3.0.1</h1>
                <p class="text-sm" style="color: var(--text-secondary); margin-top: 4px;">Enhanced File Server by <strong>Parth Padhiyar</strong></p>
            </div>
        </div>

        <!-- Content Area -->
        <div class="content-area">
            <!-- File Explorer Panel -->
            <div class="file-explorer" id="fileExplorer">
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

            <!-- Resizer -->
            <div class="resizer" id="resizer"></div>

            <!-- Text Panel -->
            <div class="text-panel" id="textPanel">
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
            setupResizer();
            initAnimatedBackground();
        }};

        // Animated Background System
        function initAnimatedBackground() {{
            const canvas = document.getElementById('backgroundCanvas');
            if (!canvas) {{
                console.error('Canvas element not found!');
                return;
            }}
            
            const ctx = canvas.getContext('2d');
            if (!ctx) {{
                console.error('Could not get canvas context!');
                return;
            }}
            
            console.log('Initializing animated background...');
            
            // Set canvas size
            function resizeCanvas() {{
                canvas.width = window.innerWidth;
                canvas.height = window.innerHeight;
                console.log('Canvas resized to:', canvas.width, 'x', canvas.height);
            }}
            resizeCanvas();
            window.addEventListener('resize', resizeCanvas);
            
            // Network nodes
            const nodes = [];
            const nodeCount = 30;
            const maxDistance = 200;
            
            // Particle system for data flow
            const particles = [];
            const particleCount = 20;
            
            // Get theme colors
            function getThemeColors() {{
                const isDark = !document.body.classList.contains('light-theme');
                return {{
                    node: isDark ? 'rgba(255, 255, 255, 0.4)' : 'rgba(0, 0, 0, 0.25)',
                    connection: isDark ? 'rgba(255, 255, 255, 0.2)' : 'rgba(0, 0, 0, 0.15)',
                    particle: isDark ? 'rgba(0, 122, 255, 0.6)' : 'rgba(0, 122, 255, 0.5)',
                    glow: isDark ? 'rgba(0, 122, 255, 0.3)' : 'rgba(0, 122, 255, 0.2)'
                }};
            }}
            
            // Node class
            class Node {{
                constructor() {{
                    this.x = Math.random() * canvas.width;
                    this.y = Math.random() * canvas.height;
                    this.vx = (Math.random() - 0.5) * 0.5;
                    this.vy = (Math.random() - 0.5) * 0.5;
                    this.radius = Math.random() * 3 + 2;
                    this.pulse = Math.random() * Math.PI * 2;
                }}
                
                update() {{
                    this.x += this.vx;
                    this.y += this.vy;
                    this.pulse += 0.02;
                    
                    // Bounce off edges
                    if (this.x < 0 || this.x > canvas.width) this.vx *= -1;
                    if (this.y < 0 || this.y > canvas.height) this.vy *= -1;
                    
                    // Keep in bounds
                    this.x = Math.max(0, Math.min(canvas.width, this.x));
                    this.y = Math.max(0, Math.min(canvas.height, this.y));
                }}
                
                draw(colors) {{
                    const pulseSize = Math.sin(this.pulse) * 0.5 + 1;
                    ctx.beginPath();
                    ctx.arc(this.x, this.y, this.radius * pulseSize, 0, Math.PI * 2);
                    ctx.fillStyle = colors.node;
                    ctx.fill();
                    
                    // Subtle glow
                    ctx.beginPath();
                    ctx.arc(this.x, this.y, this.radius * pulseSize * 3, 0, Math.PI * 2);
                    const gradient = ctx.createRadialGradient(this.x, this.y, 0, this.x, this.y, this.radius * pulseSize * 3);
                    gradient.addColorStop(0, colors.glow);
                    gradient.addColorStop(1, 'rgba(0, 0, 0, 0)');
                    ctx.fillStyle = gradient;
                    ctx.fill();
                }}
            }}
            
            // Particle class for data flow
            class Particle {{
                constructor() {{
                    this.reset();
                }}
                
                reset() {{
                    this.x = Math.random() * canvas.width;
                    this.y = Math.random() * canvas.height;
                    this.vx = (Math.random() - 0.5) * 2;
                    this.vy = (Math.random() - 0.5) * 2;
                    this.life = 1;
                    this.decay = Math.random() * 0.005 + 0.002;
                    this.size = Math.random() * 2 + 1;
                }}
                
                update() {{
                    this.x += this.vx;
                    this.y += this.vy;
                    this.life -= this.decay;
                    
                    if (this.life <= 0 || this.x < 0 || this.x > canvas.width || this.y < 0 || this.y > canvas.height) {{
                        this.reset();
                    }}
                }}
                
                draw(colors) {{
                    ctx.beginPath();
                    ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
                    ctx.fillStyle = colors.particle.replace(/[\\d\\.]+\\)$/, this.life * 0.6 + ')');
                    ctx.fill();
                    
                    // Trail effect
                    ctx.beginPath();
                    ctx.arc(this.x, this.y, this.size * 3, 0, Math.PI * 2);
                    const gradient = ctx.createRadialGradient(this.x, this.y, 0, this.x, this.y, this.size * 3);
                    gradient.addColorStop(0, colors.particle.replace(/[\\d\\.]+\\)$/, this.life * 0.4 + ')'));
                    gradient.addColorStop(1, 'rgba(0, 0, 0, 0)');
                    ctx.fillStyle = gradient;
                    ctx.fill();
                }}
            }}
            
            // Initialize nodes
            for (let i = 0; i < nodeCount; i++) {{
                nodes.push(new Node());
            }}
            console.log('Created', nodeCount, 'nodes');
            
            // Initialize particles
            for (let i = 0; i < particleCount; i++) {{
                particles.push(new Particle());
            }}
            console.log('Created', particleCount, 'particles');
            
            // Draw connections between nearby nodes
            function drawConnections(colors) {{
                for (let i = 0; i < nodes.length; i++) {{
                    for (let j = i + 1; j < nodes.length; j++) {{
                        const dx = nodes[i].x - nodes[j].x;
                        const dy = nodes[i].y - nodes[j].y;
                        const distance = Math.sqrt(dx * dx + dy * dy);
                        
                        if (distance < maxDistance) {{
                            const opacity = (1 - distance / maxDistance);
                            ctx.beginPath();
                            ctx.moveTo(nodes[i].x, nodes[i].y);
                            ctx.lineTo(nodes[j].x, nodes[j].y);
                            ctx.strokeStyle = colors.connection.replace(/[\\d\\.]+\\)$/, opacity * 0.3 + ')');
                            ctx.lineWidth = 1;
                            ctx.stroke();
                        }}
                    }}
                }}
            }}
            
            // Animation loop
            let frameCount = 0;
            function animate() {{
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                
                const colors = getThemeColors();
                
                // Update and draw connections
                drawConnections(colors);
                
                // Update and draw nodes
                nodes.forEach(node => {{
                    node.update();
                    node.draw(colors);
                }});
                
                // Update and draw particles
                particles.forEach(particle => {{
                    particle.update();
                    particle.draw(colors);
                }});
                
                frameCount++;
                if (frameCount === 1) {{
                    console.log('First frame rendered successfully');
                }}
                
                requestAnimationFrame(animate);
            }}
            
            console.log('Starting animation loop...');
            animate();
            
            // React to upload progress (optional enhancement)
            window.addEventListener('uploadProgress', function(e) {{
                // Add burst of particles on upload
                for (let i = 0; i < 5; i++) {{
                    particles.push(new Particle());
                }}
            }});
        }}

        // Resizer Functionality
        function setupResizer() {{
            const resizer = document.getElementById('resizer');
            const fileExplorer = document.getElementById('fileExplorer');
            const textPanel = document.getElementById('textPanel');
            const contentArea = document.querySelector('.content-area');
            
            if (!resizer || !fileExplorer || !textPanel) return;
            
            let isResizing = false;
            let startX = 0;
            let startWidth = 0;
            
            resizer.addEventListener('mousedown', function(e) {{
                isResizing = true;
                startX = e.clientX;
                startWidth = fileExplorer.offsetWidth;
                resizer.classList.add('resizing');
                document.body.style.cursor = 'col-resize';
                document.body.style.userSelect = 'none';
                e.preventDefault();
            }});
            
            document.addEventListener('mousemove', function(e) {{
                if (!isResizing) return;
                
                const containerWidth = contentArea.offsetWidth;
                const deltaX = e.clientX - startX;
                const newWidth = startWidth + deltaX;
                const minWidth = 300;
                const maxWidth = containerWidth - 300 - 8; // 8px for resizer
                
                if (newWidth >= minWidth && newWidth <= maxWidth) {{
                    fileExplorer.style.flex = 'none';
                    fileExplorer.style.width = newWidth + 'px';
                    textPanel.style.width = (containerWidth - newWidth - 8) + 'px';
                }}
            }});
            
            document.addEventListener('mouseup', function() {{
                if (isResizing) {{
                    isResizing = false;
                    resizer.classList.remove('resizing');
                    document.body.style.cursor = '';
                    document.body.style.userSelect = '';
                }}
            }});
            
            // Touch support for mobile
            resizer.addEventListener('touchstart', function(e) {{
                isResizing = true;
                startX = e.touches[0].clientX;
                startWidth = fileExplorer.offsetWidth;
                resizer.classList.add('resizing');
                e.preventDefault();
            }});
            
            document.addEventListener('touchmove', function(e) {{
                if (!isResizing) return;
                
                const containerWidth = contentArea.offsetWidth;
                const deltaX = e.touches[0].clientX - startX;
                const newWidth = startWidth + deltaX;
                const minWidth = 300;
                const maxWidth = containerWidth - 300 - 8;
                
                if (newWidth >= minWidth && newWidth <= maxWidth) {{
                    fileExplorer.style.flex = 'none';
                    fileExplorer.style.width = newWidth + 'px';
                    textPanel.style.width = (containerWidth - newWidth - 8) + 'px';
                }}
            }});
            
            document.addEventListener('touchend', function() {{
                if (isResizing) {{
                    isResizing = false;
                    resizer.classList.remove('resizing');
                }}
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