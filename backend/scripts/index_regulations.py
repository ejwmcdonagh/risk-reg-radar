"""
Build the regulation knowledge base in regulation_chunks.

Regulation text is loaded from data/regulation_chunks.json - edit that file
to add or update articles without touching Python code. Idempotent: clears
all existing rows before re-indexing.

Run from backend/ with the venv active:
    python scripts/index_regulations.py

Requires VOYAGE_API_KEY in backend/.env.
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import truststore
truststore.inject_into_ssl()

from app.config import settings
from app.db.client import get_db
from app.services.embeddings import generate_embedding

_DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "regulation_chunks.json")

with open(_DATA_FILE) as _f:
    CHUNKS: list[dict] = json.load(_f)


def main() -> None:
    if not settings.voyage_api_key:
        print("VOYAGE_API_KEY not set in backend/.env - exiting.")
        sys.exit(1)

    db = get_db()

    # Idempotent: wipe all existing chunks before re-indexing
    db.table("regulation_chunks").delete().neq(
        "id", "00000000-0000-0000-0000-000000000000"
    ).execute()
    print(f"Cleared existing chunks. Indexing {len(CHUNKS)} regulation articles...\n")

    ok = 0
    failed = 0
    for chunk in CHUNKS:
        embedding = generate_embedding(chunk["content"])
        if embedding is None:
            print(f"  FAILED  {chunk['regulation']:15} {chunk['article_ref']}")
            failed += 1
            continue

        db.table("regulation_chunks").insert({
            "regulation":  chunk["regulation"],
            "article_ref": chunk["article_ref"],
            "title":       chunk["title"],
            "content":     chunk["content"],
            "embedding":   embedding,
        }).execute()
        ok += 1
        print(f"  [{ok:02d}] {chunk['regulation']:15} {chunk['article_ref']}")
        time.sleep(20)  # Voyage AI free tier allows ~3 requests/minute

    print(f"\nDone. Indexed {ok} chunks. {failed} failed.")
    if failed:
        print("Re-run the script to retry failed chunks (it will clear and rebuild from scratch).")


if __name__ == "__main__":
    main()
