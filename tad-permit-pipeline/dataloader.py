"""dataloader.py -- Ingestion Orchestrator

Pulls raw permit data from whichever jurisdiction adapter is requested (see
sources/registry.py) and either writes it straight to the database (API
sources, one record = one permit) or streams ledger pages out to the Hatchet
PDF workflow for LLM extraction (PDF sources, one page = many permits).

Adding a new jurisdiction never requires touching this file -- register an
adapter in sources/registry.py instead.
"""
import argparse

from dotenv import load_dotenv
from hatchet_sdk import Hatchet
from pydantic import ValidationError

import database
from logging_setup import get_logger
from permit import PermitSchemaV2
from sources import APIPermitSource, PDFPermitSource, get_source, list_sources

load_dotenv()
logger = get_logger("dataloader")

hatchet = Hatchet()


def _ingest_api_source(source: APIPermitSource, size: int):
    raw_records = source.fetch_raw_records(size=size)
    if not raw_records:
        logger.warning("%s: no records retrieved, nothing to ingest", source.name)
        return

    inserted = skipped = failed = 0

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

        try:
            hatchet.event.push(
                "permit:enrich",
                {"permit_id": validated_permit.permit_id, "raw_text": validated_permit.raw_scope_of_work},
            )
        except Exception as e:
            logger.warning(
                "%s: permit %s saved but enrichment could not be queued (is the Hatchet worker running?): %s",
                source.name, validated_permit.permit_id, e,
            )

    logger.info("%s: ingestion complete -- inserted=%s skipped=%s failed=%s", source.name, inserted, skipped, failed)


def _ingest_pdf_source(source: PDFPermitSource, size: int):
    # `size` is repurposed as a rough page budget for PDF sources, matching
    # historical behavior (page_cap ~= size / 5), with a floor of 1 page.
    page_cap = max(1, size // 5) if size else None
    month_cap = 1

    queued = 0
    for filename, page_number, page_text in source.iter_pages(month_cap=month_cap, page_cap=page_cap):
        try:
            hatchet.event.push(
                "pdf:process",
                {
                    "jurisdiction": source.name,
                    "source_pdf_name": filename,
                    "page_number": page_number,
                    "page_text": page_text,
                    "extraction_hints": source.extraction_hints,
                },
            )
            queued += 1
        except Exception as e:
            logger.error(
                "%s: failed to queue page %s of '%s' (is the Hatchet worker running?): %s",
                source.name, page_number, filename, e,
            )

    logger.info("%s: queued %s ledger pages for processing", source.name, queued)


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