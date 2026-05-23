#!/usr/bin/env python3
"""
GitHub Large File Reassembler
Reads the manifest and restores all split files back to originals.
"""

import os
import json
import hashlib
import sys
import time

MANIFEST_FILE = ".file_manifest.json"


# ─────────────────────────────────────────────
# Progress Bar
# ─────────────────────────────────────────────

def progress_bar(current, total, label="", bar_width=40):
    percent = current / total if total else 1
    filled = int(bar_width * percent)
    bar = "█" * filled + "░" * (bar_width - filled)
    sys.stdout.write(f"\r  [{bar}] {percent*100:.1f}%  {label}")
    sys.stdout.flush()
    if current >= total:
        print()


# ─────────────────────────────────────────────
# MD5 Verify
# ─────────────────────────────────────────────

def md5_hash(filepath, chunk_bytes=8192):
    h = hashlib.md5()
    with open(filepath, "rb") as f:
        while True:
            data = f.read(chunk_bytes)
            if not data:
                break
            h.update(data)
    return h.hexdigest()


# ─────────────────────────────────────────────
# Reassemble One File
# ─────────────────────────────────────────────

def reassemble(entry):
    original = entry["original_file"]
    chunks = entry["chunks"]
    expected_hash = entry["md5"]
    expected_size = entry["original_size_bytes"]
    total_chunks = entry["total_chunks"]

    print(f"\n  🔧 Reassembling: {original}")
    print(f"      Chunks : {total_chunks}")
    print(f"      Size   : {expected_size / (1024**2):.1f} MB expected")

    # Check all chunks exist
    missing = [c for c in chunks if not os.path.exists(c)]
    if missing:
        print(f"  ❌ Missing chunks:")
        for m in missing:
            print(f"     • {m}")
        return False

    # Reassemble
    os.makedirs(os.path.dirname(original) if os.path.dirname(original) else ".", exist_ok=True)

    bytes_done = 0
    with open(original, "wb") as out:
        for i, chunk_path in enumerate(chunks):
            with open(chunk_path, "rb") as cf:
                data = cf.read()
                out.write(data)
                bytes_done += len(data)
            progress_bar(bytes_done, expected_size, label=f"chunk {i+1}/{total_chunks} ")

    # Verify size
    actual_size = os.path.getsize(original)
    if actual_size != expected_size:
        print(f"  ⚠️  Size mismatch! Expected {expected_size}, got {actual_size}")
        return False

    # Verify MD5
    print(f"  🔎 Verifying MD5...")
    actual_hash = md5_hash(original)
    if actual_hash != expected_hash:
        print(f"  ❌ MD5 mismatch!")
        print(f"     Expected : {expected_hash}")
        print(f"     Got      : {actual_hash}")
        os.remove(original)
        return False

    print(f"  ✅ MD5 verified: {actual_hash}")

    # Delete chunks
    print(f"  🗑️  Removing {total_chunks} chunk(s)...")
    for chunk_path in chunks:
        os.remove(chunk_path)

    print(f"  ✅ Restored: {original}\n")
    return True


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

def main():
    print("\n" + "█"*50)
    print("  📥 GITHUB FILE REASSEMBLER")
    print("█"*50)

    if not os.path.exists(MANIFEST_FILE):
        print(f"\n  ❌ No manifest found ({MANIFEST_FILE})")
        print("     Make sure you're in the repo root.\n")
        sys.exit(1)

    with open(MANIFEST_FILE, "r") as f:
        manifest = json.load(f)

    if not manifest:
        print("\n  ℹ️  Manifest is empty — nothing to reassemble.\n")
        sys.exit(0)

    print(f"\n  Found {len(manifest)} file(s) to reassemble:\n")
    for key in manifest:
        size_mb = manifest[key]["original_size_bytes"] / (1024**2)
        chunks = manifest[key]["total_chunks"]
        print(f"    • {key}  ({size_mb:.1f} MB, {chunks} chunks)")

    print()
    start = time.time()
    success = 0
    failed = 0

    for key, entry in manifest.items():
        # Skip if original already exists
        if os.path.exists(entry["original_file"]):
            print(f"  ⏭️  Skipping {key} — already exists.")
            continue
        if reassemble(entry):
            success += 1
        else:
            failed += 1

    elapsed = time.time() - start
    print("═"*50)
    print(f"  ✅ Reassembled : {success}")
    print(f"  ❌ Failed      : {failed}")
    print(f"  ⏱️  Time        : {elapsed:.1f}s")
    print("═"*50 + "\n")


if __name__ == "__main__":
    main()
