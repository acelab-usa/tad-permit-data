"""Registers every jurisdiction the pipeline knows how to ingest.

To onboard a new jurisdiction, add one entry to SOURCES below -- either a
SocrataAPISource or a PDFLedgerSource. Nothing else in the pipeline needs to
change.

A SocrataAPISource needs a FieldMapping (see sources/field_mapping.py) that
declares which raw field(s) hold each piece of PermitSchemaV2 -- most cities
need nothing more than that (see `seattle` below). Only reach for a custom
`scope_builder` (see `nyc` below) when a field genuinely can't be expressed
as "rename this column" or "try these columns in order."
"""
from sources.arcgis import ArcGISFeatureSource
from sources.field_mapping import FieldMapping, build_mapper
from sources.pdf_ledger import PDFLedgerSource
from sources.socrata import SocrataAPISource

# Candidate point-geometry field names to check per dataset, in addition to
# the plain latitude/longitude-ish fields geo.py always tries first. Not
# verified against live API responses -- see geo.py's module docstring.
_GEO_POINT_FIELDS = ("location", "geocoded_location", "the_geom")


CHICAGO_MAPPING = FieldMapping(
    jurisdiction="chicago",
    source_url="https://data.cityofchicago.org/resource/ydr8-56us.json",
    permit_id_field="permit_",
    address_fields=("street_number", "street_direction", "street_name", "suffix"),
    date_fields=("issue_date",),
    owner_name_fields=("contact_1_name",),
    contractor_name_fields=("contact_2_name",),
    permit_type_fields=("permit_type",),
    valuation_field="reported_cost",
    scope_fields=("work_description",),
    point_fields=_GEO_POINT_FIELDS,
)


def _nyc_scope_builder(raw_item: dict) -> tuple:
    raw_scope = (
        f"Work on Floor: {raw_item.get('work_on_floor', 'N/A')}. "
        f"Job Description: {raw_item.get('job_description', 'N/A')}"
    )
    scope_summary = f"Permit issued for {raw_item.get('work_type', 'general')} construction."
    return raw_scope, scope_summary


NYC_MAPPING = FieldMapping(
    jurisdiction="nyc",
    source_url="https://a810-dobnow.nyc.gov/html/",
    permit_id_field="job_filing_number",
    address_fields=("house_no", "street_name"),
    date_fields=("issued_date", "approved_date"),
    owner_name_fields=("owner_name",),
    contractor_name_fields=("licensee_s_business_name",),
    # work_type carries the actual construction category (e.g. "Plumbing",
    # "Mechanical"); filing_reason is permit lifecycle status (e.g. "Initial
    # Permit", "Renewal Permit Without Changes") and is present on
    # essentially every record, so it only matters as a fallback.
    permit_type_fields=("work_type", "filing_reason"),
    valuation_field="estimated_job_costs",
    # NYC's raw_scope_of_work/scope_summary are built from two separate
    # fields with fixed labels, not "pick a field and truncate" -- the one
    # thing here a flat FieldMapping can't express declaratively.
    scope_builder=_nyc_scope_builder,
    point_fields=_GEO_POINT_FIELDS,
)


AUSTIN_MAPPING = FieldMapping(
    jurisdiction="austin",
    source_url="https://data.austintexas.gov/resource/3syk-w9eu.json",
    permit_id_field="permit_number",
    address_fields=("original_address1",),
    date_fields=("issue_date",),
    # owner_name_fields intentionally left empty -- Austin redacts primary
    # owners from this endpoint due to privacy laws, not because the field
    # is simply absent.
    contractor_name_fields=("contractor_company_name", "contractor_name"),
    # permit_class_mapped is Austin's own Residential/Commercial split -- a
    # different axis (property class, not work type) from what this column
    # means everywhere else, so it's only a secondary signal for the
    # normalizer, never surfaced as permit_type_raw itself. work_class (e.g.
    # "New", "Remodel", "Demolition") is the actual construction-type signal.
    permit_type_fields=("work_class", "permit_class_mapped"),
    square_footage_field="total_lot_sq_ft",
    valuation_field="total_job_valuation",
    scope_fields=("description", "project_name"),
    point_fields=_GEO_POINT_FIELDS,
)


# Added from a live sample (`data.seattle.gov/resource/76t5-zqzr.json`), so
# these field names are actually verified -- unlike Chicago/NYC/Austin's
# geometry field guesses. Needs no custom mapper_func or scope_builder at
# all: every field is a plain rename or ordered candidate, and Seattle's
# plain top-level latitude/longitude fields are already covered by the
# fields geo.extract_lat_lon() tries first, with no point_fields needed.
# NOTE: the `url` below (the bulk-query endpoint used by fetch_raw_records)
# wasn't independently verified live -- only the plain /resource/ endpoint
# used to pull the sample was. Confirm with a real ingestion run.
SEATTLE_MAPPING = FieldMapping(
    jurisdiction="seattle",
    source_url="https://data.seattle.gov/resource/76t5-zqzr.json",
    permit_id_field="permitnum",
    address_fields=("originaladdress1", "originalcity", "originalstate", "originalzip"),
    address_separator=", ",
    date_fields=("issueddate", "applieddate"),
    # permittypedesc is the closest single field to what the other cities
    # call "permit type" (e.g. "New", "Alteration"); permitclass is a
    # fallback/secondary signal for the normalizer. Seattle's sample payload
    # has no owner/contractor/square-footage fields at all.
    permit_type_fields=("permittypedesc", "permitclass"),
    valuation_field="estprojectcost",
    scope_fields=("description",),
    point_fields=_GEO_POINT_FIELDS,
)


# Added from a live sample (`data.lacity.org/resource/xnhu-aczu.json`), so
# these field names are actually verified. Needs no custom mapper_func or
# scope_builder. Two things this dataset genuinely lacks, rather than us
# just not mapping them: no latitude/longitude or geometry field at all
# (LA permits get coordinates entirely from the geocoding fallback -- see
# the "la" entry in geo.JURISDICTION_LOCATIONS), and no complete owner-name
# field -- only applicant_first_name, with no last name alongside it, too
# incomplete to trust as owner_name.
LA_MAPPING = FieldMapping(
    jurisdiction="la",
    source_url="https://data.lacity.org/resource/xnhu-aczu.json",
    permit_id_field="pcis_permit",
    # zip_code is included (unlike Chicago/NYC/Austin's address_fields,
    # which have no zip field to draw from at all) since LA's addresses are
    # otherwise disambiguated only by "Los Angeles, CA" -- a huge, dense
    # city with many similarly-named streets across neighborhoods. Without
    # zip, the geocode fallback had a real, observed failure mode: an
    # unqualified-enough address occasionally matched a same-named street
    # elsewhere in the country. The zip's position (after the street, before
    # the appended "Los Angeles, CA") isn't standard USPS order -- worth
    # confirming match-rate improvement against a real ingestion run.
    address_fields=("address_start", "street_direction", "street_name", "street_suffix", "zip_code"),
    date_fields=("issue_date",),
    contractor_name_fields=("contractors_business_name",),
    # permit_sub_type (e.g. "1 or 2 Family Dwelling") is occupancy, not
    # construction type -- kept only as a secondary signal for the
    # normalizer, same role Seattle's permitclass and Austin's
    # permit_class_mapped play. permit_type (e.g. "Bldg-New") is the actual
    # construction-type signal.
    permit_type_fields=("permit_type", "permit_sub_type"),
    valuation_field="valuation",
    square_footage_field="floor_area_l_a_building_code_definition",
    scope_fields=("work_description",),
)


# Added from a real onboard_jurisdiction.py run against DC's ArcGIS
# FeatureServer layer 17, then reviewed by hand -- the first jurisdiction
# onboarded through that tool. Two things the LLM's draft got wrong, caught
# by checking the full field list rather than trusting the draft: it
# proposed FEES_PAID for valuation_field, but this dataset has no real
# cost/valuation field at all (FEE_TYPE/FEES_PAID are the processing fee,
# not the project's reported cost -- a fee of $36 does not mean a $36
# project) -- left unmapped rather than storing a systematically wrong
# number. No square footage field exists either.
#
# permit_type_fields' "Other" cases are a genuine no-signal situation, not
# a taxonomy gap: DC's "Post Card" (fast-track) permits all show
# PERMIT_SUBTYPE_NAME="BUILDING" regardless of actual scope (a deck, a
# fence, an interior demo) -- too generic to safely map to any one
# category without misclassifying the others that share the same value.
#
# No point_fields needed -- FULL_ADDRESS already includes city/state/zip,
# and coordinates come from ArcGISFeatureSource's geometry flattening
# (this layer also happens to expose plain LATITUDE/LONGITUDE attribute
# fields, redundant with the geometry).
DC_MAPPING = FieldMapping(
    jurisdiction="dc",
    source_url="https://maps2.dcgis.dc.gov/dcgis/rest/services/FEEDS/DCRA/FeatureServer/17",
    permit_id_field="PERMIT_ID",
    address_fields=("FULL_ADDRESS",),
    date_fields=("ISSUE_DATE",),
    owner_name_fields=("OWNER_NAME",),
    contractor_name_fields=("PERMIT_APPLICANT",),
    permit_type_fields=("PERMIT_TYPE_NAME", "PERMIT_SUBTYPE_NAME", "PERMIT_CATEGORY_NAME"),
    scope_fields=("DESC_OF_WORK",),
)


SOURCES = {
    "chicago": SocrataAPISource(
        name="chicago",
        url="https://data.cityofchicago.org/api/v3/views/ydr8-5enu/query.json",
        date_column="issue_date",
        mapper_func=build_mapper(CHICAGO_MAPPING),
    ),
    "nyc": SocrataAPISource(
        name="nyc",
        url="https://data.cityofnewyork.us/api/v3/views/rbx6-tga4/query.json",
        date_column="issued_date",
        mapper_func=build_mapper(NYC_MAPPING),
        skip_sentinel_field="permit_id",
        skip_sentinel_value="Permit is no",
    ),
    "austin": SocrataAPISource(
        name="austin",
        url="https://data.austintexas.gov/api/v3/views/3syk-w9eu/query.json",
        date_column="issue_date",
        mapper_func=build_mapper(AUSTIN_MAPPING),
    ),
    "seattle": SocrataAPISource(
        name="seattle",
        url="https://data.seattle.gov/api/v3/views/76t5-zqzr/query.json",
        date_column="issueddate",
        mapper_func=build_mapper(SEATTLE_MAPPING),
    ),
    "la": SocrataAPISource(
        name="la",
        url="https://data.lacity.org/api/v3/views/xnhu-aczu/query.json",
        date_column="issue_date",
        mapper_func=build_mapper(LA_MAPPING),
    ),
    "dc": ArcGISFeatureSource(
        name="dc",
        url="https://maps2.dcgis.dc.gov/dcgis/rest/services/FEEDS/DCRA/FeatureServer/17",
        date_column="ISSUE_DATE",
        mapper_func=build_mapper(DC_MAPPING),
    ),
    "allen": PDFLedgerSource(
        name="allen",
        folder_path="./allen_pdfs",
        extraction_hints=(
            "You are an expert data extraction engine parsing a municipal ledger page.\n"
            "CRITICAL BLOCK-IDENTIFICATION RULES:\n"
            "1. Every distinct permit entry begins at the far left with a unique alpha-numeric Permit Number pattern "
            "(e.g., '000397-2026-CO', '000808-2026-CO*', '007623-2025-CB*').\n"
            "2. IGNORE the text color of the permit number—it may be RED or DARK BLUE depending on the work class category.\n"
            "3. Extract all permit classifications on the page, including 'Commercial Building - Alteration', "
            "'Certificate of Occupancy - C/O Stand Alone', 'Commercial Misc', etc.\n"
            "4. Disregard lines containing summary metrics or 'SUBTOTALS'."
        ),
    ),
    "naperville": PDFLedgerSource(
        name="naperville",
        folder_path="./naperville_pdfs"
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
