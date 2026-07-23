"""Pluggable permit source adapters.

To add a new jurisdiction:

  * If it's a Socrata (or Socrata-shaped JSON) API, instantiate a
    `SocrataAPISource` in `sources/registry.py` with the endpoint URL, the
    date column to sort on, and a FieldMapping (see field_mapping.py) --
    most cities need no custom mapping code at all.

  * If it's an ArcGIS REST FeatureServer/MapServer layer, instantiate an
    `ArcGISFeatureSource` the same way -- see arcgis.py. Its geometry gets
    flattened into plain latitude/longitude at fetch time, so it plugs
    into the same FieldMapping machinery Socrata sources use.

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
