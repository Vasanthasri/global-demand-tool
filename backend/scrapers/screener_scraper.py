"""
Screener.in Scraper
Extracts:
- Company financial ratios & revenue trends
- Peer/competitor comparison
- Pros & cons from community
- Links to annual reports & concall transcripts
- Full text extraction from PDFs
"""

import json
import time
import re
import urllib.request
import urllib.parse
from datetime import datetime

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False
    print("[Screener] BeautifulSoup not available. Run: pip install beautifulsoup4")

try:
    import PyPDF2
    import io
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

from database import (insert_scrape_job, update_scrape_job,
                      insert_financial, insert_document_insight, insert_scraped_item)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

DEMAND_KEYWORDS = [
    "demand", "growth", "revenue", "market", "opportunity", "expansion",
    "customer", "order", "sales", "pipeline", "backlog", "momentum",
    "adoption", "uptake", "traction", "scale", "increase", "rising",
    "strong", "robust", "accelerating"
]

RISK_KEYWORDS = [
    "decline", "slowdown", "competition", "risk", "headwind", "challenge",
    "pressure", "loss", "shrink", "reduce", "weak", "uncertain", "concern"
]


def fetch_page(url, retries=3):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=20) as resp:
                return resp.read().decode("utf-8", errors="ignore")
        except Exception as e:
            if attempt == retries - 1:
                return None
            time.sleep(2 ** attempt)
    return None


def extract_text_from_pdf_url(pdf_url):
    """Download and extract text from a PDF URL."""
    if not PDF_AVAILABLE:
        return ""
    try:
        req = urllib.request.Request(pdf_url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=30) as resp:
            pdf_bytes = resp.read()

        reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
        text = ""
        for page in reader.pages[:30]:  # max 30 pages
            text += page.extract_text() or ""
        return text[:50000]  # cap at 50k chars
    except Exception as e:
        print(f"[Screener] PDF error {pdf_url}: {e}")
        return ""


def extract_demand_sentences(text):
    """Extract sentences containing demand/growth signals."""
    sentences = re.split(r'[.!?]', text)
    demand_sents = []
    risk_sents = []

    for sent in sentences:
        sent = sent.strip()
        if len(sent) < 20:
            continue
        sent_lower = sent.lower()

        if any(kw in sent_lower for kw in DEMAND_KEYWORDS):
            demand_sents.append(sent[:300])
        elif any(kw in sent_lower for kw in RISK_KEYWORDS):
            risk_sents.append(sent[:300])

    return demand_sents[:20], risk_sents[:10]


def scrape_screener_company(company_slug, query, domain, sub_domain):
    """
    Scrape a Screener.in company page.
    company_slug = e.g. 'TCS', 'INFY', 'RELIANCE'
    """
    url = f"https://www.screener.in/company/{company_slug}/consolidated/"
    print(f"[Screener] Scraping {url}")

    job_id = insert_scrape_job(
        query, domain, sub_domain, "Market Data",
        url, "screener"
    )

    html = fetch_page(url)
    if not html or not BS4_AVAILABLE:
        update_scrape_job(job_id, "failed", 0, "Could not fetch page")
        return 0

    soup = BeautifulSoup(html, "html.parser")
    items_collected = 0

    # ── Company name & basic info ──────────────────────
    company_name = ""
    h1 = soup.find("h1")
    if h1:
        company_name = h1.get_text(strip=True)

    # ── Financial ratios ──────────────────────────────
    ratios = {}
    ratio_section = soup.find("ul", id="top-ratios")
    if ratio_section:
        for li in ratio_section.find_all("li"):
            name_el = li.find("span", class_="name")
            value_el = li.find("span", class_="value") or li.find("span", class_="number")
            if name_el and value_el:
                ratios[name_el.get_text(strip=True)] = value_el.get_text(strip=True)

    market_cap = ratios.get("Market Cap", "")
    sector = ""

    # ── Revenue & Profit Trend ─────────────────────────
    revenue_trend = []
    profit_trend = []
    sales_growth = {}

    # Look for the quarterly/annual results table
    tables = soup.find_all("table")
    for table in tables:
        headers = [th.get_text(strip=True) for th in table.find_all("th")]
        if "Sales" in headers or "Revenue" in headers:
            rows = table.find_all("tr")
            for row in rows:
                cells = [td.get_text(strip=True) for td in row.find_all("td")]
                if cells and cells[0] in ["Sales", "Revenue"]:
                    revenue_trend = cells[1:]
                if cells and cells[0] in ["Net Profit", "Profit"]:
                    profit_trend = cells[1:]
            break

    # ── Peers ──────────────────────────────────────────
    peers = []
    peer_section = soup.find("section", id="peers")
    if peer_section:
        peer_rows = peer_section.find_all("tr")
        for row in peer_rows[1:6]:  # skip header, max 5 peers
            cells = row.find_all("td")
            if cells:
                peer_name = cells[0].get_text(strip=True)
                if peer_name:
                    peers.append(peer_name)

    # ── Pros & Cons ────────────────────────────────────
    pros = []
    cons = []
    pros_section = soup.find("div", class_="pros")
    if pros_section:
        pros = [li.get_text(strip=True) for li in pros_section.find_all("li")]

    cons_section = soup.find("div", class_="cons")
    if cons_section:
        cons = [li.get_text(strip=True) for li in cons_section.find_all("li")]

    # ── Save financial data ────────────────────────────
    insert_financial(
        query=query,
        company_name=company_name or company_slug,
        ticker=company_slug,
        sector=sector,
        market_cap=market_cap,
        revenue_trend=revenue_trend,
        profit_trend=profit_trend,
        sales_growth=sales_growth,
        peers=peers,
        pros=pros,
        cons=cons,
        source_url=url
    )

    # Save as scraped item too
    summary = f"Company: {company_name}. Market Cap: {market_cap}. "
    if pros:
        summary += f"Strengths: {'; '.join(pros[:3])}. "
    if cons:
        summary += f"Concerns: {'; '.join(cons[:3])}."

    insert_scraped_item(
        job_id=job_id,
        query=query,
        domain=domain,
        sub_domain=sub_domain,
        signal_type="Competitor Signal",
        source_name="screener.in",
        source_url=url,
        item_type="financial",
        title=f"{company_name} — Screener.in Financial Overview",
        content=summary,
        url=url,
        score=50.0,
        metadata={"ratios": ratios, "peers": peers}
    )
    items_collected += 1

    # ── Annual Reports ─────────────────────────────────
    ar_links = []
    documents_section = soup.find("div", id="documents")
    if documents_section:
        for a in documents_section.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(strip=True).lower()
            if "annual" in text or ".pdf" in href.lower():
                ar_links.append({"text": a.get_text(strip=True), "url": href})

    for ar in ar_links[:2]:  # scrape max 2 annual reports
        pdf_url = ar["url"]
        if not pdf_url.startswith("http"):
            pdf_url = f"https://www.screener.in{pdf_url}"

        print(f"[Screener] Extracting annual report: {pdf_url}")
        full_text = extract_text_from_pdf_url(pdf_url)

        if full_text:
            demand_sents, risk_sents = extract_demand_sentences(full_text)
            key_themes = extract_key_themes(full_text)
            year = extract_year_from_text(ar["text"])

            insert_document_insight(
                query=query,
                company_name=company_name or company_slug,
                doc_type="annual_report",
                year=year,
                quarter="",
                full_text=full_text[:30000],
                key_themes=key_themes,
                demand_mentions=demand_sents,
                growth_signals=demand_sents[:10],
                risk_signals=risk_sents[:5],
                source_url=pdf_url
            )

            insert_scraped_item(
                job_id=job_id,
                query=query,
                domain=domain,
                sub_domain=sub_domain,
                signal_type="Validation Signal",
                source_name="screener.in (Annual Report)",
                source_url=pdf_url,
                item_type="annual_report",
                title=f"{company_name} Annual Report {year}",
                content=" | ".join(demand_sents[:5]),
                url=pdf_url,
                score=70.0,
                metadata={"year": year, "themes": key_themes[:5]}
            )
            items_collected += 1
            time.sleep(2)

    # ── Concall Transcripts ────────────────────────────
    concall_links = []
    if documents_section:
        for a in documents_section.find_all("a", href=True):
            text = a.get_text(strip=True).lower()
            if "concall" in text or "transcript" in text or "earnings call" in text:
                concall_links.append({"text": a.get_text(strip=True), "url": a["href"]})

    for cc in concall_links[:3]:  # max 3 concalls
        cc_url = cc["url"]
        if not cc_url.startswith("http"):
            cc_url = f"https://www.screener.in{cc_url}"

        print(f"[Screener] Extracting concall: {cc_url}")

        if ".pdf" in cc_url.lower():
            full_text = extract_text_from_pdf_url(cc_url)
        else:
            html = fetch_page(cc_url)
            full_text = BeautifulSoup(html, "html.parser").get_text() if html else ""

        if full_text:
            demand_sents, risk_sents = extract_demand_sentences(full_text)
            key_themes = extract_key_themes(full_text)
            quarter = extract_quarter_from_text(cc["text"])
            year = extract_year_from_text(cc["text"])

            insert_document_insight(
                query=query,
                company_name=company_name or company_slug,
                doc_type="concall",
                year=year,
                quarter=quarter,
                full_text=full_text[:30000],
                key_themes=key_themes,
                demand_mentions=demand_sents,
                growth_signals=demand_sents[:10],
                risk_signals=risk_sents[:5],
                source_url=cc_url
            )

            insert_scraped_item(
                job_id=job_id,
                query=query,
                domain=domain,
                sub_domain=sub_domain,
                signal_type="Validation Signal",
                source_name="screener.in (Concall)",
                source_url=cc_url,
                item_type="concall",
                title=f"{company_name} Concall {quarter} {year}",
                content=" | ".join(demand_sents[:5]),
                url=cc_url,
                score=80.0,
                metadata={"year": year, "quarter": quarter, "themes": key_themes[:5]}
            )
            items_collected += 1
            time.sleep(2)

    update_scrape_job(job_id, "completed", items_collected)
    print(f"[Screener] {company_slug} → {items_collected} items collected")
    return items_collected


def search_screener_companies(query, max_companies=3):
    """Search Screener.in for companies related to the query."""
    search_url = f"https://www.screener.in/api/company/search/?q={urllib.parse.quote(query)}&v=3&fts=1"

    try:
        req = urllib.request.Request(search_url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())

        companies = []
        for item in data[:max_companies]:
            slug = item.get("url", "").strip("/").split("/")[-1]
            name = item.get("name", "")
            if slug:
                companies.append({"slug": slug, "name": name})
        return companies

    except Exception as e:
        print(f"[Screener] Search error: {e}")
        return []


def scrape_screener_for_query(query, domain, sub_domain, max_companies=3):
    """Full pipeline: search companies → scrape each one."""
    print(f"[Screener] Searching for companies related to: {query}")

    companies = search_screener_companies(query, max_companies)

    if not companies:
        print(f"[Screener] No companies found for '{query}'")
        return 0

    total = 0
    for company in companies:
        print(f"[Screener] Processing: {company['name']} ({company['slug']})")
        count = scrape_screener_company(company["slug"], query, domain, sub_domain)
        total += count
        time.sleep(3)  # polite delay

    return total


# ── Helpers ────────────────────────────────────────────────

def extract_key_themes(text, top_n=10):
    """Extract most frequent meaningful words as themes."""
    words = re.findall(r'\b[a-zA-Z]{5,}\b', text.lower())
    stop_words = {"which", "their", "there", "these", "those", "would", "could",
                  "should", "about", "after", "before", "during", "other", "being"}
    word_freq = {}
    for w in words:
        if w not in stop_words:
            word_freq[w] = word_freq.get(w, 0) + 1

    sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
    return [w for w, _ in sorted_words[:top_n]]


def extract_year_from_text(text):
    match = re.search(r'\b(20\d{2})\b', text)
    return match.group(1) if match else str(datetime.now().year)


def extract_quarter_from_text(text):
    match = re.search(r'\b(Q[1-4])\b', text, re.IGNORECASE)
    return match.group(1).upper() if match else ""


if __name__ == "__main__":
    from database import init_db
    init_db()
    # Test search
    companies = search_screener_companies("SAP ERP software")
    print("Found companies:", companies)
    # Test scrape
    if companies:
        scrape_screener_company(companies[0]["slug"], "SAP ERP", "Technology", "SAP & Enterprise Software")
