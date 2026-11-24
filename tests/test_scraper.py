import http.server
import threading
from functools import partial

import pandas as pd
import pytest

from email_tool import scraper
from email_tool.scraper import (
    ScraperError,
    extract_emails,
    find_contact_pages,
    read_websites,
    scrape_file,
)


def test_extract_filters_noise():
    html = (
        '<p>info@acme.com, SALES@Acme.com. logo@2x.png example@example.com</p>'
        '<a href="mailto:help@acme.com?subject=Hi">x</a>'
    )
    assert extract_emails(html) == {"info@acme.com", "sales@acme.com", "help@acme.com"}


def test_cloudflare_email_decoded():
    key = 0x42
    email = "boss@acme.com"
    encoded = bytes([key]) + bytes(ord(c) ^ key for c in email)
    html = f'<span data-cfemail="{encoded.hex()}">[email&#160;protected]</span>'
    assert "boss@acme.com" in extract_emails(html)


def test_contact_pages_same_domain_only_and_case_preserved():
    html = (
        '<a href="/Contact-Us">c</a>'
        '<a href="https://other.com/contact">x</a>'
        '<a href="mailto:contact@acme.com">m</a>'
    )
    assert find_contact_pages("https://acme.com", html) == ["https://acme.com/Contact-Us"]


def test_contact_pages_capped():
    html = "".join(f'<a href="/contact{i}">c</a>' for i in range(20))
    assert len(find_contact_pages("https://acme.com", html)) == scraper.MAX_CONTACT_PAGES


def test_read_websites(tmp_path):
    f = tmp_path / "in.xlsx"
    pd.DataFrame({" Website ": ["a.com", None, "a.com", " b.com "]}).to_excel(f, index=False)
    assert read_websites(f) == ["a.com", "b.com"]


def test_read_websites_missing_column(tmp_path):
    f = tmp_path / "in.xlsx"
    pd.DataFrame({"url": ["a.com"]}).to_excel(f, index=False)
    with pytest.raises(ScraperError):
        read_websites(f)


@pytest.fixture()
def local_site(tmp_path):
    root = tmp_path / "site"
    root.mkdir()
    (root / "index.html").write_text('<a href="/contact.html">Contact</a> hello@local.test')
    (root / "contact.html").write_text("<p>support@local.test</p>")
    (root / "empty.html").write_text("<p>nothing here</p>")
    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    handler.log_message = lambda *a, **k: None
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def test_end_to_end(tmp_path, local_site, monkeypatch):
    monkeypatch.setattr(scraper, "PAGE_DELAY", 0)
    monkeypatch.setattr(scraper, "REQUEST_TIMEOUT", 2)
    src = tmp_path / "sites.xlsx"
    pd.DataFrame(
        {"website": [local_site + "/", local_site + "/empty.html", "http://127.0.0.1:1/"]}
    ).to_excel(src, index=False)

    seen = []
    out = scrape_file(src, progress=lambda d, t, s, m, r: seen.append((d, t)))

    assert out.sites_with_emails == 1
    assert out.sites_without_emails == 1
    assert out.sites_unreachable == 1
    assert out.total_emails == 2
    assert len(seen) == 3 and seen[-1] == (3, 3)
    found = pd.read_excel(out.found_file)
    assert set(found["email"]) == {"hello@local.test", "support@local.test"}
    missing = pd.read_excel(out.not_found_file)
    assert set(missing["reason"]) == {"No emails found", "Could not load website"}
    assert out.summary_file.exists()


def test_cancel_before_start(tmp_path, local_site):
    src = tmp_path / "sites.xlsx"
    pd.DataFrame({"website": [local_site + "/"]}).to_excel(src, index=False)
    cancel = threading.Event()
    cancel.set()
    out = scrape_file(src, cancel=cancel)
    assert out.cancelled and out.sites_with_emails == 0
