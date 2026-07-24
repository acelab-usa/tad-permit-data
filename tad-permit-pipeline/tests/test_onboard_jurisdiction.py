"""Tests for onboard_jurisdiction.py -- the parts that don't require a live
Socrata host or a real OpenRouter key: URL parsing, converting an LLM's
proposed mapping into a real FieldMapping, and the review/flagging logic
that runs the proposal against sample records."""
import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import MagicMock, patch

import onboard_jurisdiction as oj
from models import ProposedFieldMapping


class ParseResourceTests(unittest.TestCase):
    def test_valid_url(self):
        base, resource_id = oj._parse_socrata_resource("https://data.lacity.org/resource/xnhu-aczu.json")
        self.assertEqual(base, "https://data.lacity.org")
        self.assertEqual(resource_id, "xnhu-aczu")

    def test_missing_resource_path_raises(self):
        with self.assertRaises(ValueError):
            oj._parse_socrata_resource("https://data.lacity.org/dataset/xnhu-aczu")

    def test_missing_scheme_raises(self):
        with self.assertRaises(ValueError):
            oj._parse_socrata_resource("data.lacity.org/resource/xnhu-aczu.json")


class IsArcgisUrlTests(unittest.TestCase):
    def test_detects_featureserver(self):
        self.assertTrue(oj._is_arcgis_url(
            "https://maps2.dcgis.dc.gov/dcgis/rest/services/FEEDS/DCRA/FeatureServer/17"
        ))

    def test_detects_mapserver(self):
        self.assertTrue(oj._is_arcgis_url(
            "https://maps.westfield.in.gov/arcgis/rest/services/CommunityDev/BuildingPermits/MapServer"
        ))

    def test_socrata_url_is_not_arcgis(self):
        self.assertFalse(oj._is_arcgis_url("https://data.lacity.org/resource/xnhu-aczu.json"))


class FetchDatasetTests(unittest.TestCase):
    def test_fetches_columns_and_samples(self):
        metadata = {
            "columns": [
                {"fieldName": "permit_number", "name": "Permit Number", "dataTypeName": "text", "description": "The case number"},
                {"fieldName": "issue_date", "name": "Issue Date", "dataTypeName": "calendar_date", "description": None},
            ]
        }
        samples = [{"permit_number": "X-1", "issue_date": "2026-01-01T00:00:00.000"}]

        def fake_get(url, params=None, timeout=None):
            response = MagicMock()
            response.raise_for_status.return_value = None
            if "api/views" in url:
                response.json.return_value = metadata
            else:
                response.json.return_value = samples
            return response

        with patch("onboard_jurisdiction.requests.get", side_effect=fake_get):
            columns, sample_records = oj.fetch_dataset(
                "https://data.denvergov.org/resource/xxxx.json", sample_size=1
            )

        self.assertEqual(len(columns), 2)
        self.assertEqual(columns[0]["fieldName"], "permit_number")
        self.assertEqual(sample_records, samples)

    def test_empty_sample_raises(self):
        def fake_get(url, params=None, timeout=None):
            response = MagicMock()
            response.raise_for_status.return_value = None
            response.json.return_value = {"columns": []} if "api/views" in url else []
            return response

        with patch("onboard_jurisdiction.requests.get", side_effect=fake_get):
            with self.assertRaises(ValueError):
                oj.fetch_dataset("https://data.denvergov.org/resource/xxxx.json", sample_size=1)


class FetchArcgisDatasetTests(unittest.TestCase):
    LAYER_URL = "https://maps2.dcgis.dc.gov/dcgis/rest/services/FEEDS/DCRA/FeatureServer/17"

    def test_dispatches_to_arcgis_and_flattens_features(self):
        layer_metadata = {
            "fields": [
                {"name": "PERMIT_NO", "alias": "Permit Number", "type": "esriFieldTypeString"},
                {"name": "ISSUE_DATE", "alias": "Issue Date", "type": "esriFieldTypeDate"},
            ]
        }
        query_result = {
            "features": [
                {"attributes": {"PERMIT_NO": "B2024-001", "ISSUE_DATE": 1700000000000},
                 "geometry": {"x": -77.02, "y": 38.9}},
            ]
        }

        calls = []

        def fake_get(url, params=None, timeout=None):
            calls.append((url, params))
            response = MagicMock()
            response.raise_for_status.return_value = None
            response.json.return_value = query_result if url.endswith("/query") else layer_metadata
            return response

        with patch("onboard_jurisdiction.requests.get", side_effect=fake_get):
            columns, sample_records = oj.fetch_dataset(self.LAYER_URL, sample_size=1)

        self.assertEqual(len(columns), 2)
        self.assertEqual(columns[0]["fieldName"], "PERMIT_NO")
        self.assertEqual(columns[1]["dataTypeName"], "esriFieldTypeDate")
        # Flattened: geometry merged in as plain lat/lon, same shape a
        # Socrata source would produce -- this is what lets propose_mapping/
        # review/to_field_mapping stay platform-agnostic.
        self.assertEqual(sample_records[0]["PERMIT_NO"], "B2024-001")
        self.assertEqual(sample_records[0]["latitude"], 38.9)
        self.assertEqual(sample_records[0]["longitude"], -77.02)

        # Without outSR=4326, ArcGIS returns geometry in the layer's native
        # (often projected) spatial reference instead of lat/lon degrees --
        # found via a real DC FeatureServer run where every coordinate
        # silently came back null in the preview because of exactly this.
        query_call_params = next(p for u, p in calls if u.endswith("/query"))
        self.assertEqual(query_call_params["outSR"], "4326")

    def test_error_response_raises(self):
        def fake_get(url, params=None, timeout=None):
            response = MagicMock()
            response.raise_for_status.return_value = None
            response.json.return_value = {"fields": []} if not url.endswith("/query") else {
                "error": {"code": 400, "message": "bad request"}
            }
            return response

        with patch("onboard_jurisdiction.requests.get", side_effect=fake_get):
            with self.assertRaises(ValueError):
                oj.fetch_dataset(self.LAYER_URL, sample_size=1)


class ToFieldMappingTests(unittest.TestCase):
    def test_converts_proposal_into_field_mapping(self):
        proposal = ProposedFieldMapping(
            permit_id_field="permit_number",
            address_fields=["address_line_1"],
            date_fields=["issue_date", "applied_date"],
            owner_name_fields=[],
            contractor_name_fields=["contractor"],
            permit_type_fields=["permit_type"],
            valuation_field="valuation",
            square_footage_field=None,
            scope_fields=["description"],
            point_fields=[],
            unmapped_notes="No owner field found.",
        )

        mapping = oj.to_field_mapping(proposal, jurisdiction="denver", source_url="https://x/resource/y.json")

        self.assertEqual(mapping.jurisdiction, "denver")
        self.assertEqual(mapping.permit_id_field, "permit_number")
        self.assertEqual(mapping.address_fields, ("address_line_1",))
        self.assertEqual(mapping.date_fields, ("issue_date", "applied_date"))
        self.assertEqual(mapping.owner_name_fields, ())
        self.assertEqual(mapping.contractor_name_fields, ("contractor",))
        self.assertEqual(mapping.valuation_field, "valuation")
        self.assertIsNone(mapping.square_footage_field)

    def test_missing_permit_id_field_becomes_empty_string(self):
        proposal = ProposedFieldMapping()
        mapping = oj.to_field_mapping(proposal, jurisdiction="denver", source_url="https://x")
        self.assertEqual(mapping.permit_id_field, "")


class ReviewTests(unittest.TestCase):
    def _run_review(self, mapping, sample_records):
        buf = io.StringIO()
        with redirect_stdout(buf):
            oj.review(mapping, sample_records)
        return buf.getvalue()

    def test_flags_unmapped_required_fields(self):
        from sources.field_mapping import FieldMapping

        mapping = FieldMapping(
            jurisdiction="denver",
            source_url="https://x",
            permit_id_field="",  # unmapped
            address_fields=(),
            date_fields=("issue_date",),
            permit_type_fields=("permit_type",),
        )
        output = self._run_review(mapping, [{"permit_type": "New Construction", "issue_date": "2026-01-01"}])
        self.assertIn("No candidate found for: permit_id_field, address_fields", output)
        self.assertIn("owner_name_fields is empty", output)
        self.assertIn("valuation_field is empty", output)

    def test_flags_taxonomy_gap_when_type_normalizes_to_other(self):
        from sources.field_mapping import FieldMapping

        mapping = FieldMapping(
            jurisdiction="denver",
            source_url="https://x",
            permit_id_field="permit_number",
            address_fields=("address",),
            date_fields=("issue_date",),
            permit_type_fields=("permit_type",),
        )
        samples = [{"permit_number": "1", "address": "1 Main St", "issue_date": "2026-01-01", "permit_type": "Zorp-Blorp"}]
        output = self._run_review(mapping, samples)
        self.assertIn("normalized to permit_type 'Other'", output)
        self.assertIn("permit_types.py", output)
        # The actual raw value(s) considered should be printed, not just the
        # count -- found via a real DC run where "Other" alone wasn't enough
        # to tell a taxonomy gap apart from genuinely no signal.
        self.assertIn("Zorp-Blorp", output)

    def test_flags_valuation_field_that_looks_like_a_fee(self):
        from sources.field_mapping import FieldMapping

        mapping = FieldMapping(
            jurisdiction="dc",
            source_url="https://x",
            permit_id_field="permit_number",
            address_fields=("address",),
            date_fields=("issue_date",),
            permit_type_fields=("permit_type",),
            valuation_field="FEES_PAID",
        )
        samples = [{
            "permit_number": "1", "address": "1 Main St", "issue_date": "2026-01-01",
            "permit_type": "New Construction", "FEES_PAID": "36.00",
        }]
        output = self._run_review(mapping, samples)
        self.assertIn("looks like it might be a processing FEE", output)
        self.assertNotIn("valuation_field is empty", output)  # it IS set, just suspect

    def test_no_flags_when_everything_maps_cleanly(self):
        from sources.field_mapping import FieldMapping

        mapping = FieldMapping(
            jurisdiction="denver",
            source_url="https://x",
            permit_id_field="permit_number",
            address_fields=("address",),
            date_fields=("issue_date",),
            owner_name_fields=("owner",),
            valuation_field="valuation",
            permit_type_fields=("permit_type",),
        )
        samples = [{
            "permit_number": "1", "address": "1 Main St", "issue_date": "2026-01-01",
            "owner": "Jane Doe", "valuation": "1000", "permit_type": "New Construction",
        }]
        output = self._run_review(mapping, samples)
        self.assertIn("All required fields", output)
        self.assertNotIn("owner_name_fields is empty", output)
        self.assertNotIn("valuation_field is empty", output)
        self.assertNotIn("'Other'", output)


class ProposeMappingTests(unittest.TestCase):
    def test_parses_valid_llm_response(self):
        fake_response = MagicMock()
        fake_response.choices = [MagicMock(message=MagicMock(content=ProposedFieldMapping(
            permit_id_field="permit_number",
            address_fields=["address"],
            date_fields=["issue_date"],
            permit_type_fields=["permit_type"],
        ).model_dump_json()))]

        with patch("onboard_jurisdiction.client.chat.completions.create", return_value=fake_response):
            proposal = oj.propose_mapping(columns=[], sample_record={"permit_number": "1"})

        self.assertEqual(proposal.permit_id_field, "permit_number")
        self.assertEqual(proposal.address_fields, ["address"])

    def test_malformed_llm_response_raises(self):
        fake_response = MagicMock()
        fake_response.choices = [MagicMock(message=MagicMock(content="not valid json"))]

        with patch("onboard_jurisdiction.client.chat.completions.create", return_value=fake_response):
            with self.assertRaises(RuntimeError):
                oj.propose_mapping(columns=[], sample_record={})


class ReviewVerbosityTests(unittest.TestCase):
    """review() defaults to a compact one-line-per-sample summary; the full
    per-sample JSON dump is opt-in via verbose=True."""

    def _mapping(self):
        from sources.field_mapping import FieldMapping
        return FieldMapping(
            jurisdiction="dc",
            source_url="https://x",
            permit_id_field="permit_id",
            address_fields=("address",),
            date_fields=("issue_date",),
            permit_type_fields=("permit_type",),
            valuation_field="valuation",
            scope_fields=("raw_scope_of_work",),
        )

    def _sample(self):
        return [{
            "permit_id": "G123", "address": "1 Main St", "issue_date": "2026-01-01",
            "permit_type": "New Construction", "valuation": "50000",
            "raw_scope_of_work": "a very long description that should not appear by default" * 3,
        }]

    def test_default_is_compact_one_liner(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            oj.review(self._mapping(), self._sample())
        output = buf.getvalue()
        self.assertIn("[1] G123 | 1 Main St | 2026-01-01 | New Construction -> New Construction | $50,000 | (no coords)", output)
        self.assertNotIn("a very long description", output)
        self.assertNotIn("--- Sample 1 ---", output)

    def test_verbose_prints_full_json(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            oj.review(self._mapping(), self._sample(), verbose=True)
        output = buf.getvalue()
        self.assertIn("--- Sample 1 ---", output)
        self.assertIn("a very long description", output)


class FormatSourceEntryTests(unittest.TestCase):
    def _mapping(self, **overrides):
        from sources.field_mapping import FieldMapping
        kwargs = dict(
            jurisdiction="denver",
            source_url="https://data.denvergov.org/resource/xxxx.json",
            permit_id_field="permit_number",
            address_fields=("address",),
            date_fields=("issue_date",),
            permit_type_fields=("permit_type",),
        )
        kwargs.update(overrides)
        return FieldMapping(**kwargs)

    def test_socrata_entry(self):
        entry = oj.format_source_entry(
            self._mapping(), "https://data.denvergov.org/resource/xxxx.json", "denver", "DENVER_MAPPING"
        )
        self.assertIn('"denver": SocrataAPISource(', entry)
        self.assertIn('url="https://data.denvergov.org/api/v3/views/xxxx/query.json"', entry)
        self.assertIn('date_column="issue_date"', entry)
        self.assertIn("mapper_func=build_mapper(DENVER_MAPPING)", entry)

    def test_arcgis_entry(self):
        layer_url = "https://maps2.dcgis.dc.gov/dcgis/rest/services/FEEDS/DCRA/FeatureServer/17"
        entry = oj.format_source_entry(self._mapping(), layer_url, "dc", "DC_MAPPING")
        self.assertIn('"dc": ArcGISFeatureSource(', entry)
        self.assertIn(f'url="{layer_url}"', entry)
        self.assertIn("mapper_func=build_mapper(DC_MAPPING)", entry)

    def test_missing_date_fields_leaves_a_todo_placeholder(self):
        mapping = self._mapping(date_fields=())
        entry = oj.format_source_entry(mapping, "https://x/resource/y.json", "x", "X_MAPPING")
        self.assertIn("TODO_DATE_COLUMN", entry)


if __name__ == "__main__":
    unittest.main()
