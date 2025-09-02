from __future__ import annotations
import json
import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Any

@dataclass
class DateRule:
    enabled: bool = False
    base_folder: str = "By Date"
    group: str = "month"  # 'year' | 'month' | 'day'

@dataclass
class DuplicateRule:
    action: str = "separate"  # 'separate' | 'skip' | 'hardlink'
    folder: str = "Duplicates"

@dataclass
class Rules:
    unknown_folder: str
    exclude_dirs: List[str]
    exclude_hidden: bool
    prefer_extension_over_glob: bool
    by_extension: Dict[str, str]
    by_glob: Dict[str, str]
    by_mime: Dict[str, str]
    by_date: DateRule
    size_buckets: List[dict]
    duplicates: DuplicateRule

    @staticmethod
    def load(path: Optional[Path]) -> "Rules":
        cfg: dict
        if path is None:
            cfg = {}
        else:
            text = path.read_text(encoding="utf-8")
            try:
                cfg = json.loads(text)
            except json.JSONDecodeError:
                # Try YAML if available
                try:
                    import yaml  # type: ignore
                    cfg = yaml.safe_load(text) or {}
                except Exception as e:
                    raise RuntimeError(
                        f"Failed to parse config as JSON, and YAML is not available/valid: {e}"
                    )
        # defaults
        def get(path, default):
            return cfg.get(path, default)
        rules = Rules(
            unknown_folder=get("unknown_folder", "Others"),
            exclude_dirs=get("exclude_dirs", [".git", "__pycache__", "node_modules"]),
            exclude_hidden=bool(get("exclude_hidden", True)),
            prefer_extension_over_glob=bool(get("prefer_extension_over_glob", True)),
            by_extension={k.lower() if not k.startswith(".") else k.lower(): v for k, v in get("by_extension", {}).items()},
            by_glob=get("by_glob", {}),
            by_mime=get("by_mime", {}),
            by_date=DateRule(**get("by_date", {"enabled": False, "base_folder": "By Date", "group": "month"})),
            size_buckets=get("size_buckets", []),
            duplicates=DuplicateRule(**get("duplicates", {"action": "separate", "folder": "Duplicates"})),
        )
        # normalize extensions: ensure leading dot
        rules.by_extension = {
            (k if k.startswith(".") else f".{k}").lower(): v for k, v in rules.by_extension.items()
        }
        return rules

    def match_folder_for(self, path: Path) -> Optional[str]:
        """Return a subfolder name for the file based on configured rules (excluding date/size)."""
        # Extension rule
        ext = path.suffix.lower()
        if ext in self.by_extension:
            return self.by_extension[ext]

        # Glob rule
        for pattern, folder in self.by_glob.items():
            if path.match(pattern):
                return folder

        # MIME rule
        mime, _ = mimetypes.guess_type(path.as_posix())
        if mime:
            for prefix, folder in self.by_mime.items():
                if mime.startswith(prefix):
                    return folder

        return None

    def match_size_bucket(self, size_bytes: int) -> Optional[str]:
        if not self.size_buckets:
            return None
        mb = size_bytes / (1024 * 1024)
        for bucket in self.size_buckets:
            max_mb = bucket.get("max_mb", None)
            folder = bucket.get("folder", None)
            if folder is None:
                continue
            if max_mb is None:
                # No upper bound -> catch-all
                return folder
            if mb <= float(max_mb):
                return folder
        return None

    def date_parts(self, ts: float):
        import datetime as _dt
        dt = _dt.datetime.fromtimestamp(ts)
        if self.by_date.group == "year":
            return [f"{dt.year:04d}"]
        elif self.by_date.group == "day":
            return [f"{dt.year:04d}", f"{dt.month:02d}", f"{dt.day:02d}"]
        return [f"{dt.year:04d}", f"{dt.month:02d}"]  # default month
