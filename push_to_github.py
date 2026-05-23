#!/usr/bin/env python3
"""
GitHub Large File Splitter & Pusher
- Splits files >95MB into chunks
- Pushes in small batches (500MB each) to avoid HTTP 500
- Tracks everything in a manifest
- Skips node_modules, .next, build folders
"""

import os
import math
import json
import hashlib
import subprocess
import sys
import time
from datetime import datetime

CHUNK_SIZE      = 95  * 1024 * 1024   # 95MB per chunk
BATCH_SIZE_GB   = 0.5                  # push 500MB at a time
MANIFEST_FILE   = ".file_manifest.json"
MAX_REPO_GB     = 4.5
REPO_PATH       = "."

SKIP_DIRS = {
    ".git", "__pycache__", "node_modules",
    ".next", "out", "build", "dist", ".cache"
}

SKIP_FILES = {".DS_Store", "Thumbs.db"}


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def progress_bar(current, total, label="", bar_width=40):
    percent = current / total if total else 1
    filled  = int(bar_width * percent)
    bar     = "█" * filled + "░" * (bar_width - filled)
    sys.stdout.write(f"\r  [{bar}] {percent*100:.1f}%  {label}")
    sys.stdout.flush()
    if current >= total:
        print()

def run(cmd, silent=False):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if not silent and result.returncode != 0:
        print(f"\n  ❌ Command failed: {' '.join(cmd)}")
        print(f"     {result.stderr.strip()}")
    return result

def md5_hash(filepath):
    h = hashlib.md5()
    with open(filepath, "rb") as f:
        while True:
            data = f.read(8192)
            if not data:
                break
            h.update(data)
    return h.hexdigest()

def file_size_gb(filepath):
    return os.path.getsize(filepath) / (1024 ** 3)


# ─────────────────────────────────────────────
# Manifest
# ─────────────────────────────────────────────

def load_manifest():
    if os.path.exists(MANIFEST_FILE):
        with open(MANIFEST_FILE, "r") as f:
            return json.load(f)
    return {}

def save_manifest(manifest):
    with open(MANIFEST_FILE, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"  📋 Manifest saved → {MANIFEST_FILE}")


# ─────────────────────────────────────────────
# Scan all files (respecting skip list)
# ─────────────────────────────────────────────

def scan_all_files():
    """Return list of (filepath, size_bytes) for all trackable files."""
    results = []
    for dirpath, dirnames, filenames in os.walk(REPO_PATH):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for filename in filenames:
            if filename in SKIP_FILES:
                continue
            if filename == MANIFEST_FILE:
                continue
            filepath = os.path.join(dirpath, filename)
            try:
                size = os.path.getsize(filepath)
                results.append((filepath, size))
            except OSError:
                pass
    return results


# ─────────────────────────────────────────────
# Split large files
# ─────────────────────────────────────────────

def split_file(filepath, manifest):
    file_size = os.path.getsize(filepath)
    num_chunks = math.ceil(file_size / CHUNK_SIZE)
    file_hash  = md5_hash(filepath)
    rel_path   = os.path.relpath(filepath, REPO_PATH)

    print(f"\n  ✂️  Splitting : {rel_path}")
    print(f"      Size    : {file_size / (1024**2):.1f} MB  →  {num_chunks} chunks")
    print(f"      MD5     : {file_hash}")

    chunk_names = []
    bytes_done  = 0

    with open(filepath, "rb") as f:
        for i in range(num_chunks):
            data       = f.read(CHUNK_SIZE)
            chunk_path = f"{filepath}.part{i+1:03d}"
            rel_chunk  = os.path.relpath(chunk_path, REPO_PATH)
            with open(chunk_path, "wb") as cf:
                cf.write(data)
            chunk_names.append(rel_chunk)
            bytes_done += len(data)
            progress_bar(bytes_done, file_size, label=f"chunk {i+1}/{num_chunks} ")

    manifest[rel_path] = {
        "original_file"      : rel_path,
        "original_size_bytes": file_size,
        "md5"                : file_hash,
        "chunks"             : chunk_names,
        "total_chunks"       : num_chunks,
        "split_date"         : datetime.now().isoformat()
    }

    os.remove(filepath)
    print(f"  ✅ Split complete.\n")

def scan_and_split():
    print("\n" + "═"*52)
    print("  🔍  SCANNING FOR LARGE FILES (>95MB)")
    print("═"*52)

    manifest = load_manifest()
    all_files = scan_all_files()
    large     = [(fp, sz) for fp, sz in all_files if sz > CHUNK_SIZE and ".part" not in fp]

    if not large:
        print("  ✅ No files exceed 95MB. Nothing to split.\n")
    else:
        print(f"  Found {len(large)} file(s) to split:\n")
        for fp, sz in large:
            print(f"    • {fp}  ({sz/(1024**2):.1f} MB)")
        print()
        for fp, _ in large:
            split_file(fp, manifest)

    save_manifest(manifest)
    return manifest


# ─────────────────────────────────────────────
# Batch push
# ─────────────────────────────────────────────

def get_unstaged_files():
    """Return list of (status, filepath) that are new/modified."""
    result = run(["git", "status", "--short", "--porcelain"], silent=True)
    files = []
    for line in result.stdout.splitlines():
        status   = line[:2].strip()
        filepath = line[3:].strip().strip('"')
        if status in ("?", "??", "M", "A", "MM", "AM"):
            files.append(filepath)
        elif status:
            files.append(filepath)
    return files

def batch_and_push():
    print("\n" + "═"*52)
    print("  📦  BATCH PUSH TO GITHUB")
    print("═"*52)

    # Increase buffer to handle large pushes
    run(["git", "config", "http.postBuffer", "524288000"], silent=True)
    run(["git", "config", "http.lowSpeedLimit", "0"],      silent=True)
    run(["git", "config", "http.lowSpeedTime",  "999999"], silent=True)

    # Total repo size check
    all_files   = scan_all_files()
    total_gb    = sum(sz for _, sz in all_files) / (1024**3)
    print(f"\n  Total size : {total_gb:.2f} GB")

    if total_gb >= 5.0:
        print(f"  ❌ Repo exceeds 5GB GitHub limit. Remove large files first.\n")
        return False
    if total_gb >= MAX_REPO_GB:
        print(f"  ⚠️  Approaching 5GB limit — pushing carefully in small batches.")

    # Stage everything first to detect changes
    run(["git", "add", "-N", "."], silent=True)   # mark untracked, don't stage content yet
    unstaged = get_unstaged_files()

    if not unstaged:
        print("  ℹ️  Nothing to commit — already up to date.\n")
        return True

    print(f"  Files to push : {len(unstaged)}")
    print(f"  Batch size    : {BATCH_SIZE_GB*1024:.0f} MB per push\n")

    # Group files into batches by size
    batches        = []
    current_batch  = []
    current_size   = 0.0

    for filepath in unstaged:
        abs_path = os.path.join(REPO_PATH, filepath)
        try:
            size_gb = os.path.getsize(abs_path) / (1024**3) if os.path.exists(abs_path) else 0
        except OSError:
            size_gb = 0

        if current_batch and (current_size + size_gb) > BATCH_SIZE_GB:
            batches.append(current_batch)
            current_batch = []
            current_size  = 0.0

        current_batch.append(filepath)
        current_size += size_gb

    if current_batch:
        batches.append(current_batch)

    print(f"  Split into {len(batches)} batch(es)\n")

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for i, batch in enumerate(batches, 1):
        batch_size_mb = sum(
            os.path.getsize(os.path.join(REPO_PATH, f)) / (1024**2)
            for f in batch if os.path.exists(os.path.join(REPO_PATH, f))
        )
        print(f"  ── Batch {i}/{len(batches)}  ({len(batch)} files, {batch_size_mb:.1f} MB) ──")

        # Stage only this batch
        for filepath in batch:
            r = run(["git", "add", filepath], silent=True)
            if r.returncode != 0:
                run(["git", "add", "--", filepath], silent=True)

        # Commit
        commit_msg = f"batch {i}/{len(batches)} [{timestamp}]"
        result = run(["git", "commit", "-m", commit_msg])
        if result.returncode != 0:
            if "nothing to commit" in result.stdout + result.stderr:
                print(f"  ⏭️  Nothing to commit in batch {i}, skipping.\n")
                continue
            print(f"  ❌ Commit failed for batch {i}\n")
            return False

        # Push with retry
        pushed = False
        for attempt in range(1, 4):
            print(f"  → Pushing batch {i} (attempt {attempt}/3)...")
            result = run(["git", "push", "-u", "origin", "main"])
            if result.returncode == 0:
                print(f"  ✅ Batch {i} pushed!\n")
                pushed = True
                break
            else:
                if attempt < 3:
                    print(f"  ⚠️  Failed, retrying in 5s...")
                    time.sleep(5)

        if not pushed:
            print(f"  ❌ Batch {i} failed after 3 attempts.")
            print(f"     Run script again to resume from here.\n")
            return False

    return True


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

def main():
    print("\n" + "█"*52)
    print("  🚀  GITHUB LARGE FILE SPLITTER & PUSHER")
    print("█"*52)

    start = time.time()

    scan_and_split()
    success = batch_and_push()

    elapsed = time.time() - start
    print("═"*52)
    if success:
        print(f"  🎉 Done in {elapsed:.1f}s")
    else:
        print(f"  💥 Finished with errors in {elapsed:.1f}s")
        print(f"     Just run the script again to resume!")
    print("═"*52 + "\n")


if __name__ == "__main__":
    main()
