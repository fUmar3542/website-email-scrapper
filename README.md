# EmailTool

Splits an Excel sheet into two files: contacts **with** an email and contacts **without**.

## For the client
1. Open `EmailTool.dmg` and drag **EmailTool** into Applications.
2. First launch: **right-click the app → Open → Open** (macOS warning for unsigned apps; only needed once).
3. Choose your `.xlsx` file. It must have a column named **Primary Email**
   (capitalisation and extra spaces don't matter). `.xls` is not supported; re-save as `.xlsx`.
4. Results appear in an `Output` folder next to your file:
   `Emailed_Sheet_<timestamp>.xlsx` and `Non_Emailed_Sheet_<timestamp>.xlsx`.

Cells containing blanks, `N/A`, `none` or `-` count as "no email".

**Problems?** Send the log file at `~/Library/Logs/EmailTool/emailtool.log`.

## For developers
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest -q
python -m email_tool            # run the app (needs PYTHONPATH=src or pip install -e .)
./build/build_mac.sh            # on a Mac: builds EmailTool.app and EmailTool.dmg
```
Edit `bundle_identifier` in `EmailTool.spec` before shipping.

### Optional scraper
`pip install -r requirements-scraper.txt` then `python -m email_tool.scraper websites.xlsx`.
It is not bundled into the app.

### Layout
- `src/email_tool/splitter.py`: pure logic (tested)
- `src/email_tool/gui.py`: Tkinter wrapper
- `src/email_tool/scraper.py`: optional website scraper
