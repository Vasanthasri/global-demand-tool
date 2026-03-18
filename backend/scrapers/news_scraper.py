"""
News Scraper
Scrapes headlines and articles from RSS feeds and news APIs
No API key needed for most sources
"""

import json
import time
import urllib.request
import urllib.parse
from datetime import datetime
from database import insert_scraped_item, insert_scrape_job, update_scrape_job

try:
    import feedparser
    FEEDPARSER_AVAILABLE = True
except ImportError:
    FEEDPARSER_AVAILABLE = False

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; GlobalDemandBot/1.0)"}

# RSS feeds for different domains
DOMAIN_RSS_FEEDS = {
    "Technology": [
        "https://feeds.feedburner.com/TechCrunch",
        "https://www.wired.com/feed/rss",
        "https://venturebeat.com/feed/",
        "https://news.ycombinator.com/rss",
    ],
    "Health & Life Sciences": [
        "https://www.fiercebiotech.com/rss.xml",
        "https://www.fiercepharma.com/rss.xml",
        "https://medcitynews.com/feed/",
    ],
    "Finance & Economy": [
        "https://feeds.bloomberg.com/markets/news.rss",
        "https://www.ft.com/?format=rss",
        "https://economictimes.indiatimes.com/rssfeedstopstories.cms",
    ],
    "Environment & Sustainability": [
        "https://www.greenbiz.com/feeds/rss.xml",
        "https://www.renewableenergyworld.com/feed/",
    ],
    "Marketing & Advertising": [
        "https://feeds.feedblitz.com/marketingland",
        "https://searchengineland.com/feed",
    ],
    "Agriculture & Food Tech": [
        "https://agfundernews.com/feed",
        "https://www.fooddive.com/feeds/news/",
    ],
    "Transportation & Mobility": [
        "https://electrek.co/feed/",
        "https://www.freightwaves.com/news/feed",
    ],
}

# Google News RSS (works for any query)
def google_news_rss_url(query):
    q = urllib.parse.quote(query)
    return f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"


def scrape_rss_feed(feed_url, query, domain, sub_domain, signal_type,
                    job_id, limit=15):
    """Scrape a single RSS feed and filter by query relevance."""
    items_collected = 0

    try:
        if FEEDPARSER_AVAILABLE:
            feed = feedparser.parse(feed_url)
            entries = feed.entries[:limit]
        else:
            # Manual RSS parsing fallback
            req = urllib.request.Request(feed_url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=15) as resp:
                content = resp.read().decode("utf-8", errors="ignore")

            if not BS4_AVAILABLE:
                return 0

            soup = BeautifulSoup(content, "xml")
            raw_entries = soup.find_all("item")[:limit]
            entries = []
            for item in raw_entries:
                entry = {
                    "title": item.find("title").text if item.find("title") else "",
                    "summary": item.find("description").text if item.find("description") else "",
                    "link": item.find("link").text if item.find("link") else "",
                    "published": item.find("pubDate").text if item.find("pubDate") else "",
                }
                entries.append(type("Entry", (), entry)())

        query_words = set(query.lower().split())

        for entry in entries:
            title = getattr(entry, "title", "") or ""
            summary = getattr(entry, "summary", "") or ""
            link = getattr(entry, "link", "") or ""
            published = getattr(entry, "published", "") or ""

            content = f"{title} {summary}"

            # Check relevance
            content_lower = content.lower()
            matches = sum(1 for w in query_words if w in content_lower and len(w) > 3)
            if matches == 0 and len(query_words) > 2:
                continue  # skip irrelevant articles

            # Clean HTML from summary
            if BS4_AVAILABLE and "<" in summary:
                summary = BeautifulSoup(summary, "html.parser").get_text()

            insert_scraped_item(
                job_id=job_id,
                query=query,
                domain=domain,
                sub_domain=sub_domain,
                signal_type=signal_type,
                source_name=urllib.parse.urlparse(feed_url).netloc,
                source_url=feed_url,
                item_type="news_article",
                title=title[:300],
                content=summary[:2000],
                url=link,
                published_at=published,
                score=float(matches * 10),
                metadata={"relevance_matches": matches, "feed_url": feed_url}
            )
            items_collected += 1

    except Exception as e:
        print(f"[News] RSS error {feed_url}: {e}")

    return items_collected


def scrape_news_for_query(query, domain, sub_domain, signal_type="Timing Signal"):
    """Scrape Google News + domain-specific RSS feeds."""

    job_id = insert_scrape_job(
        query, domain, sub_domain, signal_type,
        "news.google.com", "news_rss"
    )

    total = 0

    # 1. Google News RSS (most relevant)
    gnews_url = google_news_rss_url(query)
    total += scrape_rss_feed(gnews_url, query, domain, sub_domain, signal_type, job_id, limit=20)
    time.sleep(1)

    # 2. Domain-specific RSS feeds
    domain_feeds = DOMAIN_RSS_FEEDS.get(domain, [])
    for feed_url in domain_feeds[:3]:  # max 3 feeds per domain
        total += scrape_rss_feed(feed_url, query, domain, sub_domain, signal_type, job_id, limit=10)
        time.sleep(1)

    update_scrape_job(job_id, "completed", total)
    print(f"[News] '{query}' → {total} articles")
    return total


if __name__ == "__main__":
    from database import init_db
    init_db()
    scrape_news_for_query("SAP ERP market demand", "Technology", "SAP & Enterprise Software")
