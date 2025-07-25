#!/usr/bin/env python3

import os
import zipfile
from io import BytesIO

def format_size(size):
    if size < 1024:
        return f"{size} B"
    elif size < 1024**2:
        return f"{size / 1024:.2f} KB"
    elif size < 1024**3:
        return f"{size / (1024**2):.2f} MB"
    else:
        return f"{size / (1024**3):.2f} GB"

def zip_folder(folder_path):
    memory_file = BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(folder_path):
            for file in files:
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, folder_path)
                zipf.write(abs_path, rel_path)
    memory_file.seek(0)
    return memory_file

def write_file_in_chunks(file_path, file_content, progress_callback=None):
    total_size = len(file_content)
    bytes_written = 0
    chunk_size = 8192  # 8KB chunks

    with open(file_path, 'wb') as f:
        for i in range(0, total_size, chunk_size):
            chunk = file_content[i:i + chunk_size]
            f.write(chunk)
            bytes_written += len(chunk)
            if progress_callback:
                progress_callback(bytes_written, total_size)

def read_file_in_chunks(file_path, chunk_size=8192, progress_callback=None):
    file_size = os.path.getsize(file_path)
    bytes_read = 0
    with open(file_path, 'rb') as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            bytes_read += len(chunk)
            if progress_callback:
                progress_callback(bytes_read, file_size)
            yield chunk
