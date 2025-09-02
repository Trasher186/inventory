from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from .rules import Rules
from .utils import (
    MoveResult,
    ensure_dir,
    file_mtime,
    format_size,
    hash_file,
    is_hidden,
    next_nonconflicting_name,
    safe_link_or_copy,
    within_dir,
)

Manifest = Dict[str, List[MoveResult]]  # key 'operations' -> list

def _walk_files(root: Path, exclude_dirs: List[str], exclude_hidden: bool) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        pdir = Path(dirpath)
        # edit dirnames in-place to prune walk
        dirnames[:] = [
            d for d in dirnames
            if d not in exclude_dirs and not (exclude_hidden and d.startswith("."))
        ]
        for name in filenames:
            p = pdir / name
            if exclude_hidden and name.startswith("."):
                continue
            yield p

def compute_destination(path: Path, dest_root: Path, rules: Rules) -> Path:
    # First pass: extension/glob/mime
    folder = rules.match_folder_for(path)
    if not folder:
        folder = rules.unknown_folder

    parts = [folder]

    # Date rule (enabled)
    if rules.by_date.enabled:
        parts = [rules.by_date.base_folder] + rules.date_parts(file_mtime(path)) + parts

    # Size bucket (optional; appended at the end)
    size_bucket = rules.match_size_bucket(path.stat().st_size)
    if size_bucket:
        parts = [size_bucket] + parts

    target_dir = dest_root.joinpath(*parts)
    return target_dir / path.name

def organize(
    src_root: Path,
    dest_root: Path,
    rules: Rules,
    mode: str = "move",  # move|copy|hardlink
    dry_run: bool = False,
    undo_manifest: Optional[Path] = None,
    log_fn=print,
) -> List[MoveResult]:
    """
    Returns list of MoveResult performed (or planned if dry_run).
    """
    if not src_root.exists():
        raise FileNotFoundError(f"Source folder not found: {src_root}")
    if within_dir(dest_root, src_root):
        raise RuntimeError("Destination directory cannot be inside the source directory.")
    if src_root.resolve() == dest_root.resolve():
        raise RuntimeError("Destination must differ from source.")

    results: List[MoveResult] = []
    seen_hashes: Dict[str, Path] = {}

    # Build duplicate map only within this run (fast); for persistent DB, persist seen_hashes.
    for f in _walk_files(src_root, rules.exclude_dirs, rules.exclude_hidden):
        if f.is_dir():
            continue
        # compute destination
        dst = compute_destination(f, dest_root, rules)

        # duplicates?
        file_hash = hash_file(f)
        if file_hash in seen_hashes:
            # This file content already seen in this session
            if rules.duplicates.action == "skip":
                log_fn(f"⏭️  Duplicate (skip): {f} (same as {seen_hashes[file_hash]})")
                results.append(MoveResult(str(f), "", "skip-duplicate"))
                continue
            elif rules.duplicates.action == "separate":
                dst = dest_root / rules.duplicates.folder / f.name
            elif rules.duplicates.action == "hardlink":
                # We'll link to the first copy's final destination
                first_target = dest_root / rules.duplicates.folder / seen_hashes[file_hash].name
                # If we haven't written the first yet, ensure its folder exists later as well.
                dst = first_target

        seen_hashes[file_hash] = f

        # ensure destination dir
        final_dst = next_nonconflicting_name(dst)

        if dry_run:
            action = "plan-move" if mode == "move" else ("plan-copy" if mode == "copy" else "plan-hardlink")
            log_fn(f"🧭  {action.upper()}: {f} -> {final_dst}")
            results.append(MoveResult(str(f), str(final_dst), action))
            continue

        ensure_dir(final_dst.parent)
        action = safe_link_or_copy(f, final_dst, mode if rules.duplicates.action != "hardlink" else "hardlink")
        results.append(MoveResult(str(f), str(final_dst), action))
        log_fn(f"✅ {action.upper()}: {f.name} -> {final_dst}")

    # write undo manifest
    if not dry_run and undo_manifest:
        ensure_dir(undo_manifest.parent)
        serializable = {"operations": [r.__dict__ for r in results if r.action in ("move", "copy", "hardlink")]}
        undo_manifest.write_text(json.dumps(serializable, indent=2), encoding="utf-8")
        log_fn(f"📝 Undo manifest saved -> {undo_manifest}")
    return results

def undo(undo_manifest: Path, log_fn=print) -> List[MoveResult]:
    """
    Reverses moves/copies/hardlinks recorded in the manifest.
    """
    if not undo_manifest.exists():
        raise FileNotFoundError(f"Undo manifest not found: {undo_manifest}")
    data = json.loads(undo_manifest.read_text(encoding="utf-8"))
    ops = data.get("operations", [])
    # reverse in LIFO order to minimize conflicts
    undone: List[MoveResult] = []
    for rec in reversed(ops):
        src = Path(rec["dst"])
        dst = Path(rec["src"])
        if not src.exists():
            log_fn(f"⚠️  Missing file for undo: {src}")
            continue
        ensure_dir(dst.parent)
        # Use move (even if original was copy/hardlink) to restore source view
        final_dst = next_nonconflicting_name(dst)
        os.replace(src, final_dst)
        log_fn(f"↩️  UNDO: {src} -> {final_dst}")
        undone.append(MoveResult(str(src), str(final_dst), "undo"))
    return undone
