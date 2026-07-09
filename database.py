import sqlite3
from datetime import datetime
from permit import PermitSchema

DB_NAME = "building_permits.db"

def init_db():
    """Initializes the SQLite database and creates the unified permits table."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Create the unified schema v1 table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS building_permits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            permit_id TEXT NOT NULL,
            jurisdiction TEXT NOT NULL,
            source_format TEXT NOT NULL,
            extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            filing_date TEXT,
            permit_type TEXT,
            address TEXT,
            owner_name TEXT,
            contractor_name TEXT,
            valuation REAL,
            square_footage REAL,  -- Will remain NULL for API sources
            
            raw_scope_of_work TEXT,
            model_scope_summary TEXT,          -- Handled by LLM later
            materials_systems_mentioned TEXT,  -- Handled by LLM later
            
            UNIQUE(permit_id, jurisdiction)   -- Avoids duplicate inserts
        )
    ''')
    
    conn.commit()
    conn.close()
    print(f"✅ Database initialized successfully: '{DB_NAME}'")

def insert_permit(permit: PermitSchema) -> bool:
    """Accepts a fully validated Pydantic PermitSchema object directly."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    sql = '''
        INSERT OR IGNORE INTO building_permits (
            permit_id, jurisdiction, source_format, filing_date, 
            permit_type, address, owner_name, contractor_name, 
            valuation, square_footage, raw_scope_of_work,
            model_scope_summary, materials_systems_mentioned
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    '''
    
    # Safely unpack the Pydantic data properties
    # Convert the materials list to a string or keep it None if empty
    materials_string = ", ".join(permit.materials_systems_mentioned) if permit.materials_systems_mentioned else None
    
    values = (
        permit.permit_id,
        permit.jurisdiction,
        permit.source_format,
        permit.filing_date,
        permit.permit_type,
        permit.address,
        permit.owner_name,
        permit.contractor_name,
        permit.valuation,
        permit.square_footage,
        permit.raw_scope_of_work,
        permit.model_scope_summary,
        materials_string
    )
    
    cursor.execute(sql, values)
    conn.commit()
    changes = conn.total_changes
    conn.close()
    return changes > 0

if __name__ == "__main__":
    init_db()