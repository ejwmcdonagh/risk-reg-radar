"""
One-off backfill: set published_at for CISA KEV signals from raw_data->dateAdded.

Run from backend/ with the venv active:
    python3 scripts/backfill_kev_dates.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.client import get_db
from app.ingestion.cisa_kev import _parse_date


def main() -> None:
    db = get_db()
    result = (
        db.table("signals")
        .select("id, raw_data")
        .eq("source", "cisa_kev")
        .is_("published_at", "null")
        .execute()
    )
    rows = result.data or []
    print(f"Found {len(rows)} CISA KEV signals with null published_at")

    updated = 0
    skipped = 0
    for row in rows:
        date_added = (row.get("raw_data") or {}).get("dateAdded")
        dt = _parse_date(date_added)
        if dt is None:
            skipped += 1
            continue
        db.table("signals").update({"published_at": dt.isoformat()}).eq("id", row["id"]).execute()
        updated += 1

    print(f"Updated: {updated}  No date in raw_data (left null): {skipped}")


if __name__ == "__main__":
    main()
