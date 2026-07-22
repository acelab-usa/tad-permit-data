"""Generic adapter for Socrata (and Socrata-shaped JSON) permit APIs.

Adding a new Socrata-backed city is usually just a declarative FieldMapping
(see sources/field_mapping.py) plus this:

    SocrataAPISource(
        name="denver",
        url="https://data.denvergov.org/api/v3/views/xxxx/query.json",
        date_column="issued_date",
        mapper_func=build_mapper(DENVER_MAPPING),
    )

`mapper_func` is a plain function that turns one raw JSON record into the
dict PermitSchemaV2 needs -- `build_mapper()` generates one from a
FieldMapping for the common case. Fall back to hand-writing a `mapper_func`
directly only if a city's payload needs logic a flat field-to-field mapping
genuinely can't express (rare -- see NYC's `scope_builder` in
sources/registry.py for the one existing case, which still uses
FieldMapping/build_mapper for everything else).
"""
import time
from typing import Callable, Optional

import requests

from logging_setup import get_logger
from sources.base import APIPermitSource

logger = get_logger("sources.socrata")

MAX_RETRIES = 3
BACKOFF_SECONDS = 2
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class SocrataAPISource(APIPermitSource):
    def __init__(
        self,
        name: str,
        url: str,
        date_column: str,
        mapper_func: Callable[[dict], dict],
        app_token_env: str = "SOCRATA_APP_TOKEN",
        skip_sentinel_field: Optional[str] = None,
        skip_sentinel_value: Optional[str] = None,
    ):
        self.name = name
        self.url = url
        self.date_column = date_column
        self.mapper_func = mapper_func
        self.app_token_env = app_token_env
        # Some feeds (e.g. NYC) use a sentinel value to mean "not actually a
        # permit yet" -- e.g. job_filing_number == "Permit is no...". Optional.
        self._skip_field = skip_sentinel_field
        self._skip_value = skip_sentinel_value

    def fetch_raw_records(self, size: int, page: int = 1) -> list[dict]:
        import os

        app_token = os.getenv(self.app_token_env)
        if not app_token:
            logger.warning(
                "%s: no %s configured -- request will proceed unauthenticated "
                "and may be rate-limited or rejected.",
                self.name, self.app_token_env,
            )

        headers = {
            "X-App-Token": app_token or "",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        payload = {
            "query": f"SELECT * ORDER BY `{self.date_column}` DESC",
            "page": {"pageNumber": page, "pageSize": size},
            "includeSynthetic": False,
        }

        last_error = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.info("%s: requesting page %s (size=%s), attempt %s/%s",
                            self.name, page, size, attempt, MAX_RETRIES)
                response = requests.post(self.url, headers=headers, json=payload, timeout=15)

                if response.status_code in RETRYABLE_STATUS_CODES and attempt < MAX_RETRIES:
                    wait = BACKOFF_SECONDS * (2 ** (attempt - 1))
                    logger.warning("%s: got HTTP %s, retrying in %ss", self.name, response.status_code, wait)
                    time.sleep(wait)
                    continue

                response.raise_for_status()
                data = response.json()
                logger.info("%s: retrieved %s raw records", self.name, len(data))
                return data

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
