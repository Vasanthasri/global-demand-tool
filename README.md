# 🌐 Global Demand Analysis Tool

## What This Does
Type any topic → Get a full demand report showing:
- Which domains it belongs to (with confidence scores)
- What demand signals exist (Pain, Buyer, Competitor, Timing, etc.)
- Exactly which websites/sources to scrape for each signal

## Architecture
```
User Prompt
    ↓
Keyword Matcher (fast, no API cost)
    ↓ (if low confidence)
Gemini API Fallback (smarter classification)
    ↓
Domain + Sub-domain Classifier
    ↓
Signal Mapper (Pain / Buyer / Deal / Competitor / etc.)
    ↓
Source Resolver (500+ websites mapped to signals)
    ↓
Readable Report (JSON for dashboard)
```

---

## Setup & Run

### 1. Backend (Python)
```bash
cd backend

# Optional: set your Gemini API key
export GEMINI_API_KEY="your_key_here"

# Run the server
python server.py
# Server starts at http://localhost:8000
```

### 2. Frontend (React + Vite)
```bash
cd frontend

npm install
npm run dev
# Opens at http://localhost:3000
```

---

## Files Explained

### Backend
| File | Purpose |
|------|---------|
| `domain_map.py` | All 17 domains, sub-domains, keywords, and sources |
| `classifier.py` | Step 1: keyword match → Step 2: Gemini fallback |
| `report_generator.py` | Converts classifier output → readable report JSON |
| `server.py` | HTTP API server (POST /api/analyze) |

### Frontend
| File | Purpose |
|------|---------|
| `src/App.jsx` | Complete React dashboard UI |
| `src/main.jsx` | React entry point |
| `index.html` | HTML entry point |
| `vite.config.js` | Vite config with API proxy |

---

## API Usage

### POST /api/analyze
```json
Request:
{
  "prompt": "demand for AI tools in healthcare",
  "gemini_api_key": "AIza..."  // optional
}

Response:
{
  "status": "success",
  "summary": {
    "total_domains": 2,
    "total_signals": 8,
    "total_unique_sources": 24,
    "top_domain": "Health & Life Sciences",
    "top_confidence": 100
  },
  "domains": [
    {
      "domain": "Health & Life Sciences",
      "confidence": 100,
      "confidence_label": "High",
      "sub_domains": ["Digital Health & Telemedicine"],
      "signals": [
        {
          "signal_name": "Pain Signal",
          "description": "...",
          "sources": [{ "url": "...", "full_url": "..." }]
        }
      ]
    }
  ]
}
```

---

## CLI Testing (No Frontend Needed)
```bash
cd backend

# Test classifier directly
python classifier.py "electric vehicle charging demand in India"

# Test full report
python report_generator.py "fintech startup market in Southeast Asia"

# With Gemini fallback
GEMINI_API_KEY="your_key" python classifier.py "circular economy trends"
```

---

## Domains Covered (17)
1. Technology (AI, Cloud, Cybersecurity, Web Dev, SAP, Blockchain, IoT...)
2. Health & Life Sciences (Digital Health, Pharma, Mental Health, Biotech...)
3. Finance & Economy (Fintech, Banking, Investment...)
4. Education (EdTech, Higher Education...)
5. Retail & Consumer Goods (E-Commerce, FMCG, Luxury...)
6. Media & Entertainment (Gaming, Streaming, Music...)
7. Transportation & Mobility (EV, Logistics...)
8. Environment & Sustainability (Renewables, ESG...)
9. Agriculture & Food Tech (AgTech, Alt Proteins...)
10. Marketing & Advertising (Digital Marketing, Ad Market...)
11. Real Estate & Construction (Proptech, Construction...)
12. Manufacturing & Industry (Industry 4.0, Aerospace...)
13. Government & Public Services (Civic Tech, Defense...)
14. Tourism & Hospitality (Travel Tech, Food Service...)
15. Social & Human Services (HR, Social Impact...)
16. Science & Research (Life Sciences, Physical Sciences...)

---

## Next Steps
- [ ] Add web scraping pipeline (Playwright + Scrapy)
- [ ] Add Google Trends integration
- [ ] Add Reddit/news sentiment analysis
- [ ] Add demand scoring (0–100) per signal
- [ ] Add historical trend charts
- [ ] Add PostgreSQL storage for past reports
