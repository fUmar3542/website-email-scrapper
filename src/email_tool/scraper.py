"""Website email scraper: core logic (no GUI).

Reads an Excel sheet with a "website" column, visits each site's main page and
a few same-domain contact-style pages, and collects email addresses.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

WEBSITE_COLUMN = "website"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}
CONTACT_KEYWORDS = ("contact", "about", "support", "help", "reach-us", "get-in-touch")
EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
BLOCKED_EMAILS = {"user@domain.com", "example@example.com", "test@test.com", "admin@example.com"}
BLOCKED_PARTS = (
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".css", ".js",
    "example.com", "sentry.io", "wixpress.com",
)
MAX_CONTACT_PAGES = 5
REQUEST_TIMEOUT = 10
PAGE_DELAY = 0.5
DEFAULT_WORKERS = 5

# progress callback: (done, total, website, status_message, result_or_None)
ProgressCb = Callable[[int, int, str, str, "SiteResult | None"], None]


class ScraperError(Exception):
    """Problems the user can fix (bad file, missing column)."""


@dataclass
class SiteResult:
    website: str
    emails: dict[str, str] = field(default_factory=dict)  # email -> page found on
    reachable: bool = True


@dataclass(frozen=True)
class ScrapeOutput:
    output_dir: Path
    found_file: Path | None
    not_found_file: Path | None
    summary_file: Path
    total_sites: int
    sites_with_emails: int
    sites_without_emails: int
    sites_unreachable: int
    total_emails: int
    cancelled: bool


# ---------------------------------------------------------------- helpers

def make_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(total=2, backoff_factor=1, status_forcelist=(429, 500, 502, 503, 504))
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.mount("http://", HTTPAdapter(max_retries=retry))
    session.headers.update(HEADERS)
    return session


def normalize_url(url: str) -> str:
    url = url.strip()
    return url if url.startswith(("http://", "https://")) else "https://" + url


def fetch(session: requests.Session, url: str) -> str | None:
    """Return page HTML, or None if it could not be loaded."""
    try:
        resp = session.get(url, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 200:
            return resp.text
        logger.info("HTTP %s for %s", resp.status_code, url)
    except requests.RequestException as exc:
        logger.info("Could not fetch %s: %s", url, exc)
    return None


def _decode_cfemail(hexstr: str) -> str:
    """Decode Cloudflare's data-cfemail obfuscation."""
    try:
        data = bytes.fromhex(hexstr)
        key = data[0]
        return bytes(b ^ key for b in data[1:]).decode("utf-8", "ignore")
    except (ValueError, IndexError):
        return ""


def _clean(raw: str) -> str | None:
    email = raw.strip().lower().strip(".,;:()[]{}<>\"'")
    if "@" not in email or email in BLOCKED_EMAILS:
        return None
    if any(part in email for part in BLOCKED_PARTS):
        return None
    return email if EMAIL_REGEX.fullmatch(email) else None


def extract_emails(html: str) -> set[str]:
    """Find emails in visible text, mailto: links and Cloudflare-protected spans."""
    found: set[str] = set()
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup.find_all(attrs={"data-cfemail": True}):
        decoded = _clean(_decode_cfemail(tag["data-cfemail"]))
        if decoded:
            found.add(decoded)

    for link in soup.find_all("a", href=True):
        href = link["href"]
        if href.lower().startswith("mailto:"):
            cleaned = _clean(href[7:].split("?")[0])
            if cleaned:
                found.add(cleaned)

    for raw in EMAIL_REGEX.findall(html):
        cleaned = _clean(raw)
        if cleaned:
            found.add(cleaned)
    return found


def find_contact_pages(base_url: str, html: str) -> list[str]:
    """Same-domain contact-like links, capped at MAX_CONTACT_PAGES."""
    base_host = urlparse(base_url).netloc.lower().removeprefix("www.")
    soup = BeautifulSoup(html, "html.parser")
    pages: list[str] = []
    for link in soup.find_all("a", href=True):
        href = link["href"].strip()
        if href.lower().startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        if not any(k in href.lower() for k in CONTACT_KEYWORDS):  # lowercase only to match
            continue
        full = urljoin(base_url, href).split("#")[0]
        host = urlparse(full).netloc.lower().removeprefix("www.")
        if host == base_host and full not in pages and full.rstrip("/") != base_url.rstrip("/"):
            pages.append(full)
        if len(pages) >= MAX_CONTACT_PAGES:
            break
    return pages


# ---------------------------------------------------------------- scraping

def scrape_website(
    website: str,
    cancel: threading.Event | None = None,
    delay: float = PAGE_DELAY,
) -> SiteResult:
    url = normalize_url(website)
    result = SiteResult(website=website)
    session = make_session()
    try:
        html = fetch(session, url)
        if html is None:
            result.reachable = False
            return result
        for email in extract_emails(html):
            result.emails.setdefault(email, url)
        for page in find_contact_pages(url, html):
            if cancel and cancel.is_set():
                break
            page_html = fetch(session, page)
            if page_html:
                for email in extract_emails(page_html):
                    result.emails.setdefault(email, page)
            time.sleep(delay)
    finally:
        session.close()
    return result


def read_websites(input_file: str | Path) -> list[str]:
    """Read unique, non-empty values of the 'website' column."""
    path = Path(input_file)
    if not path.is_file():
        raise ScraperError(f"File not found: {path}")
    if path.suffix.lower() != ".xlsx":
        raise ScraperError("Only .xlsx files are supported. Please re-save as .xlsx.")
    try:
        df = pd.read_excel(path)
    except Exception as exc:
        raise ScraperError(f"Could not read the Excel file: {exc}") from exc

    column = next((c for c in df.columns if str(c).strip().lower() == WEBSITE_COLUMN), None)
    if column is None:
        raise ScraperError(
            f'Could not find a column named "{WEBSITE_COLUMN}".\n\n'
            f"Columns found: {', '.join(map(str, df.columns))}"
        )
    sites = [str(v).strip() for v in df[column].dropna() if str(v).strip()]
    unique = list(dict.fromkeys(sites))
    if not unique:
        raise ScraperError("The website column is empty.")
    return unique


def scrape_sites(
    websites: list[str],
    progress: ProgressCb | None = None,
    cancel: threading.Event | None = None,
    workers: int = DEFAULT_WORKERS,
) -> list[SiteResult]:
    """Scrape many sites in parallel. Stops early if `cancel` is set."""
    results: list[SiteResult] = []
    total = len(websites)
    done = 0
    pool = ThreadPoolExecutor(max_workers=workers)
    try:
        futures = {pool.submit(_scrape_guarded, w, cancel): w for w in websites}
        for fut in as_completed(futures):
            site = futures[fut]
            res = fut.result()
            if res is not None:
                results.append(res)
            done += 1
            if progress:
                if res is None:
                    msg = "skipped"
                elif not res.reachable:
                    msg = "could not load site"
                else:
                    msg = f"{len(res.emails)} email(s)"
                progress(done, total, site, msg, res)
            if cancel and cancel.is_set():
                break
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    return results


def _scrape_guarded(website: str, cancel: threading.Event | None) -> SiteResult | None:
    if cancel and cancel.is_set():
        return None
    try:
        return scrape_website(website, cancel)
    except Exception:
        logger.exception("Unexpected error scraping %s", website)
        return SiteResult(website=website, reachable=False)


# ---------------------------------------------------------------- output

def write_results(
    results: list[SiteResult],
    total_input: int,
    output_dir: str | Path,
    cancelled: bool = False,
) -> ScrapeOutput:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    found_rows, missing_rows = [], []
    for r in sorted(results, key=lambda x: x.website):
        if r.emails:
            for email, page in sorted(r.emails.items()):
                found_rows.append({"website": r.website, "email": email, "found_on": page})
        else:
            reason = "No emails found" if r.reachable else "Could not load website"
            missing_rows.append({"website": r.website, "reason": reason})

    found_file = out_dir / f"scraped_emails_{stamp}.xlsx"
    not_found_file = out_dir / f"no_emails_found_{stamp}.xlsx"
    summary_file = out_dir / f"summary_{stamp}.xlsx"

    try:
        if found_rows:
            pd.DataFrame(found_rows).to_excel(found_file, index=False)
        if missing_rows:
            pd.DataFrame(missing_rows).to_excel(not_found_file, index=False)

        with_emails = sum(1 for r in results if r.emails)
        unreachable = sum(1 for r in results if not r.reachable)
        without = len(results) - with_emails - unreachable
        total_emails = len({e for r in results for e in r.emails})
        metrics = [
            ("Total unique websites in input", total_input),
            ("Websites processed", len(results)),
            ("Websites with emails", with_emails),
            ("Websites with no emails found", without),
            ("Websites that could not be loaded", unreachable),
            ("Total unique emails", total_emails),
        ]
        if cancelled:
            metrics.append(("NOTE", "Run was cancelled before finishing"))
        pd.DataFrame(metrics, columns=["Metric", "Count"]).to_excel(summary_file, index=False)
    except PermissionError as exc:
        raise ScraperError(f"Could not write to {out_dir}. Check folder permissions.") from exc

    return ScrapeOutput(
        output_dir=out_dir,
        found_file=found_file if found_rows else None,
        not_found_file=not_found_file if missing_rows else None,
        summary_file=summary_file,
        total_sites=total_input,
        sites_with_emails=with_emails,
        sites_without_emails=without,
        sites_unreachable=unreachable,
        total_emails=total_emails,
        cancelled=cancelled,
    )


def scrape_file(
    input_file: str | Path,
    output_dir: str | Path | None = None,
    progress: ProgressCb | None = None,
    cancel: threading.Event | None = None,
) -> ScrapeOutput:
    """Full pipeline: read Excel -> scrape -> write Excel outputs."""
    websites = read_websites(input_file)
    logger.info("Scraping %d websites from %s", len(websites), input_file)
    results = scrape_sites(websites, progress, cancel)
    out_dir = output_dir or Path(input_file).parent / "Output"
    cancelled = bool(cancel and cancel.is_set())
    return write_results(results, len(websites), out_dir, cancelled)


if __name__ == "__main__":  # command-line use: python -m email_tool.scraper websites.xlsx
    import sys

    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python -m email_tool.scraper websites.xlsx")
    out = scrape_file(sys.argv[1], progress=lambda d, t, s, m, r: print(f"[{d}/{t}] {s}: {m}"))
    print(f"Done. Output in {out.output_dir}")
