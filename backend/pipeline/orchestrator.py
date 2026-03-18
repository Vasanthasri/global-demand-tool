"""
Pipeline Orchestrator
- Runs all scrapers for a query
- Coordinates Reddit, News, Trends, Screener, Web scrapers
- Runs AI scoring after scraping
- Schedules 24hr refresh
"""

import os
import sys
import json
import time
import threading
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import init_db, get_demand_score
from classifier import classify
from scrapers.reddit_scraper import scrape_reddit_sources
from scrapers.trends_scraper import scrape_google_trends
from scrapers.news_scraper import scrape_news_for_query
from scrapers.screener_scraper import scrape_screener_for_query
from scrapers.web_scraper import scrape_web_sources
from pipeline.ai_scorer import score_demand_with_ai

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Track active jobs
_active_jobs = {}
_job_lock = threading.Lock()


def log(msg):
    print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] {msg}")


def run_pipeline(query: str, gemini_api_key: str = None,
                 force_refresh: bool = False) -> dict:
    """
    Full scraping pipeline for a query.
    Returns demand score + report.
    """

    api_key = gemini_api_key or GEMINI_API_KEY

    # Check if we have recent data (within 24 hours)
    if not force_refresh:
        existing = get_demand_score(query)
        if existing:
            last_updated = existing.get("last_updated", "")
            if last_updated:
                try:
                    updated_dt = datetime.fromisoformat(last_updated)
                    age_hours = (datetime.utcnow() - updated_dt).total_seconds() / 3600
                    if age_hours < 24:
                        log(f"Using cached data for '{query}' (age: {age_hours:.1f}h)")
                        return format_pipeline_result(query, existing)
                except Exception:
                    pass

    log(f"Starting full pipeline for: '{query}'")

    # Step 1: Classify the query
    classification = classify(query, api_key)
    domains = classification.get("domains", {})

    if not domains:
        return {
            "status": "error",
            "message": f"Could not classify query: {query}",
            "query": query
        }

    # Get primary domain
    primary_domain = max(domains.items(), key=lambda x: x[1]["confidence"])
    domain_name = primary_domain[0]
    domain_data = primary_domain[1]
    sub_domains = domain_data.get("sub_domains", [])
    sub_domain = sub_domains[0] if sub_domains else domain_name
    sources_by_signal = domain_data.get("sources_by_signal", {})

    log(f"Domain: {domain_name} → {sub_domain} (confidence: {domain_data['confidence']}%)")

    # Flatten all source URLs
    all_sources = []
    for signal, urls in sources_by_signal.items():
        all_sources.extend(urls)

    total_items = 0
    results = {}

    # ── Step 2: Reddit Scraping ────────────────────────
    log("Running Reddit scraper...")
    reddit_sources = [u for u in all_sources if "reddit.com" in u]
    if reddit_sources:
        for signal_type, signal_urls in sources_by_signal.items():
            reddit_urls = [u for u in signal_urls if "reddit.com" in u]
            if reddit_urls:
                count = scrape_reddit_sources(query, domain_name, sub_domain,
                                               signal_type, reddit_urls)
                total_items += count
                results["reddit"] = count
    log(f"Reddit: {results.get('reddit', 0)} items")

    # ── Step 3: Google Trends ──────────────────────────
    log("Running Google Trends scraper...")
    try:
        count = scrape_google_trends(
            query, domain_name, sub_domain,
            signal_type="Timing Signal",
            geo="",
            timeframe="today 12-m"
        )
        total_items += count
        results["trends"] = count
    except Exception as e:
        log(f"Trends error: {e}")
        results["trends"] = 0
    log(f"Trends: {results.get('trends', 0)} items")

    # ── Step 4: News Scraping ──────────────────────────
    log("Running News scraper...")
    try:
        count = scrape_news_for_query(query, domain_name, sub_domain,
                                       signal_type="Timing Signal")
        total_items += count
        results["news"] = count
    except Exception as e:
        log(f"News error: {e}")
        results["news"] = 0
    log(f"News: {results.get('news', 0)} items")

    # ── Step 5: Screener.in ────────────────────────────
    log("Running Screener.in scraper...")
    try:
        count = scrape_screener_for_query(query, domain_name, sub_domain,
                                           max_companies=3)
        total_items += count
        results["screener"] = count
    except Exception as e:
        log(f"Screener error: {e}")
        results["screener"] = 0
    log(f"Screener: {results.get('screener', 0)} items")

    # ── Step 6: Web Scraping ───────────────────────────
    log("Running Web scraper (G2, ProductHunt, Indeed, Crunchbase)...")
    try:
        non_reddit = [u for u in all_sources if "reddit.com" not in u]
        count = scrape_web_sources(query, domain_name, sub_domain, non_reddit)
        total_items += count
        results["web"] = count
    except Exception as e:
        log(f"Web error: {e}")
        results["web"] = 0
    log(f"Web: {results.get('web', 0)} items")

    # ── Step 7: AI Scoring ─────────────────────────────
    log(f"Running AI scoring ({total_items} total items collected)...")
    try:
        score_result = score_demand_with_ai(query, domain_name, api_key)
    except Exception as e:
        log(f"Scoring error: {e}")
        score_result = None

    log(f"Pipeline complete for '{query}'")

    # Return formatted result
    final_score = get_demand_score(query)
    return format_pipeline_result(query, final_score, {
        "domain": domain_name,
        "sub_domain": sub_domain,
        "scraper_results": results,
        "total_items_collected": total_items,
        "classification_confidence": domain_data["confidence"]
    })


def format_pipeline_result(query, score_row, extra=None):
    """Format the final pipeline result for the API."""

    if not score_row:
        return {
            "status": "no_data",
            "query": query,
            "message": "No demand data available yet. Run the pipeline first."
        }

    key_evidence = score_row.get("key_evidence", [])
    if isinstance(key_evidence, str):
        try:
            key_evidence = json.loads(key_evidence)
        except Exception:
            key_evidence = [key_evidence]

    result = {
        "status": "success",
        "query": query,
        "timestamp": score_row.get("last_updated", datetime.utcnow().isoformat()),
        "demand_score": {
            "overall": score_row.get("overall_score", 0),
            "verdict": score_row.get("verdict", "UNKNOWN"),
            "signals": {
                "pain": score_row.get("pain_score", 0),
                "buyer": score_row.get("buyer_score", 0),
                "competitor": score_row.get("competitor_score", 0),
                "timing": score_row.get("timing_score", 0),
                "validation": score_row.get("validation_score", 0),
                "expansion": score_row.get("expansion_score", 0),
            }
        },
        "analysis": {
            "why_demand": score_row.get("why_demand", ""),
            "why_no_demand": score_row.get("why_no_demand", ""),
            "key_evidence": key_evidence
        },
        "domain": score_row.get("domain", ""),
        "next_refresh": (datetime.utcnow() + timedelta(hours=24)).isoformat()
    }

    if extra:
        result["pipeline_stats"] = extra

    return result


# ── 24-hour Auto Refresh ──────────────────────────────────

def schedule_refresh(queries: list, interval_hours: int = 24):
    """Background thread that refreshes all queries every 24 hours."""

    def refresh_loop():
        while True:
            log(f"Scheduled refresh: {len(queries)} queries")
            for q in queries:
                try:
                    run_pipeline(q, force_refresh=True)
                    time.sleep(5)  # small delay between queries
                except Exception as e:
                    log(f"Refresh error for '{q}': {e}")
            log(f"Refresh complete. Next run in {interval_hours}h")
            time.sleep(interval_hours * 3600)

    thread = threading.Thread(target=refresh_loop, daemon=True)
    thread.start()
    log(f"Scheduled auto-refresh every {interval_hours}h for {len(queries)} queries")
    return thread


if __name__ == "__main__":
    init_db()
    query = sys.argv[1] if len(sys.argv) > 1 else "SAP ERP demand"
    result = run_pipeline(query, force_refresh=True)
    print(json.dumps(result, indent=2))
