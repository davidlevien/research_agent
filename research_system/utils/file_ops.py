"""Atomic file operations and run transaction management."""

import os
import tempfile
import json
import shutil
import contextlib
from datetime import datetime
from typing import Any, Dict

def atomic_write_bytes(path: str, data: bytes) -> None:
    """Write bytes atomically using temp file + rename."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or ".", prefix=".tmp.")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)

def atomic_write_text(path: str, text: str, encoding: str = "utf-8") -> None:
    """Write text atomically."""
    atomic_write_bytes(path, text.encode(encoding))

def atomic_write_json(path: str, obj: Dict[str, Any], indent: int = 2) -> None:
    """Write JSON atomically."""
    atomic_write_text(path, json.dumps(obj, indent=indent, ensure_ascii=False))

@contextlib.contextmanager
def run_transaction(run_dir: str):
    """
    Ensures partial outputs are cleaned on crash; creates RUN_STATE.json.
    
    On success: marks run as COMPLETED
    On failure: marks run as ABORTED and removes partial final reports
    """
    os.makedirs(run_dir, exist_ok=True)
    state_path = os.path.join(run_dir, "RUN_STATE.json")
    
    # Mark run as RUNNING
    atomic_write_json(state_path, {
        "status": "RUNNING",
        "started_at": datetime.utcnow().isoformat() + "Z"
    })
    
    try:
        yield
        # Mark run as COMPLETED
        atomic_write_json(state_path, {
            "status": "COMPLETED",
            "finished_at": datetime.utcnow().isoformat() + "Z"
        })
    except Exception as e:
        # Mark run as ABORTED
        atomic_write_json(state_path, {
            "status": "ABORTED",
            "error": repr(e),
            "finished_at": datetime.utcnow().isoformat() + "Z"
        })
        
        # Delete glossy reports if any exist
        for f in ("final_report.md", "final_report.html", "executive_summary.md"):
            p = os.path.join(run_dir, f)
            if os.path.exists(p):
                try:
                    os.remove(p)
                except:
                    pass  # Best effort
        raise