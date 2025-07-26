# PyServeX

A simple HTTP server for file sharing with a retro-styled web interface.

## Installation

Install using pip:

```bash
pip install pyservx
```

Or use pipx for an isolated environment (recommended for Linux):

```bash
pipx install pyservx
```

Ensure you have Python 3.6 or higher installed.

## Usage

Run the server:

```bash
python3 run.py
```

- Follow the prompt to select a shared folder.
- The server will start at `http://localhost:8088` and other network IPs.
- Access the web interface to browse, download, or upload files.
- Use `Ctrl+C` to stop the server.

## Features

- File and folder browsing with a retro "hacker" UI.
- Download entire folders as ZIP files.
- Upload files via the web interface.
- Accessible via localhost (`127.0.0.1`) and network IPs.
- **QR Code for Easy Access:** Scan a QR code in the terminal to quickly access the server from your mobile device on the same network.
- **Real-time Progress Bars:** Enjoy real-time progress updates for both uploads and downloads, including ETA, transfer speed, and file size.
- **Multiple File Uploads:** Upload multiple files simultaneously through the web interface.
- **No File Size Restriction:** Upload files of any size without limitations.
- **Enhanced Web Interface:**
    - **Search Functionality:** Quickly find files with the new search bar.
    - **File Sorting:** Sort files by name, size, or date for better organization.
    - **Modern & Responsive UI:** A refreshed, responsive design for seamless use across all devices.
- **Automated `robots.txt`:** A `robots.txt` file is automatically generated to prevent search engines from indexing your file server, enhancing privacy.
- **Modular Codebase:** The `server.py` file has been refactored into smaller, more maintainable modules (`request_handler.py`, `html_generator.py`, `file_operations.py`).

## Requirements

- Python 3.6+
- `qrcode` library (automatically installed with pip)

## License

MIT License