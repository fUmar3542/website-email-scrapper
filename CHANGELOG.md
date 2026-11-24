# Changelog

## 1.1.0
- The desktop app is now the **website email scraper** (progress bar, cancel, live log,
  background threads, parallel scraping). The Excel splitter remains in the package as a module.
- Output files are timestamped; "not found" file says why (no emails vs. site could not load).
- Finds mailto: links and Cloudflare-protected emails; same-domain contact pages only (max 5).
- Dropped the lxml dependency (uses built-in html.parser) for a smaller, safer bundle.

## 1.0.0
- Initial refactor: splitter, GUI, scraper modules; tests; PyInstaller spec; macOS build script.
