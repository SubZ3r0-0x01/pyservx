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
pyservx
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

## Requirements

- Python 3.6+
- No external dependencies

## License

MIT License