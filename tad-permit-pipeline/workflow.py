# workflow.py
import json
from pydantic import BaseModel
from hatchet_sdk import Hatchet, Context
import llm_processor
import database

hatchet = Hatchet()

# 1. Define what input data the worker expects to receive
class EnrichInput(BaseModel):
    permit_id: str
    raw_text: str

# 2. Register the background workflow with Hatchet V1
enrich_workflow = hatchet.workflow(
    name="PermitEnrichment", 
    on_events=["permit:enrich"],
    input_validator=EnrichInput
)

# 3. Define the actual task execution block
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


if __name__ == "__main__":
    # Start the engine and wait for events to roll in
    worker = hatchet.worker(name="permit-pipeline-worker")
    worker.register_workflow(enrich_workflow)
    
    print("🚀 Hatchet worker is running and listening for jobs...")
    worker.start()