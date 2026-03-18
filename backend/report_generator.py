"""
Report Generator
Converts classifier output → readable dashboard report (JSON for frontend)
"""

import json
from datetime import datetime
from typing import Optional
from classifier import classify


def generate_report(prompt: str, gemini_api_key: Optional[str] = None) -> dict:
    """Generate a full readable demand report from a user prompt."""

    result = classify(prompt, gemini_api_key)

    if not result["domains"]:
        return {
            "status": "no_match",
            "prompt": prompt,
            "message": "Could not identify a domain for this query. Try being more specific.",
            "timestamp": datetime.utcnow().isoformat()
        }

    # Build domain sections
    domain_reports = []

    for domain_name, domain_data in result["domains"].items():
        confidence = domain_data["confidence"]
        sub_domains = domain_data["sub_domains"]
        sources_by_signal = domain_data["sources_by_signal"]

        # Build signal sections
        signal_sections = []
        for signal, urls in sources_by_signal.items():
            signal_sections.append({
                "signal_name": signal,
                "description": result["signal_descriptions"].get(
                    signal, "Relevant demand indicators for this signal."
                ),
                "sources": [
                    {
                        "url": url,
                        "display_name": url.split("/")[0].replace("www.", ""),
                        "full_url": f"https://{url}" if not url.startswith("http") else url
                    }
                    for url in urls
                ],
                "source_count": len(urls)
            })

        # Confidence label
        if confidence >= 80:
            confidence_label = "High"
            confidence_color = "green"
        elif confidence >= 50:
            confidence_label = "Medium"
            confidence_color = "amber"
        else:
            confidence_label = "Low"
            confidence_color = "red"

        domain_reports.append({
            "domain": domain_name,
            "confidence": confidence,
            "confidence_label": confidence_label,
            "confidence_color": confidence_color,
            "sub_domains": sub_domains,
            "matched_keywords": domain_data.get("matched_keywords", []),
            "total_sources": sum(len(v) for v in sources_by_signal.values()),
            "signals": signal_sections,
            "signal_count": len(signal_sections)
        })

    # Sort by confidence
    domain_reports.sort(key=lambda x: x["confidence"], reverse=True)

    # Summary stats
    all_sources = []
    for d in domain_reports:
        for sig in d["signals"]:
            all_sources.extend(sig["sources"])

    unique_sources = list({s["display_name"] for s in all_sources})

    return {
        "status": "success",
        "timestamp": datetime.utcnow().isoformat(),
        "prompt": prompt,
        "classification_source": result["classification_source"],
        "summary": {
            "total_domains": len(domain_reports),
            "total_sub_domains": sum(len(d["sub_domains"]) for d in domain_reports),
            "total_signals": sum(d["signal_count"] for d in domain_reports),
            "total_unique_sources": len(unique_sources),
            "top_domain": domain_reports[0]["domain"] if domain_reports else None,
            "top_confidence": domain_reports[0]["confidence"] if domain_reports else 0,
            "geography": result["meta"].get("geography", "global"),
            "time_sensitivity": result["meta"].get("time_sensitivity", "current"),
            "intent": result["meta"].get("intent", "Demand analysis")
        },
        "domains": domain_reports
    }


if __name__ == "__main__":
    import sys
    import os

    prompt = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "demand for AI tools in healthcare"
    api_key = os.environ.get("GEMINI_API_KEY")

    report = generate_report(prompt, api_key)
    print(json.dumps(report, indent=2))
