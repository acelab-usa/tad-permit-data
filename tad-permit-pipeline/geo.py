"""Best-effort latitude/longitude extraction from Socrata API payloads, plus
an address-based geocoding fallback for records that don't come with
coordinates at all.

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

import requests

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


# Fallback "home city" for jurisdictions whose raw address is just a bare
# street line with no city/state at all -- e.g. Allen's PDF ledger
# ("945 Stockton Dr, 4130 4") and Chicago/NYC/Austin's FieldMappings (see
# sources/registry.py), which all build `address` purely from
# street-number/name fields. This is only consulted as a second attempt,
# when geocoding the address exactly as given doesn't resolve -- a
# jurisdiction whose addresses already include city/state/zip (e.g. an API
# source returning "1955 GLACIER PARK AV, NAPERVILLE, IL 60540") never needs
# an entry here at all, so onboarding one doesn't require touching this dict.
JURISDICTION_LOCATIONS = {
    "chicago": "Chicago, IL",
    "nyc": "New York, NY",
    "austin": "Austin, TX",
    "la": "Los Angeles, CA",
    "allen": "Allen, TX",
}

_CENSUS_GEOCODER_URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
_GEOCODE_TIMEOUT_SECONDS = 5


def _geocode_one_line(one_line: str) -> tuple:
    try:
        response = requests.get(
            _CENSUS_GEOCODER_URL,
            params={"address": one_line, "benchmark": "Public_AR_Current", "format": "json"},
            timeout=_GEOCODE_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        matches = response.json()["result"]["addressMatches"]
    except (requests.RequestException, ValueError, KeyError) as e:
        logger.warning("geocode_address: lookup failed for '%s': %s", one_line, e)
        return None, None

    if not matches:
        return None, None

    coords = matches[0].get("coordinates", {})
    # Census returns x=longitude, y=latitude.
    lat, lon = _to_float(coords.get("y")), _to_float(coords.get("x"))
    return (lat, lon) if _valid(lat, lon) else (None, None)


def geocode_address(address: Optional[str], jurisdiction: str) -> tuple:
    """Best-effort fallback: resolves a street address to (lat, lon) via the
    US Census Bureau's free geocoder (no API key, US addresses only -- fine
    since every registered jurisdiction is a US city).

    For sources that never provide coordinates at all (PDF ledgers) or that
    didn't for a particular record (a malformed/missing API geometry field),
    this is the only way those permits end up with a map location. Returns
    (None, None) on any failure -- bad/unmatched address, network error,
    unrecognized jurisdiction -- so ingestion always continues without a
    location rather than blocking on this.

    Tries the address exactly as given first, since many sources already
    include city/state/zip. Only if that doesn't resolve does it retry with
    a fixed per-jurisdiction city/state appended, for sources (like Allen's
    PDF ledger) whose raw address is missing that context entirely.
    """
    if not address or not address.strip():
        return None, None

    address = address.strip()

    lat, lon = _geocode_one_line(address)
    if lat is not None:
        return lat, lon

    city_state = JURISDICTION_LOCATIONS.get(jurisdiction.lower())
    if not city_state:
        return None, None

    return _geocode_one_line(f"{address}, {city_state}")
