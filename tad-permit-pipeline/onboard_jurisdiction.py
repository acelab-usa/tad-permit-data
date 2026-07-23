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

Usage:
    uv run python onboard_jurisdiction.py <jurisdiction> <url> [--limit N]

Examples:
    uv run python onboard_jurisdiction.py denver \\
        https://data.denvergov.org/resource/xxxx.json

    uv run python onboard_jurisdiction.py dc \\
        https://maps2.dcgis.dc.gov/dcgis/rest/services/FEEDS/DCRA/FeatureServer/17
"""
import argparse
import json
import sys
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
    response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


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


def review(mapping: FieldMapping, sample_records: list) -> None:
    """Runs the proposed mapping against every fetched sample record and
    prints the result, flagging anything worth a second look -- an unmapped
    canonical field, or a permit type that normalized to 'Other' (the exact
    class of gap LA's "Bldg-New" surfaced)."""
    mapper = build_mapper(mapping)

    print("\n=== Mapped sample records ===")
    other_count = 0
    for i, raw_item in enumerate(sample_records, start=1):
        mapped = mapper(raw_item)
        print(f"\n--- Sample {i} ---")
        print(json.dumps(mapped, indent=2, default=str))
        if mapped["permit_type_normalized"] == "Other":
            other_count += 1

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
    if other_count:
        print(
            f"- {other_count}/{len(sample_records)} sample(s) normalized to permit_type 'Other' -- "
            "the raw permit_type value(s) may need a new entry in permit_types.py's "
            "_KEYWORD_RULES/_EXACT_MATCH_OVERRIDES (same as LA's 'Bldg-New' needed)."
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("jurisdiction", help="Short jurisdiction key to use, e.g. 'denver'")
    parser.add_argument(
        "resource_url",
        help="A Socrata '.../resource/<id>.json' URL, or an ArcGIS '.../FeatureServer/<layer>' "
             "or '.../MapServer/<layer>' URL",
    )
    parser.add_argument("--limit", type=int, default=5, help="Sample records to fetch and validate against (default: 5)")
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
    review(mapping, sample_records)

    source_class = "ArcGISFeatureSource" if _is_arcgis_url(args.resource_url) else "SocrataAPISource"

    print(f"\n=== Draft FieldMapping (paste into sources/registry.py after reviewing above) ===\n")
    print(_format_as_python(mapping, f"{args.jurisdiction.upper()}_MAPPING"))
    print(
        f"\nNot done yet -- this hasn't touched sources/registry.py. Review the flags above, "
        f"add any needed permit_types.py entries, then add {args.jurisdiction.upper()}_MAPPING "
        f"and a \"{args.jurisdiction}\": {source_class}(...) entry by hand, the same way "
        f"Seattle/LA were added."
    )


if __name__ == "__main__":
    main()
