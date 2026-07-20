# llm_processor.py
import os
from openai import OpenAI
from dotenv import load_dotenv
from models import PermitEnrichmentSchema, MonthlyPDFPageExtractSchema

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

def extract_multiple_permits_from_text(chunk_text: str) -> MonthlyPDFPageExtractSchema | None:
    """
    Analyzes a chunk of text containing multiple permit listings and 
    extracts them into a structured collection of individual permits.
    """
    if not chunk_text or not chunk_text.strip():
        return None

    try:
        response = client.chat.completions.create(
            model="google/gemini-2.5-flash",
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert data extraction assistant processing pages from a monthly municipal permit ledger. "
                        "Identify every single distinct permit listed in the text. "
                        "Return a JSON object containing a list named 'permits_found' matching this schema blueprint:\n"
                        "{\n"
                        "  'permits_found': [\n"
                        "    {\n"
                        "      'permit_id': 'string',\n"
                        "      'filing_date': 'YYYY-MM-DD',\n"
                        "      'permit_type_raw': 'string',\n"
                        "      'permit_type_normalized': 'string',\n"
                        "      'address': 'string',\n"
                        "      'owner_name': 'string',\n"
                        "      'contractor_name': 'string',\n"
                        "      'valuation': 0.0,\n"
                        "      'square_footage': 0.0,\n"
                        "      'raw_scope_of_work': 'verbatim text from document',\n"
                        "      'scope_summary': '1 sentence summary',\n"
                        "      'building_systems': ['material1', 'material2']\n"
                        "    }\n"
                        "  ]\n"
                        "}"
                    )
                },
                {
                    "role": "user",
                    "content": f"Raw Monthly Ledger Page Text:\n{chunk_text}"
                }
            ],
            temperature=0.1
        )
        
        raw_json = response.choices[0].message.content
        return MonthlyPDFPageExtractSchema.model_validate_json(raw_json)

    except Exception as e:
        print(f"❌ Failed multi-permit extraction: {e}")
        return None