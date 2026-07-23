"""Tests for pdf_processor.iter_pdf_pages()'s start_page/page_cap behavior,
against a real generated PDF (not mocked) since this is the actual PyMuPDF
integration point."""
import os
import tempfile
import unittest

import fitz

from pdf_processor import iter_pdf_pages


def _make_pdf(path: str, page_count: int):
    doc = fitz.open()
    for i in range(page_count):
        page = doc.new_page()
        page.insert_text((72, 72), f"Page {i + 1} content")
    doc.save(path)
    doc.close()


class IterPdfPagesTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.pdf_path = os.path.join(self._tmpdir.name, "test.pdf")
        _make_pdf(self.pdf_path, page_count=10)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_reads_from_the_start_by_default(self):
        pages = list(iter_pdf_pages(self.pdf_path))
        self.assertEqual([p[0] for p in pages], list(range(1, 11)))
        self.assertIn("Page 1 content", pages[0][1])

    def test_page_cap_limits_from_the_start(self):
        pages = list(iter_pdf_pages(self.pdf_path, page_cap=3))
        self.assertEqual([p[0] for p in pages], [1, 2, 3])

    def test_start_page_resumes_partway_through(self):
        # start_page=5 (0-indexed) should resume at page 6, not restart at 1
        # -- this is the fix for scheduled re-runs re-reading (and
        # re-queuing a Hatchet event for) pages already processed.
        pages = list(iter_pdf_pages(self.pdf_path, start_page=5))
        self.assertEqual([p[0] for p in pages], [6, 7, 8, 9, 10])

    def test_start_page_and_page_cap_combine(self):
        pages = list(iter_pdf_pages(self.pdf_path, page_cap=2, start_page=5))
        self.assertEqual([p[0] for p in pages], [6, 7])

    def test_start_page_past_the_end_yields_nothing(self):
        # This is what makes a fully-exhausted file safe to resume against
        # -- it just yields nothing rather than erroring.
        pages = list(iter_pdf_pages(self.pdf_path, start_page=10))
        self.assertEqual(pages, [])

    def test_start_page_past_the_end_with_cap_yields_nothing(self):
        pages = list(iter_pdf_pages(self.pdf_path, page_cap=5, start_page=20))
        self.assertEqual(pages, [])


if __name__ == "__main__":
    unittest.main()
