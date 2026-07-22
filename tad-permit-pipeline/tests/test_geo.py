"""Tests for geo.geocode_address()'s fallback logic.

The main thing worth locking down: a jurisdiction with a known
JURISDICTION_LOCATIONS entry (its raw address lacks city/state) must always
geocode the *qualified* address directly, never the bare address on its
own -- an earlier version tried the bare address first, which let a
handful of real LA permits resolve to a wrong, same-named street elsewhere
in the country (landing near the geographic center of the US) since an
unqualified street-only address gives a national geocoder nothing to
disambiguate with.
"""
import unittest
from unittest.mock import MagicMock, patch

import requests

import geo


def _mock_response(matches, status_code=200):
    response = MagicMock()
    response.status_code = status_code
    response.raise_for_status.return_value = None
    response.json.return_value = {"result": {"addressMatches": matches}}
    return response


_MATCH = [{"coordinates": {"x": -87.6298, "y": 41.8781}}]


class GeocodeAddressTests(unittest.TestCase):
    def test_known_jurisdiction_only_ever_queries_qualified_address(self):
        """A jurisdiction with a JURISDICTION_LOCATIONS entry (e.g. LA) must
        never have its bare address geocoded on its own -- only the
        city/state-qualified version, in a single request."""
        calls = []

        def fake_get(url, params, timeout):
            calls.append(params["address"])
            return _mock_response(_MATCH)

        with patch("geo.requests.get", side_effect=fake_get):
            lat, lon = geo.geocode_address("7806 N ARVILLA AVE", "la")

        self.assertEqual(calls, ["7806 N ARVILLA AVE, Los Angeles, CA"])
        self.assertAlmostEqual(lat, 41.8781)
        self.assertAlmostEqual(lon, -87.6298)

    def test_known_jurisdiction_does_not_fall_back_to_bare_address(self):
        """Even if the qualified address fails to match, a known
        jurisdiction must not then try the bare address -- that's exactly
        the unqualified, ambiguous lookup this is meant to avoid."""
        calls = []

        def fake_get(url, params, timeout):
            calls.append(params["address"])
            return _mock_response([])  # no match, even qualified

        with patch("geo.requests.get", side_effect=fake_get):
            lat, lon = geo.geocode_address("7806 N ARVILLA AVE", "la")

        self.assertEqual(calls, ["7806 N ARVILLA AVE, Los Angeles, CA"])
        self.assertIsNone(lat)
        self.assertIsNone(lon)

    def test_unknown_jurisdiction_geocodes_address_as_given(self):
        """A jurisdiction with no JURISDICTION_LOCATIONS entry (e.g.
        Naperville) is assumed to already supply a complete address."""
        calls = []

        def fake_get(url, params, timeout):
            calls.append(params["address"])
            return _mock_response(_MATCH)

        with patch("geo.requests.get", side_effect=fake_get):
            geo.geocode_address("1955 GLACIER PARK AV, NAPERVILLE, IL 60540", "naperville")

        self.assertEqual(calls, ["1955 GLACIER PARK AV, NAPERVILLE, IL 60540"])

    def test_blank_address_never_calls_out(self):
        with patch("geo.requests.get") as mock_get:
            lat, lon = geo.geocode_address("", "la")
        mock_get.assert_not_called()
        self.assertIsNone(lat)
        self.assertIsNone(lon)


class GeocodeRetryTests(unittest.TestCase):
    """The Census geocoder is known to be slow/flaky under load -- these
    lock down that a transient failure gets retried instead of silently
    dropping an otherwise-good address on the first blip."""

    def setUp(self):
        # Don't actually sleep in tests.
        self._sleep_patch = patch("geo.time.sleep")
        self._sleep_patch.start()
        self.addCleanup(self._sleep_patch.stop)

    def test_retries_on_transient_error_then_succeeds(self):
        responses = iter([
            requests.exceptions.ConnectionError("boom"),
            requests.exceptions.Timeout("slow"),
            _mock_response(_MATCH),
        ])

        def fake_get(*args, **kwargs):
            item = next(responses)
            if isinstance(item, Exception):
                raise item
            return item

        with patch("geo.requests.get", side_effect=fake_get) as mock_get:
            lat, lon = geo.geocode_address("7806 N ARVILLA AVE", "la")

        self.assertEqual(mock_get.call_count, 3)
        self.assertAlmostEqual(lat, 41.8781)
        self.assertAlmostEqual(lon, -87.6298)

    def test_retries_on_retryable_status_code_then_succeeds(self):
        responses = iter([
            _mock_response([], status_code=503),
            _mock_response(_MATCH, status_code=200),
        ])

        with patch("geo.requests.get", side_effect=lambda *a, **k: next(responses)) as mock_get:
            lat, lon = geo.geocode_address("7806 N ARVILLA AVE", "la")

        self.assertEqual(mock_get.call_count, 2)
        self.assertAlmostEqual(lat, 41.8781)

    def test_gives_up_after_max_retries(self):
        with patch("geo.requests.get", side_effect=requests.exceptions.Timeout("slow")) as mock_get:
            lat, lon = geo.geocode_address("7806 N ARVILLA AVE", "la")

        self.assertEqual(mock_get.call_count, geo._GEOCODE_MAX_RETRIES)
        self.assertIsNone(lat)
        self.assertIsNone(lon)


if __name__ == "__main__":
    unittest.main()
