#!/usr/bin/env python3
"""
PyServeX - Automated PyPI Publishing Script
Author: Parth Padhiyar (SubZ3r0-0x01)
"""

import subprocess
import sys
import os
import shutil

def run_command(command, description):
    """Run a command and handle errors"""
    print(f"\n{'='*60}")
    print(f"🔧 {description}")
    print(f"{'='*60}")
    print(f"Running: {command}\n")
    
    try:
        # Use list format for better handling of paths with spaces
        if isinstance(command, str):
            result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        else:
            result = subprocess.run(command, check=True, capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
        print(f"✅ {description} - SUCCESS")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} - FAILED")
        print(f"Error: {e.stderr}")
        return False

def clean_build_artifacts():
    """Remove old build artifacts"""
    print("\n🧹 Cleaning old build artifacts...")
    
    dirs_to_remove = ['dist', 'build', 'pyservx.egg-info']
    for dir_name in dirs_to_remove:
        if os.path.exists(dir_name):
            try:
                shutil.rmtree(dir_name)
                print(f"  ✅ Removed {dir_name}/")
            except Exception as e:
                print(f"  ⚠️  Could not remove {dir_name}/: {e}")
        else:
            print(f"  ℹ️  {dir_name}/ does not exist")

def check_prerequisites():
    """Check if required tools are installed"""
    print("\n🔍 Checking prerequisites...")
    
    # Check if build is installed
    try:
        subprocess.run([sys.executable, "-m", "build", "--version"], 
                      capture_output=True, check=True)
        print("  ✅ build is installed")
    except:
        print("  ❌ build is not installed")
        print("  Installing build...")
        subprocess.run([sys.executable, "-m", "pip", "install", "build"], check=True)
    
    # Check if twine is installed
    try:
        subprocess.run([sys.executable, "-m", "twine", "--version"], 
                      capture_output=True, check=True)
        print("  ✅ twine is installed")
    except:
        print("  ❌ twine is not installed")
        print("  Installing twine...")
        subprocess.run([sys.executable, "-m", "pip", "install", "twine"], check=True)

def main():
    """Main publishing workflow"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║           PyServeX - PyPI Publishing Script                  ║
║                                                              ║
║           Author: Parth Padhiyar (SubZ3r0-0x01)             ║
║           Version: 1.2.0                                     ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    # Check prerequisites
    check_prerequisites()
    
    # Clean old builds
    clean_build_artifacts()
    
    # Build the package
    if not run_command(
        [sys.executable, "-m", "build"],
        "Building distribution packages"
    ):
        print("\n❌ Build failed. Exiting.")
        sys.exit(1)
    
    # Check the package
    if not run_command(
        [sys.executable, "-m", "twine", "check", "dist/*"],
        "Checking package validity"
    ):
        print("\n⚠️  Package check failed. Review the errors above.")
        response = input("\nDo you want to continue anyway? (y/N): ")
        if response.lower() != 'y':
            sys.exit(1)
    
    # Ask user which repository to upload to
    print("\n" + "="*60)
    print("📦 Ready to upload!")
    print("="*60)
    print("\nChoose upload destination:")
    print("  1. TestPyPI (recommended for testing)")
    print("  2. PyPI (production)")
    print("  3. Both (TestPyPI first, then PyPI)")
    print("  4. Exit")
    
    choice = input("\nEnter your choice (1-4): ").strip()
    
    if choice == "1":
        # Upload to TestPyPI
        print("\n🚀 Uploading to TestPyPI...")
        run_command(
            [sys.executable, "-m", "twine", "upload", "--repository", "testpypi", "dist/*"],
            "Uploading to TestPyPI"
        )
        print("\n✅ Upload to TestPyPI complete!")
        print("\nTest installation with:")
        print("  pip install --index-url https://test.pypi.org/simple/ --no-deps pyservx")
        
    elif choice == "2":
        # Upload to PyPI
        print("\n⚠️  WARNING: You are about to upload to PRODUCTION PyPI!")
        confirm = input("Are you sure? Type 'yes' to confirm: ")
        if confirm.lower() == 'yes':
            print("\n🚀 Uploading to PyPI...")
            run_command(
                [sys.executable, "-m", "twine", "upload", "dist/*"],
                "Uploading to PyPI"
            )
            print("\n✅ Upload to PyPI complete!")
            print("\nInstall with:")
            print("  pip install pyservx")
        else:
            print("\n❌ Upload cancelled.")
            
    elif choice == "3":
        # Upload to both
        print("\n🚀 Uploading to TestPyPI first...")
        if run_command(
            [sys.executable, "-m", "twine", "upload", "--repository", "testpypi", "dist/*"],
            "Uploading to TestPyPI"
        ):
            print("\n✅ TestPyPI upload successful!")
            print("\n⚠️  Now uploading to PRODUCTION PyPI!")
            confirm = input("Continue to PyPI? Type 'yes' to confirm: ")
            if confirm.lower() == 'yes':
                run_command(
                    [sys.executable, "-m", "twine", "upload", "dist/*"],
                    "Uploading to PyPI"
                )
                print("\n✅ Upload to PyPI complete!")
            else:
                print("\n❌ PyPI upload cancelled.")
        else:
            print("\n❌ TestPyPI upload failed. Not proceeding to PyPI.")
            
    elif choice == "4":
        print("\n👋 Exiting without upload.")
        sys.exit(0)
    else:
        print("\n❌ Invalid choice. Exiting.")
        sys.exit(1)
    
    print("\n" + "="*60)
    print("🎉 Publishing process complete!")
    print("="*60)
    print("\nNext steps:")
    print("  1. Verify on PyPI: https://pypi.org/project/pyservx/")
    print("  2. Test installation: pip install pyservx")
    print("  3. Tag release in Git: git tag -a v1.2.0 -m 'Version 1.2.0'")
    print("  4. Push to GitHub: git push origin main --tags")
    print("\n✨ Great job! Your package is now available to the world! ✨\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Publishing cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ An error occurred: {e}")
        sys.exit(1)