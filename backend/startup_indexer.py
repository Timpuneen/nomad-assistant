"""
Runs once at backend startup.
Scans /app/laws/ for .docx files and indexes any that are
new or have been modified since last index.
"""

import os
import json
import hashlib
from pathlib import Path
from rag import RAGEngine

LAWS_DIR = Path(os.getenv("LAWS_DIR", "/app/laws"))
STATE_FILE = Path(os.getenv("LAWS_DIR", "/app/laws")) / ".index_state.json"


def file_hash(path: Path) -> str:
    """MD5 of file contents — used to detect changes."""
    h = hashlib.md5()
    h.update(path.read_bytes())
    return h.hexdigest()


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            return {}
    return {}


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def run(rag: RAGEngine):
    if not LAWS_DIR.exists():
        print(f"[startup] Laws directory not found: {LAWS_DIR} — skipping auto-index")
        return

    docx_files = sorted(LAWS_DIR.glob("*.docx"))
    if not docx_files:
        print(f"[startup] No .docx files found in {LAWS_DIR}")
        return

    state = load_state()
    indexed, skipped, failed = 0, 0, 0

    for path in docx_files:
        name = path.name
        current_hash = file_hash(path)

        if state.get(name) == current_hash:
            print(f"[startup] SKIP (unchanged): {name}")
            skipped += 1
            continue

        print(f"[startup] Indexing: {name} ...", end=" ", flush=True)
        try:
            result = rag.ingest_docx(path.read_bytes(), name)
            print(f"{result['chunks_indexed']} chunks")
            state[name] = current_hash
            indexed += 1
        except Exception as e:
            print(f"ERROR: {e}")
            failed += 1

    save_state(state)
    print(f"[startup] Done — indexed: {indexed}, skipped: {skipped}, failed: {failed}")
