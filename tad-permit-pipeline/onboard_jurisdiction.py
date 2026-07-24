"""onboard_jurisdiction.py -- draft a FieldMapping for a new city, from
either a Socrata or an ArcGIS REST FeatureServer/MapServer URL.

Fetches the dataset's column metadata (field names, types, descriptions --
richer signal than a raw sample record alone) plus a few sample records,
asks an LLM to propose a sources.field_mapping.FieldMapping matching them,
then immediately runs that proposal against the real sample records so you
can eyeball the result before anything touches sources/registry.py.

This is a draft-and-review tool, not an auto-onboarding pipeline. Two real
bugs already slipped past careful manual mapping in this project (NYC's
FieldMapping initially missing valuation_field; LA's "Bldg-New" falling
into "Other" in the taxonomy) -- neither would have been caught by clever
field-matching alone, only by looking at real mapped output. This tool
speeds up the tedious part (reading raw JSON, guessing which column is
what); it doesn't replace checking the result against reality.

Prints a one-line summary per sample record by default (pass --verbose for
the full mapped JSON, e.g. to check raw_scope_of_work), plus both the
FieldMapping and the ready-to-paste SOURCES dict entry (SocrataAPISource
or ArcGISFeatureSource, picked by URL shape) at the end.

Usage:
    uv run python onboard_jurisdiction.py <jurisdiction> <url> [--limit N] [--verbose]

Examples:
    uv run python onboard_jurisdiction.py denver \\
        https://data.denvergov.org/resource/xxxx.json

    uv run python onboard_jurisdiction.py dc \\
        https://maps2.dcgis.dc.gov/dcgis/rest/services/FEEDS/DCRA/FeatureServer/17
"""
import argparse
import json
import sys
import time
from urllib.parse import urlparse

import requests
from pydantic import ValidationError

from llm_processor import _call_with_retry, client
from logging_setup import get_logger
from models import ProposedFieldMapping
from permit_types import normalize_permit_type
from sources.arcgis import _flatten_feature
from sources.field_mapping import FieldMapping, build_mapper

logger = get_logger("onboard_jurisdiction")

REQUEST_TIMEOUT_SECONDS = 15
_MAX_RETRIES = 3
_BACKOFF_SECONDS = 1
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def _is_arcgis_url(url: str) -> bool:
    return "/FeatureServer" in url or "/MapServer" in url


def _parse_socrata_resource(resource_url: str) -> tuple:
    """Splits a Socrata `/resource/{id}.json` URL into (scheme://domain, resource_id)."""
    parsed = urlparse(resource_url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"'{resource_url}' doesn't look like a full URL (missing scheme/host)")

    path = parsed.path.rstrip("/")
    if not path.endswith(".json") or "/resource/" not in path:
        raise ValueError(
            f"Expected a Socrata '.../resource/<id>.json' URL, got '{resource_url}'"
        )

    resource_id = path.split("/resource/")[-1].removesuffix(".json")
    base = f"{parsed.scheme}://{parsed.netloc}"
    return base, resource_id


def _fetch_json(url: str, params: dict = None) -> object:
    """Fetches JSON with retry/backoff on transient failures (timeout,
    connection error, rate-limit/server-error status) -- same pattern as
    geo.py's Census geocoder fetch and the production Socrata/ArcGIS
    adapters. A smaller city's server (a single self-hosted ArcGIS instance,
    say, vs. a well-provisioned metro's) can be meaningfully slower or
    flakier than the endpoints this tool happened to be exercised against
    first -- a single attempt with no retry means one slow response kills
    the whole onboarding run instead of just costing a few seconds.
    """
    last_error = None

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
            if response.status_code in _RETRYABLE_STATUS_CODES:
                raise requests.exceptions.HTTPError(f"HTTP {response.status_code}", response=response)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            last_error = e
            if attempt < _MAX_RETRIES:
                wait = _BACKOFF_SECONDS * (2 ** (attempt - 1))
                logger.warning(
                    "Fetch failed for %s (attempt %s/%s): %s, retrying in %ss",
                    url, attempt, _MAX_RETRIES, e, wait,
                )
                time.sleep(wait)

    raise last_error


def _fetch_socrata_dataset(resource_url: str, sample_size: int) -> tuple:
    """Returns (columns, sample_records) for a Socrata resource URL.

    `columns` is Socrata's own column metadata (name/fieldName/dataTypeName/
    description) -- much stronger signal for guessing intent than a raw
    field name alone. `sample_records` are real rows to validate against.
    """
    base, resource_id = _parse_socrata_resource(resource_url)

    metadata = _fetch_json(f"{base}/api/views/{resource_id}.json")
    columns = [
        {
            "fieldName": c.get("fieldName"),
            "name": c.get("name"),
            "dataTypeName": c.get("dataTypeName"),
            "description": c.get("description"),
        }
        for c in metadata.get("columns", [])
    ]

    sample_records = _fetch_json(resource_url, params={"$limit": sample_size})
    if not isinstance(sample_records, list) or not sample_records:
        raise ValueError(f"No sample records returned from {resource_url}")

    return columns, sample_records


def _fetch_arcgis_dataset(layer_url: str, sample_size: int) -> tuple:
    """Returns (columns, sample_records) for an ArcGIS FeatureServer/
    MapServer layer URL (including its numeric layer ID).

    ArcGIS's own field metadata (name/type/alias) plays the same role
    Socrata's column metadata does. Sample records come back as
    {"features": [{"attributes": {...}, "geometry": {...}}, ...]} --
    flattened via the same _flatten_feature() the real ArcGISFeatureSource
    adapter uses, so the rest of this script (propose_mapping, review,
    to_field_mapping) never needs to know which platform it's looking at.
    """
    layer_url = layer_url.rstrip("/")

    metadata = _fetch_json(layer_url, params={"f": "json"})
    if "error" in metadata:
        raise ValueError(f"ArcGIS error fetching layer metadata: {metadata['error']}")

    columns = [
        {
            "fieldName": f.get("name"),
            "name": f.get("alias") or f.get("name"),
            "dataTypeName": f.get("type"),  # e.g. "esriFieldTypeDate", "esriFieldTypeString"
            "description": None,  # ArcGIS field metadata rarely includes one
        }
        for f in metadata.get("fields", [])
    ]

    query = _fetch_json(f"{layer_url}/query", params={
        "where": "1=1", "outFields": "*", "f": "json", "resultRecordCount": sample_size,
        # Request WGS84 explicitly -- otherwise geometry comes back in the
        # layer's native (often projected, e.g. State Plane feet) spatial
        # reference, which looks like garbage lat/lon to a human reviewing
        # the sample output and fails geo._valid()'s range check for real
        # ingestion. Same fix as sources/arcgis.py's ArcGISFeatureSource.
        "outSR": "4326",
    })
    if "error" in query:
        raise ValueError(f"ArcGIS error fetching sample records: {query['error']}")

    features = query.get("features", [])
    if not features:
        raise ValueError(f"No sample records returned from {layer_url}")

    sample_records = [_flatten_feature(f) for f in features]
    return columns, sample_records


def fetch_dataset(resource_url: str, sample_size: int) -> tuple:
    """Returns (columns, sample_records) for either a Socrata or an ArcGIS
    FeatureServer/MapServer URL, dispatching on URL shape."""
    if _is_arcgis_url(resource_url):
        return _fetch_arcgis_dataset(resource_url, sample_size)
    return _fetch_socrata_dataset(resource_url, sample_size)


_SYSTEM_PROMPT = """You are helping onboard a new city's building-permit API into a pipeline \
that normalizes many cities' data into one shared schema. You'll be given a permit \
dataset's column metadata and a real sample record (from either a Socrata or an ArcGIS \
FeatureServer/MapServer source -- treat both the same way). Propose which raw column(s) \
map to each canonical field.

Canonical fields and what they mean:
- permit_id_field: the unique permit/case/application number.
- address_fields: the site's street address, possibly split across multiple columns \
(e.g. street number + name + suffix, or a single combined field). List them in the \
order they should be joined.
- date_fields: the permit's filing/issue date (a real calendar_date-typed column, not a \
status/expiration date).
- owner_name_fields / contractor_name_fields: property owner and contractor/licensee \
name, if present and not redacted/incomplete.
- permit_type_fields: whichever column(s) actually signal construction type (new \
construction, alteration, demolition, electrical, etc.) -- not permit *status* or \
review-stage columns.
- valuation_field / square_footage_field: numeric columns for reported cost and area.
- scope_fields: free-text work description columns.
- point_fields: a column holding a NESTED point/geometry object (a Socrata "point"-typed \
column with its own lat/lon or GeoJSON coordinates) -- do NOT list plain top-level \
latitude/longitude columns, those are already detected automatically without any config. \
(An ArcGIS source's geometry is already flattened into plain latitude/longitude before \
you see it, so this will normally be empty for ArcGIS sources.)

Be conservative: leave a field unmapped (empty list / null) rather than guessing at a \
weak candidate -- a wrong mapping is worse than an honest gap a human can fill in. Use \
unmapped_notes for anything a human should double-check."""


def propose_mapping(columns: list, sample_record: dict) -> ProposedFieldMapping:
    def _request():
        return client.chat.completions.create(
            model="google/gemini-2.5-flash",
            response_format={"type": "json_object"},
            temperature=0.1,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Column metadata:\n{json.dumps(columns, indent=2)}\n\n"
                        f"Sample record:\n{json.dumps(sample_record, indent=2)}\n\n"
                        "Return a JSON object matching this schema exactly:\n"
                        f"{json.dumps(ProposedFieldMapping.model_json_schema(), indent=2)}"
                    ),
                },
            ],
        )

    response = _call_with_retry(_request, label="propose_mapping")
    if response is None:
        raise RuntimeError("LLM call failed -- see log above for details")

    raw_json = response.choices[0].message.content
    try:
        return ProposedFieldMapping.model_validate_json(raw_json)
    except ValidationError as e:
        raise RuntimeError(f"LLM returned JSON that didn't match schema: {e}\nRaw: {raw_json}")


def to_field_mapping(proposal: ProposedFieldMapping, jurisdiction: str, source_url: str) -> FieldMapping:
    return FieldMapping(
        jurisdiction=jurisdiction,
        source_url=source_url,
        permit_id_field=proposal.permit_id_field or "",
        address_fields=tuple(proposal.address_fields),
        address_separator=proposal.address_separator,
        date_fields=tuple(proposal.date_fields),
        owner_name_fields=tuple(proposal.owner_name_fields),
        contractor_name_fields=tuple(proposal.contractor_name_fields),
        permit_type_fields=tuple(proposal.permit_type_fields),
        valuation_field=proposal.valuation_field,
        square_footage_field=proposal.square_footage_field,
        scope_fields=tuple(proposal.scope_fields),
        point_fields=tuple(proposal.point_fields),
    )


def _format_as_python(mapping: FieldMapping, var_name: str) -> str:
    def _fmt(value):
        return repr(value)

    lines = [f"{var_name} = FieldMapping("]
    for field_name in (
        "jurisdiction", "source_url", "permit_id_field", "address_fields",
        "address_separator", "date_fields", "owner_name_fields",
        "contractor_name_fields", "permit_type_fields", "valuation_field",
        "square_footage_field", "scope_fields", "point_fields",
    ):
        lines.append(f"    {field_name}={_fmt(getattr(mapping, field_name))},")
    lines.append(")")
    return "\n".join(lines)


def _derive_socrata_query_url(resource_url: str) -> str:
    """Best-effort derivation of the bulk /api/v3/views/{id}/query.json
    endpoint from a plain /resource/{id}.json URL -- matches the pattern
    every existing Socrata entry in sources/registry.py uses. Not
    independently verified live; confirm with a real ingestion run, same
    caveat as those entries."""
    base, resource_id = _parse_socrata_resource(resource_url)
    return f"{base}/api/v3/views/{resource_id}/query.json"


def format_source_entry(mapping: FieldMapping, resource_url: str, jurisdiction: str, var_name: str) -> str:
    """Returns the ready-to-paste SOURCES dict entry for sources/registry.py,
    picking ArcGISFeatureSource or SocrataAPISource by URL shape."""
    date_column = mapping.date_fields[0] if mapping.date_fields else "TODO_DATE_COLUMN"

    if _is_arcgis_url(resource_url):
        return (
            f'"{jurisdiction}": ArcGISFeatureSource(\n'
            f'    name="{jurisdiction}",\n'
            f'    url="{resource_url}",\n'
            f'    date_column="{date_column}",\n'
            f'    mapper_func=build_mapper({var_name}),\n'
            f"),"
        )

    query_url = _derive_socrata_query_url(resource_url)
    return (
        f'"{jurisdiction}": SocrataAPISource(\n'
        f'    name="{jurisdiction}",\n'
        f'    url="{query_url}",\n'
        f'    date_column="{date_column}",\n'
        f'    mapper_func=build_mapper({var_name}),\n'
        f"),"
    )


_VALUATION_FIELD_FEE_HINTS = ("fee", "fees")  # e.g. FEES_PAID -- a permit fee is not a project valuation


def _summarize_sample(mapped: dict) -> str:
    """One-line summary of a mapped record -- just enough to sanity-check
    the mapping (did each field get a sensible value), not the full
    record. Use --verbose for the complete JSON, e.g. to inspect
    raw_scope_of_work."""
    if mapped["latitude"] is not None and mapped["longitude"] is not None:
        coords = f"({mapped['latitude']:.4f}, {mapped['longitude']:.4f})"
    else:
        coords = "(no coords)"
    valuation = f"${mapped['valuation']:,.0f}" if mapped["valuation"] is not None else "no valuation"
    return (
        f"{mapped['permit_id']} | {mapped['address']} | {mapped['filing_date']} | "
        f"{mapped['permit_type_raw']} -> {mapped['permit_type_normalized']} | {valuation} | {coords}"
    )


def review(mapping: FieldMapping, sample_records: list, verbose: bool = False) -> None:
    """Runs the proposed mapping against every fetched sample record and
    prints the result, flagging anything worth a second look -- an unmapped
    canonical field, a permit type that normalized to 'Other' (the exact
    class of gap LA's "Bldg-New" surfaced, printed with the actual raw
    candidate values so it's clear whether that's a taxonomy gap or
    genuinely no signal), or a valuation field that looks like it might
    actually be a processing fee rather than a project cost."""
    mapper = build_mapper(mapping)

    print("\n=== Mapped sample records ===")
    other_samples = []
    for i, raw_item in enumerate(sample_records, start=1):
        mapped = mapper(raw_item)
        if verbose:
            print(f"\n--- Sample {i} ---")
            print(json.dumps(mapped, indent=2, default=str))
        else:
            print(f"[{i}] {_summarize_sample(mapped)}")
        if mapped["permit_type_normalized"] == "Other":
            other_samples.append({f: raw_item.get(f) for f in mapping.permit_type_fields})

    print("\n=== Review flags ===")
    unmapped = [
        name for name, value in (
            ("permit_id_field", mapping.permit_id_field),
            ("address_fields", mapping.address_fields),
            ("date_fields", mapping.date_fields),
            ("permit_type_fields", mapping.permit_type_fields),
        ) if not value
    ]
    if unmapped:
        print(f"- No candidate found for: {', '.join(unmapped)} -- check the column list by hand.")
    else:
        print("- All required fields (permit_id, address, date, permit_type) have a candidate.")

    if not mapping.owner_name_fields:
        print("- owner_name_fields is empty -- confirm this dataset really has no usable owner field.")
    if not mapping.valuation_field:
        print("- valuation_field is empty -- confirm this dataset really has no cost/valuation field.")
    elif any(hint in mapping.valuation_field.lower() for hint in _VALUATION_FIELD_FEE_HINTS):
        print(
            f"- valuation_field ('{mapping.valuation_field}') looks like it might be a processing "
            "FEE, not the project's reported cost -- these are usually very different numbers "
            "(a fee is often a small fraction of, or flat schedule against, actual valuation). "
            "Check the real field list for a genuine cost/valuation field before trusting this."
        )
    if other_samples:
        print(
            f"- {len(other_samples)}/{len(sample_records)} sample(s) normalized to permit_type 'Other' -- "
            "the raw permit_type value(s) may need a new entry in permit_types.py's "
            "_KEYWORD_RULES/_EXACT_MATCH_OVERRIDES (same as LA's 'Bldg-New' needed), or there may "
            "genuinely be no construction-type signal in this record. Raw candidate values seen:"
        )
        for values in other_samples:
            print(f"    {values}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("jurisdiction", help="Short jurisdiction key to use, e.g. 'denver'")
    parser.add_argument(
        "resource_url",
        help="A Socrata '.../resource/<id>.json' URL, or an ArcGIS '.../FeatureServer/<layer>' "
             "or '.../MapServer/<layer>' URL",
    )
    parser.add_argument("--limit", type=int, default=5, help="Sample records to fetch and validate against (default: 5)")
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Print the full mapped JSON for every sample instead of a one-line summary",
    )
    args = parser.parse_args()

    try:
        columns, sample_records = fetch_dataset(args.resource_url, args.limit)
    except (requests.RequestException, ValueError) as e:
        print(f"Failed to fetch dataset: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Fetched {len(columns)} columns and {len(sample_records)} sample record(s). Asking the LLM to propose a mapping...")

    try:
        proposal = propose_mapping(columns, sample_records[0])
    except RuntimeError as e:
        print(f"Failed to get a proposed mapping: {e}", file=sys.stderr)
        sys.exit(1)

    if proposal.unmapped_notes:
        print(f"\nLLM notes: {proposal.unmapped_notes}")

    mapping = to_field_mapping(proposal, args.jurisdiction, args.resource_url)
    review(mapping, sample_records, verbose=args.verbose)

    var_name = f"{args.jurisdiction.upper()}_MAPPING"

    print("\n=== Paste into sources/registry.py after reviewing the flags above ===\n")
    print(_format_as_python(mapping, var_name))
    print()
    print(format_source_entry(mapping, args.resource_url, args.jurisdiction, var_name))
    print(
        "\nNot done yet -- this hasn't touched sources/registry.py itself. Add any needed "
        "permit_types.py entries first if flagged above, then paste both blocks in by hand."
    )


if __name__ == "__main__":
    main()
