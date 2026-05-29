"""Single entry point: resolve an identifier and fetch its PDF."""
import pathlib
import re
from dataclasses import dataclass

from curl_cffi import requests

from .ids import ArticleId, parse_id, resolve
from .sources.pmc_oa import PmcOA
from .sources.scihub import SciHub
from .sources.unpaywall import Unpaywall


def default_sources():
    """Sources tried in order: PMC Open Access, then Unpaywall, then Sci-Hub."""
    return [PmcOA(), Unpaywall(), SciHub()]


@dataclass
class FetchResult:
    """Outcome of a single `fetch` call — success or expected failure."""

    raw: str
    article: ArticleId
    source: str | None = None
    path: str | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.path is not None


def _new_session():
    return requests.Session(impersonate="firefox133")


def _safe_name(article_id):
    base = article_id.doi or article_id.pmcid or article_id.pmid or "paper"
    return re.sub(r'[/\\<>:"|?*]', "_", base)


def fetch(raw_id, outdir="papers", sources=None, session=None):
    """Resolve `raw_id` to an article and download its PDF.

    Tries each source in order (PMC OA → Unpaywall → Sci-Hub by default) and
    writes the first PDF returned. Returns a `FetchResult` describing the
    outcome — `ok` indicates success and `path` holds the saved file path.
    Expected failures (unparseable input, no source could serve it) populate
    `error` rather than raising.
    """
    sources = sources if sources is not None else default_sources()
    sess = session or _new_session()
    raw = str(raw_id).strip()  # tolerate stray whitespace from line-end mismatches

    try:
        article = parse_id(raw_id)
    except ValueError as e:
        return FetchResult(raw=raw, article=ArticleId(), error=str(e))

    try:
        article = resolve(article, session=sess)
    except Exception:
        pass  # Resolution is best-effort; a source may still work as-is.

    errors = []
    for src in sources:
        try:
            data = src.fetch(article, sess)
        except Exception as e:
            errors.append(f"{src.name}: {e}")
            continue
        if data is None:
            continue
        if not data.startswith(b"%PDF"):
            errors.append(f"{src.name}: returned non-PDF data")
            continue
        outpath = pathlib.Path(outdir)
        outpath.mkdir(parents=True, exist_ok=True)
        fn = outpath / f"{_safe_name(article)}.pdf"
        fn.write_bytes(data)
        return FetchResult(raw=raw, article=article, source=src.name, path=str(fn))

    detail = "; ".join(errors) if errors else "no source could serve this article"
    return FetchResult(raw=raw, article=article, error=detail)
