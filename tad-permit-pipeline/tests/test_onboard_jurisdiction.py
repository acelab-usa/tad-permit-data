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
        base, resource_id = oj._parse_resource("https://data.lacity.org/resource/xnhu-aczu.json")
        self.assertEqual(base, "https://data.lacity.org")
        self.assertEqual(resource_id, "xnhu-aczu")

    def test_missing_resource_path_raises(self):
        with self.assertRaises(ValueError):
            oj._parse_resource("https://data.lacity.org/dataset/xnhu-aczu")

    def test_missing_scheme_raises(self):
        with self.assertRaises(ValueError):
            oj._parse_resource("data.lacity.org/resource/xnhu-aczu.json")


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


if __name__ == "__main__":
    unittest.main()
