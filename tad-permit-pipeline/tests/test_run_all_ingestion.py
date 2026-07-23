"""Tests for run_all_ingestion.py -- per-jurisdiction isolation (one
unexpected failure shouldn't stop the rest) and the succeeded/failed
summary it returns."""
import base64
import json
import os
import unittest
from unittest.mock import patch


def _fake_jwt() -> str:
    """See tests/test_dataloader.py for why this is needed -- importing
    run_all_ingestion pulls in dataloader, which constructs a Hatchet()
    client at module load time."""
    def _b64(obj) -> str:
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).decode().rstrip("=")

    header = _b64({"alg": "none"})
    payload = _b64({"sub": "test-tenant", "server_url": "https://localhost:8080", "grpc_broadcast_address": "localhost:7070"})
    return f"{header}.{payload}.fakesignature"


os.environ.setdefault("HATCHET_CLIENT_TOKEN", _fake_jwt())

import run_all_ingestion


class RunAllTests(unittest.TestCase):
    def test_calls_load_data_for_every_jurisdiction(self):
        with patch("run_all_ingestion.load_data") as mock_load:
            result = run_all_ingestion.run_all(["chicago", "nyc", "dc"], size=50)

        self.assertEqual(mock_load.call_count, 3)
        mock_load.assert_any_call("chicago", size=50)
        mock_load.assert_any_call("nyc", size=50)
        mock_load.assert_any_call("dc", size=50)
        self.assertEqual(result, {"succeeded": ["chicago", "nyc", "dc"], "failed": []})

    def test_one_jurisdiction_failing_does_not_stop_the_rest(self):
        def fake_load(jurisdiction, size):
            if jurisdiction == "nyc":
                raise Exception("boom")

        with patch("run_all_ingestion.load_data", side_effect=fake_load):
            result = run_all_ingestion.run_all(["chicago", "nyc", "dc"], size=100)

        self.assertEqual(result, {"succeeded": ["chicago", "dc"], "failed": ["nyc"]})

    def test_all_failing_still_attempts_every_jurisdiction(self):
        with patch("run_all_ingestion.load_data", side_effect=Exception("boom")):
            result = run_all_ingestion.run_all(["chicago", "nyc"], size=100)

        self.assertEqual(result, {"succeeded": [], "failed": ["chicago", "nyc"]})

    def test_empty_jurisdiction_list(self):
        with patch("run_all_ingestion.load_data") as mock_load:
            result = run_all_ingestion.run_all([], size=100)

        mock_load.assert_not_called()
        self.assertEqual(result, {"succeeded": [], "failed": []})


class ParseArgsTests(unittest.TestCase):
    def test_default_size(self):
        with patch("sys.argv", ["run_all_ingestion.py"]):
            args = run_all_ingestion._parse_args()
        self.assertEqual(args.size, 100)
        self.assertIsNone(args.jurisdictions)

    def test_jurisdictions_override(self):
        with patch("sys.argv", ["run_all_ingestion.py", "--jurisdictions", "dc,la", "--size", "25"]):
            args = run_all_ingestion._parse_args()
        self.assertEqual(args.jurisdictions, "dc,la")
        self.assertEqual(args.size, 25)


if __name__ == "__main__":
    unittest.main()
