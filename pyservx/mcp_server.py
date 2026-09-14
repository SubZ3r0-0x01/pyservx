#!/usr/bin/env python3
"""Model Context Protocol (MCP) bridge over HTTP for PyServeX.

Endpoint:  POST /mcp          (JSON-RPC 2.0)
           GET  /mcp          (capability discovery document)

Exposed tools:
  - list_files(path)         -> directory listing
  - read_file(path)          -> text content (UTF-8, truncated at 512 KB)
  - write_file(path, text)   -> create/overwrite text file
  - upload_file(path, data_b64) -> write binary file from base64
  - search_files(query)      -> recursive filename search
  - server_info()            -> version/paths/stats
"""

import base64
import json
import logging
import os

from . import file_operations

JSONRPC_VERSION = "2.0"
MAX_READ_BYTES = 512 * 1024


def _ok(req_id, result):
    return {"jsonrpc": JSONRPC_VERSION, "id": req_id, "result": result}


def _err(req_id, code, message):
    return {"jsonrpc": JSONRPC_VERSION, "id": req_id,
            "error": {"code": code, "message": message}}


TOOL_DEFINITIONS = [
    {
        "name": "list_files",
        "description": "List files and folders in a directory of the shared storage.",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string", "default": "/"}},
            "required": [],
        },
    },
    {
        "name": "read_file",
        "description": "Read a UTF-8 text file (max 512 KB).",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Create or overwrite a UTF-8 text file.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "upload_file",
        "description": "Write a binary file provided as base64 in 'data_b64'.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "data_b64": {"type": "string"},
            },
            "required": ["path", "data_b64"],
        },
    },
    {
        "name": "search_files",
        "description": "Recursively search filenames containing the query string.",
        "inputSchema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "server_info",
        "description": "Return server version, shared folder path and stats.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
]


class McpBridge:
    def __init__(self, base_dir, stats=None):
        self.base_dir = os.path.abspath(base_dir)
        self.stats = stats

    # ------------- path safety -------------
    def resolve(self, rel_path):
        rel = (rel_path or "/").lstrip("/\\")
        abs_path = os.path.abspath(os.path.join(self.base_dir, rel))
        if abs_path != self.base_dir and not abs_path.startswith(self.base_dir + os.sep):
            raise PermissionError("path traversal blocked")
        return abs_path

    # ------------- tool impls -------------
    def tool_list_files(self, args):
        d = self.resolve(args.get("path", "/"))
        items = []
        for name in sorted(os.listdir(d)):
            full = os.path.join(d, name)
            is_dir = os.path.isdir(full)
            item = {"name": name, "type": "dir" if is_dir else "file"}
            if not is_dir:
                st = os.stat(full)
                item["size"] = st.st_size
            items.append(item)
        return {"path": args.get("path", "/"), "entries": items}

    def tool_read_file(self, args):
        p = self.resolve(args.get("path"))
        if not os.path.isfile(p):
            raise FileNotFoundError(p)
        size = os.path.getsize(p)
        with open(p, "rb") as f:
            blob = f.read(MAX_READ_BYTES)
        try:
            text = blob.decode("utf-8")
            encoding = "utf-8"
        except UnicodeDecodeError:
            text = base64.b64encode(blob).decode()
            encoding = "base64"
        return {"path": args["path"], "size": size,
                "truncated": size > MAX_READ_BYTES,
                "encoding": encoding, "content": text}

    def tool_write_file(self, args):
        p = self.resolve(args.get("path"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(args.get("content", ""))
        return {"status": "written", "path": args["path"]}

    def tool_upload_file(self, args):
        p = self.resolve(args.get("path"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        blob = base64.b64decode(args.get("data_b64", ""))
        with open(p, "wb") as f:
            f.write(blob)
        if self.stats:
            self.stats.count_upload()
            self.stats.transfer("recv", len(blob))
        return {"status": "written", "path": args["path"], "bytes": len(blob)}

    def tool_search_files(self, args):
        query = (args.get("query") or "").lower()
        hits = []
        for root, dirs, files in os.walk(self.base_dir):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for name in files:
                if query in name.lower():
                    rel = os.path.relpath(os.path.join(root, name), self.base_dir)
                    hits.append(rel.replace("\\", "/"))
                    if len(hits) >= 100:
                        break
            if len(hits) >= 100:
                break
        return {"matches": hits}

    def tool_server_info(self, _args):
        s = self.stats.snapshot() if self.stats else {}
        return {"server": "PyServeX", "version": "4.0.0",
                "shared_folder": self.base_dir, "stats": s}

    # ------------- dispatch -------------
    def handle_request(self, body_bytes):
        try:
            req = json.loads(body_bytes.decode("utf-8"))
        except Exception:
            return _err(None, -32700, "Parse error")

        if isinstance(req, list):  # batch
            return [self.handle_request(json.dumps(r).encode()) for r in req]

        method = req.get("method")
        req_id = req.get("id")

        if method == "initialize":
            return _ok(req_id, {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "pyservx-mcp", "version": "4.0.0"},
            })
        if method in ("notifications/initialized", "initialized"):
            return None  # notification: no response
        if method == "tools/list":
            return _ok(req_id, {"tools": TOOL_DEFINITIONS})
        if method == "rpc.discovery":
            return _ok(req_id, {"methods": ["initialize", "tools/list", "tools/call"],
                                "tools": TOOL_DEFINITIONS})
        if method == "tools/call":
            params = req.get("params") or {}
            name = params.get("name")
            args = params.get("arguments") or {}
            handler = {
                "list_files": self.tool_list_files,
                "read_file": self.tool_read_file,
                "write_file": self.tool_write_file,
                "upload_file": self.tool_upload_file,
                "search_files": self.tool_search_files,
                "server_info": self.tool_server_info,
            }.get(name)
            if not handler:
                return _err(req_id, -32601, f"Unknown tool: {name}")
            try:
                result = handler(args)
                # MCP wraps tool output in content blocks
                return _ok(req_id, {
                    "content": [{"type": "text",
                                 "text": json.dumps(result, default=str)}],
                    "result": result,
                })
            except FileNotFoundError as e:
                return _err(req_id, -32002, f"Not found: {e}")
            except PermissionError as e:
                return _err(req_id, -32001, str(e))
            except Exception as e:
                logging.exception("MCP tool failure")
                return _err(req_id, -32603, f"Internal error: {e}")

        return _err(req_id, -32601, f"Method not found: {method}")
