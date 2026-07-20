# workflow.py
import json
from pydantic import BaseModel
from hatchet_sdk import Hatchet, Context
import llm_processor
import pdf_processor
import database

hatchet = Hatchet()

# Define what input data the worker expects to receive
class EnrichInput(BaseModel):
    permit_id: str
    raw_text: str

# Define input data for PDF processing
class PageIngestionInput(BaseModel):
    source_pdf_name: str
    page_number: int
    page_text: str

# Register the background workflow with Hatchet V1
enrich_workflow = hatchet.workflow(
    name="PermitEnrichment", 
    on_events=["permit:enrich"],
    input_validator=EnrichInput
)

# Define the actual task execution block
@enrich_workflow.task(name="process_llm_enrichment")
def process_llm_enrichment(input: EnrichInput, ctx: Context) -> dict:
    print(f"🎬 [Hatchet] Processing AI enrichment for permit: {input.permit_id}")
    
    # Run existing OpenRouter function
    enriched_data = llm_processor.enrich_permit_text(input.raw_text)
    
    if not enriched_data:
        raise Exception(f"OpenRouter returned empty data for {input.permit_id}")
        
    # Update SQLite database with the structured response
    conn = database.get_connection()
    cursor = conn.cursor()
    try:
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
        print(f"💾 [Hatchet] Successfully updated {input.permit_id} in DB!")
    except Exception as e:
        print(f"❌ [Hatchet] Database update failed: {e}")
        raise e  # Raising lets Hatchet know to retry the step automatically
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
    print(f"🎬 [Hatchet] Processing page {input.page_number} from '{input.source_pdf_name}'")
    
    # Send this single page text matrix to OpenRouter
    extracted_data = llm_processor.extract_multiple_permits_from_text(input.page_text)
    
    if not extracted_data or not extracted_data.permits_found:
        print(f"ℹ️ [Hatchet] No permits found on page {input.page_number}")
        return {"permits_inserted": 0}

    print(f"🧠 [Hatchet] Found {len(extracted_data.permits_found)} permits on page {input.page_number}. Writing to DB...")
    
    conn = database.get_connection()
    cursor = conn.cursor()
    inserted_count = 0
    
    try:
        for permit in extracted_data.permits_found:
            cursor.execute("""
                INSERT OR IGNORE INTO permits (
                    permit_id, jurisdiction, source_format, source_url, filing_date,
                    permit_type_raw, permit_type_normalized, address, owner_name, 
                    contractor_name, valuation, square_footage, raw_scope_of_work, 
                    scope_summary, building_systems
                ) VALUES (?, 'allen', 'PDF', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                permit.permit_id,
                input.source_pdf_name, # Track which monthly file this came from
                permit.filing_date,
                permit.permit_type_raw,
                permit.permit_type_normalized,
                permit.address,
                permit.owner_name,
                permit.contractor_name,
                permit.valuation,
                permit.square_footage,
                permit.raw_scope_of_work,
                permit.scope_summary,
                json.dumps(permit.building_systems)
            ))
            if conn.total_changes > 0:
                inserted_count += 1
                
        conn.commit()
        print(f"✅ [Hatchet] Saved {inserted_count} new entries from page {input.page_number}.")
    except Exception as e:
        print(f"❌ [Hatchet] DB write error on page {input.page_number}: {e}")
        raise e
    finally:
        conn.close()
        
    return {"permits_inserted": inserted_count}


if __name__ == "__main__":
    # Start the engine and wait for events to roll in
    worker = hatchet.worker(name="permit-pipeline-worker")
    worker.register_workflow(enrich_workflow)
    worker.register_workflow(pdf_workflow)

    print("🚀 Hatchet worker is running and listening for jobs...")
    worker.start()