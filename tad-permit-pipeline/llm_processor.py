# llm_processor.py
import os
from openai import OpenAI
from dotenv import load_dotenv
from models import PermitEnrichmentSchema

load_dotenv()

# Initialize the OpenAI client pointed at OpenRouter
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPEN_ROUTER_KEY"),
)

def enrich_permit_text(raw_description: str) -> PermitEnrichmentSchema | None:
    """
    Sends the raw permit text to OpenRouter and extracts a structured 
    summary and a list of building systems/materials.
    """
    if not raw_description or not raw_description.strip():
        return None

    try:
        response = client.chat.completions.create(
            model="google/gemini-2.5-flash", # High speed, low cost, excellent structured extraction
            response_format={"type": "json_object"}, # Forces a valid JSON response
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert construction data analyst. Analyze the provided raw municipal permit description. "
                        "Return a JSON object matching this schema exactly:\n"
                        "{\n"
                        "  'scope_summary': 'A clear, readable string summarizing the project scope.',\n"
                        "  'building_systems': ['System/Material 1', 'System/Material 2']\n"
                        "}"
                    )
                },
                {
                    "role": "user",
                    "content": f"Raw Permit Text: {raw_description}"
                }
            ],
            temperature=0.1
        )
        
        # Parse the JSON string directly back into our Pydantic model
        raw_json = response.choices[0].message.content
        return PermitEnrichmentSchema.model_validate_json(raw_json)

    except Exception as e:
        print(f"❌ OpenRouter API extraction failed: {e}")
        return None