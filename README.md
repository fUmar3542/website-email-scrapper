# Website Email Scraper

Desktop app (macOS) that reads an Excel list of websites and collects contact email
addresses from each site's main page and its contact/about/support pages.

## For production
1. Open `WebsiteScrapper.dmg` and drag **WebsiteScrapper** into Applications.
2. On first launch macOS will say it can't verify the app (it's unsigned). Open
   **System Settings → Privacy & Security**, scroll down, and click **Open Anyway**
   next to WebsiteScrapper. This is only needed once.
3. Click **Choose file…** and pick an `.xlsx` file with a column named **website**
   (e.g. `example.com` or `https://example.com`). `.xls` is not supported; re-save as `.xlsx`.
4. Click **Start**. You can **Cancel** at any time; partial results are saved.
5. Results go to an `Output` folder next to your file:
   - `scraped_emails_<timestamp>.xlsx`: website, email, page it was found on
   - `no_emails_found_<timestamp>.xlsx`: websites with no email, and why
   - `summary_<timestamp>.xlsx`: counts

**Problems?** Send the log file at `~/Library/Logs/WebsiteScrapper/websitescrapper.log`.

Only scrape websites you are permitted to, and respect each site's terms.

## For developers
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pip install -e .
python -m pytest -q
python -m email_tool                       # run the app
python -m email_tool.scraper sites.xlsx    # command-line scraping
./build/build_mac.sh                       # on a Mac: builds WebsiteScrapper.app and WebsiteScrapper.dmg
```
Edit `bundle_identifier` in `WebsiteScrapper.spec` before shipping.

### Layout
- `src/email_tool/scraper.py`: scraping logic (tested against a local test server)
- `src/email_tool/gui.py`: Tkinter app; scraping runs in a worker thread
- `src/email_tool/splitter.py`: separate Excel splitter (by "Primary Email"); not in the app
