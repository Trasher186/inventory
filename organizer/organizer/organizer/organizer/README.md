# 📂 Smart File Organizer

A safe, configurable, cross-platform file organizer (Python 3.8+). Supports:
- Rules by extension, glob, MIME
- Optional date-based folders (year/month/day)
- Size buckets (Tiny/Medium/Huge or your own)
- Duplicate detection with separate/skip/hardlink actions
- Dry-run planner + Undo via manifest
- No external dependencies (YAML optional)

## Quickstart
```bash
python -m organizer.cli plan -s "/path/Downloads" -d "/path/Library" -c config.sample.json
python -m organizer.cli organize -s "/path/Downloads" -d "/path/Library" -c config.sample.json --mode move
# If needed:
python -m organizer.cli undo -m .undo_manifest.json
