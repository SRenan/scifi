"""Sci-Hub source: fetch a PDF by DOI from one of several mirrors."""
import re
from urllib.parse import quote

from .base import Source

MIRRORS = ["https://sci-hub.st", "https://sci-hub.se", "https://sci-hub.ru", "https://sci-hub.ee"]


def _find_pdf_url(html):
    m = re.search(r'citation_pdf_url["\']\s+content=["\']([^"\']+)', html)
    if m:
        return m.group(1)
    m = re.search(r'<(?:embed|iframe)[^>]+src=["\']([^"\']+\.pdf[^"\']*)', html, re.I)
    if m:
        return m.group(1)
    return None


def _absolutize(url, base):
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return base + url
    return url


class SciHub(Source):
    """Scrape a Sci-Hub mirror's viewer page for the article PDF."""

    name = "sci-hub"

    def __init__(self, mirrors=None):
        self.mirrors = mirrors or MIRRORS

    def fetch(self, article_id, session):
        if not article_id.doi:
            return None  # Sci-Hub is keyed on DOI.

        doi = article_id.doi
        errors = []
        for base in self.mirrors:
            viewer = f"{base}/{quote(doi, safe='/')}"
            try:
                r = session.get(viewer, timeout=30)
                r.raise_for_status()
            except Exception as e:
                errors.append(f"{base}: {e}")
                continue

            url = _find_pdf_url(r.text)
            if not url:
                errors.append(f"{base}: no PDF link (missing DOI or CAPTCHA?)")
                continue

            try:
                pdf = session.get(_absolutize(url, base), headers={"Referer": viewer}, timeout=60)
                pdf.raise_for_status()
            except Exception as e:
                errors.append(f"{base}: {e}")
                continue

            if not pdf.content.startswith(b"%PDF"):
                errors.append(f"{base}: non-PDF response ({len(pdf.content)} bytes)")
                continue
            return pdf.content

        # Every mirror was tried and none worked — surface why.
        raise RuntimeError("; ".join(errors) or "no mirrors configured")
