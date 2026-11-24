# Changelog

## 1.0.0
- Refactored into splitter (logic), gui (Tkinter) and optional scraper.
- Case/whitespace-insensitive column match; "N/A", "none", "-" treated as empty.
- Timestamped outputs so previous results are never overwritten.
- Logging to file; friendly error dialogs.
- Unit tests, PyInstaller spec, macOS build script.
