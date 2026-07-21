"""Registers every jurisdiction the pipeline knows how to ingest.

To onboard a new jurisdiction, add one entry to SOURCES below -- either a
SocrataAPISource (write a small mapper function) or a PDFLedgerSource (point
it at a folder). Nothing else in the pipeline needs to change.
"""
from datetime import datetime
from typing import Optional

from logging_setup import get_logger
from permit_types import normalize_permit_type
from sources.pdf_ledger import PDFLedgerSource
from sources.socrata import SocrataAPISource

logger = get_logger("sources.registry")


def _safe_float(value) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_date(raw_date: Optional[str]):
    if not raw_date:
        return None
    try:
        date_str = str(raw_date).split("T")[0].strip()
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except (ValueError, IndexError):
        logger.warning("Could not parse date %r, storing as null", raw_date)
        return None


def map_chicago_to_schema(raw_item: dict) -> dict:
    """Maps raw Chicago API payload to our PermitSchemaV2 dictionary structure."""
    parsed_date = _safe_date(raw_item.get("issue_date"))

    address_parts = [
        raw_item.get("street_number") or "",
        raw_item.get("street_direction") or "",
        raw_item.get("street_name") or "",
        raw_item.get("suffix") or "",
    ]

    return {
        "permit_id": raw_item.get("permit_"),
        "jurisdiction": "chicago",
        "source_url": "https://data.cityofchicago.org/resource/ydr8-56us.json",
        "source_format": "API",
        "address": " ".join(p for p in address_parts if p).strip() or "UNKNOWN",
        "filing_date": parsed_date,
        "owner_name": raw_item.get("contact_1_name"),
        "contractor_name": raw_item.get("contact_2_name"),
        "permit_type_raw": raw_item.get("permit_type", "UNKNOWN"),
        "permit_type_normalized": normalize_permit_type(raw_item.get("permit_type")),
        "square_footage": None,
        "valuation": _safe_float(raw_item.get("reported_cost")),
        "raw_scope_of_work": raw_item.get("work_description") or "No description provided.",
        "scope_summary": (raw_item.get("work_description") or "No description provided.")[:150],
        "building_systems": [],
    }


def map_nyc_to_schema(raw_item: dict) -> dict:
    """Maps raw NYC DOB NOW Approved Permits payload to our unified PermitSchemaV2."""
    raw_date = raw_item.get("issued_date") or raw_item.get("approved_date")
    parsed_date = _safe_date(raw_date)

    house_num = (raw_item.get("house_no") or "").strip()
    street_name = (raw_item.get("street_name") or "").strip()
    full_address = f"{house_num} {street_name}".strip()

    return {
        "permit_id": raw_item.get("job_filing_number"),
        "jurisdiction": "nyc",
        "source_url": "https://a810-dobnow.nyc.gov/html/",
        "source_format": "API",
        "address": full_address or "UNKNOWN",
        "filing_date": parsed_date,
        "owner_name": raw_item.get("owner_name"),
        "contractor_name": raw_item.get("licensee_s_business_name"),
        # work_type carries the actual construction category (e.g. "Plumbing",
        # "Mechanical"); filing_reason is permit lifecycle status (e.g.
        # "Initial Permit", "Renewal Permit Without Changes") and is present
        # on essentially every record, so ordering it first (as this used to)
        # meant work_type was never actually used.
        "permit_type_raw": raw_item.get("work_type") or raw_item.get("filing_reason") or "UNKNOWN",
        "permit_type_normalized": normalize_permit_type(raw_item.get("work_type"), raw_item.get("filing_reason")),
        "square_footage": None,
        "valuation": _safe_float(raw_item.get("estimated_job_costs")),
        "raw_scope_of_work": (
            f"Work on Floor: {raw_item.get('work_on_floor', 'N/A')}. "
            f"Job Description: {raw_item.get('job_description', 'N/A')}"
        ),
        "scope_summary": f"Permit issued for {raw_item.get('work_type', 'general')} construction.",
        "building_systems": [],
    }


def map_austin_to_schema(raw_item: dict) -> dict:
    """Maps raw Austin API payload to our unified PermitSchemaV2."""
    parsed_date = _safe_date(raw_item.get("issue_date"))

    raw_scope = (
        raw_item.get("description")
        or raw_item.get("project_name")
        or "No description provided."
    )

    return {
        "permit_id": raw_item.get("permit_number"),
        "jurisdiction": "austin",
        "source_url": "https://data.austintexas.gov/resource/3syk-w9eu.json",
        "source_format": "API",
        "address": (raw_item.get("original_address1") or "").strip() or "UNKNOWN",
        "filing_date": parsed_date,
        "owner_name": None,  # Austin redacts primary owners from this endpoint due to privacy laws
        "contractor_name": raw_item.get("contractor_company_name") or raw_item.get("contractor_name"),
        "permit_type_raw": raw_item.get("work_class") or "UNKNOWN",
        # permit_class_mapped is Austin's own Residential/Commercial split --
        # a different axis (property class, not work type) from what this
        # column means everywhere else, so it can't be passed through
        # directly. work_class (e.g. "New", "Remodel", "Demolition") is the
        # actual construction-type signal.
        "permit_type_normalized": normalize_permit_type(raw_item.get("work_class"), raw_item.get("permit_class_mapped")),
        "square_footage": _safe_float(raw_item.get("total_lot_sq_ft")),
        "valuation": _safe_float(raw_item.get("total_job_valuation")),
        "raw_scope_of_work": raw_scope,
        "scope_summary": raw_scope[:150],
        "building_systems": [],
    }


SOURCES = {
    "chicago": SocrataAPISource(
        name="chicago",
        url="https://data.cityofchicago.org/api/v3/views/ydr8-5enu/query.json",
        date_column="issue_date",
        mapper_func=map_chicago_to_schema,
    ),
    "nyc": SocrataAPISource(
        name="nyc",
        url="https://data.cityofnewyork.us/api/v3/views/rbx6-tga4/query.json",
        date_column="issued_date",
        mapper_func=map_nyc_to_schema,
        skip_sentinel_field="permit_id",
        skip_sentinel_value="Permit is no",
    ),
    "austin": SocrataAPISource(
        name="austin",
        url="https://data.austintexas.gov/api/v3/views/3syk-w9eu/query.json",
        date_column="issue_date",
        mapper_func=map_austin_to_schema,
    ),
    "allen": PDFLedgerSource(
        name="allen",
        folder_path="./allen_pdfs",
    ),
}


def get_source(name: str):
    try:
        return SOURCES[name.lower()]
    except KeyError:
        raise ValueError(
            f"Unknown jurisdiction '{name}'. Available: {', '.join(sorted(SOURCES))}"
        )


def list_sources() -> list[str]:
    return sorted(SOURCES.keys())
