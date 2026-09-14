#!/usr/bin/env python3
"""Chunked & resumable uploads for PyServeX.

Upload lifecycle:
  1. POST /api/upload/init   {filename, size, chunk_size, dir} -> upload_id + missing chunks
  2. POST /api/upload/chunk?upload_id=X&index=N            (raw body bytes)
     ...repeat / resume: GET /api/upload/status?upload_id=X returns missing indexes
  3. POST /api/upload/complete?upload_id=X                 (stitch chunks into final file)
  4. DELETE /api/upload/abort?upload_id=X                  (cleanup)

Chunks are stored under a temp staging dir keyed by a client-generated
identifier (SHA-256 of filename+size+mtime) so interrupted uploads can be
resumed even after page reloads.
"""

import json
import logging
import os
import re
import shutil
import threading
import time


class ChunkedUploadManager:
    def __init__(self, base_dir, staging_root=None):
        self.base_dir = os.path.abspath(base_dir)
        self.staging_root = staging_root or os.path.join(
            os.path.expanduser("~"), ".pyservx_uploads")
        os.makedirs(self.staging_root, exist_ok=True)
        self.lock = threading.RLock()
        self.sessions = {}  # upload_id -> meta dict
        self._load_existing()
        self._stop = threading.Event()
        self._janitor = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._janitor.start()

    # ------------- persistence -------------
    def _meta_path(self, upload_id):
        safe = re.sub(r"[^A-Za-z0-9_.-]", "_", upload_id)[:128]
        return os.path.join(self.staging_root, safe, "meta.json")

    def _load_existing(self):
        for entry in os.listdir(self.staging_root):
            meta_file = os.path.join(self.staging_root, entry, "meta.json")
            if os.path.isfile(meta_file):
                try:
                    with open(meta_file, "r") as f:
                        self.sessions[entry] = json.load(f)
                except Exception:
                    shutil.rmtree(os.path.join(self.staging_root, entry),
                                  ignore_errors=True)

    def _persist(self, upload_id):
        try:
            with open(self._meta_path(upload_id), "w") as f:
                json.dump(self.sessions[upload_id], f)
        except Exception as e:
            logging.warning("chunk meta persist failed: %s", e)

    # ------------- api -------------
    def init_upload(self, upload_id, filename, size, chunk_size, rel_dir=""):
        with self.lock:
            if upload_id in self.sessions:
                return self.status(upload_id)
            safe_name = os.path.basename(filename).strip() or "upload.bin"
            # idempotent: same file already fully uploaded before
            target = os.path.abspath(os.path.join(
                self.base_dir, (rel_dir or "").strip("/\\"), safe_name))
            base = os.path.abspath(self.base_dir)
            if os.path.isfile(target) and os.path.getsize(target) == int(size) \
                    and target.startswith(base + os.sep):
                return {"upload_id": upload_id, "filename": safe_name,
                        "size": int(size), "chunk_size": max(65536, int(chunk_size)),
                        "total": 1, "missing": [], "complete": True}
            session = {
                "filename": safe_name,
                "size": int(size),
                "chunk_size": max(65536, int(chunk_size)),
                "rel_dir": rel_dir.strip("/\\"),
                "created": time.time(),
                "updated": time.time(),
                "received": [],
            }
            self.sessions[upload_id] = session
            os.makedirs(self.session_dir(upload_id), exist_ok=True)
            self._persist(upload_id)
            return self.status(upload_id)

    def session_dir(self, upload_id):
        safe = re.sub(r"[^A-Za-z0-9_.-]", "_", upload_id)[:128]
        return os.path.join(self.staging_root, safe)

    def receive_chunk(self, upload_id, index, data):
        with self.lock:
            sess = self.sessions.get(upload_id)
            if not sess:
                return {"error": "unknown upload_id"}
            idx = int(index)
            if idx < 0 or (sess["size"] and idx * sess["chunk_size"] >= sess["size"] + sess["chunk_size"]):
                return {"error": "index out of range"}
            path = os.path.join(self.session_dir(upload_id), f"chunk_{idx}")
            tmp = path + ".part"
            with open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, path)
            if idx not in sess["received"]:
                sess["received"].append(idx)
            sess["updated"] = time.time()
            self._persist(upload_id)
            total = self.total_chunks(sess)
            return {"received": len(sess["received"]), "total": total,
                    "complete": len(sess["received"]) >= total}

    @staticmethod
    def total_chunks(sess):
        if not sess.get("size"):
            return 1
        return max(1, -(-int(sess["size"]) // int(sess["chunk_size"])))

    def status(self, upload_id):
        with self.lock:
            sess = self.sessions.get(upload_id)
            if not sess:
                return None
            total = self.total_chunks(sess)
            missing = [i for i in range(total) if i not in set(sess["received"])]
            return {"upload_id": upload_id, "filename": sess["filename"],
                    "size": sess["size"], "chunk_size": sess["chunk_size"],
                    "total": total, "missing": missing,
                    "complete": not missing}

    def target_path(self, upload_id):
        """Absolute final path the assembled file will land at (may not exist)."""
        with self.lock:
            sess = self.sessions.get(upload_id)
        if not sess:
            return None
        return os.path.abspath(os.path.join(
            self.base_dir, sess.get("rel_dir", ""), sess["filename"]))

    def complete_upload(self, upload_id):
        with self.lock:
            sess = self.sessions.get(upload_id)
        if not sess:
            return {"error": "unknown upload_id"}
        stat = self.status(upload_id)
        if not stat or not stat["complete"]:
            return {"error": "chunks missing",
                    "missing": (stat or {}).get("missing", [])}
        target_dir = os.path.abspath(os.path.join(
            self.base_dir, sess["rel_dir"]))
        if os.path.commonpath([target_dir]) != os.path.commonpath([target_dir, self.base_dir]):
            return {"error": "path traversal blocked"}
        os.makedirs(target_dir, exist_ok=True)
        final_path = os.path.join(target_dir, sess["filename"])
        sdir = self.session_dir(upload_id)
        tmp_final = final_path + ".pyservx-part"
        with open(tmp_final, "wb") as out:
            for i in range(self.total_chunks(sess)):
                with open(os.path.join(sdir, f"chunk_{i}"), "rb") as cf:
                    shutil.copyfileobj(cf, out, 1024 * 1024)
        os.replace(tmp_final, final_path)
        with self.lock:
            self.sessions.pop(upload_id, None)
        shutil.rmtree(sdir, ignore_errors=True)
        logging.info("Chunked upload complete: %s (%s bytes)",
                     final_path, sess["size"])
        return {"status": "success", "path": os.path.relpath(final_path, self.base_dir)}

    def abort_upload(self, upload_id):
        with self.lock:
            existed = self.sessions.pop(upload_id, None) is not None
        shutil.rmtree(self.session_dir(upload_id), ignore_errors=True)
        return {"aborted": existed}

    # ------------- janitor -------------
    def _cleanup_loop(self):
        while not self._stop.wait(300):
            cutoff = time.time() - 24 * 3600
            with self.lock:
                stale = [uid for uid, s in self.sessions.items()
                         if s["updated"] < cutoff]
                for uid in stale:
                    self.sessions.pop(uid, None)
            for uid in stale:
                shutil.rmtree(self.session_dir(uid), ignore_errors=True)

    def shutdown(self):
        self._stop.set()
