#!/usr/bin/env python3
"""
PyServeX Enhanced Installation Script
"""

import subprocess
import sys
import os

def install_requirements():
    """Install required packages"""
    print("🚀 Installing PyServeX Enhanced dependencies...")
    
    try:
        # Install qrcode
        subprocess.check_call([sys.executable, "-m", "pip", "install", "qrcode"])
        print("✅ qrcode installed successfully")
        
        # Install Pillow for thumbnail generation
        subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow"])
        print("✅ Pillow installed successfully")
        
        print("\n🎉 All dependencies installed successfully!")
        print("\n🚀 You can now run PyServeX Enhanced with:")
        print("   python run.py")
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Error installing dependencies: {e}")
        print("Please install manually with: pip install qrcode Pillow")

def main():
    print("=" * 50)
    print("🚀 PyServeX Enhanced v2.0.0 Installation")
    print("=" * 50)
    
    install_requirements()

if __name__ == "__main__":
    main()