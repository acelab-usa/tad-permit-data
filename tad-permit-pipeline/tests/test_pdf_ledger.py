"""Tests for PDFLedgerSource.iter_pages()'s resume/spillover logic --
mocked at the pdf_processor.iter_pdf_pages() level (already covered against
a real PDF in tests/test_pdf_processor.py) so these can focus purely on the
file-selection/cursor mechanics: which file to resume into, and what
happens when it spills into the next one."""
import os
import tempfile
import unittest
from unittest.mock import patch

from sources.pdf_ledger import PDFLedgerSource


def _touch(folder: str, *filenames: str):
    for name in filenames:
        open(os.path.join(folder, name), "w").close()


class IterPagesResumeTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.folder = self._tmpdir.name
        self.source = PDFLedgerSource(name="test", folder_path=self.folder)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _fake_iter_pdf_pages_factory(self, pages_by_file: dict):
        """pages_by_file maps filename -> total page count. The fake mimics
        the real iter_pdf_pages's start_page/page_cap contract."""
        def fake(local_path, page_cap=None, start_page=0):
            filename = os.path.basename(local_path)
            total = pages_by_file[filename]
            end = total if page_cap is None else min(total, start_page + page_cap)
            for page_idx in range(start_page, end):
                yield page_idx + 1, f"{filename} page {page_idx + 1}"
        return fake

    def test_no_cursor_starts_from_first_file_page_one(self):
        # Zero-padded names so alphabetical sort matches intended order --
        # plain month names ("February" < "January") would sort wrong,
        # a separate pre-existing quirk unrelated to what's tested here.
        _touch(self.folder, "Allen - 2026-01.pdf", "Allen - 2026-02.pdf")
        fake = self._fake_iter_pdf_pages_factory({
            "Allen - 2026-01.pdf": 5, "Allen - 2026-02.pdf": 5,
        })
        with patch("sources.pdf_ledger.iter_pdf_pages", side_effect=fake):
            pages = list(self.source.iter_pages(month_cap=1, page_cap=3))

        self.assertEqual([p[:2] for p in pages], [
            ("Allen - 2026-01.pdf", 1),
            ("Allen - 2026-01.pdf", 2),
            ("Allen - 2026-01.pdf", 3),
        ])

    def test_resumes_partway_through_the_cursor_file(self):
        _touch(self.folder, "Allen - 2026-01.pdf")
        fake = self._fake_iter_pdf_pages_factory({"Allen - 2026-01.pdf": 10})
        with patch("sources.pdf_ledger.iter_pdf_pages", side_effect=fake):
            pages = list(self.source.iter_pages(
                month_cap=1, page_cap=3, start_filename="Allen - 2026-01.pdf", start_page=5
            ))

        # Resuming after page 5 (0-indexed start_page=5) -> pages 6,7,8
        self.assertEqual([p[1] for p in pages], [6, 7, 8])

    def test_exhausted_resume_file_spills_into_next_file_without_costing_month_cap(self):
        # The cursor file has no pages left -- this must not get stuck
        # re-selecting the same exhausted file forever; it should silently
        # move on to the next one within the same run.
        _touch(self.folder, "Allen - 2026-01.pdf", "Allen - 2026-02.pdf")
        fake = self._fake_iter_pdf_pages_factory({
            "Allen - 2026-01.pdf": 5, "Allen - 2026-02.pdf": 5,
        })
        with patch("sources.pdf_ledger.iter_pdf_pages", side_effect=fake):
            pages = list(self.source.iter_pages(
                month_cap=1, page_cap=3, start_filename="Allen - 2026-01.pdf", start_page=5
            ))

        self.assertEqual([p[:2] for p in pages], [
            ("Allen - 2026-02.pdf", 1),
            ("Allen - 2026-02.pdf", 2),
            ("Allen - 2026-02.pdf", 3),
        ])

    def test_month_cap_stops_after_n_files_that_actually_yielded_pages(self):
        _touch(self.folder, "A.pdf", "B.pdf", "C.pdf")
        fake = self._fake_iter_pdf_pages_factory({"A.pdf": 2, "B.pdf": 2, "C.pdf": 2})
        with patch("sources.pdf_ledger.iter_pdf_pages", side_effect=fake):
            pages = list(self.source.iter_pages(month_cap=2, page_cap=None))

        self.assertEqual(sorted(set(p[0] for p in pages)), ["A.pdf", "B.pdf"])

    def test_page_cap_budget_spans_multiple_files(self):
        # page_cap is a total budget across the whole run, not per-file --
        # once it exhausts file A, it should keep spending the remainder in
        # file B rather than stopping.
        _touch(self.folder, "A.pdf", "B.pdf")
        fake = self._fake_iter_pdf_pages_factory({"A.pdf": 2, "B.pdf": 5})
        with patch("sources.pdf_ledger.iter_pdf_pages", side_effect=fake):
            pages = list(self.source.iter_pages(month_cap=2, page_cap=4))

        self.assertEqual([p[:2] for p in pages], [
            ("A.pdf", 1), ("A.pdf", 2), ("B.pdf", 1), ("B.pdf", 2),
        ])

    def test_no_pdf_files_yields_nothing(self):
        self.assertEqual(list(self.source.iter_pages()), [])

    def test_missing_folder_is_created_and_yields_nothing(self):
        folder = os.path.join(self.folder, "does_not_exist_yet")
        source = PDFLedgerSource(name="test", folder_path=folder)
        self.assertEqual(list(source.iter_pages()), [])
        self.assertTrue(os.path.isdir(folder))


if __name__ == "__main__":
    unittest.main()
