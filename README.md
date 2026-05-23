# 🚀 GitHub Large File Splitter & Pusher

Automatically splits files >95MB into chunks, tracks them in a manifest, pushes to GitHub, and reassembles them later.

---

## 📁 Files

| File | Purpose |
|---|---|
| `push_to_github.py` | Scan, split large files, push to GitHub |
| `reassemble.py` | Restore split files back to originals |
| `.file_manifest.json` | Auto-generated tracker (commit this!) |

---

## ⚡ Quick Start

### Step 1 — Push to GitHub
```bash
python3 push_to_github.py
```

**What it does:**
- Scans your folder for files >95MB
- Splits them into `.part001`, `.part002`... chunks
- Saves a manifest with MD5 hash for verification
- Checks repo size (warns if near 5GB)
- Runs `git add` → `git commit` → `git push`

---

### Step 2 — Reassemble after cloning
```bash
# Clone your repo
git clone https://github.com/yourname/yourrepo.git
cd yourrepo

# Restore all split files
python3 reassemble.py
```

**What it does:**
- Reads `.file_manifest.json`
- Joins all chunks back into original files
- Verifies MD5 hash (data integrity check)
- Deletes chunks after successful restore

---

## 📊 Example Output

### push_to_github.py
```
██████████████████████████████████████████████████
  🚀 GITHUB LARGE FILE SPLITTER & PUSHER
██████████████████████████████████████████████████

══════════════════════════════════════════════════
  🔍 SCANNING FOR LARGE FILES
══════════════════════════════════════════════════
  Found 2 file(s) to split:

    • course.zip  (380.0 MB)
    • assets.zip  (210.0 MB)

  ✂️  Splitting: course.zip
      Size   : 380.0 MB
      Chunks : 4
      MD5    : a1b2c3d4e5f6...

  [████████████████████████████████████████] 100%  chunk 4/4
  ✅ Original removed. Chunks ready.

  📋 Manifest saved → .file_manifest.json

══════════════════════════════════════════════════
  📦 PUSHING TO GITHUB
══════════════════════════════════════════════════

  Repo size : 0.58 GB
  ✅ Size OK. Proceeding...

  → git add .
  → git commit -m "auto: split & push [2026-05-23 10:30:00]"
  → git push -u origin main

  ✅ Successfully pushed to GitHub!

══════════════════════════════════════════════════
  🎉 Done in 42.3s
══════════════════════════════════════════════════
```

---

## ⚠️ Limits

| Limit | Value |
|---|---|
| Max file chunk size | 95MB (safe under GitHub's 100MB) |
| Max repo size | 4.5GB warning, 5GB hard stop |
| Manifest file | Must be committed alongside chunks |

---

## 🔧 Configuration

Edit these at the top of `push_to_github.py`:

```python
CHUNK_SIZE = 95 * 1024 * 1024   # Change chunk size (default 95MB)
MAX_REPO_SIZE_GB = 4.5           # Warning threshold
REPO_PATH = "."                  # Root of your repo
```

---

## ❓ FAQ

**Q: What if my push fails halfway?**  
Re-run `push_to_github.py` — it skips already-split files.

**Q: Can I reassemble on Windows?**  
Yes — `reassemble.py` is pure Python, works on any OS.

**Q: What if a chunk is corrupted?**  
MD5 verification will catch it and abort — original won't be created.

**Q: Should I commit `.file_manifest.json`?**  
Yes! It's how `reassemble.py` knows what to restore.
