"""scifi — download scientific PDFs by DOI, PMID, or PMCID from multiple sources."""
from .fetch import FetchResult, fetch
from .ids import ArticleId, parse_id, resolve

__all__ = ["fetch", "FetchResult", "ArticleId", "parse_id", "resolve"]
