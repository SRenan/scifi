"""Single entry point: resolve an identifier and fetch its PDF."""
import json
import pathlib
import re
from dataclasses import dataclass, replace

from curl_cffi import requests

from .ids import ArticleId, parse_id, resolve
from .sources.biorxiv_medrxiv import BiorxivMedrxiv
from .sources.pmc_oa import PmcOA
from .sources.scihub import SciHub
from .sources.unpaywall import Unpaywall


def default_sources():
    """Sources tried in order: PMC OA → Unpaywall → bioRxiv/medRxiv → Sci-Hub."""
    return [PmcOA(), Unpaywall(), BiorxivMedrxiv(), SciHub()]


@dataclass
class FetchResult:
    """Outcome of a single `fetch` call — success or expected failure."""

    raw: str
    article: ArticleId
    source: str | None = None
    path: str | None = None
    error: str | None = None
    cached: bool = False

    @property
    def ok(self) -> bool:
        return self.path is not None


class Manifest:
    """Skip-if-already-done record for an outdir.

    Successful fetches are appended as JSONL to `<outdir>/_scifi_manifest.jsonl`.
    On construction the file is read into memory; later `get(raw)` calls return
    the cached `FetchResult` iff its PDF still exists on disk. Deleting the
    manifest file (or the PDF it points to) forces a re-download.
    """

    FILENAME = "_scifi_manifest.jsonl"

    def __init__(self, outdir):
        self.outdir = pathlib.Path(outdir)
        self.path = self.outdir / self.FILENAME
        self._done = {}
        if self.path.exists():
            for line in self.path.open():
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("path"):
                    self._done[rec["raw"]] = _result_from_dict(rec)

    def get(self, raw):
        rec = self._done.get(raw)
        if rec is None:
            return None
        if not pathlib.Path(rec.path).exists():
            del self._done[raw]  # PDF was deleted — force a re-fetch
            return None
        return rec

    def add(self, result):
        if not result.ok:
            return
        self.outdir.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as f:
            f.write(json.dumps(_result_to_dict(result)) + "\n")
        self._done[result.raw] = result


def _result_to_dict(r):
    return {
        "raw": r.raw,
        "article": {"doi": r.article.doi, "pmid": r.article.pmid, "pmcid": r.article.pmcid},
        "source": r.source,
        "path": r.path,
        "error": r.error,
    }


def _result_from_dict(d):
    a = d.get("article") or {}
    return FetchResult(
        raw=d["raw"],
        article=ArticleId(doi=a.get("doi"), pmid=a.get("pmid"), pmcid=a.get("pmcid")),
        source=d.get("source"),
        path=d.get("path"),
        error=d.get("error"),
    )


def _new_session():
    return requests.Session(impersonate="firefox133")


def _safe_name(article_id):
    base = article_id.doi or article_id.pmcid or article_id.pmid or "paper"
    return re.sub(r'[/\\<>:"|?*]', "_", base)


def fetch(raw_id, outdir="papers", sources=None, session=None, manifest=None):
    """Resolve `raw_id` to an article and download its PDF.

    Tries each source in order (PMC OA → Unpaywall → bioRxiv/medRxiv → Sci-Hub
    by default) and writes the first PDF returned. Returns a `FetchResult`
    describing the outcome — `ok` indicates success and `path` holds the saved
    file path. Expected failures (unparseable input, no source could serve it)
    populate `error` rather than raising.

    If `manifest` is provided, prior successful fetches of the same `raw_id`
    are returned without doing any network work (the result's `cached` flag is
    set to `True`); fresh successes are appended to the manifest for the next
    run.
    """
    sources = sources if sources is not None else default_sources()
    sess = session or _new_session()
    raw = str(raw_id).strip()  # tolerate stray whitespace from line-end mismatches

    if manifest is not None:
        prior = manifest.get(raw)
        if prior is not None:
            return replace(prior, cached=True)

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
        result = FetchResult(raw=raw, article=article, source=src.name, path=str(fn))
        if manifest is not None:
            manifest.add(result)
        return result

    detail = "; ".join(errors) if errors else "no source could serve this article"
    return FetchResult(raw=raw, article=article, error=detail)
