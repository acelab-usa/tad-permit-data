import os
import requests
from dotenv import load_dotenv
import database
from hatchet_sdk import Hatchet
from permit import PermitSchemaV2
from datetime import datetime
import database
import fitz

load_dotenv()
APP_TOKEN = os.getenv("SOCRATA_APP_TOKEN")
NYC_NO_PERMIT = "Permit is no"

# City Configurations: Centralizing the API URLs and sorting columns
CITY_CONFIGS = {
    "chicago": {
        "url": "https://data.cityofchicago.org/api/v3/views/ydr8-5enu/query.json",
        "date_column": "issue_date"
    },
    "nyc": {
        "url": "https://data.cityofnewyork.us/api/v3/views/rbx6-tga4/query.json",
        "date_column": "issued_date"
    }
}


def fetch_permits(url, date_column, limit, page, app_token=APP_TOKEN,) -> list:
    headers = {
        "X-App-Token": app_token,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    # Dynamically inject the correct sorting column for the respective city
    payload = {
        "query": f"SELECT * ORDER BY `{date_column}` DESC",
        "page": {
            "pageNumber": page,
            "pageSize": limit
        },
        "includeSynthetic": False  
    }

    print(f"🚀 Sending request to portal endpoint...")
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        response.raise_for_status()
        
        data = response.json()

        print(f"✅ Success! Retrieved {len(data)} raw records.")
        return data

    except requests.exceptions.Timeout:
        print("❌ Error: The network request timed out.")
        return []
    except requests.exceptions.HTTPError as http_err:
        print(f"❌ HTTP Error occurred: {http_err}")
        print(f"Response details: {response.text}")
        return []
    except Exception as err:
        print(f"❌ An unexpected error occurred: {err}")
        return []


def map_chicago_to_schema(raw_item: dict) -> dict:
    """
    Maps raw Chicago API payload to our new PermitSchemaV2 dictionary structure.
    """
    # 1. Parse raw filing date safely
    raw_date = raw_item.get("issue_date")
    parsed_date = None
    if raw_date:
        # Standard Chicago date format helper
        parsed_date = datetime.strptime(raw_date.split("T")[0], "%Y-%m-%d").date()

    # 2. Build the exact dictionary Pydantic expects
    return {
        # --- Required Metadata ---
        "permit_id": raw_item.get("permit_"),
        "jurisdiction": "chicago",
        "source_url": "https://data.cityofchicago.org/resource/ydr8-56us.json", # The API endpoint url
        "source_format": "API",
        
        # --- Core Info ---
        "address": f"{raw_item.get('street_number', '')} {raw_item.get('street_direction', '')} {raw_item.get('street_name', '')} {raw_item.get('suffix', '')}".strip(),
        "filing_date": parsed_date,
        "owner_name": raw_item.get("contact_1_name"),  # Chicago sometimes lists owner/contact here
        "contractor_name": raw_item.get("contact_2_name"), # Chicago lists contractor info here
        
        # --- Taxonomies & Valuation ---
        "permit_type_raw": raw_item.get("permit_type", "UNKNOWN"),
        "permit_type_normalized": "Other",
        "square_footage": None,             
        "valuation": float(raw_item.get("reported_cost", 0)) if raw_item.get("reported_cost") else None,
        
        # --- Scopes ---
        "raw_scope_of_work": raw_item.get("work_description", "No description provided."),
        "scope_summary": raw_item.get("work_description", "No description provided.")[:150],
        "building_systems": [] 
    }


def map_nyc_to_schema(raw_item: dict) -> dict:
    """
    Maps raw NYC DOB NOW Approved Permits payload to our unified PermitSchemaV2.
    """
    # 1. Safely extract and parse a primary date
    raw_date = raw_item.get("issued_date") or raw_item.get("approved_date")
    parsed_date = None
    if raw_date:
        try:
            date_str = str(raw_date).split("T")[0].strip()
            parsed_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except (ValueError, IndexError):
            parsed_date = None

    # 2. Construct the clean address (DOB NOW uses 'house_no' and 'street_name')
    house_num = raw_item.get("house_no", "").strip()
    street_name = raw_item.get("street_name", "").strip()
    full_address = f"{house_num} {street_name}".strip()

    # 3. Create fallback portal URL
    source_url = f"https://a810-dobnow.nyc.gov/html/"

    return {
        "permit_id": raw_item.get("job_filing_number"),
        "jurisdiction": "nyc",
        "source_url": source_url,
        "source_format": "API",
        "address": full_address or "UNKNOWN",
        "filing_date": parsed_date,
        "owner_name": raw_item.get("owner_s_business_name"),
        "contractor_name": raw_item.get("licensee_s_business_name"),
        "permit_type_raw": raw_item.get("filing_reason") or raw_item.get("work_type") or "UNKNOWN",
        "permit_type_normalized": "Other",
        "square_footage": None,
        "valuation": float(raw_item.get("estimated_job_costs", 0)) if raw_item.get("estimated_job_costs") else None,
        "raw_scope_of_work": f"Work on Floor: {raw_item.get('work_on_floor', 'N/A')}. Job Description: {raw_item.get('job_description', 'N/A')}",
        "scope_summary": f"Permit issued for {raw_item.get('work_type', 'general')} construction.",
        "building_systems": [] 
    }


def monthly_pdf_ingestion(folder_path: str = "./temp_pdfs", month_cap: int = 1, page_cap: int = None):
    """
    Scans for large multi-page monthly PDF reports, rips them into single page 
    text strings, and streams them out as parallel tasks via Hatchet.
    """
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
        return

    pdf_files = [f for f in os.listdir(folder_path) if f.lower().endswith('.pdf')]

    for i in range(month_cap):
        filename = pdf_files[i]
        local_path = os.path.join(folder_path, filename)
        print(f"📖 Opening monthly compilation report: {filename}")
        
        try:
            with fitz.open(local_path) as doc:
                total_pages = page_cap if page_cap != None else len(doc)
                print(f"⚡ Discovered {total_pages} total ledger pages. Splitting into Hatchet queue...")
                
                for page_idx in range(total_pages):
                    page = doc[page_idx]
                    page_text = page.get_text()
                    
                    if not page_text.strip():
                        continue # Skip empty blank spacer pages
                        
                    # Send each individual page text payload out as its own event
                    hatchet.event.push(
                        "pdf:process",
                        {
                            "source_pdf_name": filename,
                            "page_number": page_idx + 1,
                            "page_text": page_text
                        }
                    )
            
        except Exception as e:
            print(f"❌ Error splitting monthly ledger {filename}: {e}")


def load_data(city: str = "chicago", size=100):
    city = city.lower()
    database.init_db()

    # Structured API Data Handling
    if city in CITY_CONFIGS:
        config = CITY_CONFIGS[city]
        
        # 1. Fetch live data
        raw_records = fetch_permits(url=config["url"], date_column=config["date_column"], limit=size, page=1)
        mapper_func = map_chicago_to_schema if city == "chicago" else map_nyc_to_schema

        # 2. Loop through and process records
        for raw_item in raw_records:
            try:
                # Validate and create the Pydantic object
                validated_permit = PermitSchemaV2(**mapper_func(raw_item))

                if city == "nyc" and validated_permit.permit_id == NYC_NO_PERMIT:
                    print(f"  ⚠️ ({city}) Skipping: {validated_permit.permit_id}")
                    continue

                # 3. Pass the Pydantic object directly to the database!
                inserted = database.insert_permit(validated_permit)
                if inserted:
                    print(f"  🎉 ({city}) Saved: Permit {validated_permit.permit_id} ({validated_permit.address})")
                    
                    hatchet.event.push(
                        "permit:enrich",
                        {"permit_id": validated_permit.permit_id, "raw_text": validated_permit.raw_scope_of_work}
                    )

                else:
                    print(f"  ⚠️ ({city}) Skipped: Permit {validated_permit.permit_id} already exists.")
                    
            except Exception as e:
                print(f"Failed to parse a record: {e}")
    
    # Default to Local PDF Ingestion
    else:
        if city == "allen":
            monthly_pdf_ingestion(folder_path = './allen_pdfs', page_cap=int(size/5))


hatchet = Hatchet()

if __name__ == "__main__":
    # Test loading Chicago data
    print("--- INGESTING CHICAGO DATA ---")
    load_data("chicago", size=100)
    
    
    # Test loading NYC data
    print("\n--- INGESTING NYC DATA ---")
    load_data("nyc", size=100)
    
    # Test loading Allen data
    print("\n--- INGESTING ALLEN DATA ---")
    load_data("allen", size=100)