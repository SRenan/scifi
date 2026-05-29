"""Unpaywall source: fetch a free OA copy via the Unpaywall REST API.

Unpaywall (https://unpaywall.org/) aggregates legitimate open-access copies of
articles across publishers, preprint servers, and institutional repositories.
Given a DOI, it returns the best free PDF available, if any.

API docs: https://unpaywall.org/products/api
"""
import os
from urllib.parse import quote

from .base import Source

_API_URL = "https://api.unpaywall.org/v2/"
_EMAIL = os.environ.get("SCIFI_EMAIL", "renan.sauteraud@gmail.com")


class Unpaywall(Source):
    """Fetch a freely-available PDF via the Unpaywall API."""

    name = "unpaywall"

    def fetch(self, article_id, session):
        if not article_id.doi:
            return None  # Unpaywall is keyed on DOI.

        r = session.get(
            f"{_API_URL}{quote(article_id.doi, safe='/')}",
            params={"email": _EMAIL},
            timeout=30,
        )
        if r.status_code == 404:
            return None  # Unknown DOI to Unpaywall — let another source try.
        r.raise_for_status()
        data = r.json()
        if not data.get("is_oa"):
            return None  # No legal OA copy known.

        errors = []
        for loc in _ordered_locations(data):
            url = loc.get("url_for_pdf")
            if not url:
                continue
            label = loc.get("host_type") or "?"
            try:
                resp = session.get(url, timeout=60)
                resp.raise_for_status()
            except Exception as e:
                errors.append(f"{label}: {e}")
                continue
            if not resp.content.startswith(b"%PDF"):
                errors.append(f"{label}: non-PDF response ({len(resp.content)} bytes)")
                continue
            return resp.content

        if errors:
            raise RuntimeError("; ".join(errors))
        # Unpaywall reported OA copies but none had a direct PDF URL.
        return None


def _ordered_locations(data):
    """Best-first iteration over OA locations, with `best_oa_location` up front."""
    best = data.get("best_oa_location")
    all_locs = data.get("oa_locations") or []
    if best is None:
        return all_locs
    # best_oa_location is also present inside oa_locations; dedupe by url.
    seen = {best.get("url")}
    ordered = [best]
    for loc in all_locs:
        if loc.get("url") not in seen:
            ordered.append(loc)
            seen.add(loc.get("url"))
    return ordered
