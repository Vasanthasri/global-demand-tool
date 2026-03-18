"""
Google Trends Scraper
Gets search interest over time, related queries, rising topics
Uses pytrends library
"""

import time
import json
from datetime import datetime
from database import (insert_scrape_job, update_scrape_job,
                      insert_trend_data, insert_scraped_item)

try:
    from pytrends.request import TrendReq
    PYTRENDS_AVAILABLE = True
except ImportError:
    PYTRENDS_AVAILABLE = False
    print("[Trends] pytrends not installed. Run: pip install pytrends")


def determine_trend_direction(values):
    """Determine if trend is rising, falling, or stable."""
    if not values or len(values) < 4:
        return "stable"
    recent = sum(values[-4:]) / 4
    older = sum(values[:4]) / 4
    if older == 0:
        return "rising" if recent > 0 else "stable"
    change = (recent - older) / older
    if change > 0.15:
        return "rising"
    elif change < -0.15:
        return "falling"
    return "stable"


def scrape_google_trends(query, domain, sub_domain, signal_type="Timing Signal",
                          geo="", timeframe="today 12-m"):
    """
    Scrape Google Trends for a query.
    geo="" = global, geo="IN" = India, geo="US" = USA
    """

    if not PYTRENDS_AVAILABLE:
        print("[Trends] Skipping - pytrends not available")
        return 0

    job_id = insert_scrape_job(
        query, domain, sub_domain, signal_type,
        "trends.google.com", "google_trends"
    )

    try:
        pytrends = TrendReq(hl="en-US", tz=360, timeout=(10, 25))

        # Build payload
        keywords = [query]
        # Add related keywords if query is short
        if len(query.split()) == 1:
            keywords.append(f"{query} market")

        pytrends.build_payload(
            keywords[:5],
            cat=0,
            timeframe=timeframe,
            geo=geo,
            gprop=""
        )

        # Interest over time
        interest_df = pytrends.interest_over_time()
        interest_data = {}
        values_list = []

        if not interest_df.empty:
            for kw in keywords:
                if kw in interest_df.columns:
                    series = interest_df[kw].tolist()
                    dates = [str(d.date()) for d in interest_df.index]
                    interest_data[kw] = dict(zip(dates, series))
                    values_list.extend(series)

        time.sleep(1)

        # Related queries
        related_queries = {}
        try:
            rq = pytrends.related_queries()
            for kw in keywords:
                if kw in rq and rq[kw]:
                    top = rq[kw].get("top")
                    rising = rq[kw].get("rising")
                    related_queries[kw] = {
                        "top": top.to_dict("records") if top is not None else [],
                        "rising": rising.to_dict("records") if rising is not None else []
                    }
        except Exception:
            pass

        time.sleep(1)

        # Related topics
        related_topics = {}
        try:
            rt = pytrends.related_topics()
            for kw in keywords:
                if kw in rt and rt[kw]:
                    top = rt[kw].get("top")
                    related_topics[kw] = top.to_dict("records") if top is not None else []
        except Exception:
            pass

        # Calculate summary metrics
        peak = max(values_list) if values_list else 0
        current = values_list[-1] if values_list else 0
        trend_dir = determine_trend_direction(values_list)

        # Save to trend_data table
        insert_trend_data(
            query=query,
            keyword=query,
            region=geo if geo else "global",
            interest_over_time=interest_data,
            related_queries=related_queries,
            related_topics=related_topics,
            peak_interest=int(peak),
            current_interest=int(current),
            trend_direction=trend_dir
        )

        # Also save as scraped item for unified analysis
        summary = (
            f"Google Trends for '{query}': "
            f"Current interest: {current}/100, "
            f"Peak: {peak}/100, "
            f"Trend: {trend_dir.upper()}. "
        )

        if related_queries:
            rising_list = []
            for kw_data in related_queries.values():
                for r in kw_data.get("rising", [])[:5]:
                    rising_list.append(r.get("query", ""))
            if rising_list:
                summary += f"Rising related searches: {', '.join(rising_list[:5])}."

        insert_scraped_item(
            job_id=job_id,
            query=query,
            domain=domain,
            sub_domain=sub_domain,
            signal_type=signal_type,
            source_name="Google Trends",
            source_url="trends.google.com",
            item_type="trend",
            title=f"Google Trends: {query} ({trend_dir})",
            content=summary,
            url=f"https://trends.google.com/trends/explore?q={query}",
            score=float(current),
            metadata={
                "peak_interest": peak,
                "current_interest": current,
                "trend_direction": trend_dir,
                "geo": geo or "global",
                "timeframe": timeframe
            }
        )

        update_scrape_job(job_id, "completed", 1)
        print(f"[Trends] '{query}' → interest: {current}/100, trend: {trend_dir}")
        return 1

    except Exception as e:
        update_scrape_job(job_id, "failed", 0, str(e))
        print(f"[Trends] ERROR for '{query}': {e}")
        return 0


if __name__ == "__main__":
    from database import init_db
    init_db()
    scrape_google_trends("SAP ERP", "Technology", "SAP & Enterprise Software")
