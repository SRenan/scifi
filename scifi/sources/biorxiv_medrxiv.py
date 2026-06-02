"""bioRxiv / medRxiv source: fetch a preprint PDF via the CSHL details API.

bioRxiv and medRxiv share one API (Cold Spring Harbor Laboratory):
    https://api.biorxiv.org/details/{biorxiv|medrxiv}/<doi>
Both servers use DOIs in the `10.1101/` namespace, but a DOI is hosted by
exactly one of them, so we try `biorxiv` first and fall back to `medrxiv`.
"""
from .base import Source

_API_URL = "https://api.biorxiv.org/details"
_PDF_URL = "https://www.{server}.org/content/{doi}v{version}.full.pdf"


class BiorxivMedrxiv(Source):
    """Fetch a preprint PDF from bioRxiv or medRxiv."""

    name = "biorxiv-medrxiv"

    def fetch(self, article_id, session):
        # CSHL DOIs all start with 10.1101/. Filtering here skips an API call
        # on every non-preprint article that reaches this source.
        if not article_id.doi or not article_id.doi.startswith("10.1101/"):
            return None

        for server in ("biorxiv", "medrxiv"):
            collection = self._lookup(server, article_id.doi, session)
            if not collection:
                continue
            version = max(_int_version(v) for v in collection)
            url = _PDF_URL.format(server=server, doi=article_id.doi, version=version)
            r = session.get(url, timeout=120)
            r.raise_for_status()
            if not r.content.startswith(b"%PDF"):
                raise RuntimeError(f"{server} returned non-PDF for {article_id.doi}")
            return r.content

        return None

    @staticmethod
    def _lookup(server, doi, session):
        r = session.get(f"{_API_URL}/{server}/{doi}", timeout=30)
        if r.status_code != 200:
            return None
        return r.json().get("collection") or None


def _int_version(record):
    try:
        return int(record.get("version", "1"))
    except (TypeError, ValueError):
        return 1
