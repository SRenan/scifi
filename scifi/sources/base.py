"""Source abstraction shared by every PDF provider."""
from abc import ABC, abstractmethod


class Source(ABC):
    """A place to get a PDF from, given an article's identifiers."""

    name = "source"

    @abstractmethod
    def fetch(self, article_id, session):
        """Return PDF bytes, or None if this source cannot serve the article.

        Return None for the expected "not available here" case (wrong/missing
        identifier, not in this collection) so the dispatcher falls through to
        the next source. Raise only when a fetch was attempted and failed.
        """
        raise NotImplementedError
