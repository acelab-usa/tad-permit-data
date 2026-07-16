import os
import requests
from dotenv import load_dotenv
import database
from permit import PermitSchema

load_dotenv()
APP_TOKEN = os.getenv("SOCRATA_APP_TOKEN")

# City Configurations: Centralizing the API URLs and sorting columns
CITY_CONFIGS = {
    "chicago": {
        "url": "https://data.cityofchicago.org/api/v3/views/ydr8-5enu/query.json",
        "date_column": "issue_date"
    },
    "nyc": {
        "url": "https://data.cityofnewyork.us/api/v3/views/rbx6-tga4/query.json",
        "date_column": "issued_date" # NYC uses 'issued_date' on dataset rbx6-tga4
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


def map_chicago_to_schema(raw: dict) -> PermitSchema:
    full_address = f"{raw.get('street_number', '')} {raw.get('street_direction', '')} {raw.get('street_name', '')}".strip()
    return PermitSchema(
        permit_id=raw.get("permit_"),
        jurisdiction="Chicago",
        source_format="API",
        filing_date=raw.get("application_start_date"),
        permit_type=raw.get("permit_type"),
        address=full_address,
        owner_name=None,
        contractor_name=raw.get("contact_2_name"),
        valuation=raw.get("reported_cost"), 
        square_footage=None,
        raw_scope_of_work=raw.get("work_description")
    )


def map_nyc_to_schema(raw: dict) -> PermitSchema:
    full_address = f"{raw.get('house_no', '')} {raw.get('street_name', '')}, {raw.get('borough', '')} {raw.get('zip_code', '')}".strip()
    return PermitSchema(
        permit_id=raw.get("tracking_number"),
        jurisdiction="NYC",
        source_format="API",
        filing_date=raw.get("issued_date"), # NYC provides the issue date directly here
        permit_type=raw.get("work_type"),
        address=full_address,
        owner_name=raw.get("owner_name"),
        contractor_name=raw.get("applicant_business_name"),
        valuation=raw.get("estimated_job_costs"), 
        square_footage=None,
        raw_scope_of_work=raw.get("job_description")
    )


def load_data(city: str = "chicago", size=100):
    city = city.lower()
    if city not in CITY_CONFIGS:
        print(f"❌ Unknown city target context: {city}")
        return

    database.init_db()
    config = CITY_CONFIGS[city]
    
    # 1. Fetch live data
    raw_records = fetch_permits(url=config["url"], date_column=config["date_column"], limit=size, page=1)
    
    mapper_func = map_chicago_to_schema if city == "chicago" else map_nyc_to_schema

    # 2. Loop through and process records
    for raw_item in raw_records:
        try:
            # Validate and create the Pydantic object
            validated_permit = mapper_func(raw_item)

            # 3. Pass the Pydantic object directly to the database!
            inserted = database.insert_permit(validated_permit)
            if inserted:
                print(f"  🎉 Saved: Permit {validated_permit.permit_id} ({validated_permit.address})")
            else:
                print(f"  ⚠️ Skipped: Permit {validated_permit.permit_id} already exists.")
                
        except Exception as e:
            print(f"Failed to parse a record: {e}")

if __name__ == "__main__":
    # Test loading Chicago data
    print("--- INGESTING CHICAGO DATA ---")
    load_data("chicago", size=100)
    
    '''
    # Test loading NYC data
    print("\n--- INGESTING NYC DATA ---")
    load_data("nyc", size=100)
    '''