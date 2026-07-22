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
class EnrichInput(BaseModel):
    permit_id: str
    raw_text: str

# Define input data for PDF processing
class PageIngestionInput(BaseModel):
    jurisdiction: str
    source_pdf_name: str
    page_number: int
    page_text: str
    extraction_hints: str | None = None

# Register the background workflow with Hatchet V1
enrich_workflow = hatchet.workflow(
    name="PermitEnrichment",
    on_events=["permit:enrich"],
    input_validator=EnrichInput
)

# Define the actual task execution block
@enrich_workflow.task(name="process_llm_enrichment")
def process_llm_enrichment(input: EnrichInput, ctx: Context) -> dict:
    logger.info("Processing AI enrichment for permit: %s", input.permit_id)

    if not input.raw_text or not input.raw_text.strip():
        # Nothing to enrich -- not a failure, just skip. Raising here would
        # make Hatchet retry indefinitely on input that will never change.
        logger.info("Permit %s has no raw text to enrich, skipping", input.permit_id)
        return {"status": "skipped", "reason": "empty raw_text"}

    enriched_data = llm_processor.enrich_permit_text(input.raw_text)

    if not enriched_data:
        # Could be a transient API failure (already retried inside
        # llm_processor) or a malformed LLM response -- either way, letting
        # Hatchet retry the step gives transient failures another chance.
        raise Exception(f"LLM enrichment failed for permit {input.permit_id}")

    try:
        conn = database.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE permits
            SET scope_summary = ?,
                building_systems = ?
            WHERE permit_id = ?
        """, (
            enriched_data.scope_summary,
            json.dumps(enriched_data.building_systems),
            input.permit_id
        ))
        conn.commit()
        logger.info("Successfully updated %s in DB", input.permit_id)
    except Exception as e:
        logger.error("Database update failed for permit %s: %s", input.permit_id, e)
        raise  # Raising lets Hatchet know to retry the step automatically
    finally:
        conn.close()

    return {"status": "success"}

# Register the PDF processing workflow with Hatchet V1
pdf_workflow = hatchet.workflow(
    name="PDFProcessing",
    on_events=["pdf:process"],
    input_validator=PageIngestionInput
)

# Define the actual task execution block
@pdf_workflow.task(name="parse_ledger_page")
def parse_ledger_page(input: PageIngestionInput, ctx: Context) -> dict:
    logger.info("Processing page %s from '%s'", input.page_number, input.source_pdf_name)

    extracted_data = llm_processor.extract_multiple_permits_from_text(
        input.page_text, extraction_hints=input.extraction_hints
    )

    if not extracted_data or not extracted_data.permits_found:
        logger.info("No permits found on page %s of '%s'", input.page_number, input.source_pdf_name)
        return {"permits_inserted": 0}

    logger.info(
        "Found %s permits on page %s of '%s'. Writing to DB...",
        len(extracted_data.permits_found), input.page_number, input.source_pdf_name,
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
                    input.page_number, input.source_pdf_name,
                )
                continue

            # PDF ledgers never carry coordinates themselves -- this is the
            # only source of a map location for these permits.
            latitude, longitude = geo.geocode_address(permit.address, input.jurisdiction)

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
                    input.jurisdiction,
                    input.source_pdf_name, # Track which monthly file this came from
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
                    permit.permit_id, input.page_number, input.source_pdf_name, e,
                )

        conn.commit()
        logger.info(
            "Saved %s new entries from page %s of '%s' (%s failed)",
            inserted_count, input.page_number, input.source_pdf_name, failed_count,
        )
    except Exception as e:
        logger.error("DB write error on page %s of '%s': %s", input.page_number, input.source_pdf_name, e)
        raise
    finally:
        conn.close()

    return {"permits_inserted": inserted_count, "permits_failed": failed_count}


if __name__ == "__main__":
    # Start the engine and wait for events to roll in
    worker = hatchet.worker(name="permit-pipeline-worker")
    worker.register_workflow(enrich_workflow)
    worker.register_workflow(pdf_workflow)

    logger.info("Hatchet worker is running and listening for jobs...")
    worker.start()
