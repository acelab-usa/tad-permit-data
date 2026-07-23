"""Tests for dataloader.py's event batching -- both the API-source
enrichment path (chunked into ENRICH_BATCH_SIZE-sized permit:enrich_batch
events instead of one event per permit) and the PDF-source path (one
pdf:process_batch event per file, with the ingestion cursor advanced only
after a successful push).

Hatchet() validates a client token exists at construction time, which
dataloader.py does at module import -- set a dummy one before importing so
this works without real Hatchet credentials (dataloader.hatchet itself is
mocked in every test below anyway; nothing here makes a real Hatchet call)."""
import base64
import json
import os
import unittest
from unittest.mock import MagicMock, patch


def _fake_jwt() -> str:
    """Hatchet validates its client token looks like a real JWT (starts
    with "ey", three dot-separated segments, a middle segment decoding to
    JSON with sub/server_url/grpc_broadcast_address claims) at construction
    time -- even though nothing in these tests makes a real Hatchet call,
    dataloader.hatchet is mocked in every test below. This just satisfies
    that shape check so `import dataloader` succeeds."""
    def _b64(obj) -> str:
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).decode().rstrip("=")

    header = _b64({"alg": "none"})
    payload = _b64({"sub": "test-tenant", "server_url": "https://localhost:8080", "grpc_broadcast_address": "localhost:7070"})
    return f"{header}.{payload}.fakesignature"


os.environ.setdefault("HATCHET_CLIENT_TOKEN", _fake_jwt())

import dataloader


class ChunksTests(unittest.TestCase):
    def test_splits_into_even_chunks(self):
        self.assertEqual(list(dataloader._chunks([1, 2, 3, 4], 2)), [[1, 2], [3, 4]])

    def test_last_chunk_can_be_smaller(self):
        self.assertEqual(list(dataloader._chunks([1, 2, 3, 4, 5], 2)), [[1, 2], [3, 4], [5]])

    def test_empty_list_yields_nothing(self):
        self.assertEqual(list(dataloader._chunks([], 5)), [])

    def test_size_larger_than_list_yields_one_chunk(self):
        self.assertEqual(list(dataloader._chunks([1, 2], 10)), [[1, 2]])


def _make_api_source(records, jurisdiction="chicago"):
    source = MagicMock()
    source.name = jurisdiction
    source.fetch_raw_records.return_value = records
    source.map_to_schema.side_effect = lambda raw: raw
    source.should_skip.return_value = None
    return source


def _valid_permit_dict(permit_id, jurisdiction="chicago"):
    return {
        "permit_id": permit_id,
        "jurisdiction": jurisdiction,
        "source_url": "https://x",
        "source_format": "API",
        "address": "1 Main St",
        "permit_type_raw": "New",
        "permit_type_normalized": "New Construction",
        "raw_scope_of_work": f"scope for {permit_id}",
        "scope_summary": "scope",
    }


class IngestApiSourceBatchingTests(unittest.TestCase):
    def setUp(self):
        patcher = patch("dataloader.hatchet")
        self.mock_hatchet = patcher.start()
        self.addCleanup(patcher.stop)

        geo_patcher = patch("dataloader.geo.geocode_address", return_value=(None, None))
        geo_patcher.start()
        self.addCleanup(geo_patcher.stop)

    def test_all_new_permits_batch_into_a_single_event_under_the_batch_size(self):
        records = [_valid_permit_dict(f"P{i}") for i in range(5)]
        source = _make_api_source(records)

        with patch("dataloader.database.insert_permit", return_value=True):
            dataloader._ingest_api_source(source, size=100)

        self.mock_hatchet.event.push.assert_called_once()
        event_name, payload = self.mock_hatchet.event.push.call_args[0]
        self.assertEqual(event_name, "permit:enrich_batch")
        self.assertEqual(len(payload["permits"]), 5)
        self.assertEqual(payload["permits"][0]["permit_id"], "P0")

    def test_more_than_batch_size_splits_into_multiple_events(self):
        n = dataloader.ENRICH_BATCH_SIZE + 5
        records = [_valid_permit_dict(f"P{i}") for i in range(n)]
        source = _make_api_source(records)

        with patch("dataloader.database.insert_permit", return_value=True):
            dataloader._ingest_api_source(source, size=200)

        self.assertEqual(self.mock_hatchet.event.push.call_count, 2)
        sizes = [len(call.args[1]["permits"]) for call in self.mock_hatchet.event.push.call_args_list]
        self.assertEqual(sorted(sizes), sorted([dataloader.ENRICH_BATCH_SIZE, 5]))

    def test_duplicate_permits_are_not_enriched_and_push_nothing(self):
        records = [_valid_permit_dict("P0")]
        source = _make_api_source(records)

        with patch("dataloader.database.insert_permit", return_value=False):  # already existed
            dataloader._ingest_api_source(source, size=100)

        self.mock_hatchet.event.push.assert_not_called()

    def test_no_new_permits_pushes_no_events(self):
        source = _make_api_source([])
        dataloader._ingest_api_source(source, size=100)
        self.mock_hatchet.event.push.assert_not_called()


def _make_pdf_source(pages, name="allen", extraction_hints=None):
    source = MagicMock()
    source.name = name
    source.extraction_hints = extraction_hints
    source.iter_pages.return_value = iter(pages)
    return source


class IngestPdfSourceBatchingTests(unittest.TestCase):
    def setUp(self):
        patcher = patch("dataloader.hatchet")
        self.mock_hatchet = patcher.start()
        self.addCleanup(patcher.stop)

        cursor_patcher = patch("dataloader.database.get_pdf_cursor", return_value=(None, 0))
        cursor_patcher.start()
        self.addCleanup(cursor_patcher.stop)

        self.update_cursor = patch("dataloader.database.update_pdf_cursor").start()
        self.addCleanup(patch.stopall)

    def test_pages_from_one_file_batch_into_a_single_event(self):
        pages = [
            ("Allen - 2026-01.pdf", 1, "page 1 text"),
            ("Allen - 2026-01.pdf", 2, "page 2 text"),
            ("Allen - 2026-01.pdf", 3, "page 3 text"),
        ]
        source = _make_pdf_source(pages)

        dataloader._ingest_pdf_source(source, size=100)

        self.mock_hatchet.event.push.assert_called_once()
        event_name, payload = self.mock_hatchet.event.push.call_args[0]
        self.assertEqual(event_name, "pdf:process_batch")
        self.assertEqual(payload["source_pdf_name"], "Allen - 2026-01.pdf")
        self.assertEqual(len(payload["pages"]), 3)
        self.assertEqual([p["page_number"] for p in payload["pages"]], [1, 2, 3])

    def test_pages_spanning_two_files_produce_two_events(self):
        pages = [
            ("Allen - 2026-01.pdf", 1, "a"),
            ("Allen - 2026-01.pdf", 2, "b"),
            ("Allen - 2026-02.pdf", 1, "c"),
        ]
        source = _make_pdf_source(pages)

        dataloader._ingest_pdf_source(source, size=100)

        self.assertEqual(self.mock_hatchet.event.push.call_count, 2)
        names = [call.args[1]["source_pdf_name"] for call in self.mock_hatchet.event.push.call_args_list]
        self.assertEqual(names, ["Allen - 2026-01.pdf", "Allen - 2026-02.pdf"])

    def test_cursor_advances_to_the_last_page_of_each_file_after_a_successful_push(self):
        pages = [
            ("Allen - 2026-01.pdf", 1, "a"),
            ("Allen - 2026-01.pdf", 2, "b"),
            ("Allen - 2026-02.pdf", 1, "c"),
        ]
        source = _make_pdf_source(pages)

        dataloader._ingest_pdf_source(source, size=100)

        calls = [call.args for call in self.update_cursor.call_args_list]
        self.assertEqual(calls, [
            ("allen", "Allen - 2026-01.pdf", 2),
            ("allen", "Allen - 2026-02.pdf", 1),
        ])

    def test_failed_push_does_not_advance_the_cursor(self):
        pages = [("Allen - 2026-01.pdf", 1, "a")]
        source = _make_pdf_source(pages)
        self.mock_hatchet.event.push.side_effect = Exception("hatchet is down")

        dataloader._ingest_pdf_source(source, size=100)

        self.update_cursor.assert_not_called()

    def test_no_pages_pushes_no_events_and_does_not_touch_the_cursor(self):
        source = _make_pdf_source([])
        dataloader._ingest_pdf_source(source, size=100)
        self.mock_hatchet.event.push.assert_not_called()
        self.update_cursor.assert_not_called()

    def test_resumes_from_the_stored_cursor(self):
        with patch("dataloader.database.get_pdf_cursor", return_value=("Allen - 2026-01.pdf", 5)):
            source = _make_pdf_source([("Allen - 2026-01.pdf", 6, "resumed page")])
            dataloader._ingest_pdf_source(source, size=100)

        _, kwargs = source.iter_pages.call_args
        self.assertEqual(kwargs["start_filename"], "Allen - 2026-01.pdf")
        self.assertEqual(kwargs["start_page"], 5)


if __name__ == "__main__":
    unittest.main()
