"""Article identifiers: parsing raw input and cross-referencing DOI / PMID / PMCID."""
import os
import re
from dataclasses import dataclass
from urllib.parse import unquote

from curl_cffi import requests

# NCBI asks API callers to identify themselves and rate-limits anonymous use.
# See https://www.ncbi.nlm.nih.gov/pmc/tools/id-converter-api/
NCBI_TOOL = "scifi"
NCBI_EMAIL = os.environ.get("SCIFI_EMAIL", "renan.sauteraud@gmail.com")

_IDCONV_URL = "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/"
_ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

_DOI_RE = re.compile(r"10\.\d{4,9}/\S+")
_PMID_URL_RE = re.compile(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)", re.I)


@dataclass
class ArticleId:
    """An article known by any combination of DOI, PMID, and PMCID."""

    doi: str | None = None
    pmid: str | None = None
    pmcid: str | None = None

    def __bool__(self):
        return bool(self.doi or self.pmid or self.pmcid)

    def __str__(self):
        return self.doi or self.pmcid or self.pmid or "<empty>"


def normalize_doi(s):
    """Extract a bare DOI from a string or URL, raising ValueError if absent."""
    s = unquote(str(s)).strip()
    m = _DOI_RE.search(s)
    if not m:
        raise ValueError(f"could not extract DOI from {s!r}")
    return m.group(0).rstrip(".,;)>\"'")


def parse_id(raw):
    """Detect which kind of identifier `raw` is and return an ArticleId.

    Accepts bare DOIs/PMIDs/PMCIDs, `PMID:`/`PMC` prefixes, and pubmed/pmc URLs.
    """
    s = unquote(str(raw)).strip()

    # DOI first: a real DOI URL never carries a PMID/PMCID, but a Sci-Hub or
    # publisher URL does carry a DOI we want to pick out.
    m = _DOI_RE.search(s)
    if m:
        return ArticleId(doi=m.group(0).rstrip(".,;)>\"'"))

    m = re.search(r"\bPMC\d+\b", s, re.I)
    if m:
        return ArticleId(pmcid=m.group(0).upper())

    m = _PMID_URL_RE.search(s)
    if m:
        return ArticleId(pmid=m.group(1))
    bare = re.sub(r"^(?:pmid|pubmed)[:\s]*", "", s, flags=re.I)
    if re.fullmatch(r"\d{1,9}", bare):
        return ArticleId(pmid=bare)

    raise ValueError(f"could not interpret {raw!r} as a DOI, PMID, or PMCID")


def resolve(article_id, session=None):
    """Fill in missing DOI/PMID/PMCID fields via NCBI's identifier APIs.

    Tries the PMC ID Converter first (one call fills all three for any article
    in PMC). For PMIDs not in PMC, the converter has no record — so if we still
    have no DOI and we do have a PMID, fall back to PubMed's `esummary`, whose
    `articleids` carries the DOI for every PubMed record.

    Best-effort: API failures leave `article_id` unchanged rather than raising.
    """
    if not article_id:
        raise ValueError("cannot resolve an empty ArticleId")
    sess = session or requests.Session(impersonate="firefox133")

    article_id = _from_idconv(article_id, sess)
    if article_id.pmid and not article_id.doi:
        article_id = _from_esummary(article_id, sess)
    return article_id


def _from_idconv(article_id, session):
    known = article_id.pmcid or article_id.pmid or article_id.doi
    r = session.get(
        _IDCONV_URL,
        params={"ids": known, "format": "json", "tool": NCBI_TOOL, "email": NCBI_EMAIL},
        timeout=30,
    )
    r.raise_for_status()
    records = r.json().get("records") or []
    if not records or records[0].get("status") == "error":
        return article_id

    # The converter returns pmid as a JSON number; keep every field a string.
    rec = {k: (str(v) if v is not None else None) for k, v in records[0].items()}
    return ArticleId(
        doi=article_id.doi or rec.get("doi"),
        pmid=article_id.pmid or rec.get("pmid"),
        pmcid=article_id.pmcid or rec.get("pmcid"),
    )


def _from_esummary(article_id, session):
    r = session.get(
        _ESUMMARY_URL,
        params={
            "db": "pubmed",
            "id": article_id.pmid,
            "retmode": "json",
            "tool": NCBI_TOOL,
            "email": NCBI_EMAIL,
        },
        timeout=30,
    )
    r.raise_for_status()
    rec = r.json().get("result", {}).get(article_id.pmid)
    if not rec:
        return article_id

    doi = pmcid = None
    for aid in rec.get("articleids", []):
        if aid.get("idtype") == "doi":
            doi = aid.get("value")
        elif aid.get("idtype") == "pmc":
            pmcid = aid.get("value")
    return ArticleId(
        doi=article_id.doi or doi,
        pmid=article_id.pmid,
        pmcid=article_id.pmcid or pmcid,
    )
