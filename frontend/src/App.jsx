import { useState, useEffect, useRef } from "react";

const API = "https://global-demand-tool.onrender.com";


// ── Design tokens ──────────────────────────────────────────
const C = {
  bg:          "#07090d",
  surface:     "#0d1117",
  card:        "#0f1520",
  border:      "#1a2234",
  borderHover: "#2a3550",
  text:        "#e8edf5",
  muted:       "#5a6a85",
  faint:       "#1a2234",
  cyan:        "#00d4ff",
  green:       "#00e676",
  amber:       "#ffb300",
  red:         "#ff5252",
  purple:      "#b388ff",
  pink:        "#f48fb1",
  blue:        "#4fc3f7",
  orange:      "#ff8a65",
};

const VERDICT = {
  HIGH:        { color: C.green,  glow: "#00e67620", label: "Strong Demand",  icon: "▲", bar: C.green  },
  MEDIUM:      { color: C.amber,  glow: "#ffb30020", label: "Medium Demand",  icon: "◆", bar: C.amber  },
  LOW:         { color: C.red,    glow: "#ff525220", label: "Weak Demand",    icon: "▼", bar: C.red    },
  "NO DEMAND": { color: C.muted,  glow: "#00000000", label: "No Demand",      icon: "○", bar: C.muted  },
  UNKNOWN:     { color: C.muted,  glow: "#00000000", label: "Analyzing…",     icon: "…", bar: C.muted  },
};

const SIGNALS = {
  pain:       { label: "Pain Signal",       icon: "⚡", color: C.red,    desc: "Real & recurring problems" },
  buyer:      { label: "Buyer Signal",      icon: "👤", color: C.blue,   desc: "Right person ready to act" },
  competitor: { label: "Competitor Signal", icon: "🏆", color: C.amber,  desc: "Market already proven" },
  timing:     { label: "Timing Signal",     icon: "⏰", color: C.purple, desc: "Window opening now" },
  validation: { label: "Validation Signal", icon: "✅", color: C.green,  desc: "Buyers confirmed with action" },
  expansion:  { label: "Expansion Signal",  icon: "📈", color: C.cyan,   desc: "Demand compounds over time" },
};

const SOURCE_META = {
  reddit_post:    { label: "Reddit",        color: "#ff6314", icon: "R",  bg: "#1a0e00" },
  news_article:   { label: "News",          color: C.blue,   icon: "N",  bg: "#001525" },
  financial:      { label: "Screener.in",   color: C.amber,  icon: "₹",  bg: "#1a1200" },
  annual_report:  { label: "Annual Report", color: C.purple, icon: "📄", bg: "#100a25" },
  concall:        { label: "Concall",       color: C.green,  icon: "🎙", bg: "#001510" },
  trend:          { label: "Google Trends", color: C.cyan,   icon: "↗",  bg: "#001a25" },
  review_summary: { label: "G2 Review",     color: C.pink,   icon: "★",  bg: "#1a0015" },
  product_launch: { label: "ProductHunt",   color: "#da552f",icon: "🚀", bg: "#1a0800" },
  job_postings:   { label: "Job Market",    color: C.blue,   icon: "💼", bg: "#001525" },
  funded_company: { label: "Crunchbase",    color: "#42a5f5",icon: "💰", bg: "#001020" },
};

const PIPELINE_STAGES = [
  { key: "classify", label: "Classifying domain",             icon: "🔍" },
  { key: "reddit",   label: "Scraping Reddit",                icon: "R"  },
  { key: "trends",   label: "Google Trends",                  icon: "↗"  },
  { key: "news",     label: "News & RSS feeds",               icon: "📰" },
  { key: "screener", label: "Screener.in (financials)",       icon: "₹"  },
  { key: "web",      label: "G2 · Indeed · Crunchbase",       icon: "🌐" },
  { key: "scoring",  label: "AI scoring demand",              icon: "🤖" },
  { key: "done",     label: "Complete",                       icon: "✅" },
];

const EXAMPLES = [
  "Is there demand for SAP consulting?",
  "demand for AI tools in healthcare",
  "electric vehicle market India",
  "mental health apps for teenagers",
  "fintech startup Southeast Asia",
  "sustainable packaging ecommerce",
];

// ── Helpers ─────────────────────────────────────────────────
const sleep = ms => new Promise(r => setTimeout(r, ms));

function scoreColor(v) {
  if (v >= 70) return C.green;
  if (v >= 45) return C.amber;
  if (v >= 20) return C.red;
  return C.muted;
}

// ── Small components ─────────────────────────────────────────

function Ring({ value, color, size = 100 }) {
  const r = (size - 12) / 2;
  const circ = 2 * Math.PI * r;
  const offset = circ - (value / 100) * circ;
  return (
    <svg width={size} height={size} style={{ transform: "rotate(-90deg)", flexShrink: 0 }}>
      <circle cx={size/2} cy={size/2} r={r} fill="none"
        stroke={`${color}20`} strokeWidth={9} />
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={color}
        strokeWidth={9} strokeDasharray={circ} strokeDashoffset={offset}
        strokeLinecap="round"
        style={{ transition: "stroke-dashoffset 1.4s cubic-bezier(0.4,0,0.2,1)" }} />
      <text x={size/2} y={size/2} textAnchor="middle" dominantBaseline="central"
        style={{
          transform: `rotate(90deg)`,
          transformOrigin: `${size/2}px ${size/2}px`,
          fill: color, fontSize: size < 70 ? 14 : 20, fontWeight: 800,
          fontFamily: "'DM Sans', sans-serif"
        }}>{Math.round(value)}</text>
    </svg>
  );
}

function SignalBar({ label, icon, value, color, desc }) {
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ display:"flex", justifyContent:"space-between",
        alignItems:"center", marginBottom: 5 }}>
        <div style={{ display:"flex", alignItems:"center", gap: 7 }}>
          <span style={{ fontSize: 14 }}>{icon}</span>
          <span style={{ color: C.text, fontSize: 13, fontWeight: 500 }}>{label}</span>
          <span style={{ color: C.muted, fontSize: 11 }}>{desc}</span>
        </div>
        <span style={{ color, fontSize: 14, fontWeight: 700 }}>{Math.round(value)}</span>
      </div>
      <div style={{ height: 6, background: `${color}15`,
        borderRadius: 3, overflow:"hidden", position:"relative" }}>
        <div style={{
          height:"100%", width:`${value}%`, background: color,
          borderRadius: 3,
          boxShadow: `0 0 8px ${color}60`,
          transition: "width 1.4s cubic-bezier(0.4,0,0.2,1)"
        }} />
      </div>
    </div>
  );
}

function EvidenceCard({ item }) {
  const [open, setOpen] = useState(false);
  const m = SOURCE_META[item.item_type] || { label: item.item_type, color: C.muted, icon: "•", bg: C.faint };
  return (
    <div onClick={() => setOpen(!open)}
      style={{
        background: C.card, border: `1px solid ${C.border}`,
        borderRadius: 10, padding: "12px 16px", cursor: "pointer",
        marginBottom: 8, transition: "all 0.15s",
      }}
      onMouseEnter={e => {
        e.currentTarget.style.borderColor = m.color + "50";
        e.currentTarget.style.background = m.bg;
      }}
      onMouseLeave={e => {
        e.currentTarget.style.borderColor = C.border;
        e.currentTarget.style.background = C.card;
      }}
    >
      <div style={{ display:"flex", gap: 12, alignItems:"flex-start" }}>
        <div style={{
          minWidth: 30, height: 30, background: `${m.color}20`,
          border: `1px solid ${m.color}40`, color: m.color,
          borderRadius: 7, display:"flex", alignItems:"center",
          justifyContent:"center", fontSize: 12, fontWeight: 800, flexShrink: 0
        }}>{m.icon}</div>

        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display:"flex", gap: 8, alignItems:"center",
            flexWrap:"wrap", marginBottom: 4 }}>
            <span style={{ color: m.color, fontSize: 10, fontWeight: 700,
              textTransform:"uppercase", letterSpacing:"0.07em" }}>{m.label}</span>
            <span style={{ color: C.muted, fontSize: 10 }}>{item.source_name}</span>
            <span style={{ color: C.faint, fontSize: 10,
              background: `${C.muted}15`, borderRadius: 4, padding: "1px 6px" }}>
              {item.signal_type}
            </span>
          </div>

          <p style={{ color: C.text, fontSize: 13, margin: 0,
            lineHeight: 1.5, fontWeight: 500 }}>
            {(item.title || "").slice(0, 120)}
            {(item.title || "").length > 120 ? "…" : ""}
          </p>

          {open && (
            <div style={{ marginTop: 10 }}>
              {item.content && (
                <p style={{ color: C.muted, fontSize: 12, lineHeight: 1.7,
                  margin:"0 0 8px",
                  borderLeft: `2px solid ${m.color}40`, paddingLeft: 10 }}>
                  {item.content.slice(0, 600)}
                  {item.content.length > 600 ? "…" : ""}
                </p>
              )}
              {item.url && (
                <a href={item.url} target="_blank" rel="noreferrer"
                  onClick={e => e.stopPropagation()}
                  style={{ color: C.cyan, fontSize: 11, display:"inline-flex",
                    alignItems:"center", gap: 4 }}>
                  View source ↗
                </a>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function PipelineTracker({ stageIndex, stages, scraper_results, message, cached }) {
  return (
    <div style={{
      background: C.surface, border: `1px solid ${C.border}`,
      borderRadius: 14, padding: 24, marginBottom: 28
    }}>
      {cached ? (
        <div style={{ color: C.cyan, fontSize: 13, marginBottom: 16 }}>
          ⚡ Loaded from cache — data is less than 24 hours old
        </div>
      ) : (
        <div style={{ display:"flex", alignItems:"center", gap: 10, marginBottom: 18 }}>
          <div style={{
            width: 8, height: 8, borderRadius:"50%", background: C.amber,
            boxShadow: `0 0 8px ${C.amber}`,
            animation: stageIndex < 7 ? "pulse 1s ease-in-out infinite" : "none"
          }} />
          <span style={{ color: C.amber, fontSize: 13, fontWeight: 600 }}>
            {message || "Running…"}
          </span>
        </div>
      )}

      <div style={{ display:"flex", flexWrap:"wrap", gap: 8 }}>
        {PIPELINE_STAGES.map((stage, i) => {
          const done = i < stageIndex || stageIndex === 7;
          const active = i === stageIndex && stageIndex < 7;
          const count = scraper_results?.[stage.key];
          return (
            <div key={stage.key} style={{
              display:"flex", alignItems:"center", gap: 7,
              background: done ? `${C.green}10` : active ? `${C.amber}10` : C.faint,
              border: `1px solid ${done ? C.green+"40" : active ? C.amber+"40" : C.border}`,
              borderRadius: 8, padding: "6px 12px",
              transition: "all 0.3s"
            }}>
              <span style={{ fontSize: 12 }}>{stage.icon}</span>
              <span style={{ fontSize: 11, color: done ? C.green : active ? C.amber : C.muted,
                fontWeight: done || active ? 600 : 400 }}>
                {stage.label}
              </span>
              {done && count !== undefined && count > 0 && (
                <span style={{ fontSize: 10, color: C.green,
                  background: `${C.green}15`, borderRadius: 4, padding: "1px 5px" }}>
                  {count}
                </span>
              )}
              {done && (count === undefined || count === 0) && i > 0 && i < 7 && (
                <span style={{ fontSize: 10, color: C.green }}>✓</span>
              )}
              {active && (
                <span style={{ width: 6, height: 6, borderRadius:"50%",
                  background: C.amber, animation:"pulse 1s ease-in-out infinite" }} />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function App() {
  const [query, setQuery] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [appState, setAppState] = useState("idle");
  const [jobId, setJobId] = useState(null);
  const [pollStatus, setPollStatus] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [evFilter, setEvFilter] = useState("all");
  const [forceRefresh, setForceRefresh] = useState(false);

  const pollRef = useRef(null);
  const resultRef = useRef(null);

  const handleSearch = async () => {
    if (!query.trim() || appState === "running") return;

    setAppState("loading");
    setError("");
    setResult(null);
    setPollStatus(null);
    setEvFilter("all");

    try {
      const res = await fetch(`${API}/api/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: query.trim(),
          gemini_api_key: apiKey || undefined,
          force_refresh: forceRefresh
        })
      });
      const data = await res.json();

      if (!res.ok) {
        setError(data.error || "Server error");
        setAppState("error");
        return;
      }

      setJobId(data.job_id);
      setAppState("running");

    } catch (e) {
      setError(`Cannot reach backend at ${API}. Make sure Python server is running:\n  cd backend && python server.py`);
      setAppState("error");
    }
  };

  useEffect(() => {
    if (appState !== "running" || !jobId) return;

    const poll = async () => {
      try {
        const res = await fetch(`${API}/api/search/status/${encodeURIComponent(jobId)}`);
        const data = await res.json();
        setPollStatus(data);

        if (data.is_done) {
          clearInterval(pollRef.current);

          if (data.status === "error") {
            setError(data.error || "Pipeline failed");
            setAppState("error");
            return;
          }

          const rres = await fetch(`${API}/api/search/result/${encodeURIComponent(jobId)}`);
          const rdata = await rres.json();
          setResult(rdata.result);
          setAppState("complete");

          setTimeout(() => {
            resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
          }, 300);
        }
      } catch (e) {}
    };

    poll();
    pollRef.current = setInterval(poll, 2500);
    return () => clearInterval(pollRef.current);
  }, [appState, jobId]);

  const evidence = result?.evidence || [];
  const itemTypes = [...new Set(evidence.map(i => i.item_type))];
  const filtered = evFilter === "all"
    ? evidence
    : evidence.filter(i => i.item_type === evFilter);

  const demandScore = result?.demand_score;
  const verdict = demandScore?.verdict || "UNKNOWN";
  const vcfg = VERDICT[verdict] || VERDICT.UNKNOWN;

  const isRunning = appState === "running";
  const isComplete = appState === "complete";
  const isIdle = appState === "idle";

  return (
    <div style={{
      minHeight: "100vh", background: C.bg, color: C.text,
      fontFamily: "'DM Sans', 'Segoe UI', sans-serif"
    }}>
      <style>{`
        @keyframes pulse  { 0%,100%{opacity:1} 50%{opacity:.35} }
        @keyframes fadeIn { from{opacity:0;transform:translateY(12px)} to{opacity:1;transform:none} }
        @keyframes glow   { 0%,100%{box-shadow:0 0 20px #00d4ff20} 50%{box-shadow:0 0 40px #00d4ff40} }
        * { box-sizing:border-box; margin:0; padding:0; }
        input, button, a { font-family:inherit; }
        ::-webkit-scrollbar { width:4px; }
        ::-webkit-scrollbar-thumb { background:#1a2234; border-radius:2px; }
        a { text-decoration:none; }
      `}</style>

      <div style={{
        background: C.surface, borderBottom: `1px solid ${C.border}`,
        padding: "0 40px", display:"flex", alignItems:"center",
        justifyContent:"space-between", position:"sticky", top: 0, zIndex: 100
      }}>
        <div style={{ padding:"16px 0", display:"flex", alignItems:"center", gap: 12 }}>
          <span style={{ color: C.cyan, fontWeight: 800, fontSize: 18,
            letterSpacing:"-0.04em" }}>◈</span>
          <span style={{ color: C.text, fontWeight: 700, fontSize: 16,
            letterSpacing:"-0.03em" }}>GlobalDemand</span>
          <span style={{ color: C.muted, fontSize: 12, marginLeft: 4 }}>
            AI-powered demand analysis
          </span>
        </div>

        <div style={{ display:"flex", alignItems:"center", gap: 8 }}>
          <span style={{ color: C.muted, fontSize: 11 }}>Gemini API key:</span>
          <input
            type={showKey ? "text" : "password"}
            value={apiKey}
            onChange={e => setApiKey(e.target.value)}
            placeholder="AIza… (optional)"
            style={{
              background: C.faint, border:`1px solid ${C.border}`,
              borderRadius: 6, padding:"5px 10px", color: C.muted,
              fontSize: 11, outline:"none", fontFamily:"monospace", width: 180
            }}
          />
          <button onClick={() => setShowKey(!showKey)} style={{
            background:"none", border:"none", color: C.muted,
            cursor:"pointer", fontSize: 11
          }}>{showKey ? "hide" : "show"}</button>
        </div>
      </div>

      <div style={{
        padding: isIdle ? "80px 24px 60px" : "40px 24px 32px",
        maxWidth: 760, margin:"0 auto",
        transition: "padding 0.4s ease"
      }}>
        {isIdle && (
          <div style={{ textAlign:"center", marginBottom: 48, animation:"fadeIn 0.5s ease" }}>
            <div style={{
              display:"inline-block", background:`${C.cyan}10`,
              border:`1px solid ${C.cyan}30`, borderRadius: 20,
              padding:"4px 16px", fontSize: 11, color: C.cyan,
              fontWeight: 600, letterSpacing:"0.06em", marginBottom: 20
            }}>
              LIVE GLOBAL DEMAND INTELLIGENCE
            </div>
            <h1 style={{
              fontSize: "clamp(30px,5vw,52px)", fontWeight: 800,
              letterSpacing:"-0.04em", lineHeight: 1.1, marginBottom: 16
            }}>
              Is there demand for<br/>
              <span style={{ color: C.cyan }}>anything in the world?</span>
            </h1>
            <p style={{ color: C.muted, fontSize: 16, lineHeight: 1.7,
              maxWidth: 500, margin:"0 auto" }}>
              Type any product, market, or technology. We scrape Reddit,
              Google Trends, Screener.in, news, G2, job boards and more —
              then tell you exactly why there is or isn't demand.
            </p>
          </div>
        )}

        <div style={{
          background: C.surface,
          border: `1px solid ${isRunning ? C.amber+"60" : C.cyan+"40"}`,
          borderRadius: 16, padding: 16,
          boxShadow: isRunning ? `0 0 30px ${C.amber}10` : `0 0 30px ${C.cyan}08`,
          transition: "all 0.3s"
        }}>
          <div style={{ display:"flex", gap: 10 }}>
            <input
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={e => e.key === "Enter" && handleSearch()}
              placeholder="e.g. Is there demand for SAP consulting in India?"
              disabled={isRunning}
              style={{
                flex: 1, background: `${C.border}60`,
                border: `1px solid ${C.border}`,
                borderRadius: 10, padding:"14px 18px",
                color: C.text, fontSize: 15, outline:"none",
                opacity: isRunning ? 0.6 : 1
              }}
            />
            <button
              onClick={handleSearch}
              disabled={isRunning || !query.trim()}
              style={{
                background: isRunning
                  ? `${C.amber}15`
                  : query.trim() ? C.cyan : C.faint,
                color: isRunning ? C.amber : query.trim() ? "#000" : C.muted,
                border: `1px solid ${isRunning ? C.amber+"40" : "transparent"}`,
                borderRadius: 10, padding:"14px 28px",
                fontSize: 14, fontWeight: 800, cursor: isRunning ? "not-allowed" : "pointer",
                minWidth: 140, transition:"all 0.2s",
                letterSpacing:"-0.01em"
              }}
            >
              {isRunning ? "⏳ Analyzing…" : "Search →"}
            </button>
          </div>

          <div style={{ display:"flex", alignItems:"center", gap: 16,
            marginTop: 12, flexWrap:"wrap" }}>
            <label style={{ display:"flex", alignItems:"center", gap: 6,
              cursor:"pointer", userSelect:"none", color: C.muted, fontSize: 12 }}>
              <input type="checkbox" checked={forceRefresh}
                onChange={e => setForceRefresh(e.target.checked)}
                style={{ accentColor: C.cyan }} />
              Force refresh (ignore 24h cache)
            </label>
            <span style={{ color: C.muted, fontSize: 11 }}>
              {apiKey ? "✓ Gemini AI scoring enabled" : "⚡ Keyword scoring (add Gemini key for AI scoring)"}
            </span>
          </div>
        </div>

        {isIdle && (
          <div style={{ display:"flex", flexWrap:"wrap", gap: 8,
            marginTop: 16, animation:"fadeIn 0.6s ease 0.1s both" }}>
            {EXAMPLES.map((ex, i) => (
              <button key={i} onClick={() => { setQuery(ex); }}
                style={{
                  background: C.surface, border:`1px solid ${C.border}`,
                  borderRadius: 20, padding:"5px 14px", fontSize: 12,
                  color: C.muted, cursor:"pointer", transition:"all 0.15s"
                }}
                onMouseEnter={e => {
                  e.currentTarget.style.borderColor = C.cyan + "50";
                  e.currentTarget.style.color = C.text;
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.borderColor = C.border;
                  e.currentTarget.style.color = C.muted;
                }}
              >{ex}</button>
            ))}
          </div>
        )}
      </div>

      <div style={{ maxWidth: 960, margin:"0 auto", padding:"0 24px 80px" }}>

        {appState === "error" && (
          <div style={{
            background:`${C.red}10`, border:`1px solid ${C.red}30`,
            borderRadius: 12, padding: "16px 20px", marginBottom: 24,
            animation:"fadeIn 0.3s ease"
          }}>
            <div style={{ color: C.red, fontWeight: 600, fontSize: 14, marginBottom: 4 }}>
              ✗ Error
            </div>
            <pre style={{ color:"#fca5a5", fontSize: 12, lineHeight: 1.6,
              whiteSpace:"pre-wrap", margin: 0 }}>{error}</pre>
            <button onClick={() => { setAppState("idle"); setError(""); }}
              style={{ marginTop: 12, background:`${C.red}20`, border:`1px solid ${C.red}40`,
                color: C.red, borderRadius: 7, padding:"6px 14px",
                fontSize: 12, cursor:"pointer" }}>
              Try again
            </button>
          </div>
        )}

        {isRunning && pollStatus && (
          <div style={{ animation:"fadeIn 0.3s ease" }}>
            <PipelineTracker
              stageIndex={pollStatus.stage_index || 0}
              stages={PIPELINE_STAGES}
              scraper_results={pollStatus.scraper_results}
              message={pollStatus.message}
              cached={pollStatus.cached}
            />
            {pollStatus.domain && (
              <div style={{ color: C.muted, fontSize: 13, marginTop:-16, marginBottom: 20 }}>
                Domain identified: <span style={{ color: C.cyan, fontWeight: 600 }}>
                  {pollStatus.domain}
                </span>
              </div>
            )}
          </div>
        )}

        {isComplete && result && (
          <div ref={resultRef} style={{ animation:"fadeIn 0.5s ease" }}>

            <PipelineTracker
              stageIndex={7}
              stages={PIPELINE_STAGES}
              scraper_results={result.scraper_results}
              message={`Analysis complete — ${result.total_collected} data points collected`}
              cached={false}
            />

            <div style={{
              background: C.card,
              border: `1px solid ${vcfg.color}40`,
              borderRadius: 18, padding: 28, marginBottom: 24,
              boxShadow: `0 0 60px ${vcfg.glow}`
            }}>
              <div style={{ display:"grid", gridTemplateColumns:"auto 1fr",
                gap: 28, alignItems:"start" }}>

                <div style={{ textAlign:"center" }}>
                  <Ring value={demandScore?.overall || 0} color={vcfg.color} size={110} />
                  <div style={{
                    marginTop: 10, background:`${vcfg.color}15`,
                    border:`1px solid ${vcfg.color}40`, color: vcfg.color,
                    borderRadius: 20, padding:"4px 14px",
                    fontSize: 13, fontWeight: 800, display:"inline-block"
                  }}>
                    {vcfg.icon} {vcfg.label}
                  </div>
                  <div style={{ color: C.muted, fontSize: 11, marginTop: 8 }}>
                    {result.primary_domain}
                  </div>
                </div>

                <div>
                  <div style={{ color: C.muted, fontSize: 11, fontWeight: 600,
                    textTransform:"uppercase", letterSpacing:"0.07em",
                    marginBottom: 14 }}>Demand Signals</div>
                  {Object.entries(SIGNALS).map(([key, meta]) => (
                    <SignalBar key={key} {...meta}
                      value={demandScore?.signals?.[key] || 0} />
                  ))}
                </div>
              </div>
            </div>

            <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr",
              gap: 16, marginBottom: 24 }}>

              <div style={{
                background:`${C.green}06`,
                border:`1px solid ${C.green}25`,
                borderRadius: 14, padding: 22
              }}>
                <div style={{
                  display:"flex", alignItems:"center", gap: 8, marginBottom: 14
                }}>
                  <div style={{ width: 28, height: 28, background:`${C.green}20`,
                    border:`1px solid ${C.green}40`, borderRadius: 7,
                    display:"flex", alignItems:"center", justifyContent:"center",
                    fontSize: 14 }}>✓</div>
                  <span style={{ color: C.green, fontSize: 12, fontWeight: 700,
                    textTransform:"uppercase", letterSpacing:"0.07em" }}>
                    Why there IS demand
                  </span>
                </div>
                <p style={{ color:"#bbf7d0", fontSize: 14, lineHeight: 1.8, margin: 0 }}>
                  {demandScore?.why_demand || "Insufficient data to determine demand reasons."}
                </p>
              </div>

              <div style={{
                background:`${C.red}06`,
                border:`1px solid ${C.red}25`,
                borderRadius: 14, padding: 22
              }}>
                <div style={{
                  display:"flex", alignItems:"center", gap: 8, marginBottom: 14
                }}>
                  <div style={{ width: 28, height: 28, background:`${C.red}20`,
                    border:`1px solid ${C.red}40`, borderRadius: 7,
                    display:"flex", alignItems:"center", justifyContent:"center",
                    fontSize: 14 }}>✗</div>
                  <span style={{ color: C.red, fontSize: 12, fontWeight: 700,
                    textTransform:"uppercase", letterSpacing:"0.07em" }}>
                    Risks / Why demand may be low
                  </span>
                </div>
                <p style={{ color:"#fecaca", fontSize: 14, lineHeight: 1.8, margin: 0 }}>
                  {demandScore?.why_no_demand || "No significant risks identified."}
                </p>
              </div>
            </div>

            {demandScore?.key_evidence?.length > 0 && (
              <div style={{
                background: C.card, border:`1px solid ${C.border}`,
                borderRadius: 14, padding: 22, marginBottom: 24
              }}>
                <div style={{ color: C.cyan, fontSize: 12, fontWeight: 700,
                  textTransform:"uppercase", letterSpacing:"0.07em", marginBottom: 14 }}>
                  📌 Key Evidence Points
                </div>
                <div style={{ display:"grid",
                  gridTemplateColumns:"repeat(auto-fill, minmax(280px,1fr))", gap: 10 }}>
                  {demandScore.key_evidence.map((ev, i) => (
                    <div key={i} style={{
                      background:`${C.cyan}06`, border:`1px solid ${C.cyan}20`,
                      borderRadius: 8, padding:"10px 14px",
                      display:"flex", gap: 10, alignItems:"flex-start"
                    }}>
                      <span style={{ color: C.cyan, fontSize: 14, flexShrink: 0 }}>›</span>
                      <span style={{ color: C.text, fontSize: 13, lineHeight: 1.5 }}>{ev}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {result.domains && Object.keys(result.domains).length > 0 && (
              <div style={{
                background: C.card, border:`1px solid ${C.border}`,
                borderRadius: 14, padding: 22, marginBottom: 24
              }}>
                <div style={{ color: C.muted, fontSize: 12, fontWeight: 700,
                  textTransform:"uppercase", letterSpacing:"0.07em", marginBottom: 14 }}>
                  🗂 Domain Classification
                </div>
                <div style={{ display:"flex", flexWrap:"wrap", gap: 10 }}>
                  {Object.entries(result.domains).map(([name, data]) => {
                    const isPrimary = name === result.primary_domain;
                    const col = isPrimary ? C.cyan : C.muted;
                    return (
                      <div key={name} style={{
                        background:`${col}08`, border:`1px solid ${col}30`,
                        borderRadius: 10, padding:"10px 16px"
                      }}>
                        <div style={{ color: col, fontWeight: 600, fontSize: 13 }}>
                          {isPrimary && "◆ "}{name}
                        </div>
                        <div style={{ color: C.muted, fontSize: 11, marginTop: 4 }}>
                          {data.confidence}% confidence · {data.total_sources} sources
                        </div>
                        <div style={{ display:"flex", flexWrap:"wrap", gap: 4, marginTop: 6 }}>
                          {(data.sub_domains || []).map((s, i) => (
                            <span key={i} style={{
                              background:`${col}12`, color: col,
                              fontSize: 10, borderRadius: 4, padding:"2px 7px"
                            }}>{s}</span>
                          ))}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {evidence.length > 0 && (
              <div>
                <div style={{ display:"flex", alignItems:"center",
                  justifyContent:"space-between", marginBottom: 16,
                  flexWrap:"wrap", gap: 12 }}>
                  <div>
                    <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 2 }}>
                      Evidence Collected
                    </h3>
                    <span style={{ color: C.muted, fontSize: 12 }}>
                      {filtered.length} of {evidence.length} items shown
                    </span>
                  </div>

                  <div style={{ display:"flex", gap: 6, flexWrap:"wrap" }}>
                    <button onClick={() => setEvFilter("all")} style={{
                      background: evFilter === "all" ? `${C.cyan}20` : C.surface,
                      color: evFilter === "all" ? C.cyan : C.muted,
                      border:`1px solid ${evFilter === "all" ? C.cyan+"50" : C.border}`,
                      borderRadius: 20, padding:"4px 14px", fontSize: 11,
                      cursor:"pointer", fontWeight: evFilter === "all" ? 600 : 400
                    }}>All ({evidence.length})</button>

                    {itemTypes.map(type => {
                      const m = SOURCE_META[type] || {};
                      const count = evidence.filter(i => i.item_type === type).length;
                      return (
                        <button key={type} onClick={() => setEvFilter(type)} style={{
                          background: evFilter === type ? `${m.color}20` : C.surface,
                          color: evFilter === type ? m.color : C.muted,
                          border:`1px solid ${evFilter === type ? m.color+"50" : C.border}`,
                          borderRadius: 20, padding:"4px 14px", fontSize: 11,
                          cursor:"pointer", fontWeight: evFilter === type ? 600 : 400
                        }}>
                          {m.icon} {m.label} ({count})
                        </button>
                      );
                    })}
                  </div>
                </div>

                <div style={{ maxHeight: 700, overflowY:"auto", paddingRight: 4 }}>
                  {filtered.length === 0 ? (
                    <div style={{ color: C.muted, fontSize: 13,
                      textAlign:"center", padding: 32 }}>
                      No {evFilter} items collected
                    </div>
                  ) : (
                    filtered.map((item, i) => <EvidenceCard key={i} item={item} />)
                  )}
                </div>
              </div>
            )}

            <div style={{ marginTop: 28, display:"flex", alignItems:"center",
              justifyContent:"space-between", flexWrap:"wrap", gap: 12 }}>
              <span style={{ color: C.muted, fontSize: 11 }}>
                Scraped {new Date(result.scraped_at).toLocaleString()} ·
                Auto-refreshes in 24h
              </span>
              <button onClick={() => {
                setForceRefresh(true);
                setAppState("idle");
                setTimeout(() => {
                  document.querySelector("input")?.focus();
                }, 100);
              }} style={{
                background: C.surface, border:`1px solid ${C.border}`,
                color: C.muted, borderRadius: 8, padding:"7px 16px",
                fontSize: 12, cursor:"pointer"
              }}>
                🔄 Force refresh
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
