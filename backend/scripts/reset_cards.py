"""
Reset all cards and clusters so card generation re-runs with the updated prompt.

Run from backend/ with the venv active:
    python3 scripts/reset_cards.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.client import get_db

def main():
    db = get_db()
    cards = db.table("provocation_cards").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
    print(f"Deleted {len(cards.data)} cards")
    clusters = db.table("signal_clusters").update({"status": "pending"}).eq("status", "card_generated").execute()
    print(f"Reset {len(clusters.data)} clusters to pending")

if __name__ == "__main__":
    main()
