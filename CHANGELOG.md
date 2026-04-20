# Changelog

## [3.0.2] - 2026-04-20

### Changed
- **Simplified Server Access**: Removed custom hostname feature for better reliability
- **Direct IP Focus**: Emphasize using direct IP addresses for network sharing
- **Cleaner Startup**: Simplified server startup messages and removed complex configuration

### Removed
- Custom hostname configuration (too complex for real-world use)
- mDNS/zeroconf dependencies (unreliable on Windows)
- Local proxy server (added unnecessary complexity)
- Hostname validation and setup wizard

### Why These Changes?
- Direct IP addresses are simpler and more reliable
- Hostname features added complexity without real benefit
- mDNS resolution is inconsistent across platforms
- Users prefer straightforward IP-based sharing

## [3.0.1] - 2026-04-19

### Added
- **Apple iOS Glass Theme**: Complete UI redesign with glassmorphism effects
- **Animated Background**: Subtle network visualization with nodes and particles
- **Translucent Panels**: All UI elements show animated background through glass
- **Resizable Panels**: Drag divider between file explorer and clipboard
- **Theme Toggle**: Persistent dark/light mode with localStorage
- **Glass Theme System**: Comprehensive theming with backdrop blur and shadows

### Changed
- **UI Overhaul**: Transformed from matrix-style to Apple iOS aesthetic
- **Panel Opacity**: Reduced to 20-40% for better animation visibility
- **Background**: Pure black (#000000) with animated network visualization
- **Blur Effects**: Optimized blur strength (20px) for performance

### Removed
- QR code generation (replaced with direct IP sharing)
- Fullscreen toggle buttons (optimized for whole screen usage)

## [3.0.0] - 2026-04-18

### Major UI Overhaul
- **Fixed Layout Design** - No more scrolling! Single-page interface with dedicated panels
- **Split-Panel Layout** - File explorer (60%) and text clipboard (40%) side-by-side
- **Scrollable Sections** - File list and text areas scroll independently
- **Mobile Responsive** - Stacked layout on smaller screens

### Enhanced Features
- **Real-time Search** - Instant file filtering as you type (no page refresh needed)
- **Direct Media Downloads** - Images, videos, and audio files download directly
- **Permanent Text Clipboard** - Persistent text area with auto-save functionality
- **Improved File Icons** - Visual file type indicators

### Previous Versions
See git history for older versions.
