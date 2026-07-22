import os
import sqlite3

from permit import PermitSchemaV2
import json

from logging_setup import get_logger

logger = get_logger("database")

DB_NAME = "permits.db"
# Resolve relative to this file so the DB is found the same way regardless
# of the working directory a script/dashboard/worker happens to be launched from.
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), DB_NAME)


def get_connection() -> sqlite3.Connection:
    """Creates and returns a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initializes the SQLite database and creates the unified permits table."""
    try:
        conn = get_connection()
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
                latitude REAL,
                longitude REAL,

                raw_scope_of_work TEXT,
                scope_summary TEXT,
                building_systems TEXT,

                UNIQUE(permit_id, jurisdiction)
            )
        ''')

        # Migration guard for databases created before latitude/longitude
        # existed -- CREATE TABLE IF NOT EXISTS above is a no-op on an
        # already-existing table, so add the columns directly if missing
        # rather than requiring anyone to drop and re-ingest.
        existing_columns = {row[1] for row in cursor.execute("PRAGMA table_info(permits)").fetchall()}
        for column in ("latitude", "longitude"):
            if column not in existing_columns:
                cursor.execute(f"ALTER TABLE permits ADD COLUMN {column} REAL")
                logger.info("Migrated existing permits table: added missing column '%s'", column)

        conn.commit()
        logger.info("Database initialized successfully: '%s'", DB_PATH)
    except sqlite3.Error as e:
        logger.error("Failed to initialize database: %s", e)
        raise
    finally:
        conn.close()


def insert_permit(permit: PermitSchemaV2) -> bool:
    """Accepts a fully validated Pydantic PermitSchema object and inserts it.

    Returns True if a new row was inserted, False if it was a duplicate
    (UNIQUE(permit_id, jurisdiction) conflict) or the write failed.
    """
    sql = '''
        INSERT OR IGNORE INTO permits (
                permit_id, jurisdiction, source_url, source_format, address, filing_date,
                owner_name, contractor_name, permit_type_raw, permit_type_normalized,
                square_footage, valuation, latitude, longitude,
                raw_scope_of_work, scope_summary, building_systems
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        permit.latitude,
        permit.longitude,
        permit.raw_scope_of_work,
        permit.scope_summary,
        json.dumps(permit.building_systems) if permit.building_systems else "[]",
    )

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(sql, values)
        conn.commit()
        # cursor.rowcount reflects rows affected by *this* statement (0 if the
        # UNIQUE constraint silently ignored a duplicate, 1 if inserted) --
        # unlike conn.total_changes, which accumulates across the whole
        # connection and over-reports on a connection reused across a loop.
        return cursor.rowcount > 0
    except sqlite3.Error as e:
        logger.error(
            "DB write failed for permit %s/%s: %s", permit.jurisdiction, permit.permit_id, e
        )
        return False
    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    init_db()
