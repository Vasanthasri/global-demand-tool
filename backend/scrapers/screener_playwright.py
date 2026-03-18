"""
screener_playwright.py — Complete Financial KPI Extractor
==========================================================
Extracts from Screener.in using Playwright (real browser):
  - Key financial ratios (Market Cap, P/E, ROE, ROCE, Debt/Equity)
  - P&L: Sales, Operating Profit, OPM%, Net Profit, EPS (10 years)
  - Quarterly results: Sales, OPM%, Net Profit (last 8 quarters)
  - Balance Sheet: Total Assets, Borrowings, Reserves
  - Cash Flow: Operating, Investing, Financing
  - Sales Growth %: YoY, 3-Year CAGR, 5-Year CAGR
  - Peer comparison table with Market Cap and P/E
  - Pros & Cons
  - Annual Reports + Concall PDF text extraction

Install: pip install playwright pypdf
         playwright install chromium
"""

import re, json, io, os, sys
import urllib.parse, urllib.request
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND  = os.path.dirname(_THIS_DIR)
sys.path.insert(0, _BACKEND)

from database import (insert_scrape_job, update_scrape_job,
                      insert_financial, insert_document_insight,
                      insert_scraped_item)

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    PLAYWRIGHT_OK = True
except ImportError:
    PLAYWRIGHT_OK = False
    print("[Screener] playwright not installed — run: pip install playwright && playwright install chromium")

try:
    from pypdf import PdfReader
    PDF_OK = True
except ImportError:
    try:
        from PyPDF2 import PdfReader
        PDF_OK = True
    except ImportError:
        PDF_OK = False

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
HEADERS = {"User-Agent": UA}

DEMAND_KW = [
    "demand","growth","revenue","market","opportunity","expansion","customer",
    "order","sales","pipeline","backlog","momentum","adoption","uptake",
    "traction","scale","increase","rising","strong","robust","accelerating",
    "record","highest","milestone","beat","outperform","guidance"
]
RISK_KW = [
    "decline","slowdown","competition","risk","headwind","challenge","pressure",
    "loss","shrink","reduce","weak","uncertain","concern","miss","below"
]
STOP_WORDS = {
    "is","there","a","an","the","for","in","of","on","at","demand","market",
    "what","how","does","are","was","were","will","can","should","would","could",
    "do","any","some","about","with","and","or","to","from","by","has","have",
    "need","want","looking","search","find","analysis","growth","potential",
    "opportunity","trend","trends","info","information","why","which","who",
    "please","tell","me","give","show","explain"
}

_COMPANIES_CONFIG = None

def _find_config_path():
    candidates = [
        os.path.join(_BACKEND, "backend", "config", "screener_companies.json"),
        os.path.join(_BACKEND, "config", "screener_companies.json"),
        os.path.join(_BACKEND, "screener_companies.json"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return candidates[0]

def load_companies_config():
    global _COMPANIES_CONFIG
    if _COMPANIES_CONFIG is None:
        path = _find_config_path()
        try:
            with open(path, encoding="utf-8") as f:
                _COMPANIES_CONFIG = json.load(f)
            print(f"[Screener] Config loaded from {path}")
        except FileNotFoundError:
            print(f"[Screener] Config not found at {path}")
            _COMPANIES_CONFIG = {}
        except Exception as e:
            print(f"[Screener] Config error: {e}")
            _COMPANIES_CONFIG = {}
    return _COMPANIES_CONFIG

def get_companies_for_domain(domain, sub_domain, query):
    """
    Return the most intent-relevant company tickers for a query.
    Matching priority:
      1. Longest keyword override match (most specific wins)
      2. Sub-domain default
      3. Try all sub-domains in domain (in case sub_domain is wrong/missing)
      4. Empty list → caller will use Screener API search
    """
    cfg = load_companies_config()
    q   = query.lower().strip()

    # Case-insensitive domain lookup
    domain_cfg = cfg.get(domain, {})
    if not domain_cfg:
        for k in cfg:
            if isinstance(cfg[k], dict) and k.lower() == domain.lower():
                domain_cfg = cfg[k]
                break
    if not domain_cfg:
        return []

    def _best_match(sub_cfg):
        """Return (matched_keyword, companies) with longest keyword match."""
        overrides = sub_cfg.get("keyword_overrides", {})
        best_kw, best_cos = "", []
        for kw, cos in overrides.items():
            if kw in q and len(kw) > len(best_kw):
                best_kw, best_cos = kw, cos
        if best_cos:
            return best_kw, best_cos
        default = sub_cfg.get("default", [])
        return ("default", default) if default else ("", [])

    # 1. Try exact sub_domain match
    sub_cfg = domain_cfg.get(sub_domain, {})
    if sub_cfg:
        kw, cos = _best_match(sub_cfg)
        if cos:
            tag = f"override '{kw}'" if kw != "default" else "default"
            print(f"[Screener] {domain}/{sub_domain} {tag} -> {cos[:3]}")
            return cos[:3]

    # 2. Try ALL sub_domains — keyword override might hit in a sibling sub_domain
    # e.g. query='sap fi' but sub_domain resolved as 'Artificial Intelligence' by classifier
    best_kw_global, best_cos_global, best_sub_global = "", [], ""
    for sub_key, sub_val in domain_cfg.items():
        if not isinstance(sub_val, dict):
            continue
        overrides = sub_val.get("keyword_overrides", {})
        for kw, cos in overrides.items():
            if kw in q and len(kw) > len(best_kw_global):
                best_kw_global, best_cos_global, best_sub_global = kw, cos, sub_key

    if best_cos_global:
        print(f"[Screener] Cross-sub match: '{best_kw_global}' in {best_sub_global} -> {best_cos_global[:3]}")
        return best_cos_global[:3]

    # 3. Fall back to sub_domain default (even if sub is wrong)
    if sub_cfg:
        default = sub_cfg.get("default", [])
        if default:
            print(f"[Screener] {sub_domain} default (fallback) -> {default[:3]}")
            return default[:3]

    # 4. Fall back to first sub_domain default in domain
    for sub_key, sub_val in domain_cfg.items():
        if isinstance(sub_val, dict):
            default = sub_val.get("default", [])
            if default:
                print(f"[Screener] Domain fallback ({sub_key}) -> {default[:3]}")
                return default[:3]

    return []


def extract_intent_keywords(query):
    """
    Extract the core meaningful keywords from a query for Screener API search.
    Strips question words, filler words, and returns the key terms.
    """
    words = re.findall(r'\b[a-zA-Z0-9/\.]+\b', query)
    clean = [w for w in words if w.lower() not in STOP_WORDS and len(w) > 1]
    # Prefer compound terms (keep adjacent pairs)
    return " ".join(clean[:4])


def search_screener_companies(query, domain, sub_domain, max_companies=3):
    """
    Find the most relevant companies to scrape for this query.
    Uses config-based intent matching first, then Screener API as fallback.
    """
    # Config-based lookup (intent-matched, most accurate)
    tickers = get_companies_for_domain(domain, sub_domain, query)
    if tickers:
        return [{"slug": t, "name": t, "intent_matched": True}
                for t in tickers[:max_companies]]

    # Screener search API fallback
    clean = extract_intent_keywords(query)
    print(f"[Screener] API search fallback: '{clean}'")
    try:
        url = (f"https://www.screener.in/api/company/search/"
               f"?q={urllib.parse.quote(clean)}&v=3&fts=1")
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=12) as r:
            data = json.loads(r.read().decode())
        companies = []
        for item in data[:max_companies]:
            raw   = item.get("url", "").rstrip("/")
            parts = [p for p in raw.split("/") if p]
            slug  = ""
            for i, p in enumerate(parts):
                if p == "company" and i + 1 < len(parts):
                    slug = parts[i + 1]; break
            if not slug:
                slug = parts[-1] if parts else ""
            if slug in ("consolidated", "standalone", ""):
                continue
            companies.append({"slug": slug, "name": item.get("name", slug),
                               "intent_matched": False})
        if companies:
            print(f"[Screener] API found: {[c['slug'] for c in companies]}")
            return companies
    except Exception as e:
        print(f"[Screener] API search error: {e}")
    return []

def _parse_number(s):
    try:
        return float(re.sub(r'[^0-9.\-]', '', s or ""))
    except Exception:
        return 0.0

def _compute_growth(values):
    nums = [_parse_number(v) for v in values if _parse_number(v) != 0]
    if len(nums) < 2:
        return {"yoy": None, "cagr_3y": None, "cagr_5y": None}
    def cagr(start, end, years):
        if start <= 0 or years <= 0:
            return None
        try:
            return round(((end / start) ** (1 / years) - 1) * 100, 1)
        except Exception:
            return None
    yoy     = round((nums[-1] / nums[-2] - 1) * 100, 1) if nums[-2] != 0 else None
    cagr_3y = cagr(nums[-4], nums[-1], 3) if len(nums) >= 4 else None
    cagr_5y = cagr(nums[-6], nums[-1], 5) if len(nums) >= 6 else None
    return {"yoy": yoy, "cagr_3y": cagr_3y, "cagr_5y": cagr_5y}

def _extract_table(page, selectors):
    """Try multiple CSS selectors, return {row_label: [values]} dict."""
    data = {}
    headers = []
    for sel in selectors:
        section = page.query_selector(sel)
        if not section:
            continue
        headers = [th.inner_text().strip()
                   for th in section.query_selector_all("th")
                   if th.inner_text().strip()]
        for row in section.query_selector_all("tr"):
            cells = [td.inner_text().strip() for td in row.query_selector_all("td")]
            if len(cells) >= 2:
                data[cells[0]] = cells[1:]
        if data:
            break
    return data, headers

def scrape_company_with_playwright(slug, query, domain, sub_domain, job_id):
    if not PLAYWRIGHT_OK:
        return []
    url   = f"https://www.screener.in/company/{slug}/consolidated/"
    items = []
    print(f"[Screener] Scraping {url}")
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage",
                      "--disable-blink-features=AutomationControlled"]
            )
            ctx  = browser.new_context(user_agent=UA)
            page = ctx.new_page()
            page.goto(url, timeout=35000, wait_until="domcontentloaded")
            if "login" in page.url or "accounts" in page.url:
                page.goto(f"https://www.screener.in/company/{slug}/",
                          timeout=25000, wait_until="domcontentloaded")
            try:
                page.wait_for_selector("#top-ratios, .company-name", timeout=12000)
            except PWTimeout:
                print(f"  [Screener] {slug}: timeout waiting for ratios")

            # Company name
            company_name = slug
            try:
                h1 = page.query_selector("h1, .company-name h1")
                if h1:
                    company_name = h1.inner_text().strip()
            except Exception:
                pass

            # Key ratios
            ratios = {}
            try:
                for li in page.query_selector_all("#top-ratios li"):
                    ne = li.query_selector(".name")
                    ve = li.query_selector(".value, .number, b")
                    if ne and ve:
                        k = ne.inner_text().strip()
                        v = ve.inner_text().strip()
                        if k and v:
                            ratios[k] = v
            except Exception:
                pass

            # P&L table
            pl_data, pl_headers = _extract_table(page, [
                "#profit-loss", "section#profit-loss",
                "[data-section='profit-loss']", ".profit-loss"
            ])
            # Fallback: find any table with Sales header
            if not pl_data:
                for tbl in page.query_selector_all("table"):
                    ths = [th.inner_text().strip() for th in tbl.query_selector_all("th")]
                    if any(h in ths for h in ["Sales","Revenue","Net Sales"]):
                        pl_headers = ths
                        for row in tbl.query_selector_all("tr"):
                            cells = [td.inner_text().strip() for td in row.query_selector_all("td")]
                            if len(cells) >= 2:
                                pl_data[cells[0]] = cells[1:]
                        break

            revenue_key   = next((k for k in pl_data if k in ["Sales","Revenue","Net Sales","Net Revenue"]), None)
            profit_key    = next((k for k in pl_data if k in ["Net Profit","Profit after tax","PAT","Net profit"]), None)
            opm_key       = next((k for k in pl_data if "OPM" in k or "Operating Profit Margin" in k), None)
            op_profit_key = next((k for k in pl_data if k in ["Operating Profit","EBITDA","PBIDT"]), None)
            eps_key       = next((k for k in pl_data if k.startswith("EPS") or k == "Earnings per share"), None)

            revenue_trend   = pl_data.get(revenue_key,   [])[:10]
            profit_trend    = pl_data.get(profit_key,    [])[:10]
            opm_trend       = pl_data.get(opm_key,       [])[:10]
            op_profit_trend = pl_data.get(op_profit_key, [])[:10]
            eps_trend       = pl_data.get(eps_key,       [])[:10]

            sales_growth = _compute_growth(revenue_trend)
            opm_values   = [_parse_number(v) for v in opm_trend if v]
            opm_avg      = round(sum(opm_values) / len(opm_values), 1) if opm_values else None
            opm_latest   = opm_values[-1] if opm_values else None

            # Quarterly results
            quarterly, q_headers = _extract_table(page, [
                "#quarters", "section#quarters",
                "[data-section='quarters']", ".quarters"
            ])
            q_sales  = quarterly.get("Sales",      quarterly.get("Revenue", []))[:8]
            q_opm    = quarterly.get("OPM %",       quarterly.get("OPM",    []))[:8]
            q_profit = quarterly.get("Net Profit",  quarterly.get("PAT",    []))[:8]

            # Balance sheet
            bs_data, _ = _extract_table(page, [
                "#balance-sheet", "section#balance-sheet",
                "[data-section='balance-sheet']"
            ])
            total_assets = bs_data.get("Total Assets", bs_data.get("Balance Sheet Total", []))[:5]
            borrowings   = bs_data.get("Borrowings",   bs_data.get("Total Debt",          []))[:5]
            reserves     = bs_data.get("Reserves",     [])[:5]

            # Cash flow
            cf_data, _ = _extract_table(page, [
                "#cash-flow", "section#cash-flow",
                "[data-section='cash-flow']"
            ])
            cf_operating = cf_data.get("Cash from Operating Activity",
                                       cf_data.get("Operating Cash Flow", []))[:5]
            cf_investing = cf_data.get("Cash from Investing Activity",
                                       cf_data.get("Investing Cash Flow", []))[:5]

            # Peers
            peers, peer_data = [], []
            try:
                for row in page.query_selector_all("#peers tr")[1:8]:
                    cells = row.query_selector_all("td")
                    if len(cells) >= 2:
                        name   = cells[0].inner_text().strip()
                        mktcap = cells[1].inner_text().strip() if len(cells) > 1 else ""
                        pe     = cells[2].inner_text().strip() if len(cells) > 2 else ""
                        if name:
                            peers.append(name)
                            peer_data.append({"name": name, "market_cap": mktcap, "pe": pe})
            except Exception:
                pass

            # Pros & Cons
            pros, cons = [], []
            try:
                pros = [li.inner_text().strip()
                        for li in page.query_selector_all(".pros li, #pros li")][:6]
                cons = [li.inner_text().strip()
                        for li in page.query_selector_all(".cons li, #cons li")][:6]
            except Exception:
                pass

            # Document links
            doc_links = []
            try:
                for a in page.query_selector_all("#documents a[href]"):
                    text = a.inner_text().strip()
                    href = a.get_attribute("href") or ""
                    if any(k in text.lower() for k in
                           ["annual","concall","transcript","report","result","earnings","q1","q2","q3","q4"]):
                        doc_links.append({"text": text, "url": href})
            except Exception:
                pass

            browser.close()

        # Save to DB
        insert_financial(
            query=query, company_name=company_name, ticker=slug, sector="",
            market_cap=ratios.get("Market Cap", ratios.get("Mkt Cap", "")),
            revenue_trend=revenue_trend, profit_trend=profit_trend,
            sales_growth=sales_growth, peers=peers, pros=pros, cons=cons,
            source_url=url
        )

        # Build full summary
        parts = [f"COMPANY: {company_name} ({slug})"]
        ratio_keys = ["Market Cap","Mkt Cap","P/E","ROE","ROCE","Debt / Equity","Book Value"]
        ratio_str  = " | ".join(f"{k}: {ratios[k]}" for k in ratio_keys if k in ratios)
        if ratio_str:
            parts.append(f"KEY RATIOS: {ratio_str}")
        if sales_growth.get("yoy") is not None:
            sg = f"SALES GROWTH: YoY={sales_growth['yoy']}%"
            if sales_growth.get("cagr_3y"):
                sg += f" | 3Y CAGR={sales_growth['cagr_3y']}%"
            if sales_growth.get("cagr_5y"):
                sg += f" | 5Y CAGR={sales_growth['cagr_5y']}%"
            parts.append(sg)
        if opm_latest is not None:
            parts.append(f"OPERATING MARGIN (OPM): Latest={opm_latest}%" +
                         (f" | Avg={opm_avg}%" if opm_avg else ""))
        if revenue_trend:
            parts.append(f"ANNUAL REVENUE (Cr): {', '.join(revenue_trend[:8])}")
        if profit_trend:
            parts.append(f"NET PROFIT (Cr): {', '.join(profit_trend[:8])}")
        if op_profit_trend:
            parts.append(f"OPERATING PROFIT/EBITDA (Cr): {', '.join(op_profit_trend[:8])}")
        if eps_trend:
            parts.append(f"EPS: {', '.join(eps_trend[:8])}")
        if q_sales:
            parts.append(f"QUARTERLY SALES (Cr, last 8Q): {', '.join(q_sales)}")
        if q_opm:
            parts.append(f"QUARTERLY OPM%: {', '.join(q_opm)}")
        if q_profit:
            parts.append(f"QUARTERLY NET PROFIT (Cr): {', '.join(q_profit)}")
        if total_assets:
            parts.append(f"TOTAL ASSETS (Cr): {', '.join(total_assets[:4])}")
        if borrowings:
            parts.append(f"BORROWINGS (Cr): {', '.join(borrowings[:4])}")
        if cf_operating:
            parts.append(f"OPERATING CASH FLOW (Cr): {', '.join(cf_operating[:4])}")
        if peer_data:
            peer_str = " | ".join(
                f"{p['name']} (MCap:{p['market_cap']} PE:{p['pe']})" for p in peer_data[:5]
            )
            parts.append(f"PEERS: {peer_str}")
        if pros:
            parts.append(f"STRENGTHS: {'; '.join(pros[:4])}")
        if cons:
            parts.append(f"CONCERNS: {'; '.join(cons[:3])}")
        if doc_links:
            parts.append(f"DOCUMENTS: {len(doc_links)} available")

        insert_scraped_item(
            job_id=job_id, query=query, domain=domain, sub_domain=sub_domain,
            signal_type="Market Data", source_name="screener.in", source_url=url,
            item_type="financial",
            title=f"{company_name} — Screener.in Financial Overview",
            content="\n".join(parts), url=url, score=75.0,
            metadata={
                "ticker": slug, "ratios": ratios,
                "sales_growth": sales_growth, "opm_latest": opm_latest, "opm_avg": opm_avg,
                "revenue_trend": revenue_trend, "profit_trend": profit_trend,
                "opm_trend": opm_trend, "op_profit_trend": op_profit_trend,
                "quarterly_sales": q_sales, "quarterly_opm": q_opm, "quarterly_profit": q_profit,
                "total_assets": total_assets, "borrowings": borrowings,
                "cf_operating": cf_operating, "cf_investing": cf_investing,
                "peers": peer_data, "pros": pros, "cons": cons,
                "doc_count": len(doc_links), "pl_headers": pl_headers[:10],
                "q_headers": q_headers[:10],
            }
        )
        items.append(company_name)
        print(f"  [Screener] {slug}: ratios={len(ratios)} revenue_yrs={len(revenue_trend)} "
              f"quarters={len(q_sales)} peers={len(peers)} docs={len(doc_links)} growth={sales_growth}")

        if doc_links:
            pdfs = scrape_pdfs_parallel(doc_links[:2], company_name, query, domain, sub_domain, job_id)
            items.extend(pdfs)

    except Exception as e:
        import traceback
        print(f"  [Screener] {slug} error: {type(e).__name__}: {e}")
        traceback.print_exc()

    return items


def extract_pdf_text(pdf_url):
    if not PDF_OK:
        return "", 0
    try:
        req = urllib.request.Request(pdf_url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=35) as r:
            data = r.read()
        reader    = PdfReader(io.BytesIO(data))
        full_text = "".join(p.extract_text() or "" for p in reader.pages[:25])
        return full_text, len(reader.pages)
    except Exception as e:
        print(f"    [PDF] error {pdf_url[:60]}: {e}")
        return "", 0

def extract_demand_sentences(text):
    sentences = re.split(r'(?<=[.!?])\s+', text)
    d_sents, r_sents = [], []
    for s in sentences:
        s = s.strip()
        if len(s) < 25 or len(s) > 500:
            continue
        sl = s.lower()
        if any(k in sl for k in DEMAND_KW):
            d_sents.append(s)
        elif any(k in sl for k in RISK_KW):
            r_sents.append(s)
    return d_sents[:25], r_sents[:10]

def scrape_one_pdf(doc, company_name, query, domain, sub_domain, job_id):
    href       = doc["url"]
    text_label = doc["text"]
    pdf_url    = href if href.startswith("http") else f"https://www.screener.in{href}"
    full_text, page_count = extract_pdf_text(pdf_url)
    if len(full_text) < 150:
        return None
    demand_sents, risk_sents = extract_demand_sentences(full_text)
    tl       = text_label.lower()
    doc_type = ("concall" if any(k in tl for k in ["concall","transcript","call","q1","q2","q3","q4"])
                else "annual_report")
    year_m   = re.search(r'\b(20\d{2})\b', text_label)
    year     = year_m.group(1) if year_m else str(datetime.now().year)
    qtr_m    = re.search(r'\b(Q[1-4])\b', text_label, re.I)
    qtr      = qtr_m.group(1).upper() if qtr_m else ""
    words    = re.findall(r'\b[A-Za-z]{5,}\b', full_text.lower())
    freq     = {}
    for w in words:
        if w not in STOP_WORDS:
            freq[w] = freq.get(w, 0) + 1
    themes = [w for w, _ in sorted(freq.items(), key=lambda x: -x[1])[:10]]
    insert_document_insight(
        query=query, company_name=company_name, doc_type=doc_type, year=year, quarter=qtr,
        full_text=full_text[:30000], key_themes=themes,
        demand_mentions=demand_sents[:20], growth_signals=demand_sents[:10],
        risk_signals=risk_sents[:5], source_url=pdf_url
    )
    content = " | ".join(demand_sents[:5]) if demand_sents else f"Extracted {len(full_text)} chars"
    insert_scraped_item(
        job_id=job_id, query=query, domain=domain, sub_domain=sub_domain,
        signal_type="Validation Signal",
        source_name=f"screener.in ({doc_type})",
        source_url=pdf_url, item_type=doc_type,
        title=f"{company_name} — {doc_type.replace('_',' ').title()} {qtr} {year}".strip(),
        content=content, url=pdf_url, score=80.0,
        metadata={"year": year, "quarter": qtr, "doc_type": doc_type,
                  "demand_count": len(demand_sents), "risk_count": len(risk_sents),
                  "pages": page_count, "key_themes": themes[:5]}
    )
    print(f"    [PDF] {doc_type} {qtr} {year} — {len(demand_sents)} demand / {len(risk_sents)} risk sentences")
    return text_label

def scrape_pdfs_parallel(doc_links, company_name, query, domain, sub_domain, job_id):
    results = []
    with ThreadPoolExecutor(max_workers=4) as ex:
        futures = {ex.submit(scrape_one_pdf, doc, company_name,
                             query, domain, sub_domain, job_id): doc["text"]
                   for doc in doc_links}
        for f in as_completed(futures, timeout=60):
            try:
                r = f.result()
                if r:
                    results.append(r)
            except Exception as e:
                print(f"    [PDF] error: {e}")
    return results

def scrape_screener_query_pw(query, domain, sub_domain, job_id):
    companies = search_screener_companies(query, domain, sub_domain, max_companies=3)
    if not companies:
        print(f"[Screener] No companies found for '{query}' ({domain}/{sub_domain})")
        return []
    print(f"[Screener] Scraping: {[c['slug'] for c in companies]}")
    items = []
    with ThreadPoolExecutor(max_workers=3) as ex:
        futures = {
            ex.submit(scrape_company_with_playwright,
                      c["slug"], query, domain, sub_domain, job_id): c["slug"]
            for c in companies
        }
        for f in as_completed(futures, timeout=120):
            slug = futures[f]
            try:
                items.extend(f.result())
            except Exception as e:
                print(f"[Screener] {slug} error: {e}")
    print(f"[Screener] Done — {len(items)} items")
    return items

if __name__ == "__main__":
    from database import init_db
    init_db()
    q  = sys.argv[1] if len(sys.argv) > 1 else "Is there demand for SAP"
    d  = sys.argv[2] if len(sys.argv) > 2 else "Technology"
    sd = sys.argv[3] if len(sys.argv) > 3 else "SAP & Enterprise Software"
    print(f"\nTesting: {q!r} | {d} | {sd}\n{'='*60}")
    jid = insert_scrape_job(q, d, sd, "Market Data", "screener.in", "test")
    results = scrape_screener_query_pw(q, d, sd, jid)
    print(f"\nResults: {results}")