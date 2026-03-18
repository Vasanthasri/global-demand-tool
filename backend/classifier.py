"""
Domain Classifier Engine
Step 1: Keyword-based fast matching
Step 2: Gemini API fallback for complex/ambiguous prompts
"""

import re
import json
import os
from collections import defaultdict
from typing import Optional
import urllib.request
import urllib.parse

from domain_map import DOMAIN_MAP, SIGNAL_DESCRIPTIONS


# ─────────────────────────────────────────
# STEP 1: Keyword Matcher
# ─────────────────────────────────────────

def normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return text

def extract_keywords(prompt: str) -> list[str]:
    return normalize(prompt).split()

def keyword_match(prompt: str) -> dict:
    tokens = set(extract_keywords(prompt))
    prompt_lower = normalize(prompt)

    domain_scores = defaultdict(float)
    matched_domains = {}

    for domain, data in DOMAIN_MAP.items():
        score = 0
        matched_kw = []

        # Single keyword match
        for kw in data["keywords"]:
            kw_norm = normalize(kw)
            if kw_norm in prompt_lower:
                weight = 2.0 if len(kw.split()) > 1 else 1.0  # multi-word = higher weight
                score += weight
                matched_kw.append(kw)

        if score > 0:
            domain_scores[domain] = score
            matched_domains[domain] = matched_kw

    if not domain_scores:
        return {}

    # Sort by score, return top matches
    sorted_domains = sorted(domain_scores.items(), key=lambda x: x[1], reverse=True)

    # Confidence threshold: only return domains with score >= 30% of top score
    top_score = sorted_domains[0][1]
    threshold = top_score * 0.3

    result = {}
    for domain, score in sorted_domains:
        if score >= threshold:
            confidence = min(100, round((score / top_score) * 100))
            result[domain] = {
                "confidence": confidence,
                "matched_keywords": matched_domains[domain][:5],
                "sub_domains": get_sub_domains(domain, prompt_lower)
            }

    return result


def get_sub_domains(domain: str, prompt_lower: str) -> list[str]:
    matched = []
    for sub, data in DOMAIN_MAP[domain]["sub_domains"].items():
        for kw in data["keywords"]:
            if normalize(kw) in prompt_lower:
                matched.append(sub)
                break
    return matched if matched else list(DOMAIN_MAP[domain]["sub_domains"].keys())[:2]


# ─────────────────────────────────────────
# STEP 2: Gemini Fallback
# ─────────────────────────────────────────

def gemini_classify(prompt: str, api_key: str) -> dict:
    """Call Gemini API when keyword matching has low confidence."""

    domain_names = list(DOMAIN_MAP.keys())

    system_prompt = f"""You are a demand analysis classifier. Given a user query, identify which domains it belongs to.

Available domains: {json.dumps(domain_names)}

Respond ONLY with a valid JSON object like this example:
{{
  "domains": [
    {{
      "name": "Technology",
      "sub_domains": ["Artificial Intelligence", "Cloud Computing"],
      "confidence": 95,
      "reasoning": "Query is about AI tools"
    }}
  ],
  "intent": "Market demand research",
  "geography": "global",
  "time_sensitivity": "current"
}}

No explanation, no markdown, just the JSON object."""

    payload = json.dumps({
        "contents": [
            {
                "parts": [
                    {"text": f"{system_prompt}\n\nUser query: {prompt}"}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 1000
        }
    }).encode("utf-8")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"

    try:
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode())

        text = result["candidates"][0]["content"]["parts"][0]["text"]
        text = text.strip().lstrip("```json").rstrip("```").strip()
        parsed = json.loads(text)

        # Convert to our format
        domains = {}
        for d in parsed.get("domains", []):
            name = d["name"]
            if name in DOMAIN_MAP:
                domains[name] = {
                    "confidence": d.get("confidence", 80),
                    "matched_keywords": [],
                    "sub_domains": d.get("sub_domains", []),
                    "reasoning": d.get("reasoning", ""),
                    "source": "gemini"
                }

        return {
            "domains": domains,
            "intent": parsed.get("intent", ""),
            "geography": parsed.get("geography", "global"),
            "time_sensitivity": parsed.get("time_sensitivity", "current")
        }

    except Exception as e:
        return {"error": str(e), "domains": {}}


# ─────────────────────────────────────────
# STEP 3: Source Resolver
# ─────────────────────────────────────────

def resolve_sources(domain: str, sub_domains: list[str]) -> dict:
    sources = defaultdict(set)

    for sub in sub_domains:
        if sub in DOMAIN_MAP[domain]["sub_domains"]:
            sub_data = DOMAIN_MAP[domain]["sub_domains"][sub]
            for signal, urls in sub_data.get("sources", {}).items():
                for url in urls:
                    sources[signal].add(url)

    return {signal: list(urls) for signal, urls in sources.items()}


# ─────────────────────────────────────────
# STEP 4: Main Classify Function
# ─────────────────────────────────────────

def classify(prompt: str, gemini_api_key: Optional[str] = None) -> dict:
    """
    Main entry point. Returns full classification result.
    1. Try keyword matching
    2. If low confidence or no match → use Gemini
    """

    keyword_result = keyword_match(prompt)

    # Determine if we need Gemini fallback
    needs_gemini = False
    top_confidence = 0

    if not keyword_result:
        needs_gemini = True
    else:
        top_confidence = max(v["confidence"] for v in keyword_result.values())
        if top_confidence < 40:
            needs_gemini = True

    gemini_meta = {}
    source = "keyword_match"

    if needs_gemini and gemini_api_key:
        gemini_result = gemini_classify(prompt, gemini_api_key)
        if "domains" in gemini_result and gemini_result["domains"]:
            keyword_result = gemini_result["domains"]
            gemini_meta = {
                "intent": gemini_result.get("intent", ""),
                "geography": gemini_result.get("geography", "global"),
                "time_sensitivity": gemini_result.get("time_sensitivity", "current")
            }
            source = "gemini_fallback"

    # Build final output
    classified_domains = {}
    for domain, data in keyword_result.items():
        sub_domains = data.get("sub_domains", [])
        sources = resolve_sources(domain, sub_domains)

        classified_domains[domain] = {
            "confidence": data["confidence"],
            "sub_domains": sub_domains,
            "matched_keywords": data.get("matched_keywords", []),
            "sources_by_signal": sources,
            "all_signals": list(sources.keys())
        }

    return {
        "prompt": prompt,
        "classification_source": source,
        "domains": classified_domains,
        "meta": gemini_meta,
        "signal_descriptions": {
            k: v for k, v in SIGNAL_DESCRIPTIONS.items()
            if any(k in d["all_signals"] for d in classified_domains.values())
        }
    }


# ─────────────────────────────────────────
# CLI Test
# ─────────────────────────────────────────

if __name__ == "__main__":
    import sys

    prompt = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "What is the demand for AI tools in healthcare?"
    api_key = os.environ.get("GEMINI_API_KEY")

    result = classify(prompt, api_key)

    print(json.dumps(result, indent=2))
