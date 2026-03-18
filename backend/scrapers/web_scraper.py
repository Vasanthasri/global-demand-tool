"""
Web Scraper
Scrapes:
- G2 & Capterra reviews (competitor/pain signals)
- Product Hunt launches (validation signals)
- Job postings count from Indeed (buyer signals)
- General web pages
"""

import json
import time
import re
import urllib.request
import urllib.parse
from datetime import datetime
from database import insert_scraped_item, insert_scrape_job, update_scrape_job

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}


def fetch_page(url, retries=2):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.read().decode("utf-8", errors="ignore")
        except Exception as e:
            if attempt == retries - 1:
                return None
            time.sleep(2)
    return None


# ─────────────────────────────────────────────────────────
# G2 Reviews
# ─────────────────────────────────────────────────────────

def scrape_g2_reviews(query, domain, sub_domain, job_id, limit=10):
    """Scrape G2.com for reviews of products related to query."""
    items = 0

    search_url = f"https://www.g2.com/search?query={urllib.parse.quote(query)}"
    html = fetch_page(search_url)

    if not html or not BS4_AVAILABLE:
        return 0

    soup = BeautifulSoup(html, "html.parser")

    # Find product listings
    products = soup.find_all("div", class_=re.compile("product-card|grid-item"))[:5]

    for product in products:
        name_el = product.find(["h3", "h4", "a"], class_=re.compile("product-name|title"))
        rating_el = product.find(["span", "div"], class_=re.compile("rating|stars"))
        reviews_el = product.find(text=re.compile(r'\d+ reviews', re.I))

        name = name_el.get_text(strip=True) if name_el else ""
        rating = rating_el.get_text(strip=True) if rating_el else ""
        review_count = reviews_el.strip() if reviews_el else ""

        if not name:
            continue

        content = f"Product: {name}. Rating: {rating}. Reviews: {review_count}"

        insert_scraped_item(
            job_id=job_id,
            query=query,
            domain=domain,
            sub_domain=sub_domain,
            signal_type="Competitor Signal",
            source_name="g2.com",
            source_url=search_url,
            item_type="review_summary",
            title=f"G2: {name}",
            content=content,
            url=search_url,
            score=30.0,
            metadata={"rating": rating, "review_count": review_count, "source": "g2"}
        )
        items += 1

    return items


# ─────────────────────────────────────────────────────────
# Product Hunt
# ─────────────────────────────────────────────────────────

def scrape_product_hunt(query, domain, sub_domain, job_id):
    """Scrape Product Hunt for recent launches related to query."""
    items = 0

    search_url = f"https://www.producthunt.com/search?q={urllib.parse.quote(query)}"
    html = fetch_page(search_url)

    if not html or not BS4_AVAILABLE:
        return 0

    soup = BeautifulSoup(html, "html.parser")

    # Find product listings
    product_items = soup.find_all("li", attrs={"data-test": re.compile("post-item")})[:10]
    if not product_items:
        product_items = soup.find_all("div", class_=re.compile("post|product"))[:10]

    for item in product_items:
        title_el = item.find(["h3", "h2", "a"])
        desc_el = item.find(["p", "span"], class_=re.compile("tagline|desc"))
        votes_el = item.find(text=re.compile(r'\d+'))

        title = title_el.get_text(strip=True) if title_el else ""
        desc = desc_el.get_text(strip=True) if desc_el else ""
        votes = votes_el.strip() if votes_el else "0"

        if not title:
            continue

        content = f"{title}: {desc}"
        insert_scraped_item(
            job_id=job_id,
            query=query,
            domain=domain,
            sub_domain=sub_domain,
            signal_type="Validation Signal",
            source_name="producthunt.com",
            source_url=search_url,
            item_type="product_launch",
            title=f"Product Hunt: {title}",
            content=content[:500],
            url=search_url,
            score=float(re.sub(r'\D', '', votes)[:6] or 0),
            metadata={"votes": votes, "description": desc}
        )
        items += 1

    return items


# ─────────────────────────────────────────────────────────
# Indeed Job Postings (demand proxy)
# ─────────────────────────────────────────────────────────

def scrape_indeed_jobs(query, domain, sub_domain, job_id):
    """Count job postings as a proxy for buyer/market demand."""
    items = 0

    search_url = f"https://www.indeed.com/jobs?q={urllib.parse.quote(query)}&sort=date"
    html = fetch_page(search_url)

    if not html or not BS4_AVAILABLE:
        return 0

    soup = BeautifulSoup(html, "html.parser")

    # Job count
    count_el = soup.find(["div", "span"], string=re.compile(r'\d+ jobs', re.I))
    job_count = count_el.get_text(strip=True) if count_el else "Unknown"

    # Recent job titles
    job_cards = soup.find_all("h2", class_=re.compile("jobTitle"))[:10]
    job_titles = [j.get_text(strip=True) for j in job_cards if j.get_text(strip=True)]

    content = f"Job postings for '{query}': {job_count}. "
    if job_titles:
        content += f"Recent roles: {', '.join(job_titles[:5])}."

    insert_scraped_item(
        job_id=job_id,
        query=query,
        domain=domain,
        sub_domain=sub_domain,
        signal_type="Buyer Signal",
        source_name="indeed.com",
        source_url=search_url,
        item_type="job_postings",
        title=f"Job Market: {query} — {job_count}",
        content=content,
        url=search_url,
        score=50.0,
        metadata={"job_count": job_count, "sample_titles": job_titles[:10]}
    )
    items += 1
    return items


# ─────────────────────────────────────────────────────────
# Crunchbase (funding signals)
# ─────────────────────────────────────────────────────────

def scrape_crunchbase_search(query, domain, sub_domain, job_id):
    """Search Crunchbase for funded companies in the space."""
    items = 0

    search_url = f"https://www.crunchbase.com/textsearch?q={urllib.parse.quote(query)}"
    html = fetch_page(search_url)

    if not html or not BS4_AVAILABLE:
        return 0

    soup = BeautifulSoup(html, "html.parser")

    # Extract any company/funding mentions
    results = soup.find_all("a", class_=re.compile("company|entity"))[:10]

    for r in results:
        name = r.get_text(strip=True)
        href = r.get("href", "")
        if name and len(name) > 2:
            insert_scraped_item(
                job_id=job_id,
                query=query,
                domain=domain,
                sub_domain=sub_domain,
                signal_type="Competitor Signal",
                source_name="crunchbase.com",
                source_url=search_url,
                item_type="funded_company",
                title=f"Crunchbase: {name}",
                content=f"Funded company in {query} space: {name}",
                url=f"https://www.crunchbase.com{href}",
                score=40.0,
                metadata={"company": name}
            )
            items += 1

    return items


# ─────────────────────────────────────────────────────────
# Main Web Scraper Entry Point
# ─────────────────────────────────────────────────────────

def scrape_web_sources(query, domain, sub_domain, source_urls):
    """Run all web scrapers for a given query."""

    job_id = insert_scrape_job(
        query, domain, sub_domain, "Mixed",
        "multiple_web_sources", "web_scraper"
    )

    total = 0

    # G2 Reviews
    if any("g2.com" in u for u in source_urls):
        total += scrape_g2_reviews(query, domain, sub_domain, job_id)
        time.sleep(2)

    # Product Hunt
    if any("producthunt.com" in u for u in source_urls):
        total += scrape_product_hunt(query, domain, sub_domain, job_id)
        time.sleep(2)

    # Indeed Jobs
    if any("indeed.com" in u or "linkedin.com/jobs" in u for u in source_urls):
        total += scrape_indeed_jobs(query, domain, sub_domain, job_id)
        time.sleep(2)

    # Crunchbase
    if any("crunchbase.com" in u for u in source_urls):
        total += scrape_crunchbase_search(query, domain, sub_domain, job_id)
        time.sleep(2)

    update_scrape_job(job_id, "completed", total)
    print(f"[Web] '{query}' → {total} items from web sources")
    return total


if __name__ == "__main__":
    from database import init_db
    init_db()
    scrape_web_sources(
        "SAP ERP software",
        "Technology",
        "SAP & Enterprise Software",
        ["g2.com", "producthunt.com", "linkedin.com/jobs", "crunchbase.com"]
    )
