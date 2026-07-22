"""Best-effort latitude/longitude extraction from Socrata API payloads.

Socrata datasets expose location data inconsistently -- sometimes as plain
`latitude`/`longitude` fields, sometimes as a nested point-geometry field
whose shape varies (`{"latitude": .., "longitude": ..}` or GeoJSON-style
`{"type": "Point", "coordinates": [lon, lat]}`). This tries the common
shapes so each mapper doesn't have to reimplement parsing, while letting a
mapper pass the specific geometry field name(s) its own dataset uses.

NOTE: the exact field names Chicago/NYC/Austin's APIs use for geometry
weren't verified against live responses (no network access to those hosts
from the environment this was written in) -- the `point_fields` guesses
passed in from sources/registry.py are a starting point, not a guarantee.
If coordinate coverage looks low after a real ingestion run, check the
actual raw API response for the real field name and add it there.
"""
from typing import Optional

from logging_setup import get_logger

logger = get_logger("geo")

# Sanity bounds -- rejects (0, 0) placeholder coordinates and obviously
# out-of-range values rather than silently plotting a permit in the ocean.
_LAT_RANGE = (-90.0, 90.0)
_LON_RANGE = (-180.0, 180.0)


def _to_float(value) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _valid(lat: Optional[float], lon: Optional[float]) -> bool:
    if lat is None or lon is None:
        return False
    if not (_LAT_RANGE[0] <= lat <= _LAT_RANGE[1]):
        return False
    if not (_LON_RANGE[0] <= lon <= _LON_RANGE[1]):
        return False
    if lat == 0 and lon == 0:
        return False
    return True


def extract_lat_lon(raw_item: dict, point_fields: tuple = ()) -> tuple:
    """Returns (latitude, longitude), or (None, None) if nothing usable is found.

    Checks, in order: plain latitude/longitude-ish top-level fields, then
    each field name in `point_fields` for a nested {"latitude", "longitude"}
    or GeoJSON {"coordinates": [lon, lat]} shape.
    """
    for lat_key, lon_key in (
        ("latitude", "longitude"),
        ("lat", "lon"),
        ("lat", "lng"),
        ("gis_latitude", "gis_longitude"),
    ):
        lat, lon = _to_float(raw_item.get(lat_key)), _to_float(raw_item.get(lon_key))
        if _valid(lat, lon):
            return lat, lon

    for field in point_fields:
        point = raw_item.get(field)
        if not isinstance(point, dict):
            continue

        if "latitude" in point or "longitude" in point:
            lat, lon = _to_float(point.get("latitude")), _to_float(point.get("longitude"))
            if _valid(lat, lon):
                return lat, lon

        coords = point.get("coordinates")
        if isinstance(coords, (list, tuple)) and len(coords) == 2:
            lon, lat = _to_float(coords[0]), _to_float(coords[1])  # GeoJSON order is [lon, lat]
            if _valid(lat, lon):
                return lat, lon

    return None, None
