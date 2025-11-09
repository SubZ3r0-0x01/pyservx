# 📦 PyPI Publishing Guide for PyServeX

This guide will help you publish PyServeX to PyPI (Python Package Index).

## 🔧 Prerequisites

1. **PyPI Account**: Create accounts on both:
   - PyPI: https://pypi.org/account/register/
   - TestPyPI (for testing): https://test.pypi.org/account/register/

2. **Install Required Tools**:
```bash
pip install --upgrade build twine
```

## 📝 Step-by-Step Publishing Process

### Step 1: Verify Your Package Structure

Make sure your project has these files:
```
pyservx/
├── pyservx/
│   ├── __init__.py
│   ├── server.py
│   ├── request_handler.py
│   ├── html_generator.py
│   └── file_operations.py
├── pyproject.toml
├── README.md
├── LICENSE
└── MANIFEST.in (if needed)
```

### Step 2: Update Version Number

The version is already set to **1.2.0** in `pyproject.toml`.

For future updates, increment the version:
- Patch: 1.2.0 → 1.2.1 (bug fixes)
- Minor: 1.2.0 → 1.3.0 (new features)
- Major: 1.2.0 → 2.0.0 (breaking changes)

### Step 3: Clean Previous Builds

```bash
# Remove old build artifacts
rmdir /s /q dist
rmdir /s /q build
rmdir /s /q pyservx.egg-info
```

### Step 4: Build the Package

```bash
# Build distribution packages
python -m build
```

This creates:
- `dist/pyservx-1.2.0.tar.gz` (source distribution)
- `dist/pyservx-1.2.0-py3-none-any.whl` (wheel distribution)

### Step 5: Test on TestPyPI (Recommended)

```bash
# Upload to TestPyPI first
python -m twine upload --repository testpypi dist/*
```

You'll be prompted for:
- Username: Your TestPyPI username
- Password: Your TestPyPI password (or API token)

**Test Installation from TestPyPI:**
```bash
pip install --index-url https://test.pypi.org/simple/ --no-deps pyservx
```

### Step 6: Upload to PyPI (Production)

Once tested, upload to the real PyPI:

```bash
# Upload to PyPI
python -m twine upload dist/*
```

You'll be prompted for:
- Username: Your PyPI username (or `__token__` if using API token)
- Password: Your PyPI password or API token

### Step 7: Verify Installation

```bash
# Install from PyPI
pip install pyservx

# Test the installation
pyservx --version
```

## 🔐 Using API Tokens (Recommended)

API tokens are more secure than passwords.

### Create API Token:
1. Go to https://pypi.org/manage/account/token/
2. Click "Add API token"
3. Name: "PyServeX Upload"
4. Scope: "Entire account" or specific to "pyservx"
5. Copy the token (starts with `pypi-`)

### Configure Token:

Create `~/.pypirc` file:
```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
username = __token__
password = pypi-YOUR_TOKEN_HERE

[testpypi]
username = __token__
password = pypi-YOUR_TESTPYPI_TOKEN_HERE
```

**Important**: Keep this file secure! Add to `.gitignore`.

Now you can upload without entering credentials:
```bash
python -m twine upload dist/*
```

## 🚀 Quick Commands Reference

```bash
# 1. Clean old builds
rmdir /s /q dist build pyservx.egg-info

# 2. Build package
python -m build

# 3. Check package
python -m twine check dist/*

# 4. Upload to TestPyPI (optional)
python -m twine upload --repository testpypi dist/*

# 5. Upload to PyPI
python -m twine upload dist/*

# 6. Install and test
pip install pyservx
pyservx --version
```

## 📋 Pre-Upload Checklist

- [ ] Version number updated in `pyproject.toml`
- [ ] README.md is up to date
- [ ] All tests pass
- [ ] LICENSE file exists
- [ ] CHANGELOG updated (if you have one)
- [ ] Git committed and tagged
- [ ] Old build artifacts cleaned
- [ ] Package built successfully
- [ ] Package checked with twine
- [ ] Tested on TestPyPI (optional but recommended)

## 🏷️ Git Tagging (Recommended)

Tag your releases in Git:

```bash
# Commit your changes
git add .
git commit -m "Release v1.2.0 - Added dark/light mode, notepad, and enhanced features"

# Create a tag
git tag -a v1.2.0 -m "Version 1.2.0"

# Push to GitHub
git push origin main
git push origin v1.2.0
```

## 🔄 Updating Your Package

When you want to release a new version:

1. Update version in `pyproject.toml`
2. Update `__version__` in `pyservx/__init__.py`
3. Clean old builds: `rmdir /s /q dist build pyservx.egg-info`
4. Build: `python -m build`
5. Upload: `python -m twine upload dist/*`

## ❌ Common Issues

### Issue: "File already exists"
**Solution**: You're trying to upload a version that already exists. Increment the version number.

### Issue: "Invalid credentials"
**Solution**: Check your username/password or use API tokens.

### Issue: "Package name already taken"
**Solution**: The package name "pyservx" is already yours, so this shouldn't happen. For new packages, choose a unique name.

### Issue: "README rendering issues"
**Solution**: Validate your README.md:
```bash
python -m twine check dist/*
```

## 📊 After Publishing

1. **Verify on PyPI**: Visit https://pypi.org/project/pyservx/
2. **Test Installation**: `pip install pyservx`
3. **Update GitHub**: Add PyPI badge to README
4. **Announce**: Share on social media, Reddit, etc.

## 🎉 PyPI Badge for README

Add this to your README.md:

```markdown
[![PyPI version](https://badge.fury.io/py/pyservx.svg)](https://badge.fury.io/py/pyservx)
[![Downloads](https://pepy.tech/badge/pyservx)](https://pepy.tech/project/pyservx)
```

## 📞 Support

- PyPI Help: https://pypi.org/help/
- Packaging Guide: https://packaging.python.org/
- Twine Docs: https://twine.readthedocs.io/

---

**Good luck with your PyPI release! 🚀**

*PyServeX v1.2.0 - by Parth Padhiyar (SubZ3r0-0x01)*