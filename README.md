# PyServeX v3.0 – Advanced Python HTTP File Server

A feature-rich HTTP server for file sharing with a modern Apple iOS glass theme UI, animated background, real-time search, direct media downloads, permanent text clipboard, and dark/light themes.

**by Parth Padhiyar (SubZ3r0-0x01)**

## 🚀 What's New in v3.0

### Apple iOS Glass Theme
- **Glassmorphism Design** - Beautiful translucent panels with backdrop blur
- **Animated Background** - Subtle network visualization with nodes and particles
- **Translucent UI** - All panels show animated background through glass effects
- **Resizable Panels** - Drag divider between file explorer and clipboard
- **Theme Toggle** - Persistent dark/light mode with smooth transitions

### Enhanced Features
- **Real-time Search** - Instant file filtering as you type (no page refresh needed)
- **Direct Media Downloads** - Images, videos, and audio files download directly instead of opening in browser
- **Permanent Text Clipboard** - Persistent text area with auto-save functionality
- **Improved File Icons** - Visual file type indicators (📁 folders, 🖼️ images, 🎬 videos, etc.)

## Installation

Install using pip:

```bash
pip install pyservx
```

Or use pipx for an isolated environment (recommended):

```bash
pipx install pyservx
```

Requires Python 3.6 or higher.

## Usage

Run the server:

```bash
pyservx
```

Or with custom port:

```bash
pyservx --port 8080
```

- The server automatically creates a shared folder in your Downloads directory (`PyServeX-Shared`)
- Access the web interface at `http://localhost:8088` (or your custom port)
- Share the local network URL (e.g., `http://192.168.1.16:8088`) with others on your WiFi
- Use `Ctrl+C` to stop the server

## ✨ Features

### 🎨 Modern UI (v3.0)
- **Fixed Single-Page Layout** - No scrolling, everything visible at once
- **Split-Panel Design** - File explorer and text clipboard side-by-side
- **Real-time Search** - Instant file filtering without page refresh
- **Direct Media Downloads** - Click images/videos to download directly
- **Dark/Light Theme Toggle** with persistent settings
- **Responsive Design** for desktop and mobile

### 📝 Text Clipboard (NEW in v3.0)
- **Permanent Text Area** - Persistent across page refreshes
- **Auto-save Functionality** - Saves content automatically as you type
- **Manual Save/Clear** - Explicit save and clear buttons
- **Copy to System Clipboard** - One-click copy to system clipboard
- **Per-directory Storage** - Different clipboard content for each folder

### 📁 File Management
- **File and folder browsing** with modern interface
- **Download entire folders** as ZIP files
- **Upload multiple files** simultaneously via drag-and-drop
- **File Preview System** for images, PDFs, videos, audio, and text
- **Built-in Text Editor** with syntax highlighting
- **File Operations** - Create, edit, delete files and folders

### 🔍 Search & Navigation
- **Real-time Search** - Filter files instantly as you type
- **File Sorting** by name, size, or date with visual indicators
- **Breadcrumb Navigation** for easy folder traversal
- **File Type Icons** for better visual organization

### 📊 Analytics & Tracking
- **SQLite-based Analytics** database
- **Usage Tracking** - Monitor file access, downloads, and uploads
- **Popular Files** tracking and usage patterns
- **Client Information** logging (IP, user agent)

### 🛡️ Security & Privacy
- **Path Traversal Protection** prevents unauthorized access
- **Automated `robots.txt`** to prevent search engine indexing
- **Secure File Operations** with proper validation

### ⚡ Performance Features
- **Real-time Progress Tracking** for uploads and downloads
- **No File Size Restrictions** - upload files of any size
- **Chunked File Transfer** for efficient large file handling
- **Threaded Server** for concurrent connections

## 🎯 Key Improvements in v3.0

1. **Fixed Layout** - No more endless scrolling, everything fits on one screen
2. **Real-time Search** - Search works instantly without page reloads
3. **Direct Downloads** - Media files download directly instead of opening in browser
4. **Text Clipboard** - Permanent text area for notes, code snippets, etc.
5. **Better UX** - Improved file icons, actions, and visual feedback

## Requirements

- Python 3.6+
- `Pillow` library for image processing (automatically installed with pip)

## License

MIT License
