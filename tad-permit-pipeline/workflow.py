# workflow.py
import os
import json
from pydantic import BaseModel
from hatchet_sdk import Hatchet, Context
import pdf_processor
import database
from dotenv import load_dotenv

# Ensure environment variables are loaded first
load_dotenv()

hatchet = Hatchet()

# 1. Define the strictly typed input schema for the workflow
class EnrichInput(BaseModel):
    permit_id: str

# 2. Register the workflow with an input_validator in V1
enrich_workflow = hatchet.workflow(
    name="PermitEnrichment", 
    on_events=["permit:enrich"],
    input_validator=EnrichInput
)

# 3. Step 1: Download the PDF.
# Note: In V1, the first argument is your parsed 'EnrichInput' Pydantic model.
@enrich_workflow.task(name="download_pdf")
def download_pdf(input: EnrichInput, ctx: Context) -> dict:
    """Step 1: Download the PDF asynchronously."""
    permit_id = input.permit_id
    print(f"🎬 [Hatchet V1] Starting PDF download for {permit_id}")
    
    pdf_path = pdf_processor.download_nyc_pdf(permit_id)
    if not pdf_path:
        return {"status": "skipped", "reason": "No PDF found or download failed"}
        
    return {"status": "success", "pdf_path": pdf_path}

# 4. Step 2: Parse and Enrich.
# Note: We pass the actual python 'download_pdf' function/task object inside the parents list!
@enrich_workflow.task(name="parse_and_enrich", parents=[download_pdf])
def parse_and_enrich(input: EnrichInput, ctx: Context) -> dict:
    """Step 2: Parse PDF text and call OpenRouter."""
    # We pass the actual Python task function object to retrieve its output
    download_result = ctx.task_output(download_pdf)
    
    if download_result.get("status") == "skipped":
        return download_result
        
    permit_id = input.permit_id
    pdf_path = download_result["pdf_path"]
    
    # Extract plain text with PyMuPDF
    print(f"📄 [Hatchet V1] Extracting text from {pdf_path}")
    raw_text = pdf_processor.extract_text_from_pdf(pdf_path)
    if not raw_text.strip():
        return {"status": "failed", "reason": "PDF was empty or unparseable"}
    
    # Query OpenRouter using our native SDK implementation
    print(f"🧠 [Hatchet V1] Requesting OpenRouter extraction for {permit_id}")
    enriched_scope = pdf_processor.extract_scope_with_llm(raw_text)
    
    if not enriched_scope:
        return {"status": "failed", "reason": "OpenRouter extraction failed"}
        
    # Update your SQLite database
    conn = database.get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE building_permits
            SET raw_scope_of_work = ?,
                scope_summary = ?,
                building_systems = ?
            WHERE permit_id = ?
        """, (
            enriched_scope.raw_scope_of_work,
            enriched_scope.scope_summary,
            json.dumps(enriched_scope.building_systems),
            permit_id
        ))
        conn.commit()
        print(f"💾 [Hatchet V1] Cleanly enriched and updated permit {permit_id}!")
    except Exception as e:
        print(f"❌ [Hatchet V1] Database update failed: {e}")
    finally:
        conn.close()
        
    return {"status": "completed"}


if __name__ == "__main__":
    worker = hatchet.worker(name="permit-pipeline-worker")
    
    # Register the workflow instance
    worker.register_workflow(enrich_workflow)
    
    print("🚀 Hatchet V1 worker is running and listening for jobs...")
    worker.start()