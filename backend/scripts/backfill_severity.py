"""
One-off backfill: infer severity for signals that currently have severity=null.

Run from backend/ with the venv active:
    python scripts/backfill_severity.py

Safe to re-run — only touches rows where severity IS NULL.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.client import get_db
from app.severity_mapper import infer_severity


def main() -> None:
    db = get_db()

    result = db.table("signals").select("id, title, summary").is_("severity", "null").execute()
    rows = result.data or []
    print(f"Found {len(rows)} signals with null severity")

    updated = 0
    skipped = 0
    for row in rows:
        severity = infer_severity(row.get("title") or "", row.get("summary") or "")
        if severity is None:
            skipped += 1
            continue
        db.table("signals").update({"severity": severity.value}).eq("id", row["id"]).execute()
        updated += 1

    print(f"Updated: {updated}  No match (left null): {skipped}")


if __name__ == "__main__":
    main()
