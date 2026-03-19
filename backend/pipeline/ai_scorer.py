"""
AI Scoring Engine
Takes all scraped data for a query and uses Gemini to:
1. Score demand strength (0-100) per signal
2. Generate "Why is there demand" explanation
3. Generate "Why is there NO demand" if score is low
4. Identify key evidence points
"""

import json
import os
import urllib.request
from datetime import datetime
from database import (get_scraped_items, get_financials, get_document_insights,
                      get_trend_data, upsert_demand_score)


GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")


def call_gemini(prompt, api_key):
    """Call Gemini API and return text response."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"

    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 2000
        }
    }).encode("utf-8")

    try:
        req = urllib.request.Request(url, data=payload,
                                     headers={"Content-Type": "application/json"},
                                     method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
        return result["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        print(f"[AI] Gemini error: {e}")
        return None


def build_evidence_summary(query):
    """Compile all scraped data into a structured evidence summary."""

    items = get_scraped_items(query, limit=50)
    financials = get_financials(query)
    documents = get_document_insights(query)
    trends = get_trend_data(query)

    summary = {
        "query": query,
        "total_data_points": len(items),
        "signals": {},
        "financial_evidence": [],
        "trend_evidence": {},
        "document_evidence": []
    }

    # Group scraped items by signal type
    for item in items:
        signal = item.get("signal_type", "Unknown")
        if signal not in summary["signals"]:
            summary["signals"][signal] = []
        summary["signals"][signal].append({
            "source": item.get("source_name", ""),
            "title": item.get("title", "")[:100],
            "content": item.get("content", "")[:300],
            "score": item.get("score", 0)
        })

    # Financial evidence
    for fin in financials[:3]:
        summary["financial_evidence"].append({
            "company": fin.get("company_name", ""),
            "market_cap": fin.get("market_cap", ""),
            "revenue_trend": fin.get("revenue_trend", []),
            "pros": json.loads(fin.get("pros", "[]"))[:3] if isinstance(fin.get("pros"), str) else fin.get("pros", [])[:3],
            "cons": json.loads(fin.get("cons", "[]"))[:3] if isinstance(fin.get("cons"), str) else fin.get("cons", [])[:3]
        })

    # Trend evidence
    for trend in trends[:2]:
        summary["trend_evidence"] = {
            "current_interest": trend.get("current_interest", 0),
            "peak_interest": trend.get("peak_interest", 0),
            "trend_direction": trend.get("trend_direction", "unknown"),
            "related_queries": trend.get("related_queries", {})
        }

    # Document evidence (concalls / annual reports)
    for doc in documents[:3]:
        demand_mentions = doc.get("demand_mentions", [])
        if isinstance(demand_mentions, str):
            try:
                demand_mentions = json.loads(demand_mentions)
            except Exception:
                demand_mentions = []

        growth_signals = doc.get("growth_signals", [])
        if isinstance(growth_signals, str):
            try:
                growth_signals = json.loads(growth_signals)
            except Exception:
                growth_signals = []

        summary["document_evidence"].append({
            "company": doc.get("company_name", ""),
            "type": doc.get("doc_type", ""),
            "year": doc.get("year", ""),
            "quarter": doc.get("quarter", ""),
            "demand_mentions": demand_mentions[:5],
            "growth_signals": growth_signals[:3]
        })

    return summary


def build_compact_evidence(evidence):
    """
    Build a compact evidence summary guaranteed to include ALL signal types.
    The full evidence JSON can be 20000+ chars. If we truncate it, Pain Signal
    (which has the most items) fills the limit and all other signals get cut off.
    Gemini then scores Pain=high and everything else=0.
    Fix: limit to 5 examples per signal type so all signals fit within token budget.
    """
    compact = {
        "query":             evidence["query"],
        "total_data_points": evidence["total_data_points"],
        "signals":           {}
    }
    for sig, items in evidence["signals"].items():
        compact["signals"][sig] = {
            "count":    len(items),
            "examples": items[:5]   # max 5 per signal type — enough for scoring
        }
    compact["trend_evidence"]    = evidence.get("trend_evidence",    {})
    compact["financial_evidence"]= evidence.get("financial_evidence", [])[:2]
    compact["document_evidence"] = evidence.get("document_evidence",  [])[:2]
    return compact


def score_demand_with_ai(query, domain, api_key=None):
    """Use Gemini to analyze all evidence and generate demand score + explanation."""

    api_key = api_key or GEMINI_API_KEY

    evidence = build_evidence_summary(query)

    if evidence["total_data_points"] == 0:
        print(f"[AI] No data found for '{query}' — cannot score")
        return None

    # Build compact evidence — all signal types visible, fits within token limit
    compact = build_compact_evidence(evidence)
    print(f"[AI] Evidence: {len(evidence['signals'])} signal types, "
          f"{evidence['total_data_points']} items → compact={len(json.dumps(compact))} chars")

    # Build prompt for Gemini
    prompt = f"""You are a global demand analyst. Analyze the following evidence collected for the query: "{query}"

EVIDENCE COLLECTED:
{json.dumps(compact, indent=2)}

Based on this evidence, provide a demand analysis in ONLY valid JSON format (no markdown, no explanation outside JSON):

{{
  "overall_score": <0-100>,
  "signal_scores": {{
    "pain_score": <0-100>,
    "buyer_score": <0-100>,
    "competitor_score": <0-100>,
    "timing_score": <0-100>,
    "validation_score": <0-100>,
    "expansion_score": <0-100>
  }},
  "verdict": "<HIGH / MEDIUM / LOW / NO DEMAND>",
  "why_demand": "<2-3 sentence explanation of WHY there IS demand, citing specific evidence>",
  "why_no_demand": "<2-3 sentence explanation of WHY there might NOT be demand or what risks exist>",
  "key_evidence": [
    "<specific data point 1>",
    "<specific data point 2>",
    "<specific data point 3>",
    "<specific data point 4>",
    "<specific data point 5>"
  ],
  "demand_signals_found": ["<list of strongest signals found>"],
  "missing_signals": ["<list of signals with no evidence>"]
}}

Scoring guide:
- 80-100: Strong clear demand with multiple confirming signals
- 60-79: Good demand with some strong signals
- 40-59: Moderate demand, mixed signals
- 20-39: Weak demand, limited signals
- 0-19: No clear demand evidence found

IMPORTANT RULES FOR SIGNAL SCORING:
- Each signal has a "count" field showing total items collected — use this for scoring
- If a signal has count > 0, its score MUST be > 0
- Pain Signal count > 10 = pain_score at least 60
- Timing Signal count > 5 = timing_score at least 50
- Buyer Signal count > 0 = buyer_score at least 30
- Competitor Signal count > 0 = competitor_score at least 30
- Validation Signal count > 0 = validation_score at least 40
- Market Data count > 0 = expansion_score at least 40
- Never return 0 for a signal that has evidence"""

    if not api_key:
        # Fallback: rule-based scoring without AI
        return rule_based_score(query, domain, evidence)

    response = call_gemini(prompt, api_key)

    if not response:
        return rule_based_score(query, domain, evidence)

    try:
        # Clean response
        text = response.strip()
        if "```" in text:
            text = text.split("```")[1].replace("json", "").strip()

        scored = json.loads(text)

        # Save to database
        upsert_demand_score(
            query=query,
            domain=domain,
            overall_score=scored.get("overall_score", 0),
            pain_score=scored.get("signal_scores", {}).get("pain_score", 0),
            buyer_score=scored.get("signal_scores", {}).get("buyer_score", 0),
            competitor_score=scored.get("signal_scores", {}).get("competitor_score", 0),
            timing_score=scored.get("signal_scores", {}).get("timing_score", 0),
            validation_score=scored.get("signal_scores", {}).get("validation_score", 0),
            expansion_score=scored.get("signal_scores", {}).get("expansion_score", 0),
            verdict=scored.get("verdict", "UNKNOWN"),
            why_demand=scored.get("why_demand", ""),
            why_no_demand=scored.get("why_no_demand", ""),
            key_evidence=scored.get("key_evidence", [])
        )

        print(f"[AI] '{query}' scored: {scored.get('overall_score')}/100 — {scored.get('verdict')}")
        return scored

    except Exception as e:
        print(f"[AI] Parse error: {e}")
        return rule_based_score(query, domain, evidence)


def rule_based_score(query, domain, evidence):
    """Fallback scoring without AI — purely rule-based."""

    total_items = evidence["total_data_points"]
    signals_found = len(evidence["signals"])
    has_trends = bool(evidence["trend_evidence"])
    has_financials = bool(evidence["financial_evidence"])
    has_docs = bool(evidence["document_evidence"])

    # Base score from data volume
    base_score = min(40, total_items * 2)
    signal_bonus = signals_found * 8
    trend_bonus = 10 if has_trends else 0
    financial_bonus = 10 if has_financials else 0
    doc_bonus = 10 if has_docs else 0

    overall = min(100, base_score + signal_bonus + trend_bonus + financial_bonus + doc_bonus)

    if overall >= 70:
        verdict = "HIGH"
    elif overall >= 45:
        verdict = "MEDIUM"
    elif overall >= 20:
        verdict = "LOW"
    else:
        verdict = "NO DEMAND"

    why_demand = (
        f"Evidence collected: {total_items} data points across {signals_found} signal types. "
        f"{'Google Trends data available. ' if has_trends else ''}"
        f"{'Financial data from Screener.in available. ' if has_financials else ''}"
        f"{'Annual reports and concall transcripts analyzed.' if has_docs else ''}"
    )

    why_no_demand = (
        "Insufficient evidence to confirm strong demand. "
        "Consider adding Gemini API key for deeper AI-powered analysis."
        if overall < 50 else
        "Some risk signals detected. Monitor competition and market timing."
    )

    signals = evidence["signals"]

    result = {
        "overall_score": overall,
        "signal_scores": {
            "pain_score":       min(100, len(signals.get("Pain Signal",       [])) * 12),
            "buyer_score":      min(100, len(signals.get("Buyer Signal",      [])) * 20),
            "competitor_score": min(100, len(signals.get("Competitor Signal", [])) * 15),
            "timing_score":     min(100, max(
                                    len(signals.get("Timing Signal", [])) * 10,
                                    60 if has_trends else 0
                                )),
            "validation_score": min(100, len(signals.get("Validation Signal", [])) * 20),
            "expansion_score":  min(100, max(
                                    len(signals.get("Market Data", [])) * 10,
                                    40 if has_financials else 20
                                )),
        },
        "verdict": verdict,
        "why_demand": why_demand,
        "why_no_demand": why_no_demand,
        "key_evidence": [
            f"{total_items} data points collected",
            f"{signals_found} demand signals identified",
            f"Trend direction: {evidence.get('trend_evidence', {}).get('trend_direction', 'unknown')}",
            f"Financial data: {'available' if has_financials else 'not found'}",
            f"Concall/annual report data: {'available' if has_docs else 'not found'}"
        ]
    }

    upsert_demand_score(
        query=query, domain=domain,
        overall_score=overall,
        pain_score=result["signal_scores"]["pain_score"],
        buyer_score=result["signal_scores"]["buyer_score"],
        competitor_score=result["signal_scores"]["competitor_score"],
        timing_score=result["signal_scores"]["timing_score"],
        validation_score=result["signal_scores"]["validation_score"],
        expansion_score=result["signal_scores"]["expansion_score"],
        verdict=verdict,
        why_demand=why_demand,
        why_no_demand=why_no_demand,
        key_evidence=result["key_evidence"]
    )

    return result


if __name__ == "__main__":
    from database import init_db
    init_db()
    result = score_demand_with_ai("SAP ERP", "Technology")
    print(json.dumps(result, indent=2))
