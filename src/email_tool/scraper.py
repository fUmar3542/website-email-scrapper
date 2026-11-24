"""OPTIONAL: scrape emails from websites listed in an Excel sheet.

Not used by the GUI. Install extras first:
    pip install -r requirements-scraper.txt
Run:
    python -m email_tool.scraper websites.xlsx
"""

from __future__ import annotations

import logging
import re
import sys
import time
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; EmailTool/1.0)"}
CONTACT_KEYWORDS = ("contact", "about", "support", "help", "reach-us")
EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
BLOCKED_EMAILS = {"user@domain.com", "example@example.com", "test@test.com"}
BLOCKED_PARTS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", "example.com")
MAX_CONTACT_PAGES = 5


def make_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(total=2, backoff_factor=1, status_forcelist=(429, 500, 502, 503))
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.mount("http://", HTTPAdapter(max_retries=retry))
    session.headers.update(HEADERS)
    return session


def normalize_url(url: str) -> str:
    url = url.strip()
    return url if url.startswith(("http://", "https://")) else "https://" + url


def fetch(session: requests.Session, url: str) -> str:
    try:
        resp = session.get(url, timeout=15)
        if resp.status_code == 200:
            return resp.text
    except requests.RequestException as exc:
        logger.warning("Error fetching %s: %s", url, exc)
    return ""


def extract_emails(html: str) -> set[str]:
    emails = set()
    for raw in EMAIL_REGEX.findall(html):
        email = raw.strip().lower().strip(".,;:()[]{}<>")
        if email in BLOCKED_EMAILS or any(p in email for p in BLOCKED_PARTS):
            continue
        emails.add(email)
    return emails


def find_contact_pages(base_url: str, html: str) -> list[str]:
    """Same-domain contact-like links, capped at MAX_CONTACT_PAGES."""
    base_host = urlparse(base_url).netloc
    soup = BeautifulSoup(html, "lxml")
    found: list[str] = []
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if not any(k in href.lower() for k in CONTACT_KEYWORDS):  # lowercase only for matching
            continue
        full = urljoin(base_url, href)
        if urlparse(full).netloc == base_host and full not in found:
            found.append(full)
        if len(found) >= MAX_CONTACT_PAGES:
            break
    return found


def scrape_website(session: requests.Session, url: str, delay: float = 1.0) -> set[str]:
    url = normalize_url(url)
    logger.info("Scraping %s", url)
    html = fetch(session, url)
    if not html:
        return set()
    emails = extract_emails(html)
    for page in find_contact_pages(url, html):
        emails |= extract_emails(fetch(session, page))
        time.sleep(delay)
    return emails


def run(input_file: str) -> None:
    df = pd.read_excel(input_file)
    if "website" not in df.columns:
        raise SystemExit("Excel must contain a column named 'website'")

    session = make_session()
    found, missing = [], []
    for site in df["website"].dropna().astype(str).drop_duplicates():
        emails = scrape_website(session, site)
        if emails:
            found += [{"website": site, "email": e} for e in sorted(emails)]
        else:
            missing.append({"website": site})

    pd.DataFrame(found).to_excel("scraped_emails.xlsx", index=False)
    pd.DataFrame(missing).to_excel("no_emails_found.xlsx", index=False)
    pd.DataFrame(
        [
            {"Metric": "Total unique websites", "Count": df["website"].nunique()},
            {"Metric": "With emails", "Count": len({r["website"] for r in found})},
            {"Metric": "Without emails", "Count": len(missing)},
        ]
    ).to_excel("summary.xlsx", index=False)  # counts live here, not as fake rows in data


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python -m email_tool.scraper websites.xlsx")
    run(sys.argv[1])
