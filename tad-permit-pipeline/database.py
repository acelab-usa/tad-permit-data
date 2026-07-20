import sqlite3
from datetime import datetime
from permit import PermitSchemaV2
import json

DB_NAME = "permits.db"

def init_db():
    """Initializes the SQLite database and creates the unified permits table."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS permits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            permit_id TEXT NOT NULL,
            jurisdiction TEXT NOT NULL,
            source_url TEXT,
            source_format TEXT NOT NULL,
            extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            filing_date TEXT,
            permit_type_raw TEXT,
            permit_type_normalized TEXT,
            address TEXT,
            owner_name TEXT,
            contractor_name TEXT,
            valuation REAL,
            square_footage REAL,
            
            raw_scope_of_work TEXT,
            scope_summary TEXT,
            building_systems TEXT,
            
            UNIQUE(permit_id, jurisdiction)
        )
    ''')
    
    conn.commit()
    conn.close()
    print(f"✅ Database initialized successfully: '{DB_NAME}'")

def insert_permit(permit: PermitSchemaV2) -> bool:
    """Accepts a fully validated Pydantic PermitSchema object directly."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    sql = '''
        INSERT OR IGNORE INTO permits (
                permit_id, jurisdiction, source_url, source_format, address, filing_date,
                owner_name, contractor_name, permit_type_raw, permit_type_normalized,
                square_footage, valuation, raw_scope_of_work, scope_summary, building_systems
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
    
    values = (
        permit.permit_id,
        permit.jurisdiction,
        permit.source_url,
        permit.source_format,
        permit.address,
        permit.filing_date,
        permit.owner_name,
        permit.contractor_name,
        permit.permit_type_raw,
        permit.permit_type_normalized,
        permit.square_footage,
        permit.valuation,
        permit.raw_scope_of_work,
        permit.scope_summary,
        json.dumps(permit.building_systems) if permit.building_systems else "[]"
    )
    
    cursor.execute(sql, values)
    conn.commit()
    changes = conn.total_changes
    conn.close()
    return changes > 0

def get_connection():
    """Creates and returns a connection to the SQLite database."""
    # Replace 'permits.db' with your actual database filename
    conn = sqlite3.connect("permits.db")
    # This allows fetching rows as dictionaries instead of raw tuples if desired
    conn.row_factory = sqlite3.Row 
    return conn

if __name__ == "__main__":
    init_db()