"""
Database Manager
Uses PostgreSQL for structured data + full text storage
Falls back to SQLite if PostgreSQL is not available
"""

import os
import json
import sqlite3
from datetime import datetime
from typing import Optional

# Try PostgreSQL first, fallback to SQLite
USE_POSTGRES = False
try:
    import psycopg2
    import psycopg2.extras
    USE_POSTGRES = bool(os.environ.get("DATABASE_URL"))
except ImportError:
    pass

DB_PATH = os.environ.get("SQLITE_PATH", "demand_tool.db")
DATABASE_URL = os.environ.get("DATABASE_URL", "")


# ─────────────────────────────────────────────────
# Connection
# ─────────────────────────────────────────────────

def get_connection():
    if USE_POSTGRES:
        return psycopg2.connect(DATABASE_URL)
    return sqlite3.connect(DB_PATH)


def dict_cursor(conn):
    if USE_POSTGRES:
        return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    conn.row_factory = sqlite3.Row
    return conn.cursor()


def placeholder():
    return "%s" if USE_POSTGRES else "?"


# ─────────────────────────────────────────────────
# Schema — all tables
# ─────────────────────────────────────────────────

# Individual CREATE TABLE statements — no splitting, no comment issues
# Works reliably on Windows, Mac, Linux with Python 3.8+
TABLES = [
    """CREATE TABLE IF NOT EXISTS scrape_jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        query TEXT NOT NULL,
        domain TEXT,
        sub_domain TEXT,
        signal_type TEXT,
        source_url TEXT,
        scraper_type TEXT,
        status TEXT DEFAULT 'pending',
        started_at TEXT,
        completed_at TEXT,
        error_message TEXT,
        items_collected INTEGER DEFAULT 0
    )""",

    """CREATE TABLE IF NOT EXISTS scraped_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER,
        query TEXT,
        domain TEXT,
        sub_domain TEXT,
        signal_type TEXT,
        source_name TEXT,
        source_url TEXT,
        item_type TEXT,
        title TEXT,
        content TEXT,
        url TEXT,
        author TEXT,
        published_at TEXT,
        score REAL,
        metadata TEXT,
        scraped_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""",

    """CREATE TABLE IF NOT EXISTS company_financials (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        query TEXT,
        company_name TEXT,
        ticker TEXT,
        sector TEXT,
        market_cap TEXT,
        revenue_trend TEXT,
        profit_trend TEXT,
        sales_growth TEXT,
        peers TEXT,
        pros TEXT,
        cons TEXT,
        source_url TEXT,
        scraped_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""",

    """CREATE TABLE IF NOT EXISTS document_insights (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        query TEXT,
        company_name TEXT,
        doc_type TEXT,
        year TEXT,
        quarter TEXT,
        full_text TEXT,
        key_themes TEXT,
        demand_mentions TEXT,
        growth_signals TEXT,
        risk_signals TEXT,
        source_url TEXT,
        scraped_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""",

    """CREATE TABLE IF NOT EXISTS trend_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        query TEXT,
        keyword TEXT,
        region TEXT DEFAULT 'global',
        interest_over_time TEXT,
        related_queries TEXT,
        related_topics TEXT,
        peak_interest INTEGER,
        current_interest INTEGER,
        trend_direction TEXT,
        scraped_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""",

    """CREATE TABLE IF NOT EXISTS demand_scores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        query TEXT UNIQUE,
        domain TEXT,
        overall_score REAL,
        pain_score REAL,
        buyer_score REAL,
        competitor_score REAL,
        timing_score REAL,
        validation_score REAL,
        expansion_score REAL,
        verdict TEXT,
        why_demand TEXT,
        why_no_demand TEXT,
        key_evidence TEXT,
        last_updated TEXT DEFAULT CURRENT_TIMESTAMP
    )""",
]

# PostgreSQL uses SERIAL instead of AUTOINCREMENT
TABLES_PG = [
    t.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
    for t in TABLES
]


def init_db():
    """Initialize all tables — works reliably on Windows/Mac/Linux."""
    conn = get_connection()
    cursor = conn.cursor()
    tables = TABLES_PG if USE_POSTGRES else TABLES
    created = 0
    for sql in tables:
        try:
            cursor.execute(sql)
            created += 1
        except Exception as e:
            print(f"[DB] Table creation warning: {e}")
    conn.commit()
    conn.close()
    print(f"[DB] Initialized ({'PostgreSQL' if USE_POSTGRES else 'SQLite'}) — {created}/{len(tables)} tables ready")


# ─────────────────────────────────────────────────
# Write helpers
# ─────────────────────────────────────────────────

def insert_scrape_job(query, domain, sub_domain, signal_type, source_url, scraper_type):
    query = query.strip().lower()
    conn = get_connection()
    cur = conn.cursor()
    p = placeholder()
    cur.execute(f"""
        INSERT INTO scrape_jobs (query, domain, sub_domain, signal_type, source_url, scraper_type, status, started_at)
        VALUES ({p},{p},{p},{p},{p},{p},'running',{p})
    """, (query, domain, sub_domain, signal_type, source_url, scraper_type, datetime.utcnow().isoformat()))
    conn.commit()
    job_id = cur.lastrowid
    conn.close()
    return job_id


def update_scrape_job(job_id, status, items_collected=0, error=None):
    conn = get_connection()
    cur = conn.cursor()
    p = placeholder()
    cur.execute(f"""
        UPDATE scrape_jobs SET status={p}, completed_at={p}, items_collected={p}, error_message={p}
        WHERE id={p}
    """, (status, datetime.utcnow().isoformat(), items_collected, error, job_id))
    conn.commit()
    conn.close()


def insert_scraped_item(job_id, query, domain, sub_domain, signal_type,
                        source_name, source_url, item_type, title, content,
                        url="", author="", published_at="", score=0.0, metadata=None):
    query = query.strip().lower()
    conn = get_connection()
    cur = conn.cursor()
    p = placeholder()
    cur.execute(f"""
        INSERT INTO scraped_items
        (job_id, query, domain, sub_domain, signal_type, source_name, source_url,
         item_type, title, content, url, author, published_at, score, metadata)
        VALUES ({p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p})
    """, (job_id, query, domain, sub_domain, signal_type, source_name, source_url,
          item_type, title, content, url, author, published_at, float(score),
          json.dumps(metadata or {})))
    conn.commit()
    conn.close()


def insert_financial(query, company_name, ticker, sector, market_cap,
                     revenue_trend, profit_trend, sales_growth, peers,
                     pros, cons, source_url):
    query = query.strip().lower()
    conn = get_connection()
    cur = conn.cursor()
    p = placeholder()
    cur.execute(f"""
        INSERT INTO company_financials
        (query, company_name, ticker, sector, market_cap, revenue_trend,
         profit_trend, sales_growth, peers, pros, cons, source_url)
        VALUES ({p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p})
    """, (query, company_name, ticker, sector, market_cap,
          json.dumps(revenue_trend), json.dumps(profit_trend),
          json.dumps(sales_growth), json.dumps(peers),
          json.dumps(pros), json.dumps(cons), source_url))
    conn.commit()
    conn.close()


def insert_document_insight(query, company_name, doc_type, year, quarter,
                             full_text, key_themes, demand_mentions,
                             growth_signals, risk_signals, source_url):
    query = query.strip().lower()
    conn = get_connection()
    cur = conn.cursor()
    p = placeholder()
    cur.execute(f"""
        INSERT INTO document_insights
        (query, company_name, doc_type, year, quarter, full_text,
         key_themes, demand_mentions, growth_signals, risk_signals, source_url)
        VALUES ({p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p})
    """, (query, company_name, doc_type, year, quarter, full_text,
          json.dumps(key_themes), json.dumps(demand_mentions),
          json.dumps(growth_signals), json.dumps(risk_signals), source_url))
    conn.commit()
    conn.close()


def insert_trend_data(query, keyword, region, interest_over_time,
                      related_queries, related_topics, peak_interest,
                      current_interest, trend_direction):
    query = query.strip().lower()
    conn = get_connection()
    cur = conn.cursor()
    p = placeholder()
    cur.execute(f"""
        INSERT INTO trend_data
        (query, keyword, region, interest_over_time, related_queries,
         related_topics, peak_interest, current_interest, trend_direction)
        VALUES ({p},{p},{p},{p},{p},{p},{p},{p},{p})
    """, (query, keyword, region, json.dumps(interest_over_time),
          json.dumps(related_queries), json.dumps(related_topics),
          peak_interest, current_interest, trend_direction))
    conn.commit()
    conn.close()


def upsert_demand_score(query, domain, overall_score, pain_score, buyer_score,
                        competitor_score, timing_score, validation_score,
                        expansion_score, verdict, why_demand, why_no_demand, key_evidence):
    query = query.strip().lower()
    conn = get_connection()
    cur = conn.cursor()
    p = placeholder()
    # Delete existing then insert (works for both SQLite and PG)
    cur.execute(f"DELETE FROM demand_scores WHERE query={p}", (query,))
    cur.execute(f"""
        INSERT INTO demand_scores
        (query, domain, overall_score, pain_score, buyer_score, competitor_score,
         timing_score, validation_score, expansion_score, verdict,
         why_demand, why_no_demand, key_evidence, last_updated)
        VALUES ({p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p})
    """, (query, domain, overall_score, pain_score, buyer_score, competitor_score,
          timing_score, validation_score, expansion_score, verdict,
          why_demand, why_no_demand, json.dumps(key_evidence),
          datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────────
# Read helpers
# ─────────────────────────────────────────────────

def get_scraped_items(query, limit=100):
    conn = get_connection()
    cur = dict_cursor(conn)
    p = placeholder()
    cur.execute(f"""
        SELECT * FROM scraped_items WHERE LOWER(query)=LOWER({p})
        ORDER BY score DESC LIMIT {p}
    """, (query, limit))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_financials(query):
    conn = get_connection()
    cur = dict_cursor(conn)
    p = placeholder()
    cur.execute(f"SELECT * FROM company_financials WHERE query={p}", (query,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_document_insights(query):
    conn = get_connection()
    cur = dict_cursor(conn)
    p = placeholder()
    cur.execute(f"SELECT * FROM document_insights WHERE query={p}", (query,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_trend_data(query):
    conn = get_connection()
    cur = dict_cursor(conn)
    p = placeholder()
    cur.execute(f"SELECT * FROM trend_data WHERE query={p}", (query,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_demand_score(query):
    conn = get_connection()
    cur = dict_cursor(conn)
    p = placeholder()
    cur.execute(f"SELECT * FROM demand_scores WHERE LOWER(query)=LOWER({p})", (query,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


if __name__ == "__main__":
    init_db()
    print("[DB] All tables created successfully.")