"""dataloader.py -- Ingestion Orchestrator

Pulls raw permit data from whichever jurisdiction adapter is requested (see
sources/registry.py) and either writes it straight to the database (API
sources, one record = one permit) or streams ledger pages out to the Hatchet
PDF workflow for LLM extraction (PDF sources, one page = many permits).

Adding a new jurisdiction never requires touching this file -- register an
adapter in sources/registry.py instead.

Hatchet events are pushed in batches, not one per permit/page: every newly
inserted API permit from a single run goes into one (or a few, chunked)
`permit:enrich_batch` events, and every page queued for one PDF file goes
into a single `pdf:process_batch` event. This decouples Hatchet event
volume from data volume -- a run that inserts 100 new permits or queues 96
ledger pages costs a handful of events, not 100 or 96.
"""
import argparse

from dotenv import load_dotenv
from hatchet_sdk import Hatchet
from pydantic import ValidationError

import database
import geo
from logging_setup import get_logger
from permit import PermitSchemaV2
from sources import APIPermitSource, PDFPermitSource, get_source, list_sources

load_dotenv()
logger = get_logger("dataloader")

hatchet = Hatchet()

# Caps how many permits' worth of enrichment work rides in a single
# Hatchet event -- purely a payload-size safety margin, not a quota
# concern (a run's permits still go out in as few events as this allows).
ENRICH_BATCH_SIZE = 25


def _chunks(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def _ingest_api_source(source: APIPermitSource, size: int):
    raw_records = source.fetch_raw_records(size=size)
    if not raw_records:
        logger.warning("%s: no records retrieved, nothing to ingest", source.name)
        return

    inserted = skipped = failed = 0
    to_enrich = []

    for raw_item in raw_records:
        try:
            mapped = source.map_to_schema(raw_item)
        except Exception as e:
            failed += 1
            logger.error("%s: mapper raised on a record, skipping it: %s", source.name, e)
            continue

        skip_reason = source.should_skip(raw_item, mapped)
        if skip_reason:
            skipped += 1
            logger.info("%s: skipping record (%s)", source.name, skip_reason)
            continue

        try:
            validated_permit = PermitSchemaV2(**mapped)
        except ValidationError as e:
            failed += 1
            logger.error("%s: record failed schema validation, skipping it: %s", source.name, e)
            continue

        if validated_permit.latitude is None or validated_permit.longitude is None:
            lat, lon = geo.geocode_address(validated_permit.address, validated_permit.jurisdiction)
            if lat is not None:
                validated_permit.latitude, validated_permit.longitude = lat, lon

        try:
            was_inserted = database.insert_permit(validated_permit)
        except Exception as e:
            failed += 1
            logger.error(
                "%s: DB write failed for permit %s, skipping it: %s",
                source.name, validated_permit.permit_id, e,
            )
            continue

        if not was_inserted:
            skipped += 1
            logger.info("%s: permit %s already exists, skipped", source.name, validated_permit.permit_id)
            continue

        inserted += 1
        logger.info("%s: saved permit %s (%s)", source.name, validated_permit.permit_id, validated_permit.address)
        to_enrich.append({"permit_id": validated_permit.permit_id, "raw_text": validated_permit.raw_scope_of_work})

    queued_events = 0
    for batch in _chunks(to_enrich, ENRICH_BATCH_SIZE):
        try:
            hatchet.event.push("permit:enrich_batch", {"permits": batch})
            queued_events += 1
        except Exception as e:
            logger.warning(
                "%s: %s permit(s) saved but enrichment could not be queued (is the Hatchet worker running?): %s",
                source.name, len(batch), e,
            )

    logger.info(
        "%s: ingestion complete -- inserted=%s skipped=%s failed=%s, enrichment queued in %s event(s) for %s permit(s)",
        source.name, inserted, skipped, failed, queued_events, len(to_enrich),
    )


def _ingest_pdf_source(source: PDFPermitSource, size: int):
    # `size` is repurposed as a rough page budget for PDF sources, matching
    # historical behavior (page_cap ~= size / 5), with a floor of 1 page.
    page_cap = max(1, size // 5) if size else None
    month_cap = 1

    start_filename, start_page = database.get_pdf_cursor(source.name)

    queued_pages = 0
    queued_events = 0
    current_filename = None
    current_batch = []
    last_page_seen = 0

    def _flush():
        nonlocal current_batch, queued_events, last_page_seen
        if not current_batch:
            return
        try:
            hatchet.event.push(
                "pdf:process_batch",
                {
                    "jurisdiction": source.name,
                    "source_pdf_name": current_filename,
                    "pages": current_batch,
                    "extraction_hints": source.extraction_hints,
                },
            )
            queued_events += 1
            # Advance the cursor only once the batch is actually queued --
            # if the push above fails, the next run retries these same
            # pages rather than silently skipping them.
            database.update_pdf_cursor(source.name, current_filename, last_page_seen)
        except Exception as e:
            logger.error(
                "%s: failed to queue %s page(s) of '%s' (is the Hatchet worker running?): %s",
                source.name, len(current_batch), current_filename, e,
            )
        current_batch = []

    for filename, page_number, page_text in source.iter_pages(
        month_cap=month_cap, page_cap=page_cap, start_filename=start_filename, start_page=start_page
    ):
        if filename != current_filename:
            _flush()
            current_filename = filename
        current_batch.append({"page_number": page_number, "page_text": page_text})
        last_page_seen = page_number
        queued_pages += 1

    _flush()

    logger.info("%s: queued %s ledger page(s) across %s event(s)", source.name, queued_pages, queued_events)


def load_data(jurisdiction: str = "chicago", size: int = 100):
    database.init_db()

    try:
        source = get_source(jurisdiction)
    except ValueError as e:
        logger.error(str(e))
        return

    if isinstance(source, APIPermitSource):
        _ingest_api_source(source, size)
    elif isinstance(source, PDFPermitSource):
        _ingest_pdf_source(source, size)
    else:
        logger.error("%s: adapter is neither an APIPermitSource nor a PDFPermitSource", jurisdiction)


def _parse_args():
    parser = argparse.ArgumentParser(description="Trigger permit ingestion for a jurisdiction.")
    parser.add_argument(
        "jurisdiction",
        nargs="?",
        default="allen",
        help=f"Jurisdiction to ingest. Available: {', '.join(list_sources())}",
    )
    parser.add_argument("--size", type=int, default=100, help="Record/page batch size (default: 100)")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    logger.info("Starting ingestion: jurisdiction=%s size=%s", args.jurisdiction, args.size)
    load_data(args.jurisdiction, size=args.size)
