# workflow.py
import json
from pydantic import BaseModel
from hatchet_sdk import Hatchet, Context
import llm_processor
import database
import geo
from logging_setup import get_logger
from permit_types import normalize_permit_type

logger = get_logger("workflow")

hatchet = Hatchet()

# Define what input data the worker expects to receive
class EnrichItem(BaseModel):
    permit_id: str
    raw_text: str

class EnrichBatchInput(BaseModel):
    permits: list[EnrichItem]

# Define input data for PDF processing
class PageItem(BaseModel):
    page_number: int
    page_text: str

class PageBatchIngestionInput(BaseModel):
    jurisdiction: str
    source_pdf_name: str
    pages: list[PageItem]
    extraction_hints: str | None = None


def _enrich_one(permit_id: str, raw_text: str) -> dict:
    """Enriches and saves a single permit. Shared by the batch task below so
    one bad permit's failure doesn't need special-casing beyond a normal
    per-item try/except in the caller's loop."""
    logger.info("Processing AI enrichment for permit: %s", permit_id)

    if not raw_text or not raw_text.strip():
        # Nothing to enrich -- not a failure, just skip.
        logger.info("Permit %s has no raw text to enrich, skipping", permit_id)
        return {"status": "skipped", "reason": "empty raw_text"}

    enriched_data = llm_processor.enrich_permit_text(raw_text)

    if not enriched_data:
        # Could be a transient API failure (already retried inside
        # llm_processor) or a malformed LLM response -- raise so the batch
        # task's per-item try/except counts it as a real failure rather
        # than silently treating it as "done".
        raise Exception(f"LLM enrichment failed for permit {permit_id}")

    conn = database.get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE permits
            SET scope_summary = ?,
                building_systems = ?
            WHERE permit_id = ?
        """, (
            enriched_data.scope_summary,
            json.dumps(enriched_data.building_systems),
            permit_id
        ))
        conn.commit()
        logger.info("Successfully updated %s in DB", permit_id)
    finally:
        conn.close()

    return {"status": "success"}


# Register the background workflow with Hatchet V1. One event now carries
# every permit newly inserted in a single ingestion run (see
# dataloader._ingest_api_source) instead of one event per permit -- Hatchet
# event volume no longer scales with data volume, only with ingestion runs.
enrich_batch_workflow = hatchet.workflow(
    name="PermitEnrichmentBatch",
    on_events=["permit:enrich_batch"],
    input_validator=EnrichBatchInput,
)


@enrich_batch_workflow.task(name="process_llm_enrichment_batch")
def process_llm_enrichment_batch(input: EnrichBatchInput, ctx: Context) -> dict:
    succeeded = failed = skipped = 0

    for item in input.permits:
        try:
            result = _enrich_one(item.permit_id, item.raw_text)
        except Exception as e:
            failed += 1
            logger.error("Enrichment failed for permit %s: %s", item.permit_id, e)
            continue

        if result["status"] == "skipped":
            skipped += 1
        else:
            succeeded += 1

    logger.info(
        "Enrichment batch complete: succeeded=%s failed=%s skipped=%s (of %s)",
        succeeded, failed, skipped, len(input.permits),
    )
    return {"succeeded": succeeded, "failed": failed, "skipped": skipped}


def _process_one_page(
    jurisdiction: str, source_pdf_name: str, page_number: int, page_text: str, extraction_hints
) -> dict:
    """Extracts and saves every permit found on one ledger page. Shared by
    the batch task below."""
    extracted_data = llm_processor.extract_multiple_permits_from_text(
        page_text, extraction_hints=extraction_hints
    )

    if not extracted_data or not extracted_data.permits_found:
        logger.info("No permits found on page %s of '%s'", page_number, source_pdf_name)
        return {"permits_inserted": 0, "permits_failed": 0}

    logger.info(
        "Found %s permits on page %s of '%s'. Writing to DB...",
        len(extracted_data.permits_found), page_number, source_pdf_name,
    )

    conn = database.get_connection()
    cursor = conn.cursor()
    inserted_count = 0
    failed_count = 0

    try:
        for permit in extracted_data.permits_found:
            if not permit.permit_id or not str(permit.permit_id).strip():
                failed_count += 1
                logger.warning(
                    "Skipping a permit on page %s of '%s': missing permit_id",
                    page_number, source_pdf_name,
                )
                continue

            # PDF ledgers never carry coordinates themselves -- this is the
            # only source of a map location for these permits.
            latitude, longitude = geo.geocode_address(permit.address, jurisdiction)

            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO permits (
                        permit_id, jurisdiction, source_format, source_url, filing_date,
                        permit_type_raw, permit_type_normalized, address, owner_name,
                        contractor_name, valuation, square_footage, latitude, longitude,
                        raw_scope_of_work, scope_summary, building_systems
                    ) VALUES (?, ?, 'PDF', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    permit.permit_id,
                    jurisdiction,
                    source_pdf_name, # Track which monthly file this came from
                    permit.filing_date,
                    permit.permit_type_raw,
                    normalize_permit_type(permit.permit_type_raw),
                    permit.address,
                    permit.owner_name,
                    permit.contractor_name,
                    permit.valuation,
                    permit.square_footage,
                    latitude,
                    longitude,
                    permit.raw_scope_of_work,
                    permit.scope_summary,
                    json.dumps(permit.building_systems)
                ))
                # cursor.rowcount reflects rows affected by *this* INSERT (0 if
                # the UNIQUE constraint ignored a duplicate, 1 if inserted).
                # conn.total_changes accumulates over the connection's whole
                # lifetime, so checking it per-iteration in this loop
                # over-counted every row after the first real insert.
                if cursor.rowcount > 0:
                    inserted_count += 1
            except Exception as e:
                failed_count += 1
                logger.error(
                    "Failed to write permit %s from page %s of '%s': %s",
                    permit.permit_id, page_number, source_pdf_name, e,
                )

        conn.commit()
        logger.info(
            "Saved %s new entries from page %s of '%s' (%s failed)",
            inserted_count, page_number, source_pdf_name, failed_count,
        )
    except Exception as e:
        logger.error("DB write error on page %s of '%s': %s", page_number, source_pdf_name, e)
        raise
    finally:
        conn.close()

    return {"permits_inserted": inserted_count, "permits_failed": failed_count}


# Register the PDF processing workflow with Hatchet V1. One event now
# carries every page queued for a single file in one ingestion run (see
# dataloader._ingest_pdf_source) instead of one event per page -- a 96-page
# monthly ledger is 1 event instead of 96.
pdf_batch_workflow = hatchet.workflow(
    name="PDFProcessingBatch",
    on_events=["pdf:process_batch"],
    input_validator=PageBatchIngestionInput,
)


@pdf_batch_workflow.task(name="parse_ledger_page_batch")
def parse_ledger_page_batch(input: PageBatchIngestionInput, ctx: Context) -> dict:
    logger.info(
        "Processing %s page(s) from '%s'", len(input.pages), input.source_pdf_name,
    )

    total_inserted = total_failed = 0

    for page in input.pages:
        try:
            result = _process_one_page(
                input.jurisdiction, input.source_pdf_name, page.page_number,
                page.page_text, input.extraction_hints,
            )
        except Exception as e:
            logger.error(
                "Failed to process page %s of '%s': %s", page.page_number, input.source_pdf_name, e,
            )
            continue

        total_inserted += result["permits_inserted"]
        total_failed += result["permits_failed"]

    logger.info(
        "Batch complete for '%s': %s permit(s) inserted, %s failed across %s page(s)",
        input.source_pdf_name, total_inserted, total_failed, len(input.pages),
    )
    return {"permits_inserted": total_inserted, "permits_failed": total_failed}


if __name__ == "__main__":
    # Start the engine and wait for events to roll in
    worker = hatchet.worker(name="permit-pipeline-worker")
    worker.register_workflow(enrich_batch_workflow)
    worker.register_workflow(pdf_batch_workflow)

    logger.info("Hatchet worker is running and listening for jobs...")
    worker.start()
