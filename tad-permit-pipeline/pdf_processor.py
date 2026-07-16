import os
import re
import fitz  # PyMuPDF is imported as fitz
import requests
from openrouter import OpenRouter
from pydantic import BaseModel


MODEL = "anthropic/claude-3.5-sonnet"


# 1. Define the target schema
class ExtractedScope(BaseModel):
    raw_scope_of_work: str
    scope_summary: str
    building_systems: list[str]

def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extracts raw text from a PDF page-by-page while preserving layout columns.
    """
    extracted_text = []
    try:
        # Open the PDF document
        with fitz.open(pdf_path) as doc:
            for page in doc:
                # "blocks" or "text" modes preserve spatial layout beautifully
                text = page.get_text("text") 
                if text:
                    extracted_text.append(text)
    except Exception as e:
        print(f"  ⚠️ PDF extraction error on {pdf_path}: {e}")
        
    return "\n".join(extracted_text)

def extract_scope_with_llm(raw_text: str) -> ExtractedScope | None:
    """
    Calls OpenRouter directly using the native OpenRouter Python SDK.
    """
    api_key = os.getenv("OPEN_ROUTER_KEY", "")
    model_choice = MODEL

    # 2. Open client context (recommended by the SDK for resource management)
    try:
        with OpenRouter(
            api_key=api_key,
            http_referer="https://github.com/your-username/permit-pipeline", # Optional site tracking
            x_open_router_title="Permit Pipeline Ingestion"
        ) as client:
            
            # Send message using the native OpenRouter chat utility
            # It accepts direct typing schemas for structured outputs
            response = client.chat.send(
                model=model_choice,
                messages=[
                    {
                        "role": "system", 
                        "content": "You are a professional construction auditor. Extract clean scope variables from this raw text."
                    },
                    {
                        "role": "user", 
                        "content": f"Extract the scope details:\n\n{raw_text}"
                    }
                ],
                # If the specific model supports JSON/Pydantic schemas, we parse it
                response_format=ExtractedScope, 
            )
            
            # Extract the native parsed structure from the response envelope
            return response.choices[0].message.parsed
            
    except Exception as e:
        print(f"  ⚠️ Native OpenRouter SDK extraction failed: {e}")
        return None

import re
import requests
import os

def download_nyc_pdf(permit_id: str) -> str | None:
    """
    Translates Socrata permit format (e.g., X01411972-I1-GC-CX) 
    to NYC BIS format and downloads the PDF.
    """
    os.makedirs("./temp_pdfs", exist_ok=True)
    local_path = f"./temp_pdfs/{permit_id}.pdf"
    
    if os.path.exists(local_path):
        print(f"    ℹ️ PDF already exists locally: {local_path}")
        return local_path

    # Map Borough letters to NYC's official numeric codes
    borough_map = {"M": "1", "X": "2", "B": "3", "Q": "4", "S": "5"}

    try:
        # Parse the ID using Regex
        # Matches: [Borough Letter] [7-8 digit Job Number] -I [Sequence Number]
        match = re.match(r"^([MXBQS])(\d+)-I(\d+)", permit_id)
        if not match:
            print(f"    ⚠️ Could not parse permit ID structure: {permit_id}")
            return None
            
        boro_letter, job_num, seq_num = match.groups()
        boro_code = borough_map.get(boro_letter)
        
        # Build the exact 9-digit Job Number (e.g., 201411972)
        full_job_number = f"{boro_code}{job_num}"
        
        # Construct the official BIS query parameters
        url = (
            f"https://a810-bisweb.nyc.gov/bisweb/PermitDocumentServlet"
            f"?passjobnumber={full_job_number}"
            f"&passpermitseq={seq_num}"
        )
        
        print(f"    📡 Requesting PDF via translation: {url}")
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://a810-bisweb.nyc.gov/bisweb/PermitQuerySrvlt",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5"
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        
        # Check if we got a real PDF back
        if response.status_code == 200 and b"%PDF" in response.content[:10]:
            with open(local_path, "wb") as f:
                f.write(response.content)
            print(f"    ✅ Successfully downloaded PDF for permit {permit_id}")
            return local_path
        else:
            print(f"    ⚠️ No valid PDF returned from NYC server for permit {permit_id}")
            # 🔍 Debugging: Print the first 300 characters of the response to see what NYC actually sent
            snippet = response.content[:300].decode('utf-8', errors='ignore').strip()
            print(f"    🔍 NYC Server Response Snippet:\n{snippet}\n" + "-"*40)
            return None
            
    except Exception as e:
        print(f"    ❌ Failed to download PDF for permit {permit_id}: {e}")
        return None