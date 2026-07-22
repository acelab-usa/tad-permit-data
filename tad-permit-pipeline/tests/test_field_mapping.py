"""Regression tests for the declarative Socrata field-mapping adapter
(sources/field_mapping.py).

Chicago/NYC/Austin used to each have a hand-written map_*_to_schema
function; sources/registry.py now builds their mappers from a declarative
FieldMapping instead. The three _original_map_*_to_schema functions below
are frozen copies of that pre-refactor code, kept only so these tests can
diff the new generic mapper's output against the exact old behavior on
realistic synthetic records -- not because they're used anywhere else.

Run with: uv run python -m unittest discover tests
"""
import unittest
from datetime import datetime
from typing import Optional

from geo import extract_lat_lon
from permit_types import normalize_permit_type
from sources.field_mapping import build_mapper
from sources.registry import (
    AUSTIN_MAPPING,
    CHICAGO_MAPPING,
    LA_MAPPING,
    NYC_MAPPING,
    SEATTLE_MAPPING,
    _GEO_POINT_FIELDS,
)

PERMIT_TYPE_TAXONOMY = frozenset({
    "New Construction", "Alteration", "Demolition", "Electrical", "Plumbing",
    "Mechanical", "Roofing", "Certificate of Occupancy", "Sign",
    "Fire/Life Safety", "Other",
})


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
    date_str = str(raw_date).split("T")[0].strip()
    return datetime.strptime(date_str, "%Y-%m-%d").date()


def _original_map_chicago_to_schema(raw_item: dict) -> dict:
    parsed_date = _safe_date(raw_item.get("issue_date"))
    address_parts = [
        raw_item.get("street_number") or "",
        raw_item.get("street_direction") or "",
        raw_item.get("street_name") or "",
        raw_item.get("suffix") or "",
    ]
    latitude, longitude = extract_lat_lon(raw_item, point_fields=_GEO_POINT_FIELDS)
    return {
        "permit_id": raw_item.get("permit_"),
        "jurisdiction": "chicago",
        "source_url": "https://data.cityofchicago.org/resource/ydr8-56us.json",
        "source_format": "API",
        "address": " ".join(p for p in address_parts if p).strip() or "UNKNOWN",
        "filing_date": parsed_date,
        "owner_name": raw_item.get("contact_1_name"),
        "contractor_name": raw_item.get("contact_2_name"),
        "latitude": latitude,
        "longitude": longitude,
        "permit_type_raw": raw_item.get("permit_type", "UNKNOWN"),
        "permit_type_normalized": normalize_permit_type(raw_item.get("permit_type")),
        "square_footage": None,
        "valuation": _safe_float(raw_item.get("reported_cost")),
        "raw_scope_of_work": raw_item.get("work_description") or "No description provided.",
        "scope_summary": (raw_item.get("work_description") or "No description provided.")[:150],
        "building_systems": [],
    }


def _original_map_nyc_to_schema(raw_item: dict) -> dict:
    raw_date = raw_item.get("issued_date") or raw_item.get("approved_date")
    parsed_date = _safe_date(raw_date)
    house_num = (raw_item.get("house_no") or "").strip()
    street_name = (raw_item.get("street_name") or "").strip()
    full_address = f"{house_num} {street_name}".strip()
    latitude, longitude = extract_lat_lon(raw_item, point_fields=_GEO_POINT_FIELDS)
    return {
        "permit_id": raw_item.get("job_filing_number"),
        "jurisdiction": "nyc",
        "source_url": "https://a810-dobnow.nyc.gov/html/",
        "source_format": "API",
        "address": full_address or "UNKNOWN",
        "filing_date": parsed_date,
        "owner_name": raw_item.get("owner_name"),
        "contractor_name": raw_item.get("licensee_s_business_name"),
        "latitude": latitude,
        "longitude": longitude,
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


def _original_map_austin_to_schema(raw_item: dict) -> dict:
    parsed_date = _safe_date(raw_item.get("issue_date"))
    raw_scope = (
        raw_item.get("description")
        or raw_item.get("project_name")
        or "No description provided."
    )
    latitude, longitude = extract_lat_lon(raw_item, point_fields=_GEO_POINT_FIELDS)
    return {
        "permit_id": raw_item.get("permit_number"),
        "jurisdiction": "austin",
        "source_url": "https://data.austintexas.gov/resource/3syk-w9eu.json",
        "source_format": "API",
        "address": (raw_item.get("original_address1") or "").strip() or "UNKNOWN",
        "filing_date": parsed_date,
        "owner_name": None,
        "contractor_name": raw_item.get("contractor_company_name") or raw_item.get("contractor_name"),
        "latitude": latitude,
        "longitude": longitude,
        "permit_type_raw": raw_item.get("work_class") or "UNKNOWN",
        "permit_type_normalized": normalize_permit_type(raw_item.get("work_class"), raw_item.get("permit_class_mapped")),
        "square_footage": _safe_float(raw_item.get("total_lot_sq_ft")),
        "valuation": _safe_float(raw_item.get("total_job_valuation")),
        "raw_scope_of_work": raw_scope,
        "scope_summary": raw_scope[:150],
        "building_systems": [],
    }


class ChicagoRegressionTests(unittest.TestCase):
    def _cases(self):
        return [
            {
                "permit_": "100987654",
                "street_number": "400",
                "street_direction": "N",
                "street_name": "STATE",
                "suffix": "ST",
                "issue_date": "2026-03-01T00:00:00.000",
                "contact_1_name": "Jane Owner",
                "contact_2_name": "Acme Contracting",
                "permit_type": "PERMIT - RENOVATION/ALTERATION",
                "reported_cost": "125000",
                "work_description": "Interior buildout for retail tenant space.",
            },
            # Missing/blank optional fields.
            {"permit_": "100000001", "issue_date": None},
        ]

    def test_matches_original(self):
        mapper = build_mapper(CHICAGO_MAPPING)
        for raw_item in self._cases():
            with self.subTest(raw_item=raw_item):
                self.assertEqual(mapper(raw_item), _original_map_chicago_to_schema(raw_item))


class NycRegressionTests(unittest.TestCase):
    def _cases(self):
        return [
            {
                "job_filing_number": "M00012345",
                "house_no": "123",
                "street_name": "BROADWAY",
                "issued_date": "2026-02-10T00:00:00.000",
                "owner_name": "Broadway Holdings LLC",
                "licensee_s_business_name": "Metro Contracting Inc",
                "work_type": "Plumbing",
                "filing_reason": "Initial Permit",
                "estimated_job_costs": "45000",
                "work_on_floor": "3",
                "job_description": "Replace risers and fixtures.",
            },
            # issued_date missing -> falls back to approved_date.
            {
                "job_filing_number": "M00099999",
                "approved_date": "2026-01-05T00:00:00.000",
                "filing_reason": "Renewal Permit Without Changes",
            },
        ]

    def test_matches_original(self):
        mapper = build_mapper(NYC_MAPPING)
        for raw_item in self._cases():
            with self.subTest(raw_item=raw_item):
                self.assertEqual(mapper(raw_item), _original_map_nyc_to_schema(raw_item))


class AustinRegressionTests(unittest.TestCase):
    def _cases(self):
        return [
            {
                "permit_number": "2026-012345-BP",
                "original_address1": "512 Congress Ave",
                "issue_date": "2026-04-12T00:00:00.000",
                "contractor_company_name": "Lone Star Builders",
                "work_class": "New",
                "permit_class_mapped": "Commercial",
                "total_lot_sq_ft": "8500",
                "total_job_valuation": "2200000",
                "description": "New retail construction.",
            },
            # description missing -> falls back to project_name.
            {
                "permit_number": "2026-000001-BP",
                "original_address1": "1 Barton Springs Rd",
                "project_name": "Barton Springs Renovation",
                "contractor_name": "Solo Contractor",
            },
        ]

    def test_matches_original(self):
        mapper = build_mapper(AUSTIN_MAPPING)
        for raw_item in self._cases():
            with self.subTest(raw_item=raw_item):
                self.assertEqual(mapper(raw_item), _original_map_austin_to_schema(raw_item))


class SeattleMappingTests(unittest.TestCase):
    """Seattle is new (no prior implementation to diff against), so these
    check the mapper against a real sample record instead
    (data.seattle.gov/resource/76t5-zqzr.json)."""

    def test_real_sample_record(self):
        raw_item = {
            "permitnum": "6068060-CN",
            "permitclass": "Multifamily",
            "permitclassmapped": "Residential",
            "permittypemapped": "Building",
            "permittypedesc": "New",
            "description": (
                "Establish use as townhouses  construct a four unit "
                "townhouse building with attached garages   per plans."
            ),
            "estprojectcost": "574026.0000",
            "applieddate": "2006-03-16T00:00:00.000",
            "issueddate": "2006-10-20T00:00:00.000",
            "originaladdress1": "4705 SAND POINT WAY NE",
            "originalcity": "SEATTLE",
            "originalstate": "WA",
            "originalzip": "98105",
            "latitude": "47.66366070",
            "longitude": "-122.28454211",
        }
        mapped = build_mapper(SEATTLE_MAPPING)(raw_item)

        self.assertEqual(mapped["permit_id"], "6068060-CN")
        self.assertEqual(mapped["jurisdiction"], "seattle")
        self.assertEqual(mapped["address"], "4705 SAND POINT WAY NE, SEATTLE, WA, 98105")
        self.assertEqual(mapped["filing_date"].isoformat(), "2006-10-20")
        self.assertIsNone(mapped["owner_name"])
        self.assertIsNone(mapped["contractor_name"])
        self.assertIsNone(mapped["square_footage"])
        self.assertEqual(mapped["valuation"], 574026.0)
        self.assertEqual(mapped["permit_type_raw"], "New")
        self.assertIn(mapped["permit_type_normalized"], PERMIT_TYPE_TAXONOMY)
        self.assertEqual(mapped["permit_type_normalized"], "New Construction")
        self.assertAlmostEqual(mapped["latitude"], 47.66366070)
        self.assertAlmostEqual(mapped["longitude"], -122.28454211)
        self.assertTrue(mapped["raw_scope_of_work"].startswith("Establish use as townhouses"))
        self.assertLessEqual(len(mapped["scope_summary"]), 150)

    def test_missing_optional_fields(self):
        mapped = build_mapper(SEATTLE_MAPPING)({"permitnum": "X", "originaladdress1": "1 Main St"})
        self.assertEqual(mapped["permit_type_raw"], "UNKNOWN")
        self.assertEqual(mapped["permit_type_normalized"], "Other")
        self.assertIsNone(mapped["valuation"])
        self.assertIsNone(mapped["filing_date"])


class LaMappingTests(unittest.TestCase):
    """LA is new (no prior implementation to diff against), so these check
    the mapper against a real sample record instead
    (data.lacity.org/resource/xnhu-aczu.json)."""

    def test_real_sample_record(self):
        raw_item = {
            "pcis_permit": "18010-20000-03298",
            "reference_old_permit": "18VN77515",
            "latest_status": "CofO Issued",
            "status_date": "2020-01-23T00:00:00.000",
            "permit_type": "Bldg-New",
            "permit_sub_type": "1 or 2 Family Dwelling",
            "permit_category": "Plan Check",
            "issue_date": "2018-09-26T00:00:00.000",
            "address_start": "7806",
            "address_end": "7806",
            "street_direction": "N",
            "street_name": "ARVILLA",
            "street_suffix": "AVE",
            "zip_code": "91352",
            "work_description": (
                "NEW 27.25' X 46.25'ACCESSORY DWELLING UNIT PER AB 494 & SB 229. ALL WO"
            ),
            "valuation": "121200",
            "floor_area_l_a_zoning_code_definition": "1200",
            "floor_area_l_a_building_code_definition": "1200",
            "contractors_business_name": "OWNER-BUILDER",
            "applicant_first_name": "LEVIK",
        }
        mapped = build_mapper(LA_MAPPING)(raw_item)

        self.assertEqual(mapped["permit_id"], "18010-20000-03298")
        self.assertEqual(mapped["jurisdiction"], "la")
        self.assertEqual(mapped["address"], "7806 N ARVILLA AVE 91352")
        self.assertEqual(mapped["filing_date"].isoformat(), "2018-09-26")
        self.assertIsNone(mapped["owner_name"])
        self.assertEqual(mapped["contractor_name"], "OWNER-BUILDER")
        self.assertEqual(mapped["square_footage"], 1200.0)
        self.assertEqual(mapped["valuation"], 121200.0)
        self.assertEqual(mapped["permit_type_raw"], "Bldg-New")
        self.assertIn(mapped["permit_type_normalized"], PERMIT_TYPE_TAXONOMY)
        self.assertEqual(mapped["permit_type_normalized"], "New Construction")
        # No geometry field in this dataset at all -- coordinates come
        # entirely from the geo.geocode_address() fallback, not extraction.
        self.assertIsNone(mapped["latitude"])
        self.assertIsNone(mapped["longitude"])
        self.assertTrue(mapped["raw_scope_of_work"].startswith("NEW 27.25"))
        self.assertLessEqual(len(mapped["scope_summary"]), 150)

    def test_missing_optional_fields(self):
        mapped = build_mapper(LA_MAPPING)({"pcis_permit": "X", "address_start": "1", "street_name": "MAIN"})
        self.assertEqual(mapped["permit_type_raw"], "UNKNOWN")
        self.assertEqual(mapped["permit_type_normalized"], "Other")
        self.assertIsNone(mapped["valuation"])
        self.assertIsNone(mapped["square_footage"])
        self.assertIsNone(mapped["filing_date"])
        self.assertEqual(mapped["address"], "1 MAIN")


if __name__ == "__main__":
    unittest.main()
