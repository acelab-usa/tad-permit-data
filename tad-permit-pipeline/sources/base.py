"""Common interface every jurisdiction adapter implements."""
from abc import ABC, abstractmethod
from typing import Any, Iterable


class PermitSource(ABC):
    """A jurisdiction's ingestion adapter: how to reach it and how to map it."""

    name: str
    source_format: str  # "API" or "PDF"


class APIPermitSource(PermitSource):
    """One raw record maps 1:1 to one permit (e.g. a Socrata JSON row)."""

    source_format = "API"

    @abstractmethod
    def fetch_raw_records(self, size: int, page: int = 1) -> list[dict]:
        """Return raw records from the upstream API."""

    @abstractmethod
    def map_to_schema(self, raw_item: dict) -> dict:
        """Map one raw record into the field dict PermitSchemaV2 expects."""

    def should_skip(self, raw_item: dict, mapped: dict) -> str | None:
        """Return a skip reason string if this record shouldn't be stored, else None."""
        return None


class PDFPermitSource(PermitSource):
    """A page of ledger text maps to zero-or-more permits, via LLM extraction."""

    source_format = "PDF"

    # Optional, source-specific guidance passed to the LLM extractor (see
    # llm_processor.extract_multiple_permits_from_text) -- a permit-number
    # pattern to expect, quirks to ignore, category names it uses, etc.
    # None means "use the generic extraction instructions only", which is
    # the right default for a jurisdiction nobody's tuned a prompt for yet.
    extraction_hints: str | None = None

    @abstractmethod
    def iter_pages(
        self,
        month_cap: int = 1,
        page_cap: int | None = None,
        start_filename: str | None = None,
        start_page: int = 0,
    ) -> Iterable[tuple[str, int, str]]:
        """Yield (source_file_name, page_number, page_text) tuples to enqueue.

        `start_filename`/`start_page` resume from a prior run's progress
        (see database.get_pdf_cursor()) instead of restarting from the
        first file's page 1 every time."""
