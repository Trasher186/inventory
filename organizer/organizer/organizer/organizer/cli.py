from __future__ import annotations
import argparse
from pathlib import Path
import sys

from .rules import Rules
from .organizer import organize, undo

BANNER = "📂 Smart File Organizer — blazing-fast, safe, and configurable."

def parse_args(argv=None):
    p = argparse.ArgumentParser(description=BANNER)
    sub = p.add_subparsers(dest="cmd", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("-s", "--source", required=True, type=Path, help="Source directory")
    common.add_argument("-d", "--dest", required=True, type=Path, help="Destination directory")
    common.add_argument("-c", "--config", type=Path, default=None, help="Config file (JSON or YAML)")
    common.add_argument("--mode", choices=["move", "copy", "hardlink"], default="move", help="How to place files at destination")
    common.add_argument("--manifest", type=Path, default=Path(".undo_manifest.json"), help="Where to save undo manifest")
    common.add_argument("--no-hidden", action="store_true", help="Exclude hidden files (overrides config)")

    p_org = sub.add_parser("organize", parents=[common], help="Organize files")
    p_org.add_argument("--dry-run", action="store_true", help="Plan only; don't modify files")

    p_plan = sub.add_parser("plan", parents=[common], help="Show plan (dry-run)")
    p_plan.set_defaults(dry_run=True)

    p_undo = sub.add_parser("undo", help="Undo a previous run using manifest")
    p_undo.add_argument("-m", "--manifest", type=Path, default=Path(".undo_manifest.json"))

    return p.parse_args(argv)

def main(argv=None):
    args = parse_args(argv)
    if args.cmd in ("organize", "plan"):
        rules = Rules.load(args.config)
        if args.no_hidden:
            rules.exclude_hidden = True
        print(BANNER)
        print(f"Source: {args.source}\nDest:   {args.dest}\nMode:   {args.mode}\nDryRun: {getattr(args, 'dry_run', False)}")
        organize(
            src_root=args.source,
            dest_root=args.dest,
            rules=rules,
            mode=args.mode,
            dry_run=getattr(args, "dry_run", False),
            undo_manifest=args.manifest if not getattr(args, "dry_run", False) else None,
            log_fn=lambda m: print(m),
        )
    elif args.cmd == "undo":
        print(BANNER)
        undo(args.manifest, log_fn=lambda m: print(m))
    else:
        raise SystemExit("Unknown command")

if __name__ == "__main__":
    main(sys.argv[1:])
