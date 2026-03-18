"""
Reddit Scraper
Scrapes subreddits for pain signals, demand signals, community activity
Uses public JSON API — no credentials needed
"""

import json
import time
import urllib.request
import urllib.parse
from datetime import datetime
from database import insert_scraped_item, insert_scrape_job, update_scrape_job


HEADERS = {
    "User-Agent": "GlobalDemandTool/1.0 (demand research bot)"
}

# Map signal types to search strategies
SIGNAL_SEARCH_TERMS = {
    "Pain Signal": ["problem", "issue", "frustrated", "hate", "broken", "need", "wish", "pain"],
    "Buyer Signal": ["looking for", "recommend", "best tool", "which is better", "should i use", "anyone using"],
    "Competitor Signal": ["vs", "alternative", "compared to", "switched from", "better than"],
    "Validation Signal": ["launched", "just released", "new product", "waitlist", "early access"],
    "Behaviour Signal": ["workaround", "spreadsheet", "manual", "hack", "trick", "how do you"],
}


def fetch_reddit_json(url, retries=3):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            if attempt == retries - 1:
                raise e
            time.sleep(2 ** attempt)
    return None


def extract_subreddit_from_url(url):
    """Extract subreddit name from URL like reddit.com/r/MachineLearning"""
    parts = url.replace("https://", "").replace("http://", "").split("/")
    for i, part in enumerate(parts):
        if part == "r" and i + 1 < len(parts):
            return parts[i + 1]
    return None


def scrape_subreddit(subreddit_name, query, signal_type, domain, sub_domain,
                     source_url, limit=25):
    """Scrape a subreddit for posts relevant to the query."""

    job_id = insert_scrape_job(
        query, domain, sub_domain, signal_type,
        source_url, "reddit"
    )

    items_collected = 0
    all_posts = []

    try:
        # Search within subreddit
        search_query = urllib.parse.quote(query)
        search_url = f"https://www.reddit.com/r/{subreddit_name}/search.json?q={search_query}&sort=relevance&limit={limit}&restrict_sr=1"

        data = fetch_reddit_json(search_url)
        if data and "data" in data:
            posts = data["data"].get("children", [])
            all_posts.extend(posts)

        # Also get hot posts if search returns few results
        if len(all_posts) < 5:
            hot_url = f"https://www.reddit.com/r/{subreddit_name}/hot.json?limit=20"
            hot_data = fetch_reddit_json(hot_url)
            if hot_data and "data" in hot_data:
                all_posts.extend(hot_data["data"].get("children", []))

        for post in all_posts:
            p = post.get("data", {})
            title = p.get("title", "")
            selftext = p.get("selftext", "")
            content = f"{title}\n\n{selftext}".strip()
            score = p.get("score", 0)
            num_comments = p.get("num_comments", 0)
            permalink = p.get("permalink", "")
            author = p.get("author", "")
            created = p.get("created_utc", 0)

            if not title:
                continue

            # Check relevance to signal type
            content_lower = content.lower()
            signal_terms = SIGNAL_SEARCH_TERMS.get(signal_type, [])
            relevance_boost = sum(1 for t in signal_terms if t in content_lower)

            published_at = datetime.utcfromtimestamp(created).isoformat() if created else ""

            insert_scraped_item(
                job_id=job_id,
                query=query,
                domain=domain,
                sub_domain=sub_domain,
                signal_type=signal_type,
                source_name=f"reddit.com/r/{subreddit_name}",
                source_url=source_url,
                item_type="reddit_post",
                title=title,
                content=content[:2000],  # limit content size
                url=f"https://reddit.com{permalink}",
                author=author,
                published_at=published_at,
                score=float(score + (relevance_boost * 10)),
                metadata={
                    "subreddit": subreddit_name,
                    "upvotes": score,
                    "comments": num_comments,
                    "relevance_boost": relevance_boost,
                    "signal_type": signal_type
                }
            )
            items_collected += 1

        update_scrape_job(job_id, "completed", items_collected)
        print(f"[Reddit] r/{subreddit_name} → {items_collected} posts for '{query}'")

    except Exception as e:
        update_scrape_job(job_id, "failed", 0, str(e))
        print(f"[Reddit] ERROR r/{subreddit_name}: {e}")

    return items_collected


def scrape_reddit_sources(query, domain, sub_domain, signal_type, source_urls):
    """Scrape all Reddit URLs for a given signal."""
    total = 0
    reddit_urls = [u for u in source_urls if "reddit.com" in u]

    for url in reddit_urls:
        subreddit = extract_subreddit_from_url(url)
        if subreddit:
            count = scrape_subreddit(subreddit, query, signal_type, domain, sub_domain, url)
            total += count
            time.sleep(2)  # polite delay between requests

    return total


if __name__ == "__main__":
    from database import init_db
    init_db()
    scrape_subreddit("MachineLearning", "AI tools demand", "Pain Signal",
                     "Technology", "Artificial Intelligence",
                     "reddit.com/r/MachineLearning", limit=10)
    print("Done.")
