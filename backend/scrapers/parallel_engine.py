"""
Parallel Scraping Engine
========================
Every single source URL gets its own thread.
All threads run SIMULTANEOUSLY.
Each thread has a hard 12s timeout — slow sites are skipped, fast ones return data.
Total wall-clock time = slowest single source (not sum of all sources).
"""

import threading
import time
import json
import os
import sys
import urllib.request
import urllib.parse
import re
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError

from database import (insert_scraped_item, insert_scrape_job,
                      update_scrape_job, insert_financial,
                      insert_document_insight, insert_trend_data)

# ── Per-request settings ──────────────────────────────────
TIMEOUT_PER_URL   = 12    # seconds per individual URL
MAX_WORKERS       = 40    # max simultaneous threads
MAX_REDDIT_POSTS  = 20    # posts per subreddit
MAX_NEWS_ARTICLES = 15    # articles per feed
MAX_SCREENER_COS  = 3     # companies from screener

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

try:
    from bs4 import BeautifulSoup
    BS4 = True
except ImportError:
    BS4 = False

try:
    import feedparser
    FEEDPARSER = True
except ImportError:
    FEEDPARSER = False

try:
    from pytrends.request import TrendReq
    PYTRENDS = True
except ImportError:
    PYTRENDS = False


# ═══════════════════════════════════════════════════════════
# LOW-LEVEL FETCH
# ═══════════════════════════════════════════════════════════

def safe_fetch(url, timeout=TIMEOUT_PER_URL, extra_headers=None):
    """Fetch a URL and return HTML string or None."""
    headers = dict(HEADERS)
    if extra_headers:
        headers.update(extra_headers)
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="ignore")
    except Exception:
        return None


def safe_fetch_json(url, timeout=TIMEOUT_PER_URL, extra_headers=None):
    """Fetch a URL and return parsed JSON or None."""
    html = safe_fetch(url, timeout, extra_headers)
    if not html:
        return None
    try:
        return json.loads(html)
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════
# INDIVIDUAL SCRAPER FUNCTIONS
# Each takes (query, domain, sub_domain, url, job_id) → list of items
# ═══════════════════════════════════════════════════════════

def scrape_reddit_url(query, domain, sub_domain, signal_type, url, job_id):
    """Scrape one subreddit."""
    items = []
    try:
        # Extract subreddit name
        parts = url.replace("https://","").replace("http://","").split("/")
        sub = None
        for i, p in enumerate(parts):
            if p == "r" and i + 1 < len(parts):
                sub = parts[i + 1]
                break
        if not sub:
            return items

        q = urllib.parse.quote(query)
        search_url = (
            f"https://www.reddit.com/r/{sub}/search.json"
            f"?q={q}&sort=relevance&limit={MAX_REDDIT_POSTS}&restrict_sr=1"
        )
        data = safe_fetch_json(
            search_url,
            extra_headers={"User-Agent": "GlobalDemandTool/1.0"}
        )

        posts = []
        if data and "data" in data:
            posts = data["data"].get("children", [])

        # Also get top posts if search returns nothing
        if len(posts) < 3:
            hot_data = safe_fetch_json(
                f"https://www.reddit.com/r/{sub}/hot.json?limit=10",
                extra_headers={"User-Agent": "GlobalDemandTool/1.0"}
            )
            if hot_data and "data" in hot_data:
                posts.extend(hot_data["data"].get("children", []))

        for post in posts[:MAX_REDDIT_POSTS]:
            p = post.get("data", {})
            title    = p.get("title", "")
            selftext = p.get("selftext", "")
            if not title:
                continue

            content   = f"{title}\n\n{selftext}".strip()[:2000]
            upvotes   = p.get("score", 0)
            comments  = p.get("num_comments", 0)
            permalink = p.get("permalink", "")
            created   = p.get("created_utc", 0)
            pub_at    = datetime.utcfromtimestamp(created).isoformat() if created else ""

            insert_scraped_item(
                job_id=job_id, query=query,
                domain=domain, sub_domain=sub_domain,
                signal_type=signal_type,
                source_name=f"reddit.com/r/{sub}",
                source_url=url,
                item_type="reddit_post",
                title=title, content=content,
                url=f"https://reddit.com{permalink}",
                author=p.get("author", ""),
                published_at=pub_at,
                score=float(upvotes),
                metadata={
                    "subreddit": sub,
                    "upvotes": upvotes,
                    "comments": comments,
                }
            )
            items.append(title)

        print(f"  [Reddit] r/{sub} → {len(items)} posts")
    except Exception as e:
        print(f"  [Reddit] r/{sub if 'sub' in dir() else url} error: {e}")
    return items


def scrape_news_url(query, domain, sub_domain, signal_type, feed_url, job_id):
    """Scrape one RSS/news feed."""
    items = []
    query_words = set(query.lower().split())

    try:
        if FEEDPARSER:
            import socket
            socket.setdefaulttimeout(TIMEOUT_PER_URL)
            feed = feedparser.parse(feed_url)
            socket.setdefaulttimeout(None)
            entries = feed.entries[:MAX_NEWS_ARTICLES]
        else:
            html = safe_fetch(feed_url)
            if not html or not BS4:
                return items
            soup = BeautifulSoup(html, "xml")
            raw = soup.find_all("item")[:MAX_NEWS_ARTICLES]
            entries = []
            for it in raw:
                entries.append(type("E", (), {
                    "title":     (it.find("title") or type("",(),{"text":""})()).text,
                    "summary":   (it.find("description") or type("",(),{"text":""})()).text,
                    "link":      (it.find("link") or type("",(),{"text":""})()).text,
                    "published": (it.find("pubDate") or type("",(),{"text":""})()).text,
                })())

        for entry in entries:
            title   = getattr(entry, "title",   "") or ""
            summary = getattr(entry, "summary", "") or ""
            link    = getattr(entry, "link",    "") or ""
            pub     = getattr(entry, "published","") or ""

            text = f"{title} {summary}".lower()
            matches = sum(1 for w in query_words if w in text and len(w) > 3)
            if matches == 0 and len(query_words) > 2:
                continue

            if BS4 and "<" in str(summary):
                summary = BeautifulSoup(str(summary), "html.parser").get_text()

            insert_scraped_item(
                job_id=job_id, query=query,
                domain=domain, sub_domain=sub_domain,
                signal_type=signal_type,
                source_name=urllib.parse.urlparse(feed_url).netloc,
                source_url=feed_url,
                item_type="news_article",
                title=str(title)[:300],
                content=str(summary)[:2000],
                url=str(link),
                published_at=str(pub),
                score=float(matches * 10),
                metadata={"matches": matches}
            )
            items.append(title)

        print(f"  [News] {urllib.parse.urlparse(feed_url).netloc} → {len(items)} articles")
    except Exception as e:
        print(f"  [News] {feed_url[:50]} error: {e}")
    return items


def scrape_google_trends_url(query, domain, sub_domain, signal_type, job_id):
    """Scrape Google Trends for the query."""
    if not PYTRENDS:
        return []

    items = []
    try:
        def fetch_trends():
            pt = TrendReq(hl="en-US", tz=360, timeout=(8, 10))
            pt.build_payload([query], timeframe="today 12-m", geo="")
            return pt.interest_over_time()

        result_box = [None]
        err_box    = [None]

        def run():
            try:
                result_box[0] = fetch_trends()
            except Exception as e:
                err_box[0] = e

        t = threading.Thread(target=run, daemon=True)
        t.start()
        t.join(timeout=18)

        if t.is_alive() or err_box[0]:
            print(f"  [Trends] timeout/error — skipping")
            return []

        df = result_box[0]
        if df is None or df.empty:
            return []

        values = df[query].tolist() if query in df.columns else []
        dates  = [str(d.date()) for d in df.index]

        if not values:
            return []

        peak    = max(values)
        current = values[-1]
        recent4 = sum(values[-4:]) / 4
        old4    = sum(values[:4]) / 4 if sum(values[:4]) > 0 else 1
        change  = (recent4 - old4) / old4
        trend   = "rising" if change > 0.15 else "falling" if change < -0.15 else "stable"

        insert_trend_data(
            query=query, keyword=query, region="global",
            interest_over_time={query: dict(zip(dates, values))},
            related_queries={}, related_topics={},
            peak_interest=int(peak),
            current_interest=int(current),
            trend_direction=trend
        )

        summary = (
            f"Google Trends for '{query}': "
            f"current interest={current}/100, peak={peak}/100, "
            f"trend={trend.upper()}. "
            f"Based on 12 months of search data."
        )

        insert_scraped_item(
            job_id=job_id, query=query,
            domain=domain, sub_domain=sub_domain,
            signal_type=signal_type,
            source_name="Google Trends",
            source_url="trends.google.com",
            item_type="trend",
            title=f"Google Trends: '{query}' — {trend.upper()} ({current}/100)",
            content=summary,
            url=f"https://trends.google.com/trends/explore?q={urllib.parse.quote(query)}",
            score=float(current),
            metadata={"peak": peak, "current": current, "trend": trend,
                      "values": values[-12:]}
        )
        items.append("trends")
        print(f"  [Trends] '{query}' → {current}/100, {trend}")
    except Exception as e:
        print(f"  [Trends] error: {e}")
    return items


def _parse_num(s):
    """Convert '1,234.56' or '12.3%' to float safely."""
    try:
        return float(re.sub(r'[^0-9.\-]', '', str(s or '')) or '0')
    except Exception:
        return 0.0


def _compute_cagr(values, years):
    """Compute CAGR from a list of value strings."""
    nums = [_parse_num(v) for v in values if _parse_num(v) > 0]
    if len(nums) < years + 1:
        return None
    start, end = nums[-(years + 1)], nums[-1]
    if start <= 0:
        return None
    try:
        return round(((end / start) ** (1 / years) - 1) * 100, 1)
    except Exception:
        return None


def scrape_screener_company(company_slug, query, domain, sub_domain, job_id):
    """
    Scrape one Screener.in company using JSON APIs only (no HTML/JS needed).
    Uses:
      1. Search API  — key ratios (P/E, ROE, ROCE, sales_growth_3y, etc.)
      2. Export API  — full P&L, quarterly, balance sheet, cash flow tables
      3. Playwright  — fallback if Playwright is available
    """
    items  = []
    page_url = f"https://www.screener.in/company/{company_slug}/consolidated/"

    # ── Try Playwright first if available ────────────────────
    try:
        from screener_playwright import scrape_company_with_playwright
        from database import insert_scrape_job as _isj
        result = scrape_company_with_playwright(
            company_slug, query, domain, sub_domain, job_id
        )
        if result:
            print(f"  [Screener] {company_slug} → {len(result)} items via Playwright")
            return result
    except Exception:
        pass   # Playwright not installed or failed — continue to API approach

    # ── Approach 1: Screener Search API (always works, returns JSON) ──
    search_data = {}
    try:
        search_url = (
            f"https://www.screener.in/api/company/search/"
            f"?q={urllib.parse.quote(company_slug)}&v=3&fts=1"
        )
        api_result = safe_fetch_json(search_url)
        if api_result:
            # Find the best matching company
            for item in api_result[:5]:
                item_url = item.get("url", "")
                if company_slug.upper() in item_url.upper():
                    search_data = item
                    break
            if not search_data and api_result:
                search_data = api_result[0]
    except Exception as e:
        print(f"  [Screener] Search API error for {company_slug}: {e}")

    company_name = search_data.get("name", company_slug)

    # ── Approach 2: Screener Export API (JSON P&L + tables) ──
    export_data = {}
    pl_annual   = {}
    quarterly   = {}
    bs_data     = {}
    cf_data     = {}
    peers       = []
    pros        = []
    cons        = []
    ratios      = {}
    doc_links   = []

    export_headers = {
        "User-Agent":  HEADERS["User-Agent"],
        "Accept":      "application/json, text/javascript, */*; q=0.01",
        "Referer":     page_url,
        "X-Requested-With": "XMLHttpRequest",
    }

    # Try export endpoint
    try:
        export_url = f"https://www.screener.in/api/company/{company_slug}/?format=json"
        raw = safe_fetch(export_url, extra_headers=export_headers)
        if raw and raw.strip().startswith("{"):
            export_data = json.loads(raw)
    except Exception:
        pass

    # Fallback: try to get consolidated page with extra headers (sometimes works)
    if not export_data:
        try:
            html_headers = {
                "User-Agent":      HEADERS["User-Agent"],
                "Accept":          "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer":         "https://www.screener.in/screens/",
                "Cache-Control":   "no-cache",
            }
            html = safe_fetch(page_url, extra_headers=html_headers)
            if html and BS4 and len(html) > 5000:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html, "html.parser")

                # Try ratios
                ratio_sec = soup.find("ul", id="top-ratios")
                if ratio_sec:
                    for li in ratio_sec.find_all("li"):
                        ne = li.find("span", class_="name")
                        ve = li.find("span", class_="value") or li.find("span", class_="number")
                        if ne and ve:
                            ratios[ne.get_text(strip=True)] = ve.get_text(strip=True)

                # Try P&L table
                for tbl in soup.find_all("table"):
                    ths = [th.get_text(strip=True) for th in tbl.find_all("th")]
                    if any(h in ths for h in ["Sales", "Revenue", "Net Sales"]):
                        for row in tbl.find_all("tr"):
                            cells = [td.get_text(strip=True) for td in row.find_all("td")]
                            if len(cells) >= 2:
                                pl_annual[cells[0]] = cells[1:10]
                        break

                # Peers
                peer_sec = soup.find("section", id="peers")
                if peer_sec:
                    for row in peer_sec.find_all("tr")[1:7]:
                        cells = row.find_all("td")
                        if cells:
                            peers.append(cells[0].get_text(strip=True))

                # Pros & Cons
                pd = soup.find("div", class_="pros")
                cd = soup.find("div", class_="cons")
                pros = [li.get_text(strip=True) for li in (pd.find_all("li") if pd else [])]
                cons = [li.get_text(strip=True) for li in (cd.find_all("li") if cd else [])]

                # Document links
                doc_sec = soup.find("div", id="documents")
                if doc_sec:
                    for a in doc_sec.find_all("a", href=True):
                        txt = a.get_text(strip=True)
                        if any(k in txt.lower() for k in ["annual","concall","transcript","report"]):
                            doc_links.append({"text": txt, "url": a["href"]})
        except Exception as e:
            print(f"  [Screener] HTML fallback error {company_slug}: {e}")

    # ── Parse export_data if available ───────────────────────
    if export_data:
        company_name = export_data.get("name", company_name)
        ratios = {k: str(v) for k, v in export_data.items()
                  if isinstance(v, (int, float, str)) and k not in
                  ["id","name","url","slug","isin","bse_code","nse_code"]}
        peers     = [p.get("name","") for p in export_data.get("peers", [])][:8]
        pros      = export_data.get("pros",  [])[:6]
        cons      = export_data.get("cons",  [])[:6]
        pl_annual = export_data.get("profit_loss", {}) or pl_annual
        quarterly = export_data.get("quarterly",   {})
        bs_data   = export_data.get("balance_sheet", {})
        cf_data   = export_data.get("cash_flows",    {})

    # ── Extract P&L rows ─────────────────────────────────────
    revenue_key    = next((k for k in pl_annual if k in
                          ["Sales","Revenue","Net Sales","Net Revenue"]), None)
    profit_key     = next((k for k in pl_annual if k in
                          ["Net Profit","Profit after tax","PAT"]), None)
    opm_key        = next((k for k in pl_annual if "OPM" in k), None)
    op_profit_key  = next((k for k in pl_annual if k in
                          ["Operating Profit","EBITDA","PBIDT"]), None)
    eps_key        = next((k for k in pl_annual if k.startswith("EPS")), None)

    revenue_trend  = pl_annual.get(revenue_key,   [])[:10]
    profit_trend   = pl_annual.get(profit_key,    [])[:10]
    opm_trend      = pl_annual.get(opm_key,       [])[:10]
    op_profit_trend= pl_annual.get(op_profit_key, [])[:10]
    eps_trend      = pl_annual.get(eps_key,       [])[:10]

    # ── Combine ratios from search_data ──────────────────────
    # Search API fields map to display names
    SEARCH_FIELD_MAP = {
        "market_cap":          "Market Cap",
        "current_price":       "Current Price",
        "stock_pe":            "P/E",
        "roce":                "ROCE",
        "roe":                 "ROE",
        "sales_growth_3years": "Sales Growth 3Y",
        "profit_growth_3years":"Profit Growth 3Y",
        "debt_to_equity":      "Debt/Equity",
        "dividend_yield":      "Div Yield",
        "book_value":          "Book Value",
        "price_to_book_value": "P/B",
    }
    for api_key, display_name in SEARCH_FIELD_MAP.items():
        val = search_data.get(api_key)
        if val is not None and str(val).strip() not in ("", "None", "null", "0"):
            if display_name not in ratios:
                ratios[display_name] = str(val)

    # ── Compute growth metrics ────────────────────────────────
    yoy_growth  = None
    cagr_3y     = _compute_cagr(revenue_trend, 3) if len(revenue_trend) >= 4 else None
    cagr_5y     = _compute_cagr(revenue_trend, 5) if len(revenue_trend) >= 6 else None
    # Try from search API if no P&L data
    if cagr_3y is None:
        sg3 = search_data.get("sales_growth_3years")
        if sg3 and str(sg3) not in ("None",""):
            cagr_3y = _parse_num(sg3)
    if len(revenue_trend) >= 2:
        r1, r2 = _parse_num(revenue_trend[-1]), _parse_num(revenue_trend[-2])
        if r2 > 0:
            yoy_growth = round((r1 / r2 - 1) * 100, 1)

    opm_values = [_parse_num(v) for v in opm_trend if _parse_num(v) > 0]
    opm_latest = opm_values[-1] if opm_values else None
    opm_avg    = round(sum(opm_values) / len(opm_values), 1) if opm_values else None

    # ── Quarterly data ────────────────────────────────────────
    q_sales  = quarterly.get("Sales",      quarterly.get("Revenue",     []))[:8]
    q_opm    = quarterly.get("OPM %",      quarterly.get("OPM",         []))[:8]
    q_profit = quarterly.get("Net Profit", quarterly.get("PAT",         []))[:8]

    # ── Save to DB ────────────────────────────────────────────
    sales_growth = {
        "yoy":     yoy_growth,
        "cagr_3y": cagr_3y,
        "cagr_5y": cagr_5y,
    }

    insert_financial(
        query=query, company_name=company_name, ticker=company_slug,
        sector="",
        market_cap=ratios.get("Market Cap", ratios.get("Mkt Cap", "")),
        revenue_trend=revenue_trend,
        profit_trend=profit_trend,
        sales_growth=sales_growth,
        peers=peers, pros=pros, cons=cons,
        source_url=page_url
    )

    # ── Build rich summary ────────────────────────────────────
    parts = [f"COMPANY: {company_name} ({company_slug})"]

    ratio_keys = ["Market Cap","Current Price","P/E","ROE","ROCE",
                  "Sales Growth 3Y","Profit Growth 3Y","Debt/Equity","Book Value","Div Yield"]
    ratio_str  = " | ".join(f"{k}: {ratios[k]}" for k in ratio_keys if k in ratios)
    if ratio_str:
        parts.append(f"KEY RATIOS: {ratio_str}")

    sg_parts = []
    if yoy_growth  is not None: sg_parts.append(f"YoY={yoy_growth}%")
    if cagr_3y     is not None: sg_parts.append(f"3Y CAGR={cagr_3y}%")
    if cagr_5y     is not None: sg_parts.append(f"5Y CAGR={cagr_5y}%")
    if sg_parts:
        parts.append(f"SALES GROWTH: {' | '.join(sg_parts)}")

    if opm_latest is not None:
        parts.append(f"OPERATING MARGIN: Latest={opm_latest}%" +
                     (f" | Avg={opm_avg}%" if opm_avg else ""))

    if revenue_trend:
        parts.append(f"ANNUAL REVENUE (Cr): {', '.join(revenue_trend[:8])}")
    if profit_trend:
        parts.append(f"NET PROFIT (Cr): {', '.join(profit_trend[:8])}")
    if op_profit_trend:
        parts.append(f"EBITDA/OP.PROFIT (Cr): {', '.join(op_profit_trend[:6])}")
    if eps_trend:
        parts.append(f"EPS: {', '.join(eps_trend[:6])}")
    if q_sales:
        parts.append(f"QUARTERLY SALES (Cr, 8Q): {', '.join(q_sales)}")
    if q_opm:
        parts.append(f"QUARTERLY OPM%: {', '.join(q_opm)}")
    if q_profit:
        parts.append(f"QUARTERLY NET PROFIT (Cr): {', '.join(q_profit)}")
    if peers:
        parts.append(f"PEERS: {' | '.join(peers[:6])}")
    if pros:
        parts.append(f"STRENGTHS: {'; '.join(pros[:4])}")
    if cons:
        parts.append(f"CONCERNS: {'; '.join(cons[:3])}")
    if doc_links:
        parts.append(f"DOCUMENTS: {len(doc_links)} available")

    full_summary = "\n".join(parts)

    insert_scraped_item(
        job_id=job_id, query=query, domain=domain, sub_domain=sub_domain,
        signal_type="Market Data",
        source_name="screener.in",
        source_url=page_url,
        item_type="financial",
        title=f"{company_name} — Screener.in Financial Data",
        content=full_summary,
        url=page_url,
        score=70.0,
        metadata={
            "ticker":          company_slug,
            "ratios":          ratios,
            "sales_growth":    sales_growth,
            "opm_latest":      opm_latest,
            "revenue_trend":   revenue_trend,
            "profit_trend":    profit_trend,
            "quarterly_sales": q_sales,
            "quarterly_opm":   q_opm,
            "quarterly_profit":q_profit,
            "peers":           peers,
            "pros":            pros,
            "cons":            cons,
            "doc_count":       len(doc_links),
        }
    )
    items.append(company_name)

    print(f"  [Screener] {company_slug}: ratios={len(ratios)} | "
          f"revenue_yrs={len(revenue_trend)} | quarters={len(q_sales)} | "
          f"peers={len(peers)} | docs={len(doc_links)} | growth={sales_growth}")

    # PDF extraction if we have doc links
    if doc_links:
        pdf_results = scrape_pdfs_parallel(
            doc_links[:2], company_name, query, domain, sub_domain, job_id
        )
        items.extend(pdf_results)

    return items


def scrape_pdfs_parallel(doc_links, company_name, query, domain, sub_domain, job_id):
    """Extract PDFs (annual reports / concall transcripts) in parallel."""
    results = []

    def scrape_one_pdf(doc):
        href       = doc["url"]
        text_label = doc["text"]
        pdf_url    = href if href.startswith("http") else f"https://www.screener.in{href}"
        try:
            try:
                from pypdf import PdfReader
            except ImportError:
                import PyPDF2 as _p2
                PdfReader = _p2.PdfReader
            import io as _io
            req = urllib.request.Request(pdf_url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=25) as r:
                data = r.read()
            reader = PdfReader(_io.BytesIO(data))
            text   = "".join(p.extract_text() or "" for p in reader.pages[:20])
            if len(text) < 100:
                return None
            DKWS = ["demand","growth","revenue","sales","order","pipeline",
                    "market","expansion","traction","momentum","strong"]
            RKWS = ["risk","decline","challenge","competition","pressure","weak"]
            sents = re.split(r'(?<=[.!?])\s+', text)
            d_s = [s.strip() for s in sents if 25 < len(s.strip()) < 500
                   and any(k in s.lower() for k in DKWS)][:20]
            r_s = [s.strip() for s in sents if 25 < len(s.strip()) < 500
                   and any(k in s.lower() for k in RKWS)][:10]
            tl       = text_label.lower()
            doc_type = ("concall" if any(k in tl for k in
                        ["concall","transcript","call","q1","q2","q3","q4"])
                        else "annual_report")
            import re as _re
            ym = _re.search(r'\b(20\d{2})\b', text_label)
            yr = ym.group(1) if ym else str(datetime.now().year)
            qm = _re.search(r'\b(Q[1-4])\b', text_label, _re.I)
            qt = qm.group(1).upper() if qm else ""
            insert_document_insight(
                query=query, company_name=company_name,
                doc_type=doc_type, year=yr, quarter=qt,
                full_text=text[:30000], key_themes=[],
                demand_mentions=d_s[:20], growth_signals=d_s[:10],
                risk_signals=r_s[:5], source_url=pdf_url
            )
            insert_scraped_item(
                job_id=job_id, query=query, domain=domain, sub_domain=sub_domain,
                signal_type="Validation Signal",
                source_name=f"screener.in ({doc_type})",
                source_url=pdf_url, item_type=doc_type,
                title=f"{company_name} — {doc_type.replace('_', ' ').title()} {qt} {yr}".strip(),
                content=" | ".join(d_s[:4]) if d_s else f"Extracted {len(text)} chars",
                url=pdf_url, score=80.0,
                metadata={"year": yr, "quarter": qt, "doc_type": doc_type,
                          "demand_count": len(d_s), "risk_count": len(r_s),
                          "pages": len(reader.pages)}
            )
            print(f"    [PDF] {doc_type} {qt} {yr}: {len(d_s)} demand sentences")
            return text_label
        except Exception as e:
            print(f"    [PDF] error {pdf_url[:60]}: {e}")
            return None

    with ThreadPoolExecutor(max_workers=4) as ex:
        futures = [ex.submit(scrape_one_pdf, doc) for doc in doc_links]
        for f in as_completed(futures, timeout=30):
            try:
                r = f.result()
                if r: results.append(r)
            except Exception:
                pass
    return results


def scrape_screener_query(query, domain, sub_domain, job_id):
    """
    Find and scrape Screener.in companies for the given query.
    Intent-based: uses keyword matching across all sub-domains to find
    the most relevant companies regardless of classifier sub_domain.
    """
    companies = []

    # Use the full intent-based lookup from screener_playwright
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from screener_playwright import search_screener_companies
        result = search_screener_companies(query, domain, sub_domain, MAX_SCREENER_COS)
        companies = [{"slug": c["slug"], "name": c["name"]} for c in result]
    except Exception as e:
        print(f"  [Screener] search_screener_companies error: {e}")

    # Direct API fallback if config lookup returned nothing
    if not companies:
        try:
            clean_q = re.sub(
                r'\b(is|there|a|an|the|for|in|of|on|at|demand|market|what|how|'
                r'does|are|any|about|with|and|or|to|from|by|has|have|need|want)\b',
                '', query.lower()
            ).strip()
            clean_q = " ".join(clean_q.split()[:4])
            search_url = (f"https://www.screener.in/api/company/search/"
                          f"?q={urllib.parse.quote(clean_q)}&v=3&fts=1")
            data = safe_fetch_json(search_url)
            if data:
                for item in data[:MAX_SCREENER_COS]:
                    raw   = item.get("url", "").rstrip("/")
                    parts = [p for p in raw.split("/") if p]
                    slug  = ""
                    for i, p in enumerate(parts):
                        if p == "company" and i + 1 < len(parts):
                            slug = parts[i + 1]; break
                    if not slug:
                        slug = parts[-1] if parts else ""
                    if slug not in ("consolidated", "standalone", ""):
                        companies.append({"slug": slug, "name": item.get("name", slug)})
                print(f"  [Screener] API fallback: {[c['slug'] for c in companies]}")
        except Exception as e:
            print(f"  [Screener] API fallback error: {e}")

    if not companies:
        print(f"  [Screener] No companies found for '{query}' ({domain}/{sub_domain})")
        return []

    print(f"  [Screener] Scraping {len(companies)} companies: {[c['slug'] for c in companies]}")

    all_items = []
    with ThreadPoolExecutor(max_workers=MAX_SCREENER_COS) as ex:
        futures = {
            ex.submit(scrape_screener_company,
                      c["slug"], query, domain, sub_domain, job_id): c["slug"]
            for c in companies
        }
        for f in as_completed(futures, timeout=120):
            slug = futures[f]
            try:
                result = f.result()
                all_items.extend(result)
            except Exception as e:
                print(f"  [Screener] {slug} error: {e}")

    return all_items



# Map of sites that support search — build direct search URLs
SEARCH_URL_BUILDERS = {
    "g2.com":            lambda q: f"https://www.g2.com/search?query={urllib.parse.quote(q)}",
    "capterra.com":      lambda q: f"https://www.capterra.com/search/?query={urllib.parse.quote(q)}",
    "trustradius.com":   lambda q: f"https://www.trustradius.com/search#query={urllib.parse.quote(q)}",
    "gartner.com":       lambda q: f"https://www.gartner.com/en/search?q={urllib.parse.quote(q)}",
    "forrester.com":     lambda q: f"https://www.forrester.com/search#N=4294959528&searchId={urllib.parse.quote(q)}",
    "idc.com":           lambda q: f"https://www.idc.com/search?q={urllib.parse.quote(q)}",
    "statista.com":      lambda q: f"https://www.statista.com/search/?q={urllib.parse.quote(q)}",
    "sapinsider.org":    lambda q: f"https://sapinsider.org/?s={urllib.parse.quote(q)}",
    "softwareadvice.com":lambda q: f"https://www.softwareadvice.com/search/?query={urllib.parse.quote(q)}",
    "community.sap.com": lambda q: f"https://community.sap.com/t5/forums/searchpage/tab/message?q={urllib.parse.quote(q)}",
    "blogs.sap.com":     lambda q: f"https://community.sap.com/t5/forums/searchpage/tab/message?q={urllib.parse.quote(q)}&advanced=false&collapse_discussion=true",
    "news.sap.com":      lambda q: f"https://news.sap.com/search/?q={urllib.parse.quote(q)}",
    "peerspot.com":      lambda q: f"https://www.peerspot.com/search?q={urllib.parse.quote(q)}",
    "crunchbase.com":    lambda q: f"https://www.crunchbase.com/discover/organizations/field/organizations/categories/{urllib.parse.quote(q.lower().replace(' ','-'))}",
    "linkedin.com":      lambda q: f"https://www.linkedin.com/jobs/search/?keywords={urllib.parse.quote(q)}",
    "indeed.com":        lambda q: f"https://www.indeed.com/jobs?q={urllib.parse.quote(q)}",
    "glassdoor.com":     lambda q: f"https://www.glassdoor.com/Job/jobs.htm?sc.keyword={urllib.parse.quote(q)}",
    "producthunt.com":   lambda q: f"https://www.producthunt.com/search?q={urllib.parse.quote(q)}",
    "marketsandmarkets.com": lambda q: f"https://www.marketsandmarkets.com/search.asp?q={urllib.parse.quote(q)}",
}

def build_direct_url(base_url: str, query: str) -> str:
    """Build a direct search URL for a site if possible, else return the base URL."""
    full = base_url if base_url.startswith("http") else f"https://{base_url}"
    hostname = urllib.parse.urlparse(full).netloc.replace("www.", "")
    # Check if we have a search builder for this hostname
    for key, builder in SEARCH_URL_BUILDERS.items():
        if key in hostname or hostname in key:
            return builder(query)
    return full


def scrape_web_url(query, domain, sub_domain, signal_type, url, job_id):
    """Scrape a single web URL for demand signals."""
    items = []
    full_url  = url if url.startswith("http") else f"https://{url}"
    hostname  = urllib.parse.urlparse(full_url).netloc.replace("www.", "")
    direct_url = build_direct_url(url, query)   # smart search URL

    try:
        html = safe_fetch(direct_url)
        if not html or not BS4:
            return items

        soup = BeautifulSoup(html, "html.parser")

        # Remove scripts/styles
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()

        # Extract all meaningful text blocks
        text_blocks = []
        for tag in soup.find_all(["h1","h2","h3","h4","p","li","td"]):
            t = tag.get_text(strip=True)
            if len(t) > 30:
                text_blocks.append(t)

        if not text_blocks:
            return items

        query_words = set(query.lower().split())
        relevant = []
        for block in text_blocks:
            block_lower = block.lower()
            matches = sum(1 for w in query_words if w in block_lower and len(w) > 3)
            if matches > 0:
                relevant.append((matches, block[:400]))

        relevant.sort(key=lambda x: x[0], reverse=True)
        top = relevant[:5]

        if not top:
            # Still save something
            top = [(0, text_blocks[0][:400])]

        combined_content = "\n\n".join(b for _, b in top)

        insert_scraped_item(
            job_id=job_id, query=query,
            domain=domain, sub_domain=sub_domain,
            signal_type=signal_type,
            source_name=hostname,          # now always non-empty (fixed above)
            source_url=direct_url,         # store the actual search URL used
            item_type="web_page",
            title=f"{hostname} — {query}",  # cleaner title
            content=combined_content[:2000],
            url=direct_url,                 # direct search URL — clickable in frontend
            score=float(sum(m for m, _ in top) * 5),
            metadata={"hostname": hostname, "blocks_found": len(relevant), "direct_url": direct_url}
        )
        items.append(hostname)
        print(f"  [Web] {hostname} → {len(relevant)} relevant blocks | url={direct_url[:60]}")

    except Exception as e:
        print(f"  [Web] {hostname} error: {e}")
    return items


def scrape_indeed(query, domain, sub_domain, signal_type, job_id):
    """Scrape Indeed job count as demand proxy."""
    url = f"https://www.indeed.com/jobs?q={urllib.parse.quote(query)}&sort=date"
    html = safe_fetch(url)
    if not html or not BS4:
        return []

    soup = BeautifulSoup(html, "html.parser")
    count_el = soup.find(string=re.compile(r'\d+\s*(jobs?|results?)', re.I))
    job_count = count_el.strip() if count_el else "jobs available"
    titles = [h.get_text(strip=True)
              for h in soup.find_all("h2", class_=re.compile("jobTitle"))[:8]]

    content = f"Job market for '{query}': {job_count}."
    if titles:
        content += f" Active roles: {', '.join(titles[:5])}."

    insert_scraped_item(
        job_id=job_id, query=query,
        domain=domain, sub_domain=sub_domain,
        signal_type=signal_type,
        source_name="indeed.com",
        source_url=url,
        item_type="job_postings",
        title=f"Job Market: '{query}' — {job_count}",
        content=content, url=url,
        score=50.0,
        metadata={"job_count": job_count, "titles": titles}
    )
    print(f"  [Indeed] '{query}' → {job_count}")
    return ["indeed"]


def scrape_google_news(query, domain, sub_domain, signal_type, job_id):
    """Scrape Google News RSS."""
    feed_url = (
        f"https://news.google.com/rss/search"
        f"?q={urllib.parse.quote(query)}&hl=en-US&gl=US&ceid=US:en"
    )
    return scrape_news_url(query, domain, sub_domain, signal_type, feed_url, job_id)


# ═══════════════════════════════════════════════════════════
# MASTER PARALLEL RUNNER
# ═══════════════════════════════════════════════════════════

def run_all_scrapers_parallel(query, domain_name, sub_domain,
                               sources_by_signal, job_id,
                               progress_callback=None):
    """
    Launch ALL scraping tasks simultaneously using a thread pool.
    Returns dict of { scraper_key: count }
    """

    tasks = []   # list of (task_fn, args, label)
    counts = {}  # label → count accumulator
    counts_lock = threading.Lock()

    # ── Build task list ──────────────────────────────────

    reddit_done   = set()
    news_done     = set()
    web_done      = set()
    trends_added  = False

    for signal_type, urls in sources_by_signal.items():
        for url in urls:
            url_clean = url.lower()

            # Reddit
            if "reddit.com" in url_clean and url not in reddit_done:
                reddit_done.add(url)
                tasks.append((
                    scrape_reddit_url,
                    (query, domain_name, sub_domain, signal_type, url, job_id),
                    "reddit"
                ))

            # Google Trends (only once)
            elif "trends.google" in url_clean and not trends_added:
                trends_added = True
                tasks.append((
                    scrape_google_trends_url,
                    (query, domain_name, sub_domain, signal_type, job_id),
                    "trends"
                ))

            # Indeed / LinkedIn jobs
            elif "indeed.com" in url_clean or "linkedin.com/jobs" in url_clean:
                if "indeed" not in web_done:
                    web_done.add("indeed")
                    tasks.append((
                        scrape_indeed,
                        (query, domain_name, sub_domain, signal_type, job_id),
                        "web"
                    ))

            # News / RSS feeds
            elif any(k in url_clean for k in [
                "techcrunch","venturebeat","wired","feedburner",
                "fiercepharma","fiercebiotech","medcity",
                "economictimes","ft.com","bloomberg",
                "greenbiz","agfunder","electrek","freightwaves",
                "rss","feed","news"
            ]) and url not in news_done:
                news_done.add(url)
                full_url = url if url.startswith("http") else f"https://{url}"
                tasks.append((
                    scrape_news_url,
                    (query, domain_name, sub_domain, signal_type, full_url, job_id),
                    "news"
                ))

            # Regular web pages
            elif url not in web_done:
                web_done.add(url)
                tasks.append((
                    scrape_web_url,
                    (query, domain_name, sub_domain, signal_type, url, job_id),
                    "web"
                ))

    # Always add Google News (not in domain sources usually)
    tasks.append((
        scrape_google_news,
        (query, domain_name, sub_domain, "Timing Signal", job_id),
        "news"
    ))

    # Always add Google Trends if not already added
    if not trends_added:
        tasks.append((
            scrape_google_trends_url,
            (query, domain_name, sub_domain, "Timing Signal", job_id),
            "trends"
        ))

    # Always add Screener.in
    tasks.append((
        scrape_screener_query,
        (query, domain_name, sub_domain, job_id),
        "screener"
    ))

    # Always add Indeed
    if "indeed" not in web_done:
        tasks.append((
            scrape_indeed,
            (query, domain_name, sub_domain, "Buyer Signal", job_id),
            "web"
        ))

    total_tasks = len(tasks)
    completed   = [0]
    print(f"\n[Parallel Engine] Launching {total_tasks} tasks simultaneously...")

    # ── Launch all tasks at once ─────────────────────────

    def run_task(fn, args, label):
        try:
            result = fn(*args)
            count  = len(result) if isinstance(result, list) else int(result or 0)
        except Exception as e:
            print(f"  [Task Error] {label}: {e}")
            count = 0

        with counts_lock:
            counts[label] = counts.get(label, 0) + count
            completed[0]  += 1
            done = completed[0]

        if progress_callback:
            progress_callback(label, count, done, total_tasks)

        return count

    start_time = time.time()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(run_task, fn, args, label): label
            for fn, args, label in tasks
        }
        # Wait for all, max 90 seconds total
        for future in as_completed(futures, timeout=180):
            try:
                future.result()
            except TimeoutError:
                print(f"  [Parallel Engine] Task timed out")
            except Exception as e:
                print(f"  [Parallel Engine] Task error: {e}")

    elapsed = time.time() - start_time
    total   = sum(counts.values())

    print(f"\n[Parallel Engine] DONE in {elapsed:.1f}s")
    print(f"[Parallel Engine] Results: {counts}")
    print(f"[Parallel Engine] Total items: {total}")

    return counts