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

import geo


def _mock_response(matches):
    response = MagicMock()
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


if __name__ == "__main__":
    unittest.main()
