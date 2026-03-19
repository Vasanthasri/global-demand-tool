"""
server.py
Uses parallel_engine — ALL sources scraped simultaneously.
POST /api/search                  → start full pipeline, get job_id
GET  /api/search/status/<job_id>  → live progress updates
GET  /api/search/result/<job_id>  → final result + all evidence
GET  /api/health
"""

import os, json, uuid, threading, urllib.parse, urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

from database import init_db, get_demand_score, get_scraped_items, get_connection, dict_cursor, placeholder

GEMINI_API_KEY = "AIzaSyA0gMn6Dq1Ion9QtIxwHG5n8wl6UQxWbsk"
PORT = int(os.environ.get("PORT", 8000))

_jobs  = {}
_lock  = threading.Lock()

def upd(job_id, **kw):
    with _lock:
        if job_id in _jobs:
            _jobs[job_id].update(kw)


def resolve_query(query: str) -> str:
    """
    Resolve a user-input query to the best matching query stored in the DB.
    Tries: exact lowercase match → keyword-overlap match → original.
    This handles cases where the user typed 'IS there demand for SAP' but
    the DB has 'is there a demand for sap' (same intent, different wording).
    """
    q_norm = query.strip().lower()
    conn = get_connection()
    cur = dict_cursor(conn)

    # 1. Exact normalized match
    cur.execute(
        f"SELECT DISTINCT query FROM scraped_items WHERE LOWER(query)=LOWER({placeholder()})",
        (q_norm,)
    )
    row = cur.fetchone()
    if row:
        conn.close()
        return dict(row)["query"]

    # 2. Keyword overlap: find stored query sharing the most words with input
    cur.execute("SELECT DISTINCT query FROM scraped_items")
    all_q = [dict(r)["query"] for r in cur.fetchall()]
    conn.close()

    if not all_q:
        return q_norm

    input_words = set(w for w in q_norm.split() if len(w) > 2)
    best_query, best_score = q_norm, 0
    for stored in all_q:
        stored_words = set(w for w in stored.lower().split() if len(w) > 2)
        overlap = len(input_words & stored_words)
        if overlap > best_score:
            best_score = overlap
            best_query = stored

    return best_query if best_score > 0 else q_norm


def run_pipeline(job_id, query, api_key):
    try:
        # ── 1. Classify ─────────────────────────────────
        upd(job_id, stage="classify", stage_index=0,
            message="Identifying domain and demand signals…")

        from classifier import classify
        classification = classify(query, api_key)
        domains = classification.get("domains", {})

        if not domains:
            upd(job_id, status="error",
                error=f"Could not classify '{query}'. Try a more specific query.")
            return

        primary = max(domains.items(), key=lambda x: x[1]["confidence"])
        domain_name       = primary[0]
        domain_data       = primary[1]
        sub_domains       = domain_data.get("sub_domains", [])
        sub_domain        = sub_domains[0] if sub_domains else domain_name
        sources_by_signal = domain_data.get("sources_by_signal", {})

        upd(job_id,
            domain=domain_name,
            sub_domain=sub_domain,
            confidence=domain_data["confidence"],
            all_domains=list(domains.keys()),
            message=f"Domain: {domain_name} ({domain_data['confidence']}% confidence)")

        # ── 2. Create scrape job in DB ───────────────────
        from database import insert_scrape_job, update_scrape_job
        master_job_id = insert_scrape_job(
            query, domain_name, sub_domain,
            "All Signals", "parallel_engine", "parallel"
        )

        # ── 3. Run ALL scrapers in parallel ─────────────
        upd(job_id, stage="scraping", stage_index=1,
            message="Launching all scrapers simultaneously…")

        sr = {}  # scraper results counter

        def progress_cb(label, count, done, total):
            with _lock:
                if job_id not in _jobs: return
                sr[label] = sr.get(label, 0) + count
                total_so_far = sum(sr.values())
                pct = int((done / total) * 100)
                _jobs[job_id].update({
                    "stage":          "scraping",
                    "stage_index":    1,
                    "scraper_results": dict(sr),
                    "progress_pct":   pct,
                    "message": (
                        f"Scraping… {done}/{total} sources done "
                        f"({total_so_far} items collected)"
                    )
                })

        from scrapers.parallel_engine import run_all_scrapers_parallel
        scraper_results = run_all_scrapers_parallel(
            query, domain_name, sub_domain,
            sources_by_signal, master_job_id,
            progress_callback=progress_cb
        )

        update_scrape_job(master_job_id, "completed",
                          sum(scraper_results.values()))

        total_collected = sum(scraper_results.values())
        upd(job_id,
            scraper_results=scraper_results,
            message=f"All sources scraped — {total_collected} items collected")

        # ── 4. AI Scoring ────────────────────────────────
        upd(job_id, stage="scoring", stage_index=2,
            message=f"AI analyzing {total_collected} data points…")

        def do_score():
            try:
                from pipeline.ai_scorer import score_demand_with_ai
                score_demand_with_ai(query, domain_name, api_key)
            except Exception as e:
                print(f"[Score] error: {e}")

        score_thread = threading.Thread(target=do_score, daemon=True)
        score_thread.start()
        score_thread.join(timeout=45)

        # ── 5. Build result ──────────────────────────────
        final_score = get_demand_score(query)
        evidence    = get_scraped_items(query, limit=200)
        result      = build_result(
            query, domain_name, sub_domain,
            domain_data, domains,
            final_score, evidence, scraper_results
        )

        upd(job_id,
            status="complete", stage="done", stage_index=3,
            message=(
                f"Complete — {total_collected} items from "
                f"{len(scraper_results)} source types"
            ),
            result=result,
            scraper_results=scraper_results)

    except Exception as e:
        import traceback
        traceback.print_exc()
        upd(job_id, status="error", error=str(e))


def build_result(query, domain_name, sub_domain, domain_data,
                 all_domains, score_row, evidence, sr):

    demand_score = None
    if score_row:
        ke = score_row.get("key_evidence", [])
        if isinstance(ke, str):
            try:    ke = json.loads(ke)
            except: ke = [ke]
        demand_score = {
            "overall":       round(score_row.get("overall_score", 0)),
            "verdict":       score_row.get("verdict", "UNKNOWN"),
            "signals": {
                "pain":       round(score_row.get("pain_score", 0)),
                "buyer":      round(score_row.get("buyer_score", 0)),
                "competitor": round(score_row.get("competitor_score", 0)),
                "timing":     round(score_row.get("timing_score", 0)),
                "validation": round(score_row.get("validation_score", 0)),
                "expansion":  round(score_row.get("expansion_score", 0)),
            },
            "why_demand":    score_row.get("why_demand", ""),
            "why_no_demand": score_row.get("why_no_demand", ""),
            "key_evidence":  ke,
        }

    ev_out = []
    for item in evidence:
        meta = item.get("metadata", "{}")
        if isinstance(meta, str):
            try:    meta = json.loads(meta)
            except: meta = {}
        ev_out.append({
            "id":          item.get("id"),
            "item_type":   item.get("item_type", ""),
            "signal_type": item.get("signal_type", ""),
            "source_name": item.get("source_name", ""),
            "title":       item.get("title", ""),
            "content":     item.get("content", ""),
            "url":         item.get("url", ""),
            "score":       item.get("score", 0),
            "published_at":item.get("published_at", ""),
            "metadata":    meta,
        })

    domain_info = {}
    for dname, ddata in all_domains.items():
        sbysig = ddata.get("sources_by_signal", {})
        domain_info[dname] = {
            "confidence":    ddata["confidence"],
            "sub_domains":   ddata.get("sub_domains", []),
            "signals":       list(sbysig.keys()),
            "total_sources": sum(len(v) for v in sbysig.values()),
        }

    return {
        "query":           query,
        "primary_domain":  domain_name,
        "sub_domain":      sub_domain,
        "domains":         domain_info,
        "demand_score":    demand_score,
        "evidence":        ev_out,
        "scraper_results": sr,
        "total_collected": sum(sr.values()),
        "scraped_at":      datetime.utcnow().isoformat(),
        "next_refresh":    "24 hours",
    }



# ── Timeline & Location helpers ─────────────────────────────

def get_timeline_data(query: str) -> dict:
    """Return past 6 months of monthly evidence counts for a query."""
    query = resolve_query(query)
    from datetime import datetime, timedelta
    from email.utils import parsedate_to_datetime
    import sqlite3

    conn = get_connection()
    cur = dict_cursor(conn)
    p = placeholder()
    cur.execute(f"SELECT published_at, signal_type FROM scraped_items WHERE LOWER(query)=LOWER({p}) AND published_at != ''", (query,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    now = datetime.utcnow()
    # Build last-6-month buckets
    months = []
    for i in range(5, -1, -1):
        d = now.replace(day=1) - timedelta(days=i * 28)
        months.append(d.strftime("%Y-%m"))
    months = sorted(set(months))[-6:]

    counts = {m: {"total": 0, "pain": 0, "timing": 0, "buyer": 0, "competitor": 0, "validation": 0} for m in months}

    for row in rows:
        try:
            try:
                dt = parsedate_to_datetime(row["published_at"])
            except Exception:
                dt = datetime.fromisoformat(row["published_at"][:10])
            key = dt.strftime("%Y-%m")
            if key in counts:
                counts[key]["total"] += 1
                sig = (row.get("signal_type") or "").lower().split()[0]
                if sig in counts[key]:
                    counts[key][sig] += 1
        except Exception:
            pass

    labels = []
    from calendar import month_abbr
    for m in sorted(counts.keys()):
        y, mo = m.split("-")
        labels.append(f"{month_abbr[int(mo)]} {y}")

    return {
        "query": query,
        "labels": labels,
        "months": sorted(counts.keys()),
        "series": {
            "Total Evidence": [counts[m]["total"] for m in sorted(counts.keys())],
            "Pain Signal":    [counts[m]["pain"]  for m in sorted(counts.keys())],
            "Timing Signal":  [counts[m]["timing"] for m in sorted(counts.keys())],
            "Buyer Signal":   [counts[m]["buyer"]  for m in sorted(counts.keys())],
        }
    }


def get_location_data(query: str) -> dict:
    """Extract regional demand counts from scraped content."""
    query = resolve_query(query)
    conn = get_connection()
    cur = dict_cursor(conn)
    p = placeholder()
    cur.execute(f"SELECT title, content FROM scraped_items WHERE LOWER(query)=LOWER({p})", (query,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    REGIONS = {
        "USA":          ["usa", "united states", "u.s.", "america", "american", "north america", "new york", "san francisco", "chicago"],
        "UK":           ["u.k.", " uk ", "united kingdom", "britain", "british", "england", "london"],
        "India":        ["india", "indian", "bangalore", "bengaluru", "mumbai", "delhi", "hyderabad", "pune"],
        "Germany":      ["germany", "german", "deutschland", "dach", "berlin", "munich", "frankfurt"],
        "Europe":       ["europe", "european", "emea", "eu ", "france", "netherlands", "spain", "italy"],
        "Middle East":  ["middle east", "uae", "dubai", "saudi", "riyadh", "abu dhabi", "qatar"],
        "Asia Pacific": ["asia", "apac", "australia", "singapore", "japan", "china", "korea", "southeast asia"],
        "Global":       ["global", "worldwide", "international", "across the globe"],
    }

    region_counts = {}
    region_examples = {}

    for row in rows:
        text = ((row.get("title") or "") + " " + (row.get("content") or "")).lower()
        for region, keywords in REGIONS.items():
            for kw in keywords:
                if kw in text:
                    region_counts[region] = region_counts.get(region, 0) + 1
                    if region not in region_examples:
                        title = row.get("title", "")
                        if title:
                            region_examples[region] = title[:80]
                    break

    # Sort by count
    sorted_regions = sorted(region_counts.items(), key=lambda x: x[1], reverse=True)
    total = sum(region_counts.values()) or 1

    return {
        "query": query,
        "regions": [
            {
                "name": r,
                "count": c,
                "pct": round(c / total * 100),
                "example": region_examples.get(r, "")
            }
            for r, c in sorted_regions
        ],
        "total_mentions": sum(region_counts.values()),
    }



# ── Module Breakdown helper — FULLY DYNAMIC ─────────────────
# Reads from config/domain_modules.json — no hardcoded module names

_MODULES_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "domain_modules.json"
)
_MODULES_CONFIG_PATH_ALT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "config", "domain_modules.json"
)
_MODULES_CONFIG_PATH_ALT2 = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "backend", "config", "domain_modules.json"
)
_MODULES_CONFIG = None

def load_modules_config() -> dict:
    """Load domain_modules.json once and cache it."""
    global _MODULES_CONFIG
    if _MODULES_CONFIG is None:
        for path in [_MODULES_CONFIG_PATH, _MODULES_CONFIG_PATH_ALT, _MODULES_CONFIG_PATH_ALT2]:
            try:
                with open(path, encoding="utf-8") as f:
                    _MODULES_CONFIG = json.load(f)
                print(f"[Server] Loaded domain_modules.json from {path}")
                break
            except FileNotFoundError:
                continue
            except Exception as e:
                print(f"[Server] domain_modules.json load error at {path}: {e}")
                continue
        if _MODULES_CONFIG is None:
            print(f"[Server] domain_modules.json not found in any expected location")
            _MODULES_CONFIG = {}
    return _MODULES_CONFIG


def get_modules_for_query(query: str, domain: str, sub_domain: str) -> list:
    """
    Returns the module list for this domain/sub-domain from config.
    Falls back to checking all modules across the domain if sub-domain not found.
    """
    cfg = load_modules_config()
    domain_cfg = cfg.get(domain, {})
    if not domain_cfg:
        for k in cfg:
            if isinstance(cfg[k], dict) and k.lower() == domain.lower():
                domain_cfg = cfg[k]
                break

    # Try exact sub-domain match first
    modules = domain_cfg.get(sub_domain, [])

    # If not found, try to match any sub-domain whose name is mentioned in the query
    if not modules:
        q_lower = query.lower()
        for sub, mods in domain_cfg.items():
            if isinstance(mods, list) and sub.lower() in q_lower:
                modules = mods
                break

    # Last fallback: use first available sub-domain
    if not modules:
        for sub, mods in domain_cfg.items():
            if isinstance(mods, list):
                modules = mods
                break

    return modules


def get_module_breakdown(query: str, domain: str = "", sub_domain: str = "") -> dict:
    """
    Scan all scraped evidence and count mentions of each sub-module.
    Returns sources (url + source_name + title) and reason per module.
    """
    query = resolve_query(query)
    conn = get_connection()
    cur = dict_cursor(conn)
    p = placeholder()

    # Get domain/sub_domain from DB if not provided by caller
    if not domain or not sub_domain:
        cur.execute(f"SELECT domain FROM demand_scores WHERE LOWER(query)=LOWER({p})", (query,))
        score_row = cur.fetchone()
        if score_row:
            domain = dict(score_row).get("domain", domain) or domain
        if not sub_domain:
            cur.execute(
                f"SELECT sub_domain FROM scraped_items WHERE LOWER(query)=LOWER({p}) AND sub_domain != '' LIMIT 1",
                (query,)
            )
            sub_row = cur.fetchone()
            if sub_row:
                sub_domain = dict(sub_row).get("sub_domain", "") or ""

    # Fetch full item data including url, source_name, signal_type, score
    cur.execute(
        f"""SELECT title, content, url, source_name, signal_type, score
            FROM scraped_items WHERE LOWER(query)=LOWER({p})
            ORDER BY score DESC""",
        (query,)
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    if not rows:
        return {"query": query, "modules": [], "total_items": 0, "domain": domain}

    modules_cfg = get_modules_for_query(query, domain, sub_domain)

    if not modules_cfg:
        return {"query": query, "modules": [], "total_items": len(rows),
                "domain": domain, "message": f"No module config found for domain: {domain}"}

    module_data = {}
    for mod in modules_cfg:
        mod_name  = mod.get("name", "")
        keywords  = mod.get("keywords", [])
        emoji     = mod.get("emoji", "📌")
        count     = 0
        examples  = []
        sources   = []          # list of {url, source_name, title, signal_type}
        seen_urls = set()
        matched_kws = set()

        for row in rows:
            text = ((row.get("title") or "") + " " + (row.get("content") or "")).lower()
            for kw in keywords:
                if kw in text:
                    count += 1
                    matched_kws.add(kw)

                    title = (row.get("title") or "").strip()
                    if title and title not in examples and len(title) > 10:
                        examples.append(title[:90])

                    # Collect unique sources (url-deduped, max 5)
                    url = (row.get("url") or "").strip()
                    src = (row.get("source_name") or "").strip()
                    sig = (row.get("signal_type") or "").strip()
                    if url and url not in seen_urls and len(sources) < 5:
                        seen_urls.add(url)
                        sources.append({
                            "url":         url,
                            "source_name": src,
                            "title":       title[:80],
                            "signal_type": sig,
                        })
                    break

        if count > 0:
            module_data[mod_name] = {
                "count":        count,
                "examples":     examples[:3],
                "emoji":        emoji,
                "sources":      sources,
                "matched_keywords": list(matched_kws)[:6],
            }

    if not module_data:
        return {"query": query, "modules": [], "total_items": len(rows), "domain": domain}

    max_count      = max(v["count"] for v in module_data.values())
    total_mentions = sum(v["count"] for v in module_data.values())

    def build_reason(name, data, verdict, pct):
        """Generate a human-readable reason sentence for this module's score."""
        count   = data["count"]
        kws     = data["matched_keywords"]
        sources = data["sources"]
        src_names = list({s["source_name"] for s in sources if s["source_name"]})[:3]

        if verdict == "HIGH":
            strength = "Strong demand signal"
        elif verdict == "MEDIUM":
            strength = "Moderate demand signal"
        else:
            strength = "Emerging demand signal"

        reason = f"{strength} — found {count} mention{'s' if count != 1 else ''} across scraped content"
        if kws:
            reason += f" matching keywords: {', '.join(kws[:4])}"
        if src_names:
            reason += f". Evidence from: {', '.join(src_names)}"
        reason += f". Accounts for {round(data['count']/total_mentions*100)}% of all sub-area mentions."
        return reason

    modules_list = sorted([
        {
            "name":             name,
            "count":            data["count"],
            "pct":              round((data["count"] / max_count) * 100),
            "share":            round((data["count"] / total_mentions) * 100),
            "examples":         data["examples"],
            "emoji":            data["emoji"],
            "sources":          data["sources"],
            "matched_keywords": data["matched_keywords"],
            "verdict": (
                "HIGH"   if data["count"] / max_count >= 0.6 else
                "MEDIUM" if data["count"] / max_count >= 0.3 else
                "LOW"
            ),
            "reason": build_reason(name, data,
                "HIGH"   if data["count"] / max_count >= 0.6 else
                "MEDIUM" if data["count"] / max_count >= 0.3 else
                "LOW",
                round((data["count"] / max_count) * 100)
            ),
        }
        for name, data in module_data.items()
    ], key=lambda x: x["count"], reverse=True)

    return {
        "query":          query,
        "domain":         domain,
        "sub_domain":     sub_domain,
        "modules":        modules_list,
        "total_items":    len(rows),
        "total_mentions": total_mentions,
    }


# ── Chat helper ──────────────────────────────────────────────



def answer_chat(query: str, question: str, api_key: str) -> dict:
    """
    Answer a follow-up question using already-scraped evidence.
    Passes FULL scraped content to AI — no general knowledge, data-only answers.
    """
    query = resolve_query(query)
    conn = get_connection()
    cur = dict_cursor(conn)
    p = placeholder()

    # 1. Get demand score
    cur.execute(f"SELECT * FROM demand_scores WHERE LOWER(query)=LOWER({p})", (query,))
    score_row = cur.fetchone()
    score_row = dict(score_row) if score_row else {}

    # 2. Get ALL scraped items with full content
    cur.execute(
        f"""SELECT title, content, signal_type, source_name, url, score
            FROM scraped_items
            WHERE LOWER(query)=LOWER({p})
            ORDER BY score DESC""",
        (query,)
    )
    all_items = [dict(r) for r in cur.fetchall()]
    conn.close()

    # 3. Build module & location data
    breakdown = get_module_breakdown(query)
    loc_data  = get_location_data(query)
    modules   = breakdown.get("modules", [])
    regions   = loc_data.get("regions", [])

    # 4. Group items by signal type with FULL content
    by_signal = {}
    for it in all_items:
        sig = it.get("signal_type", "Other")
        if sig not in by_signal:
            by_signal[sig] = []
        by_signal[sig].append({
            "source":  it.get("source_name", ""),
            "title":   it.get("title", "")[:120],
            "content": (it.get("content") or "")[:400],
            "url":     it.get("url", ""),
            "score":   it.get("score", 0),
        })

    # 5. Parse key evidence
    key_ev_raw = score_row.get("key_evidence", "[]")
    if isinstance(key_ev_raw, str):
        try:    key_ev_list = json.loads(key_ev_raw)
        except: key_ev_list = [key_ev_raw]
    else:
        key_ev_list = key_ev_raw or []

    # 6. Build full evidence text for prompt
    evidence_sections = []
    for sig, items in by_signal.items():
        evidence_sections.append(f"\n--- {sig} ({len(items)} items) ---")
        for i, it in enumerate(items[:12]):
            evidence_sections.append(
                f"  [{i+1}] SOURCE: {it['source']} | SCORE: {it['score']}\n"
                f"       TITLE: {it['title']}\n"
                f"       CONTENT: {it['content']}\n"
                f"       URL: {it['url']}"
            )

    module_lines = [
        f"  {m['emoji']} {m['name']}: {m['count']} mentions ({m['share']}% share) "
        f"verdict={m['verdict']} | keywords={m.get('matched_keywords',[])} | {m.get('reason','')}"
        for m in modules
    ]
    region_lines = []
    for r in regions:
        line = f"  {r['name']}: {r['count']} mentions ({r['pct']}%)"
        if r.get("example"):
            ex = r["example"][:80]
            line += f' — e.g. "{ex}"'
        region_lines.append(line)

    context_text = f"""
=== SEARCH QUERY: {query} ===

=== DEMAND SCORES ===
Overall: {score_row.get("overall_score","N/A")}/100  Verdict: {score_row.get("verdict","UNKNOWN")}
Pain: {score_row.get("pain_score",0)}  Buyer: {score_row.get("buyer_score",0)}  Competitor: {score_row.get("competitor_score",0)}  Timing: {score_row.get("timing_score",0)}  Validation: {score_row.get("validation_score",0)}  Expansion: {score_row.get("expansion_score",0)}

Why demand exists: {score_row.get("why_demand","Not available")}
Risk/gaps: {score_row.get("why_no_demand","Not available")}

Key evidence quotes (from scraped data):
{chr(10).join(f"  > {str(e)[:280]}" for e in key_ev_list[:5])}

=== SUB-AREA BREAKDOWN ({len(modules)} sub-areas) ===
{chr(10).join(module_lines)}

=== REGIONAL DEMAND ({len(regions)} regions) ===
{chr(10).join(region_lines) if region_lines else "  No regional data"}

=== ALL SCRAPED EVIDENCE ({len(all_items)} total items) ===
{"".join(evidence_sections)}
"""

    prompt = f"""You are a demand intelligence analyst. You ONLY answer using the scraped dataset below.

RULES (STRICT):
1. Use ONLY the data provided — never use external/general knowledge.
2. Cite specific post titles, sources, quotes, and numbers from the data.
3. If a question cannot be answered from the data, say what IS available and what is missing.
4. Be specific: name actual sources (reddit.com/r/SAP, statista.com, etc.), actual post titles, actual scores.
5. Do NOT give generic market advice. Every sentence must trace back to a data point.

USER QUESTION: "{question}"

SCRAPED DATASET:
{context_text}

Respond ONLY in this exact JSON (no markdown, no text outside):
{{
  "answer": "<3-6 sentences citing specific data: source names, post titles, exact numbers, quotes from content. Start with direct answer then cite evidence.>",
  "sources_cited": [
    {{"source_name": "<n>", "title": "<title from data>", "url": "<url from data>", "signal_type": "<signal>"}}
  ],
  "chart_type": "<none | bar | donut>",
  "chart_title": "<title if chart else empty>",
  "chart_data": [{{"label": "<l>", "value": <n>, "color": "<hex>"}}],
  "follow_up_suggestions": ["<data-grounded question>", "<data-grounded question>", "<data-grounded question>"]
}}

Chart rules:
- Region/geography question → chart_type="bar", use regional counts
- Sub-area/module question → chart_type="bar", use sub-area counts  
- Score/signal breakdown → chart_type="donut", use signal scores
- Otherwise → chart_type="none", chart_data=[]

Colors: #4f8ef7, #34c98e, #a78bfa, #f7a94f, #38bdf8, #fb923c, #f75f5f, #a3e635, #ec4899, #06b6d4"""

    # 7. Call Gemini
    try:
        gurl = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
        payload = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 2000}
        }).encode()
        req = urllib.request.Request(
            gurl, data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
        text = result["candidates"][0]["content"]["parts"][0]["text"].strip()
        if "```" in text:
            parts = text.split("```")
            text = parts[1].replace("json", "").strip() if len(parts) > 1 else parts[0]
        parsed = json.loads(text)
        if "sources_cited" not in parsed:
            parsed["sources_cited"] = []
        return parsed

    except Exception as e:
        print(f"[Chat] Gemini error: {e}")
        q_lower = question.lower()

        # Region fallback
        if any(w in q_lower for w in ["where", "region", "country", "location", "india", "usa", "uk", "germany"]):
            if regions:
                top = regions[0]
                second = f" {regions[1]['name']} is second with {regions[1]['pct']}%." if len(regions) > 1 else ""
                answer = (
                    f"Based on {len(all_items)} scraped items for '{query}': "
                    f"{top['name']} leads with {top['count']} mentions ({top['pct']}% of regional evidence).{second}"
                )
                if top.get("example"):
                    ex = top["example"][:100]
                    answer += f' Example: "{ex}"'
                return {
                    "answer": answer, "sources_cited": [],
                    "chart_type": "bar", "chart_title": "Regional Demand Distribution",
                    "chart_data": [{"label": r["name"], "value": r["count"],
                                    "color": {"USA":"#4f8ef7","India":"#f7a94f","UK":"#34c98e",
                                              "Germany":"#a78bfa","Europe":"#38bdf8"}.get(r["name"],"#888")}
                                   for r in regions[:6]],
                    "follow_up_suggestions": [f"What are the pain points in {top['name']}?",
                                              "Which sub-area has highest demand?", "What do buyers say?"]
                }

        # Module/sub-area fallback
        if any(w in q_lower for w in ["module", "sub-area", "area", "which", "fi", "mm", "sd", "abap", "btp", "basis", "ewm"]):
            if modules:
                top = modules[0]
                answer = (
                    f"Based on {len(all_items)} scraped items: {top['name']} has the strongest signal "
                    f"with {top['count']} mentions ({top['share']}% share, verdict: {top['verdict']}). "
                    f"{top.get('reason', '')}"
                )
                return {
                    "answer": answer,
                    "sources_cited": [{"source_name": s["source_name"], "title": s["title"],
                                       "url": s["url"], "signal_type": s["signal_type"]}
                                      for s in top.get("sources", [])[:3]],
                    "chart_type": "bar", "chart_title": "Sub-area Demand Strength",
                    "chart_data": [{"label": m["name"], "value": m["count"],
                                    "color": ["#4f8ef7","#34c98e","#a78bfa","#f7a94f","#38bdf8","#fb923c","#f75f5f","#a3e635"][i % 8]}
                                   for i, m in enumerate(modules[:8])],
                    "follow_up_suggestions": [f"Why does {top['name']} have high demand?",
                                              "Where is this demand geographically?", "What are the risks?"]
                }

        # Score fallback
        if any(w in q_lower for w in ["score", "signal", "pain", "buyer", "competitor", "timing"]):
            signals = {"Pain": score_row.get("pain_score",0), "Buyer": score_row.get("buyer_score",0),
                       "Competitor": score_row.get("competitor_score",0), "Timing": score_row.get("timing_score",0),
                       "Validation": score_row.get("validation_score",0), "Expansion": score_row.get("expansion_score",0)}
            top_sig = max(signals, key=lambda k: signals[k])
            answer = (
                f"From {len(all_items)} scraped items: overall score {score_row.get('overall_score','N/A')}/100 "
                f"({score_row.get('verdict','UNKNOWN')}). Strongest signal: {top_sig} at {signals[top_sig]}/100. "
                f"{score_row.get('why_demand', '')}"
            )
            return {
                "answer": answer, "sources_cited": [],
                "chart_type": "donut", "chart_title": "Signal Score Breakdown",
                "chart_data": [{"label": k, "value": int(v),
                                "color": ["#4f8ef7","#34c98e","#a78bfa","#f7a94f","#38bdf8","#fb923c"][i%6]}
                               for i, (k, v) in enumerate(signals.items()) if v > 0],
                "follow_up_suggestions": ["Which sub-area has most demand?", "Where is demand strongest?", "What are the risks?"]
            }

        # General fallback with real evidence
        ev_lines = [f'"{it["title"]}" (via {it["source_name"]})' for it in all_items[:4] if it.get("title") and len(it["title"]) > 15]
        answer = (
            f"Based on {len(all_items)} scraped items (score: {score_row.get('overall_score','N/A')}/100, "
            f"{score_row.get('verdict','UNKNOWN')}): {score_row.get('why_demand', '')} "
            + ("Evidence includes: " + "; ".join(ev_lines) + "." if ev_lines else "")
        )
        return {
            "answer": answer,
            "sources_cited": [{"source_name": it["source_name"], "title": it["title"],
                               "url": it["url"], "signal_type": it["signal_type"]}
                              for it in all_items[:4] if it.get("url")],
            "chart_type": "none", "chart_title": "", "chart_data": [],
            "follow_up_suggestions": ["Which sub-area has most demand?", "Where is demand highest?", "What are the risks?"]
        }


# ── Module Split helper ──────────────────────────────────────
# Splits already-scraped items into module buckets using domain_modules.json
# No new scraping — pure classification of existing data

def get_module_split(query: str, domain: str = "", sub_domain: str = "") -> dict:
    """
    Split all scraped items for a query into module buckets.
    Uses domain_modules.json keyword matching.
    Returns each module with its items, count, and signal breakdown.
    """
    query = resolve_query(query)
    conn = get_connection()
    cur  = dict_cursor(conn)
    p    = placeholder()

    # Resolve domain/sub_domain from DB if not provided
    if not domain:
        cur.execute(f"SELECT domain FROM demand_scores WHERE LOWER(query)=LOWER({p})", (query,))
        row = cur.fetchone()
        if row: domain = dict(row).get("domain", "") or ""

    if not sub_domain:
        cur.execute(
            f"SELECT sub_domain FROM scraped_items WHERE LOWER(query)=LOWER({p}) AND sub_domain != '' LIMIT 1",
            (query,)
        )
        row = cur.fetchone()
        if row: sub_domain = dict(row).get("sub_domain", "") or ""

    # Fetch all scraped items
    cur.execute(
        f"""SELECT id, title, content, signal_type, source_name, url,
                   published_at, score, metadata
            FROM scraped_items WHERE LOWER(query)=LOWER({p}) ORDER BY score DESC""",
        (query,)
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    if not rows:
        return {"query": query, "modules": [], "unmatched": [],
                "total_items": 0, "domain": domain, "sub_domain": sub_domain}

    # Load module config
    modules_cfg = get_modules_for_query(query, domain, sub_domain)

    if not modules_cfg:
        # No module config — return all items as "General" bucket
        return {
            "query": query, "domain": domain, "sub_domain": sub_domain,
            "modules": [{
                "name": sub_domain or domain,
                "emoji": "📌",
                "count": len(rows),
                "pct": 100, "share": 100, "verdict": "MEDIUM",
                "items": _format_items(rows[:20]),
            }],
            "unmatched": [],
            "total_items": len(rows),
        }

    # Split items into modules
    module_buckets = {mod["name"]: {
        "emoji":   mod["emoji"],
        "keywords": mod["keywords"],
        "items":   [],
    } for mod in modules_cfg}

    unmatched = []

    for row in rows:
        text    = ((row.get("title") or "") + " " + (row.get("content") or "")).lower()
        matched = False
        for mod in modules_cfg:
            for kw in mod["keywords"]:
                if kw in text:
                    module_buckets[mod["name"]]["items"].append(row)
                    matched = True
                    break
            if matched:
                break
        if not matched:
            unmatched.append(row)

    # Build result list (only modules that have items)
    filled = {name: data for name, data in module_buckets.items() if data["items"]}

    if not filled:
        return {
            "query": query, "domain": domain, "sub_domain": sub_domain,
            "modules": [], "unmatched": _format_items(unmatched[:10]),
            "total_items": len(rows),
        }

    max_count      = max(len(d["items"]) for d in filled.values())
    total_matched  = sum(len(d["items"]) for d in filled.values())

    result_modules = sorted([
        {
            "name":    name,
            "emoji":   data["emoji"],
            "count":   len(data["items"]),
            "pct":     round((len(data["items"]) / max_count) * 100),
            "share":   round((len(data["items"]) / max(total_matched, 1)) * 100),
            "verdict": (
                "HIGH"   if len(data["items"]) / max_count >= 0.6 else
                "MEDIUM" if len(data["items"]) / max_count >= 0.3 else
                "LOW"
            ),
            "items":   _format_items(data["items"][:15]),
            # Signal breakdown for this module
            "signals": _count_signals(data["items"]),
        }
        for name, data in filled.items()
    ], key=lambda x: x["count"], reverse=True)

    return {
        "query":         query,
        "domain":        domain,
        "sub_domain":    sub_domain,
        "modules":       result_modules,
        "unmatched":     _format_items(unmatched[:8]),
        "total_items":   len(rows),
        "total_matched": total_matched,
    }


def _format_items(rows: list) -> list:
    """Format DB rows into clean frontend-ready dicts."""
    out = []
    for row in rows:
        meta = row.get("metadata", "{}")
        if isinstance(meta, str):
            try:    meta = json.loads(meta)
            except: meta = {}
        out.append({
            "id":          row.get("id"),
            "title":       row.get("title", ""),
            "content":     (row.get("content") or "")[:200],
            "signal_type": row.get("signal_type", ""),
            "source_name": row.get("source_name", ""),
            "url":         row.get("url", ""),
            "published_at":row.get("published_at", ""),
            "score":       row.get("score", 0),
            "upvotes":     meta.get("upvotes", 0),
            "comments":    meta.get("comments", 0),
        })
    return out


def _count_signals(rows: list) -> dict:
    """Count items per signal type in a module bucket."""
    counts = {}
    for row in rows:
        sig = row.get("signal_type", "Other")
        counts[sig] = counts.get(sig, 0) + 1
    return counts


# ═══════════════════════════════════════════════════════════════════════════════
# OPEN SUB-AREA DISCOVERY
# Instead of matching against fixed pre-defined sub-areas,
# this reads ALL scraped content and asks AI to discover what people 
# actually talk about — finding demand areas we didn't know to look for.
# ═══════════════════════════════════════════════════════════════════════════════

def discover_sub_areas(query: str, api_key: str = "") -> dict:
    """
    Discovers demand sub-areas PURELY from scraped evidence — no predefined lists.
    
    Flow:
    1. Load ALL scraped items for this query from DB
    2. Extract raw text (titles + content snippets)
    3. Send to Gemini: "What sub-topics do people actually discuss here?"
    4. Gemini clusters the content and returns discovered sub-areas with scores
    5. Returns ranked sub-areas with evidence counts and example sources
    
    This finds demand that fixed keyword lists would NEVER catch.
    """
    query = resolve_query(query)
    api_key = api_key or GEMINI_API_KEY

    conn = get_connection()
    cur  = dict_cursor(conn)
    p    = placeholder()

    # ── Step 1: Load all scraped items ────────────────────────────────────────
    cur.execute(
        f"""SELECT title, content, url, source_name, signal_type, score
            FROM scraped_items WHERE LOWER(query)=LOWER({p})
            ORDER BY score DESC""",
        (query,)
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    if not rows:
        return {
            "query": query,
            "discovered_areas": [],
            "total_items": 0,
            "method": "no_data",
            "message": "No scraped data found. Run a search first."
        }

    # ── Step 2: Build a compact text corpus for AI ────────────────────────────
    # Group by signal type so AI sees the context
    by_signal = {}
    for row in rows:
        sig   = row.get("signal_type", "General") or "General"
        title = (row.get("title") or "").strip()
        snip  = (row.get("content") or "")[:200].strip()
        src   = (row.get("source_name") or "").strip()
        if sig not in by_signal:
            by_signal[sig] = []
        if title or snip:
            by_signal[sig].append(f"[{src}] {title}: {snip}")

    corpus_lines = []
    for sig, items in by_signal.items():
        corpus_lines.append(f"\n=== {sig} ({len(items)} items) ===")
        corpus_lines.extend(items[:25])   # max 25 per signal type

    corpus = "\n".join(corpus_lines)[:12000]   # cap at ~12k chars for Gemini

    # ── Step 3: Also do keyword-frequency analysis locally (no AI needed) ─────
    import re
    from collections import Counter

    all_text = " ".join(
        ((r.get("title") or "") + " " + (r.get("content") or ""))
        for r in rows
    ).lower()

    # Extract meaningful bigrams and trigrams (topic phrases)
    words = re.findall(r"\b[a-z][a-z0-9]{2,}\b", all_text)
    STOPWORDS = {
        "the","and","for","this","that","with","from","have","been","will",
        "are","was","were","has","had","but","not","they","their","there",
        "which","about","what","more","also","some","can","its","all","any",
        "one","our","into","out","use","how","get","when","than","your",
        "very","just","each","well","per","may","new","see","used","been",
        "would","could","should","com","www","http","https","reddit","post",
        "page","site","link","click","read","view","user","users",
        "demand","market","need","want","looking","ask","help","know"
    }
    keywords_clean = [w for w in words if w not in STOPWORDS and len(w) > 3]

    # Bigrams
    bigrams = [f"{keywords_clean[i]} {keywords_clean[i+1]}"
               for i in range(len(keywords_clean)-1)]
    top_bigrams = Counter(bigrams).most_common(40)
    top_words   = Counter(keywords_clean).most_common(60)

    freq_summary = "Top topic phrases: " + ", ".join(
        f"{phrase}({cnt})" for phrase, cnt in top_bigrams[:20]
    )

    # ── Step 4: Call Gemini to cluster and name the sub-areas ────────────────
    discovered_areas = []
    method = "keyword_frequency"   # fallback if Gemini fails

    if api_key:
        try:
            import urllib.request as _ur
            import json as _json

            prompt = f"""You are a demand analyst. I searched for: "{query}"

I scraped {len(rows)} real-world data points from Reddit, news, jobs, reviews, and market reports.

Here is the raw evidence:
{corpus}

Keyword frequency analysis: {freq_summary}

TASK: Discover what specific sub-topics or sub-areas actually have demand signals in this data.
Do NOT use any pre-defined list. Only report what you actually see in the evidence above.

For each sub-area you find, assess:
- How many items mention it (approximately)
- Signal strength: HIGH / MEDIUM / LOW
- Signal type: Pain (people struggling with it), Buyer (people paying for it), Growth (market expanding), Niche (small but growing)
- 1 sentence of evidence from the actual data

Return ONLY this JSON (no markdown, no backticks):
{{
  "discovered_areas": [
    {{
      "name": "specific sub-area name",
      "signal_strength": "HIGH|MEDIUM|LOW",
      "signal_type": "Pain|Buyer|Growth|Niche",
      "mention_count": 15,
      "evidence": "one sentence from the actual data proving this",
      "is_unexpected": true
    }}
  ],
  "summary": "1-2 sentence overview of what the data reveals about this domain"
}}

Rules:
- Only include sub-areas actually present in the evidence — no guesses
- is_unexpected = true if this sub-area would NOT be in a standard predefined list
- Order by signal_strength (HIGH first)
- Include 5-12 sub-areas minimum
- Be specific: not "marketing tools" but "AI-powered email personalization tools"
"""
            payload = _json.dumps({
                "model": "gemini-2.0-flash",
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.1,
                    "maxOutputTokens": 2000,
                    "responseMimeType": "application/json"
                }
            }).encode()

            req = _ur.Request(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with _ur.urlopen(req, timeout=30) as resp:
                raw = _json.loads(resp.read().decode())

            text = raw["candidates"][0]["content"]["parts"][0]["text"]
            text = text.strip().lstrip("```json").rstrip("```").strip()
            parsed = _json.loads(text)

            discovered_areas = parsed.get("discovered_areas", [])
            ai_summary        = parsed.get("summary", "")
            method = "gemini_discovery"

        except Exception as e:
            print(f"[Discover] Gemini error: {e} — falling back to keyword clustering")
            discovered_areas = []

    # ── Step 5: Keyword-frequency fallback if Gemini failed ──────────────────
    if not discovered_areas:
        # Cluster bigrams into candidate topics and score them
        for phrase, cnt in top_bigrams[:15]:
            if cnt < 2:
                continue
            strength = "HIGH" if cnt >= 10 else "MEDIUM" if cnt >= 5 else "LOW"
            # Find an example source
            evidence_ex = next(
                (f"Found in: [{r.get('source_name','')}] {(r.get('title') or '')[:80]}"
                 for r in rows
                 if phrase in ((r.get("title","") + " " + r.get("content","")).lower())),
                f"Mentioned {cnt} times across sources"
            )
            discovered_areas.append({
                "name":           phrase.title(),
                "signal_strength": strength,
                "signal_type":    "Pain",
                "mention_count":  cnt,
                "evidence":       evidence_ex,
                "is_unexpected":  True,
            })
        ai_summary = f"Keyword-frequency analysis of {len(rows)} scraped items."
        method = "keyword_frequency"

    # ── Step 6: Attach actual source examples to each area ───────────────────
    for area in discovered_areas:
        area_name  = area["name"].lower()
        kw_tokens  = re.findall(r"\b[a-z]{3,}\b", area_name)
        area_sources = []
        seen_urls    = set()

        for row in rows:
            text = ((row.get("title") or "") + " " + (row.get("content") or "")).lower()
            if any(tok in text for tok in kw_tokens):
                url = (row.get("url") or "").strip()
                if url and url not in seen_urls and len(area_sources) < 3:
                    seen_urls.add(url)
                    area_sources.append({
                        "url":         url,
                        "source_name": row.get("source_name", ""),
                        "title":       (row.get("title") or "")[:80],
                        "signal_type": row.get("signal_type", ""),
                    })
        area["sources"] = area_sources

    return {
        "query":            query,
        "discovered_areas": discovered_areas,
        "total_items":      len(rows),
        "method":           method,
        "summary":          ai_summary if api_key else f"Analysed {len(rows)} items using keyword frequency.",
        "note":             "These sub-areas were discovered from real data — not from a predefined list."
    }

class Handler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        try:    data = json.loads(self.rfile.read(length))
        except: self._respond(400, {"error": "invalid JSON"}); return

        if self.path == "/api/search":
            query   = data.get("query", "").strip().lower()
            api_key = data.get("gemini_api_key", GEMINI_API_KEY)
            force   = data.get("force_refresh", False)

            if not query:
                self._respond(400, {"error": "query required"}); return

            # Cache check (24 hr)
            if not force:
                cached = get_demand_score(query)
                if cached:
                    evidence = get_scraped_items(query, limit=200)
                    from classifier import classify
                    cls     = classify(query, api_key or None)
                    domains = cls.get("domains", {})
                    cached_domain = cached.get("domain","")
                    dom_d = domains.get(cached_domain, {})
                    # Recover sub_domain from scraped_items (not stored in demand_scores)
                    cached_sub = ""
                    try:
                        conn_tmp = get_connection()
                        cur_tmp  = dict_cursor(conn_tmp)
                        cur_tmp.execute(
                            f"SELECT sub_domain FROM scraped_items WHERE LOWER(query)=LOWER({placeholder()}) AND sub_domain != '' LIMIT 1",
                            (query,)
                        )
                        row_tmp = cur_tmp.fetchone()
                        if row_tmp:
                            cached_sub = dict(row_tmp).get("sub_domain", "")
                        conn_tmp.close()
                    except Exception:
                        pass
                    # Also recover actual collected count from scraped_items
                    try:
                        conn_tmp2 = get_connection()
                        cur_tmp2  = dict_cursor(conn_tmp2)
                        cur_tmp2.execute(
                            f"SELECT COUNT(*) AS cnt FROM scraped_items WHERE LOWER(query)=LOWER({placeholder()})",
                            (query,)
                        )
                        cached_count = dict(cur_tmp2.fetchone()).get("cnt", 0)
                        conn_tmp2.close()
                    except Exception:
                        cached_count = 0
                    cached_sr = {"cached": cached_count} if cached_count else {}
                    result  = build_result(
                        query, cached_domain, cached_sub,
                        dom_d, domains, cached, evidence, cached_sr
                    )
                    jid = str(uuid.uuid4())
                    with _lock:
                        _jobs[jid] = {
                            "status": "complete", "stage": "done",
                            "stage_index": 3, "query": query,
                            "message": "Loaded from cache (< 24h old)",
                            "result": result, "scraper_results": {},
                            "cached": True, "progress_pct": 100
                        }
                    self._respond(200, {"job_id": jid, "cached": True})
                    return

            jid = str(uuid.uuid4())
            with _lock:
                _jobs[jid] = {
                    "status": "running", "stage": "classify",
                    "stage_index": 0, "query": query,
                    "message": "Starting…", "scraper_results": {},
                    "result": None, "cached": False, "progress_pct": 0
                }

            threading.Thread(
                target=run_pipeline,
                args=(jid, query, api_key or None),
                daemon=True
            ).start()

            self._respond(202, {"job_id": jid, "cached": False})
        elif self.path == "/api/chat":
            query    = data.get("query", "").strip().lower()
            question = data.get("question", "").strip()
            api_key  = data.get("gemini_api_key", GEMINI_API_KEY)
            if not query or not question:
                self._respond(400, {"error": "query and question required"}); return
            result = answer_chat(query, question, api_key or GEMINI_API_KEY)
            self._respond(200, result)

        elif path.startswith("/api/discover/"):
            raw   = path.replace("/api/discover/", "")
            query = urllib.parse.unquote(raw.split("?")[0]).strip().lower()
            result = discover_sub_areas(query, GEMINI_API_KEY)
            self._respond(200, result)

        else:
            self._respond(404, {"error": "not found"})

    def do_GET(self):
        path = self.path.split("?")[0]

        if path == "/api/health":
            self._respond(200, {
                "status": "ok",
                "gemini_configured": bool(GEMINI_API_KEY)
            })

        elif path.startswith("/api/search/status/"):
            jid = urllib.parse.unquote(
                path.replace("/api/search/status/", ""))
            with _lock: job = dict(_jobs.get(jid, {}))
            if not job:
                self._respond(404, {"error": "job not found"}); return
            self._respond(200, {
                "job_id":          jid,
                "status":          job.get("status"),
                "stage":           job.get("stage"),
                "stage_index":     job.get("stage_index", 0),
                "message":         job.get("message", ""),
                "domain":          job.get("domain", ""),
                "scraper_results": job.get("scraper_results", {}),
                "progress_pct":    job.get("progress_pct", 0),
                "error":           job.get("error"),
                "cached":          job.get("cached", False),
                "is_done":         job.get("status") in ["complete", "error"],
            })

        elif path.startswith("/api/search/result/"):
            jid = urllib.parse.unquote(
                path.replace("/api/search/result/", ""))
            with _lock: job = dict(_jobs.get(jid, {}))
            if not job:
                self._respond(404, {"error": "job not found"}); return
            self._respond(200, {
                "job_id": jid,
                "status": job.get("status"),
                "result": job.get("result"),
                "error":  job.get("error"),
                "cached": job.get("cached", False),
            })

        elif path.startswith("/api/timeline/"):
            query = urllib.parse.unquote(path.replace("/api/timeline/", "")).strip().lower()
            self._respond(200, get_timeline_data(query))

        elif path.startswith("/api/locations/"):
            query = urllib.parse.unquote(path.replace("/api/locations/", "")).strip().lower()
            self._respond(200, get_location_data(query))

        elif path.startswith("/api/modules/"):
            raw   = path.replace("/api/modules/", "")
            query = urllib.parse.unquote(raw.split("?")[0]).strip().lower()
            qs    = urllib.parse.parse_qs(self.path.split("?")[1]) if "?" in self.path else {}
            dom   = qs.get("domain", [""])[0]
            sub   = qs.get("sub",    [""])[0]
            self._respond(200, get_module_breakdown(query, dom, sub))

        elif path.startswith("/api/module-split/"):
            raw   = path.replace("/api/module-split/", "")
            query = urllib.parse.unquote(raw.split("?")[0]).strip().lower()
            qs    = urllib.parse.parse_qs(self.path.split("?")[1]) if "?" in self.path else {}
            dom   = qs.get("domain", [""])[0]
            sub   = qs.get("sub",    [""])[0]
            self._respond(200, get_module_split(query, dom, sub))

        elif path == "/api/clear-cache":
            # Clear all cached scores and scraped items — forces fresh analysis on next search
            try:
                conn = get_connection()
                cur  = conn.cursor()
                p    = placeholder()
                qs   = urllib.parse.parse_qs(self.path.split("?")[1]) if "?" in self.path else {}
                query_param = qs.get("query", [""])[0].strip().lower()

                if query_param:
                    # Clear cache for a specific query only
                    cur.execute(f"DELETE FROM demand_scores  WHERE LOWER(query)=LOWER({p})", (query_param,))
                    cur.execute(f"DELETE FROM scraped_items  WHERE LOWER(query)=LOWER({p})", (query_param,))
                    cur.execute(f"DELETE FROM trend_data     WHERE LOWER(query)=LOWER({p})", (query_param,))
                    cur.execute(f"DELETE FROM company_financials WHERE LOWER(query)=LOWER({p})", (query_param,))
                    cur.execute(f"DELETE FROM document_insights  WHERE LOWER(query)=LOWER({p})", (query_param,))
                    conn.commit()
                    conn.close()
                    self._respond(200, {
                        "status": "cleared",
                        "query":  query_param,
                        "message": f"Cache cleared for query: '{query_param}'"
                    })
                else:
                    # Clear ALL cache
                    cur.execute("DELETE FROM demand_scores")
                    cur.execute("DELETE FROM scraped_items")
                    cur.execute("DELETE FROM trend_data")
                    cur.execute("DELETE FROM company_financials")
                    cur.execute("DELETE FROM document_insights")
                    conn.commit()
                    conn.close()
                    self._respond(200, {
                        "status":  "cleared",
                        "message": "Full cache cleared — all queries will be re-analysed on next search"
                    })
            except Exception as e:
                self._respond(500, {"error": str(e)})

        else:
            self._respond(404, {"error": "not found"})

    def _respond(self, code, data):
        body = json.dumps(data, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type",   "application/json")
        self.send_header("Content-Length", len(body))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, PUT, DELETE")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With")
        self.send_header("Access-Control-Max-Age",       "86400")

    def log_message(self, fmt, *args):
        print(f"[{self.address_string()}] {fmt % args}")


if __name__ == "__main__":
    init_db()
    print(f"[Server] http://localhost:{PORT}")
    print(f"[Server] Gemini: {'✓ configured' if GEMINI_API_KEY else '✗ not set'}")
    print(f"[Server] Mode: ALL sources scraped in parallel (up to 40 threads)")
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
