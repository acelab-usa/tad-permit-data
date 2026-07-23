"""Tests for workflow.py's batch enrichment/PDF-extraction tasks -- the
worker side of the event batching in dataloader.py. Verifies a batch with
one bad item doesn't fail the others (each item gets its own try/except in
the loop, same as the per-permit DB-write loop parse_ledger_page_batch
already had before batching).

Calls the underlying function via Hatchet's `.fn` (the @task decorator
wraps it into a non-callable Task object) -- this logs a
"fn is internal" DeprecationWarning from the SDK, which is expected and
safe to ignore; there's no supported alternative for invoking a Hatchet
task directly without running a full worker."""
import base64
import json
import os
import unittest
from unittest.mock import MagicMock, patch


def _fake_jwt() -> str:
    """See tests/test_dataloader.py for why this is needed -- Hatchet()
    validates its client token's shape at construction time."""
    def _b64(obj) -> str:
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).decode().rstrip("=")

    header = _b64({"alg": "none"})
    payload = _b64({"sub": "test-tenant", "server_url": "https://localhost:8080", "grpc_broadcast_address": "localhost:7070"})
    return f"{header}.{payload}.fakesignature"


os.environ.setdefault("HATCHET_CLIENT_TOKEN", _fake_jwt())

import workflow


class EnrichBatchTests(unittest.TestCase):
    def _input(self, permits):
        return workflow.EnrichBatchInput(permits=[workflow.EnrichItem(**p) for p in permits])

    def test_all_succeed(self):
        enriched = MagicMock(scope_summary="a summary", building_systems=["HVAC"])
        with patch("workflow.llm_processor.enrich_permit_text", return_value=enriched), \
             patch("workflow.database.get_connection") as mock_conn:
            result = workflow.process_llm_enrichment_batch.fn(
                self._input([{"permit_id": "P1", "raw_text": "desc 1"}, {"permit_id": "P2", "raw_text": "desc 2"}]),
                ctx=None,
            )

        self.assertEqual(result, {"succeeded": 2, "failed": 0, "skipped": 0})
        self.assertEqual(mock_conn.return_value.cursor.return_value.execute.call_count, 2)

    def test_one_bad_item_does_not_fail_the_batch(self):
        enriched = MagicMock(scope_summary="a summary", building_systems=[])

        def fake_enrich(raw_text):
            if raw_text == "bad":
                return None  # simulates an LLM/parse failure
            return enriched

        with patch("workflow.llm_processor.enrich_permit_text", side_effect=fake_enrich), \
             patch("workflow.database.get_connection"):
            result = workflow.process_llm_enrichment_batch.fn(
                self._input([
                    {"permit_id": "P1", "raw_text": "good"},
                    {"permit_id": "P2", "raw_text": "bad"},
                    {"permit_id": "P3", "raw_text": "good"},
                ]),
                ctx=None,
            )

        self.assertEqual(result, {"succeeded": 2, "failed": 1, "skipped": 0})

    def test_empty_raw_text_is_skipped_not_failed(self):
        with patch("workflow.llm_processor.enrich_permit_text") as mock_enrich, \
             patch("workflow.database.get_connection"):
            result = workflow.process_llm_enrichment_batch.fn(
                self._input([{"permit_id": "P1", "raw_text": "   "}]), ctx=None,
            )

        mock_enrich.assert_not_called()
        self.assertEqual(result, {"succeeded": 0, "failed": 0, "skipped": 1})

    def test_empty_batch(self):
        result = workflow.process_llm_enrichment_batch.fn(self._input([]), ctx=None)
        self.assertEqual(result, {"succeeded": 0, "failed": 0, "skipped": 0})


class PdfBatchTests(unittest.TestCase):
    def _input(self, pages, jurisdiction="allen", filename="Allen - 2026-01.pdf", hints=None):
        return workflow.PageBatchIngestionInput(
            jurisdiction=jurisdiction,
            source_pdf_name=filename,
            pages=[workflow.PageItem(**p) for p in pages],
            extraction_hints=hints,
        )

    def _extraction_result(self, permit_ids):
        permits = [
            MagicMock(
                permit_id=pid, address="1 Main St", filing_date=None, permit_type_raw="New",
                owner_name=None, contractor_name=None, valuation=None, square_footage=None,
                raw_scope_of_work="scope", scope_summary="scope", building_systems=[],
            )
            for pid in permit_ids
        ]
        return MagicMock(permits_found=permits)

    def test_pages_batch_and_aggregate_counts(self):
        with patch("workflow.llm_processor.extract_multiple_permits_from_text") as mock_extract, \
             patch("workflow.geo.geocode_address", return_value=(None, None)), \
             patch("workflow.database.get_connection") as mock_conn:
            mock_conn.return_value.cursor.return_value.rowcount = 1
            mock_extract.side_effect = [self._extraction_result(["P1"]), self._extraction_result(["P2", "P3"])]

            result = workflow.parse_ledger_page_batch.fn(
                self._input([{"page_number": 1, "page_text": "page 1"}, {"page_number": 2, "page_text": "page 2"}]),
                ctx=None,
            )

        self.assertEqual(result, {"permits_inserted": 3, "permits_failed": 0})
        self.assertEqual(mock_extract.call_count, 2)

    def test_one_bad_page_does_not_fail_the_batch(self):
        with patch("workflow.llm_processor.extract_multiple_permits_from_text") as mock_extract, \
             patch("workflow.geo.geocode_address", return_value=(None, None)), \
             patch("workflow.database.get_connection") as mock_conn:
            mock_conn.return_value.cursor.return_value.rowcount = 1
            mock_extract.side_effect = [Exception("LLM blew up"), self._extraction_result(["P2"])]

            result = workflow.parse_ledger_page_batch.fn(
                self._input([{"page_number": 1, "page_text": "bad page"}, {"page_number": 2, "page_text": "good page"}]),
                ctx=None,
            )

        self.assertEqual(result, {"permits_inserted": 1, "permits_failed": 0})

    def test_no_permits_found_on_any_page(self):
        with patch("workflow.llm_processor.extract_multiple_permits_from_text", return_value=None):
            result = workflow.parse_ledger_page_batch.fn(
                self._input([{"page_number": 1, "page_text": "empty page"}]), ctx=None,
            )
        self.assertEqual(result, {"permits_inserted": 0, "permits_failed": 0})

    def test_extraction_hints_are_passed_through(self):
        with patch("workflow.llm_processor.extract_multiple_permits_from_text", return_value=None) as mock_extract:
            workflow.parse_ledger_page_batch.fn(
                self._input([{"page_number": 1, "page_text": "text"}], hints="some hint"), ctx=None,
            )
        mock_extract.assert_called_once_with("text", extraction_hints="some hint")


if __name__ == "__main__":
    unittest.main()
