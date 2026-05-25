"""
Runs once at backend startup.
Scans LAWS_DIR for .docx files and indexes new or changed ones.
Tracks changes via MD5 hash stored in .index_state.json.
"""

import json
import hashlib
from pathlib import Path
import os

LAWS_DIR   = Path(os.getenv("LAWS_DIR", "/app/laws"))
STATE_FILE = LAWS_DIR / ".index_state.json"


def _file_hash(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_state(state: dict):
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def run(rag):
    if not LAWS_DIR.exists():
        print(f"[startup] Laws directory not found: {LAWS_DIR} — skipping auto-index")
        return

    docx_files = sorted(LAWS_DIR.glob("*.docx"))
    if not docx_files:
        print(f"[startup] No .docx files in {LAWS_DIR}")
        return

    state = _load_state()
    indexed, skipped, failed = 0, 0, 0

    for path in docx_files:
        name         = path.name
        current_hash = _file_hash(path)

        if state.get(name) == current_hash and rag.has_source(name, "law"):
            print(f"[startup] SKIP (unchanged): {name}")
            skipped += 1
            continue

        print(f"[startup] Indexing: {name} ...", end=" ", flush=True)
        try:
            # source_type="law" so these documents get toggle-only treatment in UI
            result = rag.ingest_docx(path.read_bytes(), name, source_type="law")
            print(f"{result['chunks_indexed']} chunks")
            state[name] = current_hash
            indexed += 1
        except Exception as e:
            print(f"ERROR: {e}")
            failed += 1

    _save_state(state)
    print(f"[startup] Done — indexed: {indexed}, skipped: {skipped}, failed: {failed}")
