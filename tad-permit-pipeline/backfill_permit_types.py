"""One-off backfill: re-derive permit_type_normalized for existing rows.

The normalization logic in permit_types.py is new -- rows ingested before it
existed have whatever each source used to write there (always "Other" for
chicago/nyc, a passthrough Residential/Commercial split for austin, or the
LLM's own uncontrolled guess for allen). This recomputes permit_type_normalized
from each row's permit_type_raw so existing data is searchable/filterable
the same way newly-ingested data will be, without needing to re-run
ingestion (which would hit live APIs/incur LLM costs) just to fix a column.

Usage:
    uv run python backfill_permit_types.py            # apply the backfill
    uv run python backfill_permit_types.py --dry-run  # preview counts only, no writes
"""
import argparse
import sqlite3
from collections import Counter

import database
from logging_setup import get_logger
from permit_types import normalize_permit_type

logger = get_logger("backfill_permit_types")


def run(dry_run: bool = False) -> None:
    conn = database.get_connection()
    try:
        rows = conn.execute("SELECT id, jurisdiction, permit_type_raw, permit_type_normalized FROM permits").fetchall()

        before_counts = Counter(r["permit_type_normalized"] for r in rows)
        updates = []
        after_counts = Counter()

        for row in rows:
            new_value = normalize_permit_type(row["permit_type_raw"])
            after_counts[new_value] += 1
            if new_value != row["permit_type_normalized"]:
                updates.append((new_value, row["id"]))

        logger.info("%s total rows, %s would change", len(rows), len(updates))
        logger.info("before: %s", dict(before_counts.most_common()))
        logger.info("after:  %s", dict(after_counts.most_common()))

        if dry_run:
            logger.info("--dry-run set, no changes written")
            return

        if not updates:
            logger.info("nothing to update")
            return

        conn.executemany("UPDATE permits SET permit_type_normalized = ? WHERE id = ?", updates)
        conn.commit()
        logger.info("updated %s rows", len(updates))
    except sqlite3.Error as e:
        logger.error("backfill failed: %s", e)
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Recompute permit_type_normalized for existing rows.")
    parser.add_argument("--dry-run", action="store_true", help="Preview the before/after distribution without writing.")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
