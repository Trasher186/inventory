from __future__ import annotations
import hashlib
import os
import shutil
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

HASH_CHUNK = 2 * 1024 * 1024  # 2MB

def normalize_ext(path: Path) -> str:
    ext = path.suffix.lower()
    return ext if ext else ""

def is_hidden(path: Path) -> bool:
    if path.name.startswith("."):
        return True
    # Windows hidden attrib
    try:
        attrs = os.stat(path).st_file_attributes  # type: ignore[attr-defined]
        return bool(attrs & stat.FILE_ATTRIBUTE_HIDDEN)  # type: ignore[attr-defined]
    except Exception:
        return False

def format_size(n: int) -> str:
    for unit in ["B","KB","MB","GB","TB"]:
        if n < 1024 or unit == "TB":
            return f"{n:.1f}{unit}" if unit != "B" else f"{n}B"
        n /= 1024.0
    return f"{n:.1f}TB"

def hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(HASH_CHUNK)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()

@dataclass
class MoveResult:
    src: str
    dst: str
    action: str  # "move" | "copy" | "skip-duplicate" | "hardlink"

def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)

def next_nonconflicting_name(dst: Path) -> Path:
    if not dst.exists():
        return dst
    stem, suffix = dst.stem, dst.suffix
    parent = dst.parent
    i = 1
    while True:
        candidate = parent / f"{stem}({i}){suffix}"
        if not candidate.exists():
            return candidate
        i += 1

def safe_link_or_copy(src: Path, dst: Path, mode: str) -> str:
    """
    mode: 'move' | 'copy' | 'hardlink'
    """
    dst = next_nonconflicting_name(dst)
    if mode == "hardlink":
        try:
            os.link(src, dst)
            return "hardlink"
        except OSError:
            # Fall back to copy if hardlink not supported
            shutil.copy2(src, dst)
            return "copy"
    elif mode == "copy":
        shutil.copy2(src, dst)
        return "copy"
    else:
        shutil.move(str(src), str(dst))
        return "move"

def file_mtime(path: Path) -> float:
    return path.stat().st_mtime

def within_dir(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except Exception:
        return False
