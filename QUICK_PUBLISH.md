# 🚀 Quick PyPI Publishing Commands

## Option 1: Automated Script (Recommended)
```bash
python publish_to_pypi.py
```
This script will guide you through the entire process!

## Option 2: Manual Commands

### Step 1: Install Tools
```bash
pip install --upgrade build twine
```

### Step 2: Clean & Build
```bash
# Clean old builds
rmdir /s /q dist build pyservx.egg-info

# Build package
python -m build

# Check package
python -m twine check dist/*
```

### Step 3: Upload

**Test on TestPyPI first (recommended):**
```bash
python -m twine upload --repository testpypi dist/*
```

**Upload to PyPI (production):**
```bash
python -m twine upload dist/*
```

### Step 4: Test Installation
```bash
# From TestPyPI
pip install --index-url https://test.pypi.org/simple/ --no-deps pyservx

# From PyPI
pip install pyservx
```

## 📝 Current Version: 1.2.0

## 🔐 Using API Token

Create `~/.pypirc`:
```ini
[pypi]
username = __token__
password = pypi-YOUR_TOKEN_HERE
```

Get token from: https://pypi.org/manage/account/token/

## ✅ Pre-Publish Checklist

- [x] Version updated to 1.2.0
- [x] pyproject.toml configured
- [x] README.md updated
- [ ] Git committed
- [ ] Ready to publish!

---

**PyServeX v1.2.0** - Ready for PyPI! 🎉