"""Declarative field-mapping adapter for Socrata (and Socrata-shaped) permit
APIs.

Most cities' raw payloads differ only in field *names*, not in the actual
logic needed to turn a raw record into the dict PermitSchemaV2 expects -- a
permit ID, an address built from one or more parts, a filing date, a
valuation, are almost always a straight rename or an ordered-candidate
lookup (try field A, fall back to field B). FieldMapping captures that as
data instead of a hand-written function per city, so onboarding a typical
new Socrata city means writing a config, not code -- see the `seattle`
entry in sources/registry.py for an example that needs no custom function
at all.

The one place city payloads still genuinely diverge in a way a flat config
can't express is when the scope-of-work text needs real construction (not
just "pick a field, truncate for the summary") -- see `scope_builder` below
and the `nyc` entry in sources/registry.py, the one existing case that
needs it.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional

from geo import extract_lat_lon
from logging_setup import get_logger
from permit_types import normalize_permit_type

logger = get_logger("sources.field_mapping")


def _safe_float(value) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_date(raw_date):
    if not raw_date:
        return None
    try:
        date_str = str(raw_date).split("T")[0].strip()
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except (ValueError, IndexError):
        logger.warning("Could not parse date %r, storing as null", raw_date)
        return None


def _first_nonblank(raw_item: dict, fields: tuple) -> Optional[str]:
    """Returns the first field in `fields` with a non-blank value, else None.

    `fields` is an ordered tuple of candidate field names -- most sources
    only have one, but some (e.g. NYC's issued_date/approved_date) split the
    same real-world concept across more than one column depending on the
    record's state.
    """
    for f in fields:
        value = raw_item.get(f)
        if value not in (None, ""):
            return value
    return None


def _join_fields(raw_item: dict, fields: tuple, separator: str) -> str:
    parts = [str(raw_item.get(f) or "").strip() for f in fields]
    return separator.join(p for p in parts if p).strip()


@dataclass
class FieldMapping:
    """Declarative description of how to map one Socrata-shaped payload into
    the dict PermitSchemaV2 expects.

    Every `*_fields` attribute is an ordered tuple of raw field names tried
    in turn (first non-blank wins) -- pass a single-element tuple for a
    plain rename. Leave one empty to mean "this jurisdiction doesn't
    provide it" (e.g. Austin's redacted owner_name).
    """
    jurisdiction: str
    source_url: str
    permit_id_field: str
    address_fields: tuple
    date_fields: tuple
    permit_type_fields: tuple
    address_separator: str = " "
    owner_name_fields: tuple = ()
    contractor_name_fields: tuple = ()
    valuation_field: Optional[str] = None
    square_footage_field: Optional[str] = None
    scope_fields: tuple = ()
    scope_default: str = "No description provided."
    scope_summary_length: int = 150
    point_fields: tuple = ()
    permit_type_default: str = "UNKNOWN"
    # Escape hatch for the rare city needing genuinely custom scope
    # construction instead of the generic "pick a field, truncate for the
    # summary" behavior above. Takes the raw record, returns
    # (raw_scope_of_work, scope_summary).
    scope_builder: Optional[Callable[[dict], tuple]] = None


def build_mapper(mapping: FieldMapping) -> Callable[[dict], dict]:
    """Builds a mapper_func (as SocrataAPISource expects) from a declarative
    FieldMapping -- the generic replacement for a hand-written per-city
    mapping function."""

    def _mapper(raw_item: dict) -> dict:
        latitude, longitude = extract_lat_lon(raw_item, point_fields=mapping.point_fields)

        if mapping.scope_builder:
            raw_scope, scope_summary = mapping.scope_builder(raw_item)
        else:
            raw_scope = _first_nonblank(raw_item, mapping.scope_fields) or mapping.scope_default
            scope_summary = raw_scope[: mapping.scope_summary_length]

        permit_type_values = [raw_item.get(f) for f in mapping.permit_type_fields]

        return {
            "permit_id": raw_item.get(mapping.permit_id_field),
            "jurisdiction": mapping.jurisdiction,
            "source_url": mapping.source_url,
            "source_format": "API",
            "address": _join_fields(raw_item, mapping.address_fields, mapping.address_separator) or "UNKNOWN",
            "filing_date": _safe_date(_first_nonblank(raw_item, mapping.date_fields)),
            "owner_name": _first_nonblank(raw_item, mapping.owner_name_fields),
            "contractor_name": _first_nonblank(raw_item, mapping.contractor_name_fields),
            "latitude": latitude,
            "longitude": longitude,
            "permit_type_raw": _first_nonblank(raw_item, mapping.permit_type_fields) or mapping.permit_type_default,
            "permit_type_normalized": normalize_permit_type(*permit_type_values),
            "square_footage": _safe_float(raw_item.get(mapping.square_footage_field)) if mapping.square_footage_field else None,
            "valuation": _safe_float(raw_item.get(mapping.valuation_field)) if mapping.valuation_field else None,
            "raw_scope_of_work": raw_scope,
            "scope_summary": scope_summary,
            "building_systems": [],
        }

    return _mapper
