"""
clear_cache.py
==============
Run this from your backend/ folder to wipe all cached scrape data.
The DB structure (tables) is kept — only the data rows are deleted.

Usage:
    cd backend
    python3 clear_cache.py
"""

import sqlite3
import os

DB_PATH = os.environ.get("SQLITE_PATH", "demand_tool.db")

TABLES = [
    "scraped_items",
    "demand_scores",
    "company_financials",
    "document_insights",
    "trend_data",
    "scrape_jobs",
]

def clear_cache():
    if not os.path.exists(DB_PATH):
        print(f"[Clear] No database found at '{DB_PATH}' — nothing to clear.")
        return

    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()

    print(f"[Clear] Connected to: {DB_PATH}")
    print()

    total_deleted = 0
    for table in TABLES:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            cur.execute(f"DELETE FROM {table}")
            print(f"  ✓  {table:<25} — {count} rows deleted")
            total_deleted += count
        except Exception as e:
            print(f"  ✗  {table:<25} — error: {e}")

    conn.commit()
    conn.close()

    print()
    print(f"[Clear] Done. {total_deleted} total rows removed.")
    print("[Clear] Database tables are intact — ready for fresh scraping.")

if __name__ == "__main__":
    clear_cache()