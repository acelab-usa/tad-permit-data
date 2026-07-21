"""Pluggable permit source adapters.

To add a new jurisdiction:

  * If it's a Socrata (or Socrata-shaped JSON) API, instantiate a
    `SocrataAPISource` in `sources/registry.py` with the endpoint URL, the
    date column to sort on, and a small mapper function that turns one raw
    record into the fields `PermitSchemaV2` expects.

  * If it's a PDF ledger (monthly report, scanned table, etc.), instantiate
    a `PDFLedgerSource` pointing at the folder the files live in. Page text
    is handed to the LLM extractor, which finds every permit on the page --
    no per-city mapping function needed.

Either way, register the instance in `SOURCES` in registry.py under the
jurisdiction's slug and the rest of the pipeline (dataloader, workflow,
dashboard) picks it up automatically.
"""
from .base import APIPermitSource, PDFPermitSource, PermitSource
from .registry import get_source, list_sources

__all__ = [
    "PermitSource",
    "APIPermitSource",
    "PDFPermitSource",
    "get_source",
    "list_sources",
]
