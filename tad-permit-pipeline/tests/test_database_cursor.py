"""Tests for database.py's PDF ingestion cursor (get_pdf_cursor/
update_pdf_cursor), against a real temp SQLite DB."""
import importlib
import os
import tempfile
import unittest


class PdfCursorTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._db_path = os.path.join(self._tmpdir.name, "test_permits.db")

        import database
        self.database = importlib.reload(database)
        self.database.DB_PATH = self._db_path
        self.database.init_db()

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_no_cursor_yet_returns_none_and_zero(self):
        filename, page = self.database.get_pdf_cursor("allen")
        self.assertIsNone(filename)
        self.assertEqual(page, 0)

    def test_update_then_get_round_trips(self):
        self.database.update_pdf_cursor("allen", "Allen - 2026-01.pdf", 12)
        filename, page = self.database.get_pdf_cursor("allen")
        self.assertEqual(filename, "Allen - 2026-01.pdf")
        self.assertEqual(page, 12)

    def test_update_overwrites_the_same_jurisdiction(self):
        self.database.update_pdf_cursor("allen", "Allen - 2026-01.pdf", 12)
        self.database.update_pdf_cursor("allen", "Allen - 2026-01.pdf", 20)
        filename, page = self.database.get_pdf_cursor("allen")
        self.assertEqual(page, 20)

    def test_update_can_advance_to_a_new_file(self):
        self.database.update_pdf_cursor("allen", "Allen - 2026-01.pdf", 96)
        self.database.update_pdf_cursor("allen", "Allen - 2026-02.pdf", 3)
        filename, page = self.database.get_pdf_cursor("allen")
        self.assertEqual(filename, "Allen - 2026-02.pdf")
        self.assertEqual(page, 3)

    def test_cursors_are_independent_per_jurisdiction(self):
        self.database.update_pdf_cursor("allen", "Allen - 2026-01.pdf", 12)
        self.database.update_pdf_cursor("naperville", "Naperville - 2026-01.pdf", 5)

        self.assertEqual(self.database.get_pdf_cursor("allen"), ("Allen - 2026-01.pdf", 12))
        self.assertEqual(self.database.get_pdf_cursor("naperville"), ("Naperville - 2026-01.pdf", 5))


if __name__ == "__main__":
    unittest.main()
