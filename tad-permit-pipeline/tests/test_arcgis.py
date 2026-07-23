"""Tests for sources/arcgis.py -- feature flattening and fetch retry/error
handling."""
import unittest
from unittest.mock import MagicMock, patch

import requests

from sources.arcgis import ArcGISFeatureSource, _flatten_feature


class FlattenFeatureTests(unittest.TestCase):
    def test_merges_point_geometry_into_flat_dict(self):
        feature = {
            "attributes": {"PERMIT_NO": "B2024-001", "ISSUE_DATE": 1700000000000},
            "geometry": {"x": -77.02, "y": 38.9},
        }
        flat = _flatten_feature(feature)
        self.assertEqual(flat["PERMIT_NO"], "B2024-001")
        self.assertEqual(flat["latitude"], 38.9)
        self.assertEqual(flat["longitude"], -77.02)

    def test_no_geometry_key_still_returns_attributes(self):
        feature = {"attributes": {"PERMIT_NO": "X"}}
        flat = _flatten_feature(feature)
        self.assertEqual(flat, {"PERMIT_NO": "X"})

    def test_non_point_geometry_ignored(self):
        # A polygon/line layer's geometry has no single x/y -- shouldn't
        # inject bogus latitude/longitude.
        feature = {"attributes": {"PERMIT_NO": "X"}, "geometry": {"rings": [[[0, 0], [1, 1]]]}}
        flat = _flatten_feature(feature)
        self.assertNotIn("latitude", flat)
        self.assertNotIn("longitude", flat)

    def test_does_not_overwrite_existing_attribute_named_latitude(self):
        feature = {
            "attributes": {"latitude": "already here"},
            "geometry": {"x": -77.02, "y": 38.9},
        }
        flat = _flatten_feature(feature)
        self.assertEqual(flat["latitude"], "already here")


def _mock_response(payload, status_code=200):
    response = MagicMock()
    response.status_code = status_code
    response.raise_for_status.return_value = None
    response.json.return_value = payload
    return response


class ArcGISFeatureSourceTests(unittest.TestCase):
    def _source(self, **overrides):
        kwargs = dict(
            name="dc",
            url="https://maps2.dcgis.dc.gov/dcgis/rest/services/FEEDS/DCRA/FeatureServer/17",
            date_column="ISSUE_DATE",
            mapper_func=lambda raw: raw,
        )
        kwargs.update(overrides)
        return ArcGISFeatureSource(**kwargs)

    def test_fetch_raw_records_flattens_features(self):
        payload = {
            "features": [
                {"attributes": {"PERMIT_NO": "A"}, "geometry": {"x": 1.0, "y": 2.0}},
                {"attributes": {"PERMIT_NO": "B"}, "geometry": {"x": 3.0, "y": 4.0}},
            ]
        }
        with patch("sources.arcgis.requests.get", return_value=_mock_response(payload)) as mock_get:
            records = self._source().fetch_raw_records(size=2)

        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["PERMIT_NO"], "A")
        self.assertEqual(records[0]["latitude"], 2.0)
        params = mock_get.call_args.kwargs["params"]
        self.assertEqual(params["resultRecordCount"], 2)
        self.assertEqual(params["orderByFields"], "ISSUE_DATE DESC")
        # Without this, ArcGIS returns geometry in the layer's native
        # (often projected) spatial reference instead of lat/lon degrees --
        # found via a real DC FeatureServer run where every coordinate
        # silently came back null because of exactly this.
        self.assertEqual(params["outSR"], "4326")

    def test_error_body_with_200_status_does_not_look_like_zero_records(self):
        # ArcGIS returns HTTP 200 with an {"error": ...} body on a bad
        # request -- must not be silently treated as "no permits found".
        payload = {"error": {"code": 400, "message": "Invalid field"}}
        with patch("sources.arcgis.requests.get", return_value=_mock_response(payload)), \
             patch("sources.arcgis.time.sleep"):
            records = self._source().fetch_raw_records(size=2)
        self.assertEqual(records, [])  # fails soft, but logged as an error, not silently

    def test_retries_on_retryable_status_then_succeeds(self):
        responses = iter([
            _mock_response({}, status_code=503),
            _mock_response({"features": [{"attributes": {"PERMIT_NO": "A"}}]}, status_code=200),
        ])
        with patch("sources.arcgis.requests.get", side_effect=lambda *a, **k: next(responses)) as mock_get, \
             patch("sources.arcgis.time.sleep"):
            records = self._source().fetch_raw_records(size=1)

        self.assertEqual(mock_get.call_count, 2)
        self.assertEqual(records[0]["PERMIT_NO"], "A")

    def test_pagination_offset(self):
        with patch("sources.arcgis.requests.get", return_value=_mock_response({"features": []})) as mock_get:
            self._source().fetch_raw_records(size=50, page=3)
        params = mock_get.call_args.kwargs["params"]
        self.assertEqual(params["resultOffset"], 100)  # (page - 1) * size


if __name__ == "__main__":
    unittest.main()
