#!/usr/bin/env python3

import os
import zipfile
import shutil
import hashlib
import mimetypes
from io import BytesIO
from PIL import Image
import json
from datetime import datetime

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

# Enhanced Features

def get_file_hash(file_path, algorithm='md5'):
    """Generate hash for file to detect duplicates"""
    hash_obj = hashlib.new(algorithm)
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_obj.update(chunk)
    return hash_obj.hexdigest()

def find_duplicates(directory):
    """Find duplicate files in directory"""
    file_hashes = {}
    duplicates = []
    
    for root, _, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root, file)
            try:
                file_hash = get_file_hash(file_path)
                if file_hash in file_hashes:
                    duplicates.append({
                        'original': file_hashes[file_hash],
                        'duplicate': file_path,
                        'size': os.path.getsize(file_path)
                    })
                else:
                    file_hashes[file_hash] = file_path
            except (OSError, IOError):
                continue
    
    return duplicates

def generate_thumbnail(image_path, thumbnail_dir, size=(150, 150)):
    """Generate thumbnail for image files"""
    try:
        filename = os.path.basename(image_path)
        name, ext = os.path.splitext(filename)
        thumbnail_name = f"{name}_thumb{ext}"
        thumbnail_path = os.path.join(thumbnail_dir, thumbnail_name)
        
        if os.path.exists(thumbnail_path):
            return thumbnail_path
        
        os.makedirs(thumbnail_dir, exist_ok=True)
        
        with Image.open(image_path) as img:
            img.thumbnail(size, Image.Resampling.LANCZOS)
            img.save(thumbnail_path, optimize=True, quality=85)
        
        return thumbnail_path
    except Exception:
        return None

def copy_file(src, dst, progress_callback=None):
    """Copy file with progress tracking"""
    file_size = os.path.getsize(src)
    bytes_copied = 0
    
    with open(src, 'rb') as fsrc, open(dst, 'wb') as fdst:
        while True:
            chunk = fsrc.read(64 * 1024)  # 64KB chunks
            if not chunk:
                break
            fdst.write(chunk)
            bytes_copied += len(chunk)
            if progress_callback:
                progress_callback(bytes_copied, file_size)

def move_file(src, dst, progress_callback=None):
    """Move file with progress tracking"""
    copy_file(src, dst, progress_callback)
    os.remove(src)

def get_file_info(file_path):
    """Get comprehensive file information"""
    stat = os.stat(file_path)
    mime_type, _ = mimetypes.guess_type(file_path)
    
    return {
        'name': os.path.basename(file_path),
        'path': file_path,
        'size': stat.st_size,
        'size_formatted': format_size(stat.st_size),
        'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
        'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
        'mime_type': mime_type,
        'extension': os.path.splitext(file_path)[1].lower(),
        'is_image': mime_type and mime_type.startswith('image/'),
        'is_video': mime_type and mime_type.startswith('video/'),
        'is_audio': mime_type and mime_type.startswith('audio/'),
        'is_text': mime_type and mime_type.startswith('text/'),
    }

def search_files(directory, query, file_type=None, size_min=None, size_max=None):
    """Advanced file search with filters"""
    results = []
    query_lower = query.lower()
    
    for root, dirs, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root, file)
            
            # Name matching
            if query_lower not in file.lower():
                continue
            
            try:
                file_info = get_file_info(file_path)
                
                # File type filter
                if file_type and not file_info['mime_type']:
                    continue
                if file_type == 'image' and not file_info['is_image']:
                    continue
                if file_type == 'video' and not file_info['is_video']:
                    continue
                if file_type == 'audio' and not file_info['is_audio']:
                    continue
                if file_type == 'text' and not file_info['is_text']:
                    continue
                
                # Size filters
                if size_min and file_info['size'] < size_min:
                    continue
                if size_max and file_info['size'] > size_max:
                    continue
                
                results.append(file_info)
                
            except (OSError, IOError):
                continue
    
    return results

def create_backup(source_dir, backup_dir):
    """Create backup of directory"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"backup_{timestamp}"
    backup_path = os.path.join(backup_dir, backup_name)
    
    shutil.copytree(source_dir, backup_path)
    return backup_path

def extract_archive(archive_path, extract_to):
    """Extract ZIP archives"""
    try:
        with zipfile.ZipFile(archive_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)
        return True
    except Exception:
        return False