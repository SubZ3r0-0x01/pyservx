# PyServeX Enhanced v2.0.0 🚀

An advanced Python HTTP server for file sharing with enhanced features, analytics, and modern UI.

## 🌟 Enhanced Features

### 🎨 **User Interface**
- **Dark/Light Mode Toggle** - Switch between themes with persistent settings
- **Grid & List Views** - Choose how to display your files
- **Responsive Design** - Works perfectly on desktop and mobile
- **File Type Icons** - Visual indicators for different file types
- **Breadcrumb Navigation** - Easy navigation through folders
- **Real-time Statistics** - See folder/file counts and total size

### 🔍 **Advanced Search & Filtering**
- **Smart Search** - Search files and folders by name
- **File Type Filters** - Filter by images, videos, audio, documents, folders
- **Sorting Options** - Sort by name, size, or modification date
- **Visual Thumbnails** - Auto-generated thumbnails for images

### 📁 **Enhanced File Operations**
- **Copy & Move Files** - Drag and drop or use context menus
- **Bulk Operations** - Select and operate on multiple files
- **Duplicate Detection** - Find and manage duplicate files
- **Thumbnail Generation** - Create thumbnails for better browsing
- **Advanced Upload** - Multiple file upload with progress tracking

### ✏️ **Advanced Text Editor**
- **Syntax Highlighting** - CodeMirror integration for code editing
- **Multiple Language Support** - JavaScript, Python, HTML, CSS, Markdown
- **Theme Support** - Editor themes that match your UI theme
- **Auto-save** - Keyboard shortcuts (Ctrl+S) for quick saving
- **Line Numbers** - Professional code editing experience

### 📊 **Analytics & Monitoring**
- **Usage Analytics** - Track file access patterns
- **Popular Files** - See most accessed files
- **Access Logs** - Monitor who accessed what files
- **Performance Metrics** - Track upload/download speeds
- **SQLite Database** - Persistent analytics storage

### 🖼️ **Enhanced Media Support**
- **Image Thumbnails** - Auto-generated image previews
- **Video Previews** - HTML5 video player with controls
- **Audio Playback** - Built-in audio player
- **PDF Viewer** - Embedded PDF viewing
- **Text Preview** - Syntax-highlighted text file viewing

### 🔧 **Technical Improvements**
- **Better Error Handling** - Comprehensive error messages
- **Progress Tracking** - Real-time upload/download progress
- **File Size Limits** - Configurable upload size limits
- **Extension Filtering** - Allow/block specific file types
- **Logging System** - Detailed server and access logs

## 🚀 **Quick Start**

### Installation
```bash
# Clone the enhanced version
cd pyservx-enhanced

# Install dependencies
pip install -r requirements.txt

# Run the enhanced server
python run.py
```

### First Run
1. Server automatically creates `Downloads/PyServeX-Enhanced-Shared` folder
2. Access via `http://127.0.0.1:8088`
3. Scan QR codes for mobile access
4. Toggle between dark/light themes with the 🌙/☀️ button

## 📱 **Mobile Optimized**
- Touch-friendly interface
- Responsive grid/list views
- Mobile file upload support
- QR code access for easy connection

## 🎯 **New Features Showcase**

### **Analytics Dashboard**
- Click "📊 Analytics" to view usage statistics
- See popular files and access patterns
- Monitor server performance

### **Duplicate Finder**
- Click "🔍 Find Duplicates" to scan for duplicate files
- Identify files wasting storage space
- Clean up your file system efficiently

### **Thumbnail Generator**
- Click "🖼️ Generate Thumbnails" to create image previews
- Faster browsing with visual file previews
- Automatic thumbnail creation for new images

### **Advanced Search**
- Use the enhanced search bar with filters
- Filter by file type (images, videos, documents, etc.)
- Switch between grid and list views
- Sort by name, size, or date

### **Copy & Move Operations**
- Use "Copy" and "Move" buttons on files
- Specify destination folders
- Progress tracking for large operations

## 🔧 **Configuration**

The enhanced version uses `~/.pyservx_enhanced_config.json` for settings:

```json
{
  "shared_folder": "/path/to/folder",
  "analytics_enabled": true,
  "thumbnail_generation": true,
  "max_file_size": 104857600,
  "allowed_extensions": [],
  "theme": "dark"
}
```

## 📊 **Analytics Database**

Analytics are stored in `~/.pyservx_analytics.db` (SQLite):
- File access logs with timestamps
- User IP addresses and user agents
- Upload/download statistics
- Performance metrics

## 🎨 **Themes**

### Dark Theme (Default)
- Black background with neon green accents
- Retro hacker aesthetic
- Matrix-style animations and effects

### Light Theme
- Clean white background with black text
- Professional, modern appearance
- High contrast for better readability

## 🔒 **Security Features**
- Path traversal protection
- File size limits
- Extension filtering
- Access logging
- IP address tracking

## 🚀 **Performance**
- Chunked file transfers
- Progress tracking
- Thumbnail caching
- Efficient database queries
- Optimized for large files

## 📝 **What's New in v2.0.0**

✅ **Analytics & Monitoring**
✅ **Advanced Search & Filtering** 
✅ **Copy & Move Operations**
✅ **Duplicate File Detection**
✅ **Thumbnail Generation**
✅ **Enhanced Text Editor with Syntax Highlighting**
✅ **Grid & List View Modes**
✅ **Mobile-Optimized Interface**
✅ **Real-time Statistics**
✅ **Performance Improvements**

## 🤝 **Contributing**

This enhanced version builds upon the original PyServeX with advanced features for power users and developers.

## 📄 **License**

MIT License - Enhanced by the PyServeX community

---

**PyServeX Enhanced v2.0.0** - *Taking file sharing to the next level* 🚀