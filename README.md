# PyServeX – Advanced Python HTTP File Server

A feature-rich HTTP server for file sharing with a retro-styled web interface, dark/light themes, built-in notepad, analytics, and advanced file operations.

**by Parth Padhiyar (SubZ3r0-0x01)**

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

Or with custom options:

```bash
pyservx --port 8080 --no-qr
```

- The server automatically creates a shared folder in your Downloads directory (`PyServeX-Shared`)
- Access the web interface at `http://localhost:8088` (or your custom port)
- Scan the QR code in the terminal to access from mobile devices
- Use `Ctrl+C` to stop the server

## Features

### Core Features
- **Retro "Hacker" UI** with dark/light theme toggle
- **File and folder browsing** with modern, responsive interface
- **Download entire folders** as ZIP files
- **Upload multiple files** simultaneously via drag-and-drop
- **QR Code Access** for easy mobile device connection
- **Real-time Progress Tracking** for uploads and downloads with ETA and speed
- **No File Size Restrictions** - upload files of any size

### Advanced Features
- **Built-in Notepad/Text Editor**
  - Create and edit text files directly in the browser
  - Syntax highlighting support
  - Keyboard shortcuts (Ctrl+S to save)
  - Theme-aware editor

- **File Preview System**
  - Images (JPG, PNG, GIF, etc.)
  - PDFs (embedded viewer)
  - Videos (MP4, WebM, OGG)
  - Audio files (MP3, WAV, OGG)
  - Text files with syntax highlighting

- **Analytics & Usage Tracking**
  - SQLite-based analytics database
  - Track file access, downloads, and uploads
  - Monitor popular files and usage patterns
  - Client IP and user agent logging

- **Enhanced File Operations**
  - Duplicate file detection
  - File hash generation (MD5)
  - Advanced file search with filters
  - Thumbnail generation for images
  - File copy and move operations
  - Archive extraction support

- **Smart Configuration**
  - Persistent settings stored in user home directory
  - Automatic shared folder creation in Downloads
  - Configurable analytics and thumbnail generation
  - Custom port support

### User Interface
- **Dark/Light Theme Toggle** with persistent settings
- **Search Functionality** to quickly find files
- **File Sorting** by name, size, or date
- **Responsive Design** for desktop and mobile
- **Breadcrumb Navigation** for easy folder traversal
- **File Type Icons** for better visual organization

### Security & Privacy
- **Path Traversal Protection** prevents unauthorized access
- **Automated `robots.txt`** to prevent search engine indexing
- **Secure File Operations** with proper validation

### Technical Features
- **Modular Codebase** for easy maintenance and extension
- **Chunked File Transfer** for efficient large file handling
- **Progress Callbacks** for real-time feedback
- **Threaded Server** for concurrent connections
- **Graceful Shutdown** handling

## Requirements

- Python 3.6+
- `qrcode` library (automatically installed with pip)

## License

MIT License
