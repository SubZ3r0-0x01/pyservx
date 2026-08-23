# Phase 0 — Liquid Glass UI Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace PyServeX's retro neon-green/VT323 Tailwind theme with a Liquid Glass material system (translucent panels, backdrop blur, light/dark semantic tokens) across the directory listing, file preview, and text editor pages, sharing one CSS/JS source instead of three copy-pasted theme blocks.

**Architecture:** A new `pyservx/ui_shell.py` module exports `GLASS_CSS` (token + component CSS), `THEME_JS` (theme toggle logic), and `shell(title, body_html, extra_head="")` which wraps any page body in the common `<html><head>...<body>` skeleton, theme-toggle button, and closing script. `html_generator.py` and `request_handler.py` are edited to build only their body content and call `ui_shell.shell(...)` instead of inlining the whole HTML document. No behavior changes — every existing feature (search, sort, upload, clipboard, drag-drop, edit/preview/download buttons) keeps working, only the visual layer and theme mechanism (from a body class to an `data-theme` attribute on `<html>`) change.

**Tech Stack:** Python stdlib (`http.server`), Tailwind CDN (unchanged, layout utilities only), plain CSS custom properties for the Liquid Glass tokens, vanilla JS for the theme toggle.

**Spec:** `docs/superpowers/specs/2026-08-24-pyservx-v4-overhaul-design.md` (Phase 0 section)

## Global Constraints

- Stay stdlib-first — no new dependency in this phase.
- One shared shell module (`pyservx/ui_shell.py`) is the single source of truth for the CSS tokens and theme-toggle JS — no page defines its own copy anymore.
- Preserve every existing endpoint, JS function name, and DOM element `id` that other inline `onclick`/`fetch` code in the same page depends on — this phase is a reskin, not a rewrite of behavior.
- Theme persistence key stays `pyservx-theme` in `localStorage` (existing users' saved preference must keep working), default resolves to `'dark'` when unset (matches current behavior).

---

### Task 1: Shared Liquid Glass shell module

**Files:**
- Create: `pyservx/ui_shell.py`
- Test: `tests/test_ui_shell.py`

**Interfaces:**
- Produces: `pyservx.ui_shell.GLASS_CSS` (str), `pyservx.ui_shell.THEME_JS` (str), `pyservx.ui_shell.shell(title: str, body_html: str, extra_head: str = "") -> str`. Tasks 2-4 consume `shell()`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ui_shell.py
import unittest
from pyservx import ui_shell


class TestUiShell(unittest.TestCase):
    def test_shell_contains_title_and_body(self):
        html = ui_shell.shell("My Title", "<p>hello</p>")
        self.assertIn("My Title", html)
        self.assertIn("<p>hello</p>", html)

    def test_shell_contains_both_theme_tokens(self):
        html = ui_shell.shell("T", "<p></p>")
        self.assertIn("--glass-bg", html)
        self.assertIn("data-theme", html)
        self.assertIn("prefers-color-scheme: dark", html)

    def test_shell_includes_extra_head(self):
        html = ui_shell.shell("T", "<p></p>", extra_head="<meta name=\"x\" content=\"y\">")
        self.assertIn('<meta name="x" content="y">', html)

    def test_shell_default_theme_is_dark_when_unset(self):
        self.assertIn("|| 'dark'", ui_shell.THEME_JS)


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ui_shell.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pyservx.ui_shell'`

- [ ] **Step 3: Write the implementation**

```python
# pyservx/ui_shell.py
#!/usr/bin/env python3
"""Shared Liquid Glass UI shell: CSS tokens, theme toggle, page wrapper."""

GLASS_CSS = """
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');

        :root {
            --glass-bg: rgba(255, 255, 255, 0.6);
            --glass-bg-strong: rgba(255, 255, 255, 0.82);
            --glass-border: rgba(0, 0, 0, 0.08);
            --glass-blur: 20px;
            --page-bg: #f2f2f7;
            --text-primary: #1d1d1f;
            --text-secondary: #6e6e73;
            --accent: #0a84ff;
            --accent-contrast: #ffffff;
            --danger: #ff453a;
            --success: #32d74b;
            --shadow: 0 8px 32px rgba(0, 0, 0, 0.12);
        }

        @media (prefers-color-scheme: dark) {
            :root:not([data-theme="light"]) {
                --glass-bg: rgba(30, 30, 32, 0.55);
                --glass-bg-strong: rgba(30, 30, 32, 0.78);
                --glass-border: rgba(255, 255, 255, 0.12);
                --page-bg: #000000;
                --text-primary: #f5f5f7;
                --text-secondary: #a1a1a6;
                --shadow: 0 8px 32px rgba(0, 0, 0, 0.55);
            }
        }

        :root[data-theme="dark"] {
            --glass-bg: rgba(30, 30, 32, 0.55);
            --glass-bg-strong: rgba(30, 30, 32, 0.78);
            --glass-border: rgba(255, 255, 255, 0.12);
            --page-bg: #000000;
            --text-primary: #f5f5f7;
            --text-secondary: #a1a1a6;
            --shadow: 0 8px 32px rgba(0, 0, 0, 0.55);
        }

        html, body {
            height: 100%;
            margin: 0;
            padding: 0;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--page-bg);
            color: var(--text-primary);
            transition: background-color 0.25s ease, color 0.25s ease;
        }

        .glass-panel {
            background: var(--glass-bg);
            backdrop-filter: blur(var(--glass-blur));
            -webkit-backdrop-filter: blur(var(--glass-blur));
            border: 1px solid var(--glass-border);
            border-radius: 16px;
            box-shadow: var(--shadow);
        }

        .glass-btn {
            background: var(--glass-bg-strong);
            backdrop-filter: blur(var(--glass-blur));
            -webkit-backdrop-filter: blur(var(--glass-blur));
            border: 1px solid var(--glass-border);
            border-radius: 10px;
            color: var(--text-primary);
            padding: 0.5rem 1rem;
            cursor: pointer;
            font-family: inherit;
            transition: transform 0.15s ease, background 0.15s ease;
        }

        .glass-btn:hover { transform: translateY(-1px); }

        .glass-btn-accent { background: var(--accent); color: var(--accent-contrast); border: none; }
        .glass-btn-danger { background: var(--danger); color: #fff; border: none; }
        .glass-btn-success { background: var(--success); color: #fff; border: none; }

        .glass-input, textarea.glass-input {
            background: var(--glass-bg);
            border: 1px solid var(--glass-border);
            border-radius: 10px;
            color: var(--text-primary);
            padding: 0.5rem 0.75rem;
            font-family: inherit;
        }

        .glass-input:focus {
            outline: none;
            border-color: var(--accent);
            box-shadow: 0 0 0 3px rgba(10, 132, 255, 0.25);
        }

        table { width: 100%; border-collapse: collapse; }

        th, td {
            text-align: left;
            padding: 0.6rem 0.75rem;
            border-bottom: 1px solid var(--glass-border);
        }

        th {
            background: var(--glass-bg);
            color: var(--text-secondary);
            font-weight: 500;
            cursor: pointer;
            position: sticky;
            top: 0;
            z-index: 10;
            backdrop-filter: blur(var(--glass-blur));
            -webkit-backdrop-filter: blur(var(--glass-blur));
        }

        tr:hover { background: var(--glass-bg); }

        ::-webkit-scrollbar { width: 8px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: var(--glass-border); border-radius: 4px; }

        .theme-toggle-btn {
            position: fixed;
            top: 1rem;
            right: 1rem;
            z-index: 1000;
            font-size: 1.1rem;
        }
"""

THEME_JS = """
        function pyservxInitTheme() {
            var root = document.documentElement;
            var icon = document.getElementById('themeIcon');
            var saved = localStorage.getItem('pyservx-theme') || 'dark';
            root.setAttribute('data-theme', saved);
            if (icon) { icon.textContent = saved === 'light' ? '\\u2600\\ufe0f' : '\\ud83c\\udf19'; }
            var toggle = document.getElementById('themeToggle');
            if (toggle) {
                toggle.addEventListener('click', function () {
                    var current = root.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
                    root.setAttribute('data-theme', current);
                    localStorage.setItem('pyservx-theme', current);
                    if (icon) { icon.textContent = current === 'light' ? '\\u2600\\ufe0f' : '\\ud83c\\udf19'; }
                });
            }
        }
        window.addEventListener('DOMContentLoaded', pyservxInitTheme);
"""


def shell(title: str, body_html: str, extra_head: str = "") -> str:
    """Wrap page body content in the shared Liquid Glass shell."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>{GLASS_CSS}</style>
    {extra_head}
</head>
<body>
    <button id="themeToggle" class="glass-btn theme-toggle-btn" aria-label="Toggle theme">
        <span id="themeIcon">\U0001F319</span>
    </button>
    {body_html}
    <script>{THEME_JS}</script>
</body>
</html>
"""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_ui_shell.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add pyservx/ui_shell.py tests/test_ui_shell.py
git commit -m "feat: add shared Liquid Glass UI shell module"
```

---

### Task 2: Reskin the directory listing page

**Files:**
- Modify: `pyservx/html_generator.py` (the `list_directory_page` function, and the row-building block above it)
- Test: `tests/test_html_generator.py`

**Interfaces:**
- Consumes: `pyservx.ui_shell.shell(title, body_html, extra_head="")` from Task 1.
- Produces: `pyservx.html_generator.list_directory_page(handler, path)` — same signature and return type (`str`, full HTML document) as before; same JS globals (`navigateToPath`, `sortFiles`, `downloadFile`, `downloadFolder`, `previewFile`, `editFile`, `createNewFolder`, `createNewFile`, `setupUploadHandling`, clipboard functions) so `request_handler.py` and inline `onclick=` attributes keep working unchanged.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_html_generator.py
import os
import tempfile
import unittest
from unittest.mock import MagicMock
from pyservx import html_generator


class TestListDirectoryPage(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        with open(os.path.join(self.tmpdir, "example.txt"), "w") as f:
            f.write("hi")
        self.handler = MagicMock()
        self.handler.path = "/"

    def test_uses_glass_shell(self):
        html = html_generator.list_directory_page(self.handler, self.tmpdir)
        self.assertIn("--glass-bg", html)
        self.assertIn('id="themeToggle"', html)

    def test_lists_file_and_keeps_js_hooks(self):
        html = html_generator.list_directory_page(self.handler, self.tmpdir)
        self.assertIn("example.txt", html)
        self.assertIn("function navigateToPath(", html)
        self.assertIn("function downloadFolder(", html)
        self.assertIn("function previewFile(", html)
        self.assertIn("id=\"fileTableBody\"", html)


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_html_generator.py -v`
Expected: FAIL — `AssertionError: '--glass-bg' not found` (current page still uses the old neon theme)

- [ ] **Step 3: Rewrite `list_directory_page` to use the shared shell**

In `pyservx/html_generator.py`, add the import at the top:

```python
from . import ui_shell
```

Replace every occurrence inside the `list_rows.append(...)` blocks (both the parent-directory row and the per-entry rows) of `text-neon` with nothing (drop the class — text color now comes from `var(--text-primary)` on `body`), and `hover:bg-green-900/20` with `hover:bg-[var(--glass-bg)]`, and `border-b border-green-700/50` with `border-b` (border color comes from the shared `td` rule in `GLASS_CSS`). Concretely, the parent-directory row becomes:

```python
        list_rows.append(f"""
            <tr class="cursor-pointer" onclick="navigateToPath('{html.escape(parent)}')">
                <td>📁 .. (Parent Directory)</td>
                <td class="text-right">-</td>
                <td class="text-right">-</td>
                <td class="text-right">-</td>
            </tr>
        """)
```

The directory row becomes:

```python
            list_rows.append(
                f"""
                <tr class="cursor-pointer" onclick="navigateToPath('{href}')">
                    <td>📁 {html.escape(displayname)}</td>
                    <td class="text-right">{size}</td>
                    <td class="text-right">{date_modified}</td>
                    <td class="text-right">
                        <button onclick="event.stopPropagation(); downloadFolder('{href}')" class="glass-btn text-xs py-1 px-2">📦 Zip</button>
                    </td>
                </tr>
                """
            )
```

The file row becomes:

```python
            list_rows.append(f"""
                <tr class="cursor-pointer" onclick="{action_onclick}">
                    <td>{file_icon} {html.escape(displayname)}</td>
                    <td class="text-right">{size}</td>
                    <td class="text-right">{date_modified}</td>
                    <td class="text-right">
                        <button onclick="event.stopPropagation(); previewFile('{href}', '{html.escape(displayname)}')" class="glass-btn text-xs py-1 px-2 mr-1">👁️</button>
                        {f'<button onclick="event.stopPropagation(); editFile(\'{href}\', \'{html.escape(displayname)}\')" class="glass-btn text-xs py-1 px-2 mr-1">✏️</button>' if displayname.lower().endswith(('.txt', '.py', '.js', '.html', '.css', '.json', '.xml', '.md', '.log', '.cfg', '.ini', '.yml', '.yaml')) else ''}
                        <button onclick="event.stopPropagation(); downloadFile('{href}', '{html.escape(displayname)}')" class="glass-btn text-xs py-1 px-2">⬇️</button>
                    </td>
                </tr>
                """)
```

Then replace the entire `return f"""<!DOCTYPE html>...</html>\n"""` block (from `list_html = '\n'.join(list_rows)` to the end of the function) with:

```python
    list_html = '\n'.join(list_rows)

    body_html = f"""
    <div class="main-container" style="display:flex; flex-direction:column; height:100vh;">
        <div class="glass-panel" style="margin:1rem; padding:1rem; text-align:center; flex-shrink:0;">
            <h1 class="text-2xl md:text-3xl font-semibold">PyServeX</h1>
            <p class="text-sm" style="color: var(--text-secondary);">File Server</p>
        </div>

        <div style="flex:1; display:flex; gap:1rem; padding:0 1rem 1rem; overflow:hidden;">
            <div class="glass-panel" style="width:60%; display:flex; flex-direction:column; overflow:hidden; padding:1rem;">
                <div style="flex-shrink:0;">
                    <h2 class="text-lg mb-2">📁 {displaypath}</h2>
                    <div class="flex flex-col sm:flex-row gap-2 mb-3">
                        <input type="text" id="searchInput" placeholder="🔍 Real-time search..."
                               value="{html.escape(search_query)}"
                               class="glass-input flex-grow">
                        <button onclick="clearSearch()" class="glass-btn glass-btn-danger">Clear</button>
                    </div>

                    <form id="uploadForm" class="flex flex-col sm:flex-row gap-2">
                        <input type="file" id="fileUpload" multiple class="glass-input flex-grow">
                        <button type="submit" class="glass-btn glass-btn-accent">Upload</button>
                    </form>
                    <div class="flex gap-2 mt-2">
                        <button onclick="createNewFolder()" class="glass-btn text-sm">📁 New Folder</button>
                        <button onclick="createNewFile()" class="glass-btn text-sm">📄 New File</button>
                    </div>
                    <div id="uploadProgress" class="glass-panel mt-2" style="display:none; padding:0.5rem;">
                        <div id="progressBar" style="width:0%; height:20px; background:var(--accent); border-radius:6px; text-align:center; line-height:20px; color:#fff; font-size:0.8rem; transition:width 0.3s ease;"></div>
                        <div id="progressText" class="text-center mt-1 text-sm"></div>
                    </div>
                </div>

                <div style="flex:1; overflow-y:auto; margin-top:0.75rem;">
                    <table>
                        <thead>
                            <tr>
                                <th onclick="sortFiles('name')">📄 Name {('↓' if sort_by == 'name' and sort_order == 'desc' else '↑' if sort_by == 'name' else '')}</th>
                                <th onclick="sortFiles('size')" class="text-right">📏 Size {('↓' if sort_by == 'size' and sort_order == 'desc' else '↑' if sort_by == 'size' else '')}</th>
                                <th onclick="sortFiles('date')" class="text-right">📅 Modified {('↓' if sort_by == 'date' and sort_order == 'desc' else '↑' if sort_by == 'date' else '')}</th>
                                <th class="text-right">⚡ Actions</th>
                            </tr>
                        </thead>
                        <tbody id="fileTableBody">
                            {list_html}
                        </tbody>
                    </table>
                </div>
            </div>

            <div class="glass-panel" style="width:40%; display:flex; flex-direction:column; overflow:hidden; padding:1rem;">
                <div class="flex justify-between items-center mb-2">
                    <h3 class="text-lg">📝 Text Clipboard</h3>
                    <div class="flex gap-2">
                        <button onclick="saveTextClipboard()" class="glass-btn glass-btn-success text-sm">💾 Save</button>
                        <button onclick="clearTextClipboard()" class="glass-btn glass-btn-danger text-sm">🗑️ Clear</button>
                        <button onclick="copyToClipboard()" class="glass-btn text-sm">📋 Copy</button>
                    </div>
                </div>
                <textarea id="textClipboard" class="glass-input flex-grow" style="resize:none; font-family: 'Courier New', monospace;"
                          placeholder="Your permanent text clipboard...&#10;&#10;• Copy/paste text here&#10;• Click Save to persist&#10;• Survives page refreshes"></textarea>
                <div id="clipboardStatus" class="mt-2 text-center text-sm"></div>
            </div>
        </div>
    </div>

    <script>
        let currentPath = '{displaypath}';
        let searchTimeout;

        window.onload = function() {{
            loadTextClipboard();
            setupRealTimeSearch();
            setupUploadHandling();
        }};

        function setupRealTimeSearch() {{
            const searchInput = document.getElementById('searchInput');
            searchInput.addEventListener('input', function() {{
                clearTimeout(searchTimeout);
                searchTimeout = setTimeout(() => {{ performSearch(this.value); }}, 300);
            }});
        }}

        function performSearch(query) {{
            const rows = document.querySelectorAll('#fileTableBody tr');
            rows.forEach(row => {{
                const nameCell = row.querySelector('td:first-child');
                if (nameCell) {{
                    const fileName = nameCell.textContent.toLowerCase();
                    row.style.display = (query === '' || fileName.includes(query.toLowerCase())) ? '' : 'none';
                }}
            }});
        }}

        function clearSearch() {{
            document.getElementById('searchInput').value = '';
            performSearch('');
        }}

        function navigateToPath(path) {{ window.location.href = path; }}

        function sortFiles(sortBy) {{
            const url = new URL(window.location);
            const currentSort = url.searchParams.get('sort');
            const currentOrder = url.searchParams.get('order');
            let newOrder = (currentSort === sortBy && currentOrder === 'asc') ? 'desc' : 'asc';
            url.searchParams.set('sort', sortBy);
            url.searchParams.set('order', newOrder);
            window.location.href = url.toString();
        }}

        function downloadFile(path, filename) {{
            const link = document.createElement('a');
            link.href = path;
            link.download = filename;
            link.click();
        }}

        function downloadFolder(path) {{ window.location.href = path + 'download_folder'; }}
        function previewFile(path, filename) {{ window.open(path + '/preview', '_blank'); }}
        function editFile(path, filename) {{ window.open(path + '/edit', '_blank'); }}

        function createNewFolder() {{
            const folderName = prompt("📁 Enter new folder name:");
            if (folderName) {{
                fetch(window.location.pathname + folderName, {{ method: 'MKCOL' }})
                    .then(response => response.json())
                    .then(data => {{
                        if (data.status === 'success') {{
                            showStatus('✅ ' + data.message, 'success');
                            setTimeout(() => window.location.reload(), 1500);
                        }} else {{ showStatus('❌ ' + data.message, 'error'); }}
                    }})
                    .catch(() => showStatus('❌ Network error creating folder', 'error'));
            }}
        }}

        function createNewFile() {{ window.open(window.location.pathname + 'notepad', '_blank'); }}

        function setupUploadHandling() {{
            const uploadForm = document.getElementById('uploadForm');
            const fileUpload = document.getElementById('fileUpload');
            const uploadProgress = document.getElementById('uploadProgress');
            const progressBar = document.getElementById('progressBar');
            const progressText = document.getElementById('progressText');

            uploadForm.addEventListener('submit', function(e) {{
                e.preventDefault();
                const files = fileUpload.files;
                if (files.length === 0) {{ showStatus('❌ Please select files to upload', 'error'); return; }}

                const formData = new FormData();
                for (let i = 0; i < files.length; i++) {{ formData.append('file', files[i]); }}

                const xhr = new XMLHttpRequest();
                uploadProgress.style.display = 'block';
                progressBar.style.width = '0%';
                progressText.textContent = 'Uploading...';

                xhr.upload.addEventListener('progress', function(event) {{
                    if (event.lengthComputable) {{
                        const percent = (event.loaded / event.total) * 100;
                        progressBar.style.width = percent.toFixed(2) + '%';
                        progressText.textContent = `Uploading: ${{percent.toFixed(1)}}%`;
                    }}
                }});

                xhr.addEventListener('load', function() {{
                    uploadProgress.style.display = 'none';
                    if (xhr.status === 200) {{
                        const response = JSON.parse(xhr.responseText);
                        showStatus('✅ ' + response.message, 'success');
                        setTimeout(() => window.location.reload(), 1500);
                    }} else {{ showStatus('❌ Upload failed', 'error'); }}
                }});

                xhr.addEventListener('error', function() {{
                    uploadProgress.style.display = 'none';
                    showStatus('❌ Upload failed due to network error', 'error');
                }});

                xhr.open('POST', window.location.pathname + 'upload');
                xhr.send(formData);
            }});

            const fileExplorer = uploadForm.closest('.glass-panel');
            ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {{
                fileExplorer.addEventListener(eventName, e => {{ e.preventDefault(); e.stopPropagation(); }}, false);
            }});
            fileExplorer.addEventListener('drop', function(e) {{
                fileUpload.files = e.dataTransfer.files;
                uploadForm.dispatchEvent(new Event('submit', {{ cancelable: true }}));
            }});
        }}

        function loadTextClipboard() {{
            fetch(window.location.pathname + 'load_clipboard?path=' + encodeURIComponent(window.location.pathname))
                .then(response => response.json())
                .then(data => {{
                    if (data.status === 'success' && data.content) {{
                        document.getElementById('textClipboard').value = data.content;
                    }} else {{
                        const saved = localStorage.getItem('pyservx-clipboard-' + window.location.pathname);
                        if (saved) {{ document.getElementById('textClipboard').value = saved; }}
                    }}
                }})
                .catch(() => {{
                    const saved = localStorage.getItem('pyservx-clipboard-' + window.location.pathname);
                    if (saved) {{ document.getElementById('textClipboard').value = saved; }}
                }});
        }}

        function saveTextClipboard() {{
            const content = document.getElementById('textClipboard').value;
            fetch(window.location.pathname + 'save_clipboard', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ content: content, path: window.location.pathname }})
            }})
                .then(response => response.json())
                .then(data => {{
                    if (data.status === 'success') {{
                        localStorage.setItem('pyservx-clipboard-' + window.location.pathname, content);
                        showClipboardStatus('💾 Text saved successfully!', 'success');
                    }} else {{ showClipboardStatus('❌ Save failed: ' + data.message, 'error'); }}
                }})
                .catch(() => {{
                    localStorage.setItem('pyservx-clipboard-' + window.location.pathname, content);
                    showClipboardStatus('💾 Saved locally (server unavailable)', 'info');
                }});
        }}

        function clearTextClipboard() {{
            if (confirm('🗑️ Clear all text in clipboard?')) {{
                document.getElementById('textClipboard').value = '';
                localStorage.removeItem('pyservx-clipboard-' + window.location.pathname);
                showClipboardStatus('🗑️ Clipboard cleared', 'info');
            }}
        }}

        function copyToClipboard() {{
            const textArea = document.getElementById('textClipboard');
            textArea.select();
            textArea.setSelectionRange(0, 99999);
            navigator.clipboard.writeText(textArea.value).then(() => {{
                showClipboardStatus('📋 Copied to system clipboard!', 'success');
            }}).catch(() => showClipboardStatus('❌ Copy failed', 'error'));
        }}

        function showStatus(message, type) {{ console.log(type + ': ' + message); }}

        function showClipboardStatus(message, type) {{
            const status = document.getElementById('clipboardStatus');
            status.textContent = message;
            status.className = `mt-2 text-center text-sm ${{type === 'success' ? 'text-green-500' : type === 'error' ? 'text-red-500' : 'text-blue-500'}}`;
            setTimeout(() => {{ status.textContent = ''; status.className = 'mt-2 text-center text-sm'; }}, 3000);
        }}

        document.getElementById('textClipboard').addEventListener('input', function() {{
            clearTimeout(window.clipboardSaveTimeout);
            window.clipboardSaveTimeout = setTimeout(() => {{
                const content = document.getElementById('textClipboard').value;
                if (content.trim()) {{
                    localStorage.setItem('pyservx-clipboard-' + window.location.pathname, content);
                    fetch(window.location.pathname + 'save_clipboard', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{ content: content, path: window.location.pathname }})
                    }})
                        .then(response => response.json())
                        .then(data => {{ if (data.status === 'success') {{ showClipboardStatus('💾 Auto-saved', 'success'); }} }})
                        .catch(() => console.log('Auto-save failed, using localStorage only'));
                }}
            }}, 2000);
        }});
    </script>
    """

    return ui_shell.shell(f"PyServeX - {displaypath}", body_html)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_html_generator.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add pyservx/html_generator.py tests/test_html_generator.py
git commit -m "feat: reskin directory listing page with Liquid Glass shell"
```

---

### Task 3: Reskin file preview pages

**Files:**
- Modify: `pyservx/request_handler.py` (`get_preview_page_template` and the five `generate_*_preview` functions)
- Test: `tests/test_preview_pages.py`

**Interfaces:**
- Consumes: `pyservx.ui_shell.shell(title, body_html, extra_head="")` from Task 1.
- Produces: `get_preview_page_template(self, title, content, filename, file_url) -> str` keeps the exact same signature and return type so `generate_image_preview`, `generate_pdf_preview`, `generate_video_preview`, `generate_audio_preview`, and `generate_download_preview` (all unchanged callers) keep working.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_preview_pages.py
import unittest
from unittest.mock import MagicMock
from pyservx.request_handler import FileRequestHandler


class TestPreviewPages(unittest.TestCase):
    def setUp(self):
        # Bypass __init__ (it expects a live socket); build a bare instance.
        self.handler = FileRequestHandler.__new__(FileRequestHandler)

    def test_preview_template_uses_glass_shell(self):
        html = self.handler.get_preview_page_template("T", "<p>body</p>", "f.txt", "/f.txt")
        self.assertIn("--glass-bg", html)
        self.assertIn("<p>body</p>", html)

    def test_image_preview_uses_glass_buttons(self):
        html = self.handler.generate_image_preview("pic.png", "/pic.png")
        self.assertIn("glass-btn", html)
        self.assertIn("pic.png", html)


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_preview_pages.py -v`
Expected: FAIL — `AssertionError: '--glass-bg' not found`

- [ ] **Step 3: Rewrite the preview template and content generators**

In `pyservx/request_handler.py`, add the import near the top (with the other `from . import` lines):

```python
from . import ui_shell
```

Replace the whole `get_preview_page_template` method body with:

```python
    def get_preview_page_template(self, title, content, filename, file_url):
        """Generate a common template for preview pages with theme support"""
        return ui_shell.shell(title, content)
```

Replace the five content strings in `generate_image_preview`, `generate_pdf_preview`, `generate_video_preview`, `generate_audio_preview`, `generate_download_preview` so every `border border-green-700/50` becomes `class="glass-panel"` (dropping the old border utility), and every `bg-green-700 hover:bg-green-800 text-white font-bold py-2 px-4 rounded` / `bg-gray-700 hover:bg-gray-800 text-white font-bold py-2 px-4 rounded` becomes `glass-btn glass-btn-accent` / `glass-btn`. Concretely:

```python
    def generate_image_preview(self, filename, file_url):
        content = f"""
    <div class="max-w-4xl mx-auto p-6">
        <h1 class="text-2xl mb-4 text-center">Image Preview: {filename}</h1>
        <div class="text-center mb-4">
            <img src="{file_url}" alt="{filename}" class="glass-panel max-w-full h-auto mx-auto" style="max-height: 80vh; padding: 0.5rem;">
        </div>
        <div class="text-center">
            <a href="{file_url}" download class="glass-btn glass-btn-accent mr-2">Download</a>
            <button onclick="window.close()" class="glass-btn">Close</button>
        </div>
    </div>
"""
        return self.get_preview_page_template(f"Preview: {filename}", content, filename, file_url)

    def generate_pdf_preview(self, filename, file_url):
        content = f"""
    <div class="max-w-6xl mx-auto p-6">
        <h1 class="text-2xl mb-4 text-center">PDF Preview: {filename}</h1>
        <div class="mb-4 glass-panel" style="padding: 0.5rem;">
            <embed src="{file_url}" type="application/pdf" width="100%" height="600px">
        </div>
        <div class="text-center">
            <a href="{file_url}" download class="glass-btn glass-btn-accent mr-2">Download</a>
            <button onclick="window.close()" class="glass-btn">Close</button>
        </div>
    </div>
"""
        return self.get_preview_page_template(f"Preview: {filename}", content, filename, file_url)

    def generate_video_preview(self, filename, file_url):
        content = f"""
    <div class="max-w-4xl mx-auto p-6">
        <h1 class="text-2xl mb-4 text-center">Video Preview: {filename}</h1>
        <div class="text-center mb-4">
            <video controls class="glass-panel max-w-full h-auto mx-auto" style="max-height: 70vh; padding: 0.5rem;">
                <source src="{file_url}" type="video/mp4">
                <source src="{file_url}" type="video/webm">
                <source src="{file_url}" type="video/ogg">
                Your browser does not support the video tag.
            </video>
        </div>
        <div class="text-center">
            <a href="{file_url}" download class="glass-btn glass-btn-accent mr-2">Download</a>
            <button onclick="window.close()" class="glass-btn">Close</button>
        </div>
    </div>
"""
        return self.get_preview_page_template(f"Preview: {filename}", content, filename, file_url)

    def generate_audio_preview(self, filename, file_url):
        content = f"""
    <div class="max-w-2xl mx-auto p-6">
        <h1 class="text-2xl mb-4 text-center">Audio Preview: {filename}</h1>
        <div class="text-center mb-4 glass-panel" style="padding: 1rem;">
            <audio controls class="w-full">
                <source src="{file_url}" type="audio/mpeg">
                <source src="{file_url}" type="audio/ogg">
                <source src="{file_url}" type="audio/wav">
                Your browser does not support the audio element.
            </audio>
        </div>
        <div class="text-center">
            <a href="{file_url}" download class="glass-btn glass-btn-accent mr-2">Download</a>
            <button onclick="window.close()" class="glass-btn">Close</button>
        </div>
    </div>
"""
        return self.get_preview_page_template(f"Preview: {filename}", content, filename, file_url)
```

In `generate_text_preview`, replace the `page_content` block's classes the same way:

```python
            page_content = f"""
    <div class="max-w-4xl mx-auto p-6">
        <h1 class="text-2xl mb-4 text-center">Text Preview: {filename}</h1>
        <div class="mb-4 p-4 glass-panel overflow-auto" style="max-height: 70vh;">
            <pre class="text-sm whitespace-pre-wrap">{content}</pre>
        </div>
        <div class="text-center">
            <button onclick="window.open('{file_url}edit', '_blank')" class="glass-btn glass-btn-accent mr-2">Edit</button>
            <button onclick="window.close()" class="glass-btn">Close</button>
        </div>
    </div>
"""
```

And in `generate_download_preview`:

```python
    def generate_download_preview(self, filename, file_url):
        content = f"""
    <div class="max-w-2xl mx-auto text-center p-6">
        <h1 class="text-2xl mb-4">File: {filename}</h1>
        <p class="mb-4" style="color: var(--text-secondary);">This file type cannot be previewed in the browser.</p>
        <div>
            <a href="{file_url}" download class="glass-btn glass-btn-accent mr-2">Download File</a>
            <button onclick="window.close()" class="glass-btn">Close</button>
        </div>
    </div>
"""
        return self.get_preview_page_template(f"Preview: {filename}", content, filename, file_url)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_preview_pages.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add pyservx/request_handler.py tests/test_preview_pages.py
git commit -m "feat: reskin file preview pages with Liquid Glass shell"
```

---

### Task 4: Reskin the text editor page

**Files:**
- Modify: `pyservx/request_handler.py` (`serve_editor_page`)
- Test: `tests/test_editor_page.py`

**Interfaces:**
- Consumes: `pyservx.ui_shell.shell(title, body_html, extra_head="")` from Task 1.
- Produces: `serve_editor_page(self, file_path=None, dir_path=None)` — same signature, same behavior (writes the response itself via `self.send_response`/`self.wfile.write`, no return value), same DOM ids (`editor`, `filename`, `status`) and JS function `saveFile()` that `save_file`/`create_file` POST handlers expect nothing from (payload built client-side), so no server-side handler changes needed.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_editor_page.py
import unittest
from unittest.mock import MagicMock
from pyservx.request_handler import FileRequestHandler


class TestEditorPage(unittest.TestCase):
    def setUp(self):
        self.handler = FileRequestHandler.__new__(FileRequestHandler)
        self.handler.wfile = MagicMock()
        self.handler.send_response = MagicMock()
        self.handler.send_header = MagicMock()
        self.handler.end_headers = MagicMock()

    def test_new_file_editor_uses_glass_shell(self):
        self.handler.serve_editor_page(file_path=None, dir_path="/tmp")
        written = self.handler.wfile.write.call_args[0][0].decode('utf-8')
        self.assertIn("--glass-bg", written)
        self.assertIn('id="editor"', written)
        self.assertIn('id="filename"', written)

    def test_existing_file_editor_hides_filename_input(self):
        import tempfile, os
        fd, path = tempfile.mkstemp(suffix=".txt")
        os.write(fd, b"hello")
        os.close(fd)
        try:
            self.handler.base_dir = os.path.dirname(path)
            self.handler.serve_editor_page(file_path=path, dir_path=None)
            written = self.handler.wfile.write.call_args[0][0].decode('utf-8')
            self.assertIn("hello", written)
            self.assertNotIn('id="filename"', written)
        finally:
            os.remove(path)


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_editor_page.py -v`
Expected: FAIL — `AssertionError: '--glass-bg' not found`

- [ ] **Step 3: Rewrite `serve_editor_page`**

Replace the entire method body (from `def serve_editor_page` through the final `self.wfile.write(editor_html.encode('utf-8'))`) with:

```python
    def serve_editor_page(self, file_path=None, dir_path=None):
        """Serve a text editor page for creating or editing files"""
        if file_path:
            filename = os.path.basename(file_path)
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except Exception:
                content = ""
            rel_path = os.path.relpath(file_path, self.base_dir)
            save_url = '/' + rel_path.replace('\\', '/') + '/save_file'
            title = f"Edit: {filename}"
        else:
            filename = ""
            content = ""
            rel_path = os.path.relpath(dir_path, self.base_dir)
            save_url = '/' + rel_path.replace('\\', '/') + '/create_file'
            title = "Create New File"

        filename_field = "" if file_path else '''
        <div class="mb-4">
            <label for="filename" class="block text-sm mb-2">Filename:</label>
            <input type="text" id="filename" class="glass-input w-full" placeholder="Enter filename (e.g., myfile.txt)" value="">
        </div>
        '''

        filename_js = "const filename = document.getElementById('filename').value;" if not file_path else f"const filename = '{filename}';"
        filename_validation = "" if file_path else '''
            if (!filename.trim()) {
                alert('Please enter a filename');
                return;
            }
            '''
        payload_filename_field = "filename: filename," if not file_path else ""

        body_html = f"""
    <div class="max-w-6xl mx-auto p-6">
        <div class="mb-4 flex justify-between items-center">
            <h1 class="text-2xl">{title}</h1>
            <div class="flex space-x-2">
                <button onclick="saveFile()" class="glass-btn glass-btn-accent">Save</button>
                <button onclick="window.close()" class="glass-btn">Close</button>
            </div>
        </div>

        {filename_field}

        <div style="min-height: 70vh;">
            <textarea id="editor" class="glass-input w-full h-full" style="font-family: 'Courier New', monospace; font-size: 14px; line-height: 1.5; resize: none;" placeholder="Start typing your content here...">{content}</textarea>
        </div>

        <div id="status" class="mt-4 text-center"></div>
    </div>

    <script>
        function saveFile() {{
            const content = document.getElementById('editor').value;
            {filename_js}
            {filename_validation}
            const payload = {{
                {payload_filename_field}
                content: content
            }};

            fetch('{save_url}', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify(payload)
            }})
            .then(response => response.json())
            .then(data => {{
                const status = document.getElementById('status');
                if (data.status === 'success') {{
                    status.innerHTML = '<span style="color: var(--success);">✓ ' + data.message + '</span>';
                    setTimeout(() => {{ status.innerHTML = ''; }}, 3000);
                }} else {{
                    status.innerHTML = '<span style="color: var(--danger);">✗ ' + data.message + '</span>';
                }}
            }})
            .catch(error => {{
                console.error('Error:', error);
                document.getElementById('status').innerHTML = '<span style="color: var(--danger);">✗ Save failed due to network error</span>';
            }});
        }}

        const editor = document.getElementById('editor');
        editor.style.height = 'auto';
        editor.style.height = Math.max(500, editor.scrollHeight) + 'px';
        editor.addEventListener('input', function() {{
            this.style.height = 'auto';
            this.style.height = Math.max(500, this.scrollHeight) + 'px';
        }});

        document.addEventListener('keydown', function(e) {{
            if (e.ctrlKey && e.key === 's') {{
                e.preventDefault();
                saveFile();
            }}
        }});
    </script>
"""

        editor_html = ui_shell.shell(title, body_html)

        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(editor_html.encode('utf-8'))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_editor_page.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add pyservx/request_handler.py tests/test_editor_page.py
git commit -m "feat: reskin text editor page with Liquid Glass shell"
```

---

### Task 5: Manual smoke test across all reskinned pages

**Files:** none (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `python -m pytest tests/ -v`
Expected: all tests pass, including the pre-existing `tests/test_server.py::test_placeholder`

- [ ] **Step 2: Launch the server and check every page by hand**

Run: `python -m pyservx.server --no-qr --port 8099` from the repo root (or `python -c "from pyservx import server; server.run('.', no_qr=True, port=8099)"` if the console script isn't installed), then in a browser visit:
- `http://127.0.0.1:8099/` — confirm the directory listing renders as glass panels, search/sort/upload/new-folder/new-file/clipboard all still work, and the theme toggle switches light/dark.
- Click 👁️ on an image, a PDF, a video, an audio file, and a `.txt` file — confirm each preview page renders glass-styled and Download/Close/Edit buttons work.
- Click ✏️ on a `.txt` file — confirm the editor loads existing content, Ctrl+S and the Save button both work, and glass styling is applied.
- Click "📄 New File" — confirm the filename field appears (only in create mode) and saving creates the file.

- [ ] **Step 3: Stop the test server**

Kill the process started in Step 2 (Ctrl+C in its terminal, or close the background task).
