"""Generic adapter for ArcGIS REST FeatureServer/MapServer permit layers --
common for mid-size cities/counties that publish permit data as GIS layers
rather than through a Socrata-style open-data portal.

Unlike Socrata, ArcGIS splits each record into "attributes" (the actual
business fields) and a separate "geometry" object (`{"x": lon, "y": lat}`
for a point layer) -- not one flat dict. `_flatten_feature()` merges these
into a single dict per record with the geometry injected as plain
top-level "latitude"/"longitude" keys, which is the *first* shape
geo.extract_lat_lon() already checks. That means everything downstream --
FieldMapping, build_mapper(), onboard_jurisdiction.py -- works completely
unchanged regardless of whether a source is Socrata or ArcGIS; only this
module and onboard_jurisdiction.py's fetch step need to know the
difference.

Adding a new ArcGIS-backed city is the same as Socrata -- a FieldMapping
plus:

    ArcGISFeatureSource(
        name="dc",
        url="https://maps2.dcgis.dc.gov/dcgis/rest/services/FEEDS/DCRA/FeatureServer/17",
        date_column="ISSUE_DATE",
        mapper_func=build_mapper(DC_MAPPING),
    )

`url` is the layer URL (including its numeric layer ID), not just the
service root -- ArcGIS services can host multiple layers, and only one is
usually the actual permits table.
"""
import time
from typing import Callable, Optional

import requests

from logging_setup import get_logger
from sources.base import APIPermitSource

logger = get_logger("sources.arcgis")

MAX_RETRIES = 3
BACKOFF_SECONDS = 2
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def _flatten_feature(feature: dict) -> dict:
    """Merges one ArcGIS feature's attributes + point geometry into a
    single flat dict, matching the shape every other source already
    produces. Non-point layers (polygons, lines) have no single lat/lon to
    extract, so geometry is left out for anything but a plain {x, y}
    point."""
    flat = dict(feature.get("attributes") or {})
    geometry = feature.get("geometry")
    if isinstance(geometry, dict) and "x" in geometry and "y" in geometry:
        flat.setdefault("latitude", geometry.get("y"))
        flat.setdefault("longitude", geometry.get("x"))
    return flat


class ArcGISFeatureSource(APIPermitSource):
    def __init__(
        self,
        name: str,
        url: str,
        date_column: str,
        mapper_func: Callable[[dict], dict],
        skip_sentinel_field: Optional[str] = None,
        skip_sentinel_value: Optional[str] = None,
    ):
        self.name = name
        self.url = url.rstrip("/")
        self.date_column = date_column
        self.mapper_func = mapper_func
        self._skip_field = skip_sentinel_field
        self._skip_value = skip_sentinel_value

    def fetch_raw_records(self, size: int, page: int = 1) -> list[dict]:
        params = {
            "where": "1=1",
            "outFields": "*",
            "f": "json",
            "resultRecordCount": size,
            "resultOffset": (page - 1) * size,
            "orderByFields": f"{self.date_column} DESC",
        }

        last_error = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.info(
                    "%s: requesting %s records at offset %s, attempt %s/%s",
                    self.name, size, params["resultOffset"], attempt, MAX_RETRIES,
                )
                response = requests.get(f"{self.url}/query", params=params, timeout=15)

                if response.status_code in RETRYABLE_STATUS_CODES and attempt < MAX_RETRIES:
                    wait = BACKOFF_SECONDS * (2 ** (attempt - 1))
                    logger.warning("%s: got HTTP %s, retrying in %ss", self.name, response.status_code, wait)
                    time.sleep(wait)
                    continue

                response.raise_for_status()
                data = response.json()

                if "error" in data:
                    # ArcGIS returns HTTP 200 with an {"error": {...}} body
                    # on a bad request (e.g. an invalid orderByFields field
                    # name) rather than a 4xx status -- raise_for_status()
                    # above wouldn't catch this, and treating it as "zero
                    # records" would silently hide a real config mistake.
                    raise ValueError(f"ArcGIS error response: {data['error']}")

                features = data.get("features", [])
                records = [_flatten_feature(f) for f in features]
                logger.info("%s: retrieved %s raw records", self.name, len(records))
                return records

            except requests.exceptions.Timeout as err:
                last_error = err
                logger.warning("%s: request timed out (attempt %s/%s)", self.name, attempt, MAX_RETRIES)
            except requests.exceptions.HTTPError as err:
                last_error = err
                logger.error("%s: HTTP error: %s", self.name, err)
                break  # non-retryable status code, no point retrying
            except (requests.exceptions.RequestException, ValueError) as err:
                last_error = err
                logger.warning("%s: request failed (attempt %s/%s): %s", self.name, attempt, MAX_RETRIES, err)

            if attempt < MAX_RETRIES:
                wait = BACKOFF_SECONDS * (2 ** (attempt - 1))
                time.sleep(wait)

        logger.error("%s: giving up after %s attempts (%s)", self.name, MAX_RETRIES, last_error)
        return []

    def map_to_schema(self, raw_item: dict) -> dict:
        return self.mapper_func(raw_item)

    def should_skip(self, raw_item: dict, mapped: dict) -> Optional[str]:
        if self._skip_field and mapped.get(self._skip_field) == self._skip_value:
            return f"{self._skip_field} == {self._skip_value!r} sentinel"
        return None
