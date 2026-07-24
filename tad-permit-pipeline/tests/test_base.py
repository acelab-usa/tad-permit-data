"""Tests for sources/base.py's validate_date_column -- the guard that
catches onboard_jurisdiction.py's unfilled "TODO_DATE_COLUMN" placeholder
before it reaches an adapter and fails only at ingestion time, three
retries deep, as a cryptic upstream API error."""
import unittest

from sources.base import validate_date_column


class ValidateDateColumnTests(unittest.TestCase):
    def test_real_column_name_passes_through(self):
        self.assertEqual(validate_date_column("issue_date", "denver"), "issue_date")

    def test_rejects_todo_placeholder(self):
        with self.assertRaises(ValueError):
            validate_date_column("TODO_DATE_COLUMN", "columbus")

    def test_rejects_todo_placeholder_case_insensitively(self):
        with self.assertRaises(ValueError):
            validate_date_column("todo_date_column", "columbus")

    def test_rejects_empty_string(self):
        with self.assertRaises(ValueError):
            validate_date_column("", "columbus")

    def test_error_message_names_the_source(self):
        with self.assertRaises(ValueError) as ctx:
            validate_date_column("TODO_DATE_COLUMN", "columbus")
        self.assertIn("columbus", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
