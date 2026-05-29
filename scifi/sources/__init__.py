"""PDF sources: each turns an ArticleId into PDF bytes."""
from .base import Source
from .pmc_oa import PmcOA
from .scihub import SciHub
from .unpaywall import Unpaywall

__all__ = ["Source", "PmcOA", "SciHub", "Unpaywall"]
