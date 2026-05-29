"""PMC Open Access source: fetch a PDF from the PMC Cloud Service on AWS.

NCBI's PMC Cloud Service exposes the Open Access subset as a public S3 bucket,
readable anonymously over plain HTTPS (no AWS credentials or SDK needed). Each
article version lives under a `PMC<id>.<version>/` prefix; when the publisher's
license permits, that prefix includes the article PDF.

See https://pmc-oa-opendata.s3.amazonaws.com/README.txt

Note: this bucket replaces the retired `oa.fcgi` web service. As of mid-2026
NCBI is still migrating the back-catalogue, so articles older than ~2011 may
not be present yet; for those, fetch falls through to the next source.
"""
import re

from .base import Source

_BUCKET = "https://pmc-oa-opendata.s3.amazonaws.com"

_KEY_RE = re.compile(r"<Key>([^<]+)</Key>")
_VERSION_RE = re.compile(r"\.(\d+)/", re.I)


class PmcOA(Source):
    """Fetch the PDF for an OA-subset article from the PMC Cloud Service."""

    name = "pmc-oa"

    def fetch(self, article_id, session):
        if not article_id.pmcid:
            return None  # PMC OA is keyed on PMCID.
        pmcid = article_id.pmcid.upper()

        keys = self._list(session, f"{pmcid}.")
        pdfs = [k for k in keys if k.lower().endswith(".pdf")]
        if not pdfs:
            # Not (yet) in the bucket, or the license bars PDF redistribution.
            return None

        # An article may have several versions; take the most recent.
        key = max(pdfs, key=_version)
        r = session.get(f"{_BUCKET}/{key}", timeout=120)
        r.raise_for_status()
        if not r.content.startswith(b"%PDF"):
            raise RuntimeError(f"PMC OA returned non-PDF data for {pmcid}")
        return r.content

    @staticmethod
    def _list(session, prefix):
        """Return every object key under `prefix` via the anonymous S3 list API."""
        r = session.get(_BUCKET, params={"list-type": "2", "prefix": prefix}, timeout=30)
        r.raise_for_status()
        return _KEY_RE.findall(r.text)


def _version(key):
    """Version number embedded in a key like `PMC123.4/PMC123.4.pdf` (0 if none)."""
    m = _VERSION_RE.search(key)
    return int(m.group(1)) if m else 0
