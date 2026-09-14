#!/usr/bin/env python3

import json
import os
import shutil
import threading
import time

DEFAULT_TRASH_TTL_SECONDS = 30 * 24 * 3600   # 30 days
MAX_VERSIONS = 3

_MANIFEST = "manifest.json"


def _now_str():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _ts():
    return str(int(time.time() * 1000))


class TrashManager:
    """Move/restore/empty for the shared tree (files and folders), plus
    version snapshots taken before destructive overwrites.

    Trash lives outside the served tree (~/.pyservx_trash) so staged data is
    never browsable via HTTP while pending restore. A background loop purges
    entries older than the TTL."""

    def __init__(self, base_dir, data_dir=None, ttl_seconds=DEFAULT_TRASH_TTL_SECONDS,
                 max_versions=MAX_VERSIONS, versions_root=None):
        self.base_dir = os.path.abspath(base_dir)
        self.data_dir = os.path.abspath(data_dir or os.path.expanduser("~/.pyservx_trash"))
        self.versions_root = os.path.abspath(
            versions_root or os.path.expanduser("~/.pyservx_versions"))
        self.trash_root = self.data_dir
        self.ttl_seconds = ttl_seconds
        self.max_versions = max_versions
        self._manifest_path = os.path.join(self.trash_root, _MANIFEST)
        self._lock = threading.RLock()
        os.makedirs(self.trash_root, exist_ok=True)
        os.makedirs(self.versions_root, exist_ok=True)
        self._entries = self._load()

    # ------------------------------------------------------------------
    # manifest
    # ------------------------------------------------------------------
    def _load(self):
        try:
            with open(self._manifest_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                return data
        except (OSError, ValueError):
            pass
        return {}

    def _save(self):
        tmp = self._manifest_path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self._entries, fh, indent=1)
            os.replace(tmp, self._manifest_path)
        except OSError:
            pass

    def _resolve(self, rel):
        """Normalise + jail user-supplied path into the shared tree."""
        rel = rel.strip().replace("\\", "/").lstrip("/")
        abs_path = os.path.abspath(os.path.join(self.base_dir, rel))
        if abs_path != self.base_dir and \
                not abs_path.startswith(self.base_dir + os.sep):
            raise ValueError("path outside shared tree")
        return abs_path, rel

    # ------------------------------------------------------------------
    # trash ops
    # ------------------------------------------------------------------
    def move(self, rel_path):
        """Move a file/folder into the trash. Returns the trash entry."""
        with self._lock:
            abs_path, rel = self._resolve(rel_path)
            if not os.path.exists(abs_path) or abs_path == self.base_dir:
                raise FileNotFoundError(rel_path)
            trash_id = f"{int(time.time() * 1000)}-{os.path.basename(abs_path)}"
            staged = os.path.join(self.trash_root, trash_id)
            os.makedirs(staged, exist_ok=True)
            src_name = os.path.basename(abs_path)
            dst = os.path.join(staged, src_name)
            size = 0
            if os.path.isfile(abs_path):
                size = os.path.getsize(abs_path)
            try:
                shutil.move(abs_path, dst)
            except Exception:
                shutil.rmtree(staged, ignore_errors=True)
                raise
            entry = {
                "trash_id": trash_id,
                "rel": rel,
                "name": src_name,
                "size": size,
                "trashed_at": _now_str(),
            }
            self._entries[trash_id] = entry
            self._save()
            return entry

    def restore(self, rel_path):
        """Move the most recently trashed entry for this path back to its
        original location. Returns the restored relative path."""
        with self._lock:
            abs_path, rel = self._resolve(rel_path)
            matches = [e for e in self._entries.values() if e["rel"] == rel]
            if not matches:
                raise FileNotFoundError(rel_path)
            entry = sorted(matches, key=lambda e: e["trashed_at"])[-1]
            staged = os.path.join(self.trash_root, entry["trash_id"])
            src = os.path.join(staged, entry["name"])
            if not os.path.exists(src):
                raise FileNotFoundError(src)
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            dst = abs_path
            if os.path.exists(dst):
                dst = abs_path + f".restored-{os.path.basename(entry['trash_id'])}"
            shutil.move(src, dst)
            self._entries.pop(entry["trash_id"], None)
            self._save()
            leftover = os.path.join(self.trash_root, entry["trash_id"])
            if os.path.isdir(leftover) and not os.listdir(leftover):
                shutil.rmtree(leftover, ignore_errors=True)
            return os.path.relpath(dst, self.base_dir)

    def list(self):
        with self._lock:
            out = []
            for e in self._entries.values():
                staged = os.path.join(self.trash_root, e["trash_id"])
                exists = os.path.exists(os.path.join(staged, e["name"]))
                out.append({
                    "path": "/" + e["rel"].replace(os.sep, "/"),
                    "name": e["name"],
                    "size": e["size"],
                    "trashed_at": e["trashed_at"],
                    "restorable": exists,
                })
            return sorted(out, key=lambda x: x["trashed_at"], reverse=True)

    def empty(self):
        with self._lock:
            for tid in list(self._entries):
                shutil.rmtree(os.path.join(self.trash_root, tid), ignore_errors=True)
            self._entries.clear()
            self._save()

    def purge_loop(self, stop_event, interval=3600, ttl_seconds=None):
        ttl = ttl_seconds if ttl_seconds is not None else self.ttl_seconds
        while not stop_event.is_set():
            try:
                self._purge_expired(ttl)
            except Exception:
                pass
            stop_event.wait(interval)

    def shutdown(self):
        with self._lock:
            self._save()

    def _purge_expired(self, ttl):
        with self._lock:
            now = time.time()
            for tid, e in list(self._entries.items()):
                try:
                    t = time.mktime(time.strptime(e["trashed_at"], "%Y-%m-%dT%H:%M:%S"))
                except (ValueError, TypeError):
                    t = now
                if now - t > ttl:
                    shutil.rmtree(os.path.join(self.trash_root, tid),
                                  ignore_errors=True)
                    self._entries.pop(tid, None)
            self._save()

    # ------------------------------------------------------------------
    # version snapshots
    # ------------------------------------------------------------------
    def save_version(self, rel_path, max_copies=None):
        """Snapshot a file before overwrite. Returns version id or None."""
        with self._lock:
            abs_path, rel = self._resolve(rel_path)
            if not os.path.isfile(abs_path):
                return None
            max_copies = max_copies or self.max_versions
            vid = _ts()
            ver_dir = os.path.join(self.versions_root, rel)
            os.makedirs(ver_dir, exist_ok=True)
            dst = os.path.join(ver_dir, vid)
            shutil.copy2(abs_path, dst)
            backups = sorted(os.listdir(ver_dir), reverse=True)
            for old in backups[max_copies:]:
                try:
                    os.remove(os.path.join(ver_dir, old))
                except OSError:
                    pass
            return {"version": vid, "size": os.path.getsize(dst),
                    "at": _now_str()}

    def list_versions(self, rel_path):
        with self._lock:
            _, rel = self._resolve(rel_path)
            ver_dir = os.path.join(self.versions_root, rel)
            if not os.path.isdir(ver_dir):
                return []
            out = []
            for v in sorted(os.listdir(ver_dir), reverse=True):
                fp = os.path.join(ver_dir, v)
                try:
                    out.append({"version": v, "size": os.path.getsize(fp),
                                "at": time.strftime(
                                    "%Y-%m-%dT%H:%M:%S",
                                    time.localtime(os.path.getmtime(fp)))})
                except OSError:
                    continue
            return out

    def restore_version(self, rel_path, version):
        """Overwrite the live file with a stored snapshot."""
        with self._lock:
            abs_path, rel = self._resolve(rel_path)
            ver_dir = os.path.join(self.versions_root, rel)
            src = os.path.join(ver_dir, str(version))
            if not os.path.isfile(src):
                raise FileNotFoundError(version)
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            shutil.copy2(src, abs_path)
            return os.path.relpath(abs_path, self.base_dir)