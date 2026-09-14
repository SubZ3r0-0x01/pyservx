#!/usr/bin/env python3

import os
import re
import threading
import time

TOKEN_RE = re.compile(r"[a-z0-9]+")

TEXT_EXTS = {
    ".txt", ".md", ".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".htm",
    ".css", ".json", ".xml", ".yml", ".yaml", ".csv", ".log", ".ini",
    ".cfg", ".conf", ".toml", ".rst", ".tex", ".sh", ".bat", ".ps1",
    ".sql", ".c", ".cpp", ".h", ".hpp", ".java", ".go", ".rs", ".rb",
    ".php", ".lua", ".swift", ".kt", ".pl", ".r", ".jl", ".scala",
}

_SKIP_DIRS = {".thumbnails", ".psx_events", ".git", "__pycache__", ".psx_versions"}


def _tokenize(text):
    return TOKEN_RE.findall(text.lower())


def _is_text_file(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in TEXT_EXTS:
        return True
    try:
        with open(path, "rb") as fh:
            head = fh.read(4096)
        return b"\x00" not in head and b"\xff" not in head
    except OSError:
        return False


class SearchIndex:
    """Incremental full-share search index (filenames always, contents for
    text files). A background thread rescans signatures (mtime, size) so the
    index stays fresh with the shared tree without re-reading unchanged files.

    All public methods are thread-safe."""

    def __init__(self, base_dir, max_content_size=512 * 1024,
                 scan_interval=10.0, max_preview=1024):
        self.base_dir = os.path.abspath(base_dir)
        self.max_content_size = max_content_size
        self.scan_interval = scan_interval
        self.max_preview = max_preview

        self._lock = threading.RLock()
        self._files = {}                 # relpath -> signature tuple
        self._previews = {}              # relpath -> str preview
        self._name_terms = {}            # token -> set(relpath)
        self._content_terms = {}         # token -> set(relpath)
        self._indexed_files = 0
        self._ready = False
        self._last_indexed_at = None
        self._stop = threading.Event()
        self._thread = None

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------
    def start(self):
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(target=self._run,
                                            name="pyservx-search",
                                            daemon=True)
            self._thread.start()

    def stop(self):
        self._stop.set()
        with self._lock:
            t = self._thread
        if t and t is not threading.current_thread():
            t.join(timeout=3)

    def _run(self):
        while not self._stop.is_set():
            try:
                self._scan_once()
            except Exception:
                pass
            self._stop.wait(self.scan_interval)

    # ------------------------------------------------------------------
    # indexing
    # ------------------------------------------------------------------
    def _scan_once(self):
        seen, new_sigs = self._walk()
        with self._lock:
            removed = [p for p in self._files if p not in seen]
            originals = dict(self._files)

        for p in removed:
            self._drop(p)

        for rel in sorted(seen):
            sig = new_sigs[rel]
            if originals.get(rel) == sig:
                continue
            self._add(rel, seen[rel])

        with self._lock:
            self._indexed_files = len(self._files)
            self._ready = True
            self._last_indexed_at = time.time()

    def _walk(self):
        seen = {}
        sigs = {}
        base = self.base_dir
        for root, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
            for name in files:
                abs_path = os.path.join(root, name)
                rel = os.path.relpath(abs_path, base)
                try:
                    st = os.stat(abs_path)
                except OSError:
                    continue
                sig = (st.st_mtime_ns, st.st_size)
                seen[rel] = abs_path
                sigs[rel] = sig
        return seen, sigs

    def _read_truncated(self, abs_path):
        try:
            with open(abs_path, "rb") as fh:
                raw = fh.read(self.max_content_size)
            return raw.decode("utf-8", errors="replace")
        except OSError:
            return ""

    def _add(self, rel, abs_path):
        tokens_name = _tokenize(os.path.basename(rel))
        tokens_content = []
        preview = ""
        try:
            if os.path.getsize(abs_path) <= self.max_content_size and \
                    _is_text_file(abs_path):
                preview = self._read_truncated(abs_path)
                tokens_content = _tokenize(preview)
        except OSError:
            tokens_content = []
        if len(preview) > self.max_preview:
            preview = preview[:self.max_preview]

        with self._lock:
            old = self._files.get(rel)
            if old:
                self._drop(rel)
            self._files[rel] = self._current_sig(rel)
            if preview:
                self._previews[rel] = preview
            for tk in set(tokens_name):
                self._name_terms.setdefault(tk, set()).add(rel)
            for tk in set(tokens_content):
                self._content_terms.setdefault(tk, set()).add(rel)

    def _current_sig(self, rel):
        # recompute signature under lock (cheap) so _files stays consistent
        abs_path = os.path.join(self.base_dir, rel)
        try:
            st = os.stat(abs_path)
            return (st.st_mtime_ns, st.st_size)
        except OSError:
            return None

    def _drop(self, rel):
        with self._lock:
            self._files.pop(rel, None)
            self._previews.pop(rel, None)
            for tk, s in self._name_terms.items():
                s.discard(rel)
            for tk, s in self._content_terms.items():
                s.discard(rel)
        # collapse empty term sets
        for table in (self._name_terms, self._content_terms):
            for tk in [t for t, s in table.items() if not s]:
                table.pop(tk, None)

    # ------------------------------------------------------------------
    # search
    # ------------------------------------------------------------------
    def search(self, query, limit=50):
        query = (query or "").strip().lower()
        if not query:
            return []
        tokens = _tokenize(query)
        if not tokens:
            return []

        with self._lock:
            name_sets = [self._name_terms.get(t, set()) for t in tokens]
            content_sets = [self._content_terms.get(t, set()) for t in tokens]
            previews = dict(self._previews)

        profiles = {}
        rels = set()
        for tk, s in zip(tokens, name_sets):
            rels |= s
        for tk, s in zip(tokens, content_sets):
            rels |= s

        for rel in rels:
            score = 0.0
            name = os.path.basename(rel).lower()
            for tk in tokens:
                if tk in self._terms_lookup(tokens, name_sets, rel):
                    score += 4
                if name.startswith(tk):
                    score += 2
                if name == tk:
                    score += 2
            for tk in tokens:
                if tk in self._terms_lookup(tokens, content_sets, rel):
                    score += 1
            profiles[rel] = score

        ranked = sorted(profiles.items(), key=lambda kv: -kv[1])
        results = []
        for rel, score in ranked[:limit]:
            snippet, hit = self._snippet(rel, tokens, previews.get(rel, ""))
            results.append({
                "path": "/" + rel.replace(os.sep, "/"),
                "name": os.path.basename(rel),
                "score": round(score, 1),
                "snippet": snippet,
                "hit": hit,
            })
        return results

    @staticmethod
    def _terms_lookup(tokens, sets, rel):
        found = set()
        for tk, s in zip(tokens, sets):
            if rel in s:
                found.add(tk)
        return found

    def _snippet(self, rel, tokens, preview):
        for tk in tokens:
            idx = preview.lower().find(tk)
            if idx >= 0:
                start = max(0, idx - 60)
                end = min(len(preview), idx + 120)
                return ("…" if start else "") + preview[start:end] + "…", tk
        return "", ""

    @property
    def ready(self):
        with self._lock:
            return self._ready

    @property
    def indexed_files(self):
        with self._lock:
            return len(self._files)

    def status(self):
        with self._lock:
            return {
                "ready": self._ready,
                "files": self._indexed_files,
                "content_tokens": len(self._content_terms),
                "indexed_at": self._last_indexed_at,
            }

    def force_reindex(self):
        with self._lock:
            self._files.clear()
            self._previews.clear()
            self._name_terms.clear()
            self._content_terms.clear()
            self._ready = False
        self._scan_once()