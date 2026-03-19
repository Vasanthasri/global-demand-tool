import { useState, useEffect, useRef, useCallback } from "react";
import { createRoot } from "react-dom/client";

const API = "https://global-demand-tool.onrender.com";

const C = {
  bg:      "#07090f",
  panel:   "#0e1219",
  panel2:  "#111827",
  border:  "#1c2030",
  accent:  "#4f8ef7",
  accent2: "#34c98e",
  warn:    "#f7a94f",
  danger:  "#f75f5f",
  muted:   "#4a5568",
  text:    "#e2e8f0",
  sub:     "#8899aa",
};

const SIGNAL_COLORS = {
  "Pain Signal":       "#f75f5f",
  "Buyer Signal":      "#34c98e",
  "Competitor Signal": "#f7a94f",
  "Timing Signal":     "#4f8ef7",
  "Validation Signal": "#a78bfa",
  "Market Data":       "#38bdf8",
};

const VERDICT_CONFIG = {
  HIGH:        { color: "#34c98e", bg: "#0d2e1f", label: "HIGH DEMAND" },
  MEDIUM:      { color: "#f7a94f", bg: "#2e1f0d", label: "MEDIUM DEMAND" },
  LOW:         { color: "#f75f5f", bg: "#2e0d0d", label: "LOW DEMAND" },
  "NO DEMAND": { color: "#8899aa", bg: "#1a1e2a", label: "NO DEMAND" },
  UNKNOWN:     { color: "#8899aa", bg: "#1a1e2a", label: "UNKNOWN" },
};

const VERDICT_COLORS = { HIGH:"#34c98e", MEDIUM:"#f7a94f", LOW:"#f75f5f" };

const STYLE = `
  @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: ${C.bg}; color: ${C.text}; font-family: 'Space Grotesk', sans-serif; min-height: 100vh; overflow-x: hidden; }
  ::-webkit-scrollbar { width: 5px; }
  ::-webkit-scrollbar-track { background: ${C.bg}; }
  ::-webkit-scrollbar-thumb { background: ${C.border}; border-radius: 3px; }
  a { color: ${C.accent}; text-decoration: none; }
  a:hover { text-decoration: underline; }

  @keyframes fadeUp  { from { opacity:0; transform:translateY(14px); } to { opacity:1; transform:none; } }
  @keyframes pulse   { 0%,100%{opacity:1}50%{opacity:.4} }
  @keyframes spin    { to{transform:rotate(360deg)} }
  @keyframes barIn   { from{width:0} to{width:var(--w)} }
  @keyframes slideIn { from{transform:translateX(100%);opacity:0} to{transform:none;opacity:1} }

  .fade-up  { animation: fadeUp .4s ease both; }
  .pulse    { animation: pulse 1.6s ease infinite; }
  .spinner  { animation: spin .8s linear infinite; border:2px solid ${C.border}; border-top-color:${C.accent}; border-radius:50%; width:18px; height:18px; flex-shrink:0; }

  .card     { background:${C.panel}; border:1px solid ${C.border}; border-radius:12px; }
  .tag      { display:inline-flex; align-items:center; gap:4px; padding:2px 8px; border-radius:20px; font-size:11px; font-weight:600; letter-spacing:.4px; text-transform:uppercase; }

  .source-item { display:flex; align-items:flex-start; gap:10px; padding:10px 12px; border-radius:8px; border:1px solid ${C.border}; transition:border-color .2s,background .2s; }
  .source-item:hover { border-color:${C.accent}; background:rgba(79,142,247,.06); }

  .bar-row   { display:flex; align-items:center; gap:10px; margin-bottom:8px; }
  .bar-label { width:130px; font-size:12px; color:${C.sub}; text-align:right; flex-shrink:0; }
  .bar-track { flex:1; height:8px; background:${C.border}; border-radius:4px; overflow:hidden; }
  .bar-fill  { height:100%; border-radius:4px; animation:barIn .8s cubic-bezier(.4,0,.2,1) both; }

  .tab-btn { padding:7px 16px; border-radius:6px; font-size:13px; font-weight:500; cursor:pointer; border:1px solid transparent; transition:all .2s; background:none; color:${C.sub}; }
  .tab-btn.active { background:${C.accent}22; border-color:${C.accent}44; color:${C.accent}; }
  .tab-btn:hover:not(.active) { background:${C.border}; color:${C.text}; }

  .chat-msg-user { background:${C.accent}18; border:1px solid ${C.accent}33; border-radius:12px 12px 4px 12px; padding:10px 14px; font-size:13px; align-self:flex-end; max-width:85%; }
  .chat-msg-bot  { background:${C.panel2}; border:1px solid ${C.border}; border-radius:12px 12px 12px 4px; padding:12px 14px; font-size:13px; align-self:flex-start; max-width:95%; }
  .chat-input    { background:${C.panel2}; border:1px solid ${C.border}; border-radius:8px; padding:10px 12px; font-size:13px; color:${C.text}; font-family:'Space Grotesk',sans-serif; outline:none; flex:1; transition:border-color .2s; }
  .chat-input:focus { border-color:${C.accent}; }
  .chat-send  { background:${C.accent}; color:#fff; border:none; border-radius:8px; padding:10px 16px; font-size:13px; font-weight:600; cursor:pointer; font-family:'Space Grotesk',sans-serif; transition:opacity .2s; }
  .chat-send:disabled { opacity:.4; cursor:not-allowed; }
  .chat-send:hover:not(:disabled) { opacity:.85; }
  .suggestion-btn { background:${C.border}; border:1px solid ${C.border}; color:${C.sub}; border-radius:20px; padding:4px 12px; font-size:11px; cursor:pointer; transition:all .2s; white-space:nowrap; font-family:'Space Grotesk',sans-serif; }
  .suggestion-btn:hover { border-color:${C.accent}; color:${C.accent}; background:${C.accent}11; }
`;

function injectStyle() {
  const el = document.createElement("style");
  el.textContent = STYLE;
  document.head.appendChild(el);
}
injectStyle();

// ─────────────────────────────────────────────────────────────
// SVG LINE CHART
// ─────────────────────────────────────────────────────────────
function LineChart({ labels, series }) {
  const W=680, H=170, PAD={t:20,r:16,b:36,l:36};
  const IW=W-PAD.l-PAD.r, IH=H-PAD.t-PAD.b;
  const allVals=Object.values(series).flat();
  const maxVal=Math.max(...allVals,1);
  const n=labels.length;
  const xPos=i=>PAD.l+(i/Math.max(n-1,1))*IW;
  const yPos=v=>PAD.t+IH-(v/maxVal)*IH;
  const LINE_COLORS=["#4f8ef7","#f75f5f","#34c98e","#f7a94f"];
  const pathFor=vals=>vals.map((v,i)=>`${i===0?"M":"L"} ${xPos(i).toFixed(1)} ${yPos(v).toFixed(1)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{width:"100%",height:"auto"}}>
      {[0,.5,1].map((t,i)=>{
        const y=PAD.t+IH*(1-t);
        return <g key={i}>
          <line x1={PAD.l} y1={y} x2={PAD.l+IW} y2={y} stroke={C.border} strokeWidth="1" strokeDasharray="4 3"/>
          <text x={PAD.l-4} y={y+4} fontSize="9" fill={C.muted} textAnchor="end">{Math.round(t*maxVal)}</text>
        </g>;
      })}
      {Object.entries(series).map(([name,vals],idx)=>{
        const line=pathFor(vals);
        const area=`${line} L ${xPos(n-1).toFixed(1)} ${(PAD.t+IH).toFixed(1)} L ${PAD.l.toFixed(1)} ${(PAD.t+IH).toFixed(1)} Z`;
        return <g key={name}>
          <path d={area} fill={LINE_COLORS[idx%LINE_COLORS.length]} fillOpacity=".07" stroke="none"/>
          <path d={line} fill="none" stroke={LINE_COLORS[idx%LINE_COLORS.length]} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round"/>
          {vals.map((v,i)=><circle key={i} cx={xPos(i)} cy={yPos(v)} r="3" fill={LINE_COLORS[idx%LINE_COLORS.length]} stroke={C.panel} strokeWidth="2"/>)}
        </g>;
      })}
      {labels.map((lbl,i)=><text key={i} x={xPos(i)} y={H-6} fontSize="9" fill={C.sub} textAnchor="middle">{lbl}</text>)}
      {Object.keys(series).map((name,idx)=>(
        <g key={name} transform={`translate(${PAD.l+idx*120},${PAD.t-6})`}>
          <line x1="0" y1="5" x2="12" y2="5" stroke={LINE_COLORS[idx%LINE_COLORS.length]} strokeWidth="2"/>
          <circle cx="6" cy="5" r="2.5" fill={LINE_COLORS[idx%LINE_COLORS.length]}/>
          <text x="16" y="9" fontSize="9" fill={C.sub}>{name}</text>
        </g>
      ))}
    </svg>
  );
}

// ─────────────────────────────────────────────────────────────
// LOCATION CHART
// ─────────────────────────────────────────────────────────────
function LocationChart({ regions }) {
  if (!regions?.length) return <div style={{color:C.sub,fontSize:13,padding:"16px 0"}}>No regional data found.</div>;
  const max=regions[0]?.count||1;
  const FLAGS={"USA":"🇺🇸","UK":"🇬🇧","India":"🇮🇳","Germany":"🇩🇪","Europe":"🇪🇺","Middle East":"🇦🇪","Asia Pacific":"🌏","Global":"🌐"};
  const COLS=["#4f8ef7","#34c98e","#f7a94f","#f75f5f","#a78bfa","#38bdf8","#fb923c","#a3e635"];
  return (
    <div style={{display:"flex",flexDirection:"column",gap:10}}>
      {regions.map((r,i)=>(
        <div key={r.name}>
          <div style={{display:"flex",justifyContent:"space-between",marginBottom:4}}>
            <span style={{fontSize:13,fontWeight:500}}>{FLAGS[r.name]||"📍"} {r.name}</span>
            <span style={{fontSize:11,color:C.sub,fontFamily:"JetBrains Mono,monospace"}}>{r.count} · {r.pct}%</span>
          </div>
          <div style={{height:8,background:C.border,borderRadius:4,overflow:"hidden"}}>
            <div style={{height:"100%",borderRadius:4,background:COLS[i%COLS.length],width:`${(r.count/max)*100}%`,transition:"width 1s cubic-bezier(.4,0,.2,1)"}}/>
          </div>
          {r.example&&<div style={{fontSize:11,color:C.muted,marginTop:2,fontStyle:"italic"}}>e.g. "{r.example}"</div>}
        </div>
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// SUB-AREA MODULE BREAKDOWN CHART
// ─────────────────────────────────────────────────────────────
function ModuleBreakdown({ modules, onModuleClick }) {
  if (!modules?.length) return (
    <div style={{color:C.sub,fontSize:13,padding:"16px 0"}}>
      No sub-area mentions detected in scraped data yet. Try a fresh search.
    </div>
  );

  const VERDICT_COLORS_MAP = { HIGH:"#34c98e", MEDIUM:"#f7a94f", LOW:"#f75f5f" };
  const max = modules[0]?.count || 1;

  return (
    <div style={{display:"flex",flexDirection:"column",gap:12}}>
      {modules.map((m, i) => (
        <div key={m.name}
          onClick={() => onModuleClick && onModuleClick(m.name)}
          style={{
            background: C.panel2, border:`1px solid ${C.border}`,
            borderRadius:10, padding:"12px 16px",
            cursor: onModuleClick ? "pointer" : "default",
            transition:"border-color .2s,background .2s",
          }}
          onMouseEnter={e=>{e.currentTarget.style.borderColor=C.accent;e.currentTarget.style.background="#0d1525";}}
          onMouseLeave={e=>{e.currentTarget.style.borderColor=C.border;e.currentTarget.style.background=C.panel2;}}
        >
          {/* Header row */}
          <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:8}}>
            <div style={{display:"flex",alignItems:"center",gap:8}}>
              <span style={{fontSize:18}}>{m.emoji}</span>
              <span style={{fontSize:13,fontWeight:600,color:C.text}}>{m.name}</span>
            </div>
            <div style={{display:"flex",alignItems:"center",gap:8}}>
              <span style={{
                fontSize:11,fontWeight:700,padding:"2px 8px",borderRadius:20,
                background:VERDICT_COLORS_MAP[m.verdict]+"22",
                color:VERDICT_COLORS_MAP[m.verdict],
              }}>{m.verdict}</span>
              <span style={{fontSize:11,color:C.sub,fontFamily:"JetBrains Mono,monospace"}}>
                {m.count} mentions · {m.share}%
              </span>
            </div>
          </div>

          {/* Bar */}
          <div style={{height:6,background:C.border,borderRadius:3,overflow:"hidden",marginBottom:6}}>
            <div style={{
              height:"100%",borderRadius:3,
              background: m.verdict==="HIGH" ? "#34c98e" : m.verdict==="MEDIUM" ? "#f7a94f" : "#f75f5f",
              width:`${m.pct}%`,transition:"width 1s cubic-bezier(.4,0,.2,1)",
            }}/>
          </div>

          {/* Example evidence */}
          {m.examples?.length > 0 && (
            <div style={{fontSize:11,color:C.muted,lineHeight:1.5}}>
              📌 {m.examples[0]}
            </div>
          )}

          {onModuleClick && (
            <div style={{fontSize:10,color:C.accent,marginTop:6}}>
              Click to deep-dive into {m.name} →
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// CHAT MINI CHART (inline in chat messages)
// ─────────────────────────────────────────────────────────────
function ChatChart({ chartType, chartTitle, chartData }) {
  if (!chartType || chartType === "none" || !chartData?.length) return null;
  const max = Math.max(...chartData.map(d => d.value), 1);
  const total = chartData.reduce((s, d) => s + d.value, 0);

  return (
    <div style={{marginTop:10,background:C.bg,borderRadius:8,padding:"12px 14px",border:`1px solid ${C.border}`}}>
      {chartTitle && (
        <div style={{fontSize:11,fontWeight:700,color:C.sub,textTransform:"uppercase",letterSpacing:.5,marginBottom:10}}>
          {chartTitle}
        </div>
      )}
      <div style={{display:"flex",flexDirection:"column",gap:7}}>
        {chartData.map((d, i) => (
          <div key={i}>
            <div style={{display:"flex",justifyContent:"space-between",marginBottom:3}}>
              <span style={{fontSize:12,color:C.text}}>{d.label}</span>
              <span style={{fontSize:11,color:C.sub,fontFamily:"JetBrains Mono,monospace"}}>
                {d.value} ({Math.round((d.value/total)*100)}%)
              </span>
            </div>
            <div style={{height:6,background:C.border,borderRadius:3,overflow:"hidden"}}>
              <div style={{
                height:"100%",borderRadius:3,
                background:d.color||C.accent,
                width:`${(d.value/max)*100}%`,
                transition:"width 0.8s ease",
              }}/>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// CHAT SIDEBAR
// ─────────────────────────────────────────────────────────────
function ChatSidebar({ query, domain, isOpen, onClose }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput]       = useState("");
  const [thinking, setThinking] = useState(false);
  const bottomRef = useRef(null);

  // Welcome message when sidebar opens with a query
  useEffect(() => {
    if (isOpen && query && messages.length === 0) {
      setMessages([{
        role: "bot",
        text: `I've analysed the data for **"${query}"**. Ask me anything — like which sub-area has most demand, where demand is highest geographically, or what the key risks are.`,
        suggestions: [
          "Which sub-area has highest demand?",
          "Where is the demand highest geographically?",
          "What are the main risk factors?",
          "Is there demand in India specifically?",
        ],
        chart: null,
      }]);
    }
  }, [isOpen, query]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, thinking]);

  const sendMessage = async (text) => {
    const q = (text || input).trim();
    if (!q || thinking) return;
    setInput("");
    setMessages(prev => [...prev, { role: "user", text: q }]);
    setThinking(true);
    try {
      const res = await fetch(`${API}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, question: q }),
      }).then(r => r.json());
      setMessages(prev => [...prev, {
        role: "bot",
        text: res.answer || "Sorry, I could not answer that.",
        suggestions: res.follow_up_suggestions || [],
        chart: {
          chartType: res.chart_type,
          chartTitle: res.chart_title,
          chartData: res.chart_data,
        },
      }]);
    } catch (e) {
      setMessages(prev => [...prev, {
        role: "bot",
        text: "Error connecting to server. Make sure the backend is running.",
        suggestions: [],
        chart: null,
      }]);
    }
    setThinking(false);
  };

  if (!isOpen) return null;

  return (
    <div style={{
      position:"fixed", top:0, right:0, height:"100vh", width:380,
      background:C.panel, borderLeft:`1px solid ${C.border}`,
      display:"flex", flexDirection:"column", zIndex:1000,
      animation:"slideIn .3s ease both", boxShadow:"-8px 0 32px rgba(0,0,0,.4)",
    }}>
      {/* Header */}
      <div style={{
        padding:"16px 20px", borderBottom:`1px solid ${C.border}`,
        display:"flex", justifyContent:"space-between", alignItems:"center",
        flexShrink:0,
      }}>
        <div>
          <div style={{fontSize:15,fontWeight:700,color:C.text}}>🤖 {domain || "Demand"} Analyst</div>
          <div style={{fontSize:11,color:C.sub,marginTop:2}}>Ask about the scraped results</div>
        </div>
        <button onClick={onClose} style={{
          background:"none",border:"none",color:C.sub,cursor:"pointer",
          fontSize:20,padding:"4px 8px",borderRadius:6,transition:"color .2s",
        }}
          onMouseEnter={e=>e.target.style.color=C.text}
          onMouseLeave={e=>e.target.style.color=C.sub}
        >✕</button>
      </div>

      {/* Query context pill */}
      {query && (
        <div style={{padding:"10px 20px",borderBottom:`1px solid ${C.border}`,flexShrink:0}}>
          <div style={{
            background:C.accent+"18",border:`1px solid ${C.accent}33`,
            borderRadius:8,padding:"6px 12px",fontSize:11,color:C.accent,
          }}>
            📊 Context: "{query.length>50 ? query.slice(0,50)+"…" : query}"
          </div>
        </div>
      )}

      {/* Messages */}
      <div style={{flex:1,overflowY:"auto",padding:"16px 16px 8px",display:"flex",flexDirection:"column",gap:12}}>
        {messages.map((msg, i) => (
          <div key={i} style={{display:"flex",flexDirection:"column",gap:6,
            alignItems:msg.role==="user"?"flex-end":"flex-start"}}>
            <div className={msg.role==="user"?"chat-msg-user":"chat-msg-bot"}>
              {msg.text.split("**").map((part, j) =>
                j%2===1 ? <strong key={j}>{part}</strong> : part
              )}
              {msg.chart && (
                <ChatChart
                  chartType={msg.chart.chartType}
                  chartTitle={msg.chart.chartTitle}
                  chartData={msg.chart.chartData}
                />
              )}
            </div>
            {/* Suggestions */}
            {msg.role==="bot" && msg.suggestions?.length>0 && (
              <div style={{display:"flex",flexWrap:"wrap",gap:6,marginTop:2}}>
                {msg.suggestions.map((s,j)=>(
                  <button key={j} className="suggestion-btn" onClick={()=>sendMessage(s)}>
                    {s}
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}
        {thinking && (
          <div style={{display:"flex",alignItems:"center",gap:8,color:C.sub,fontSize:12}}>
            <div className="spinner"/>
            Analysing your question…
          </div>
        )}
        <div ref={bottomRef}/>
      </div>

      {/* Input */}
      <div style={{padding:"12px 16px",borderTop:`1px solid ${C.border}`,flexShrink:0}}>
        <div style={{display:"flex",gap:8}}>
          <input
            className="chat-input"
            value={input}
            onChange={e=>setInput(e.target.value)}
            placeholder="Ask about the demand data…"
            onKeyDown={e=>e.key==="Enter"&&sendMessage()}
            disabled={thinking||!query}
          />
          <button className="chat-send" onClick={()=>sendMessage()} disabled={thinking||!input.trim()||!query}>
            Send
          </button>
        </div>
        <div style={{fontSize:10,color:C.muted,marginTop:6,textAlign:"center"}}>
          Answers based on already-scraped data · No new searches
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// SCORE RING
// ─────────────────────────────────────────────────────────────
function ScoreRing({ score, verdict }) {
  const cfg = VERDICT_CONFIG[verdict] || VERDICT_CONFIG.UNKNOWN;
  const r=70, circ=2*Math.PI*r, offset=circ-(score/100)*circ;
  return (
    <div style={{display:"flex",flexDirection:"column",alignItems:"center",gap:8}}>
      <svg width="180" height="180" viewBox="0 0 180 180">
        <circle cx="90" cy="90" r={r} fill="none" stroke={C.border} strokeWidth="12"/>
        <circle cx="90" cy="90" r={r} fill="none" stroke={cfg.color} strokeWidth="12"
          strokeDasharray={circ} strokeDashoffset={offset} strokeLinecap="round"
          transform="rotate(-90 90 90)"
          style={{transition:"stroke-dashoffset 1.2s cubic-bezier(.4,0,.2,1)"}}/>
        <text x="90" y="83" textAnchor="middle" fontSize="34" fontWeight="700"
          fill={cfg.color} fontFamily="Space Grotesk,sans-serif">{score}</text>
        <text x="90" y="101" textAnchor="middle" fontSize="11" fill={C.sub}
          fontFamily="Space Grotesk,sans-serif">out of 100</text>
      </svg>
      <div style={{background:cfg.bg,color:cfg.color,padding:"4px 14px",borderRadius:20,
        fontSize:12,fontWeight:700,letterSpacing:1}}>{cfg.label}</div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// SOURCE CARD
// ─────────────────────────────────────────────────────────────
function SourceCard({ item }) {
  const sig=item.signal_type||"", color=SIGNAL_COLORS[sig]||C.muted;
  const url=item.url||"", isReal=url.startsWith("http")&&!url.includes("localhost");
  let displayDomain=item.source_name||"";
  try { if(url.startsWith("http")) displayDomain=new URL(url).hostname.replace("www.",""); } catch(_){}
  let dateStr="";
  if(item.published_at){ try{ dateStr=new Date(item.published_at).toLocaleDateString("en-US",{year:"numeric",month:"short",day:"numeric"}); }catch(_){} }
  const typeIcon={reddit_post:"💬",news_article:"📰",web_page:"🌐",financial:"📊",job_postings:"💼",trend:"📈",concall:"🎙️",annual_report:"📋"}[item.item_type]||"🔗";
  return (
    <div className="source-item">
      <span style={{fontSize:18,flexShrink:0,marginTop:1}}>{typeIcon}</span>
      <div style={{flex:1,minWidth:0}}>
        {isReal
          ? <a href={url} target="_blank" rel="noopener noreferrer"
              style={{fontSize:13,fontWeight:500,color:C.accent,wordBreak:"break-word"}}>{item.title||displayDomain}</a>
          : <span style={{fontSize:13,fontWeight:500,color:C.text}}>{item.title||displayDomain}</span>
        }
        {isReal&&<div style={{fontSize:11,color:C.accent,marginTop:2,fontFamily:"JetBrains Mono,monospace"}}>
          <a href={url} target="_blank" rel="noopener noreferrer" style={{color:C.accent}}>
            ↗ {url.length>80?url.slice(0,80)+"…":url}
          </a>
        </div>}
        {item.content&&<div style={{fontSize:12,color:C.sub,marginTop:4,lineHeight:1.5,
          display:"-webkit-box",WebkitLineClamp:2,WebkitBoxOrient:"vertical",overflow:"hidden"}}>
          {item.content.slice(0,200)}
        </div>}
        <div style={{display:"flex",gap:8,marginTop:5,flexWrap:"wrap"}}>
          <span className="tag" style={{background:color+"18",color}}>{sig}</span>
          {displayDomain&&<span className="tag" style={{background:C.border+"80",color:C.sub}}>{displayDomain}</span>}
          {dateStr&&<span style={{fontSize:11,color:C.muted,fontFamily:"JetBrains Mono,monospace"}}>{dateStr}</span>}
          {item.metadata?.upvotes>0&&<span style={{fontSize:11,color:C.muted}}>▲ {item.metadata.upvotes} · 💬 {item.metadata.comments||0}</span>}
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// SIGNAL BARS
// ─────────────────────────────────────────────────────────────
function SignalBars({ signals }) {
  const entries=[
    {label:"Pain",key:"pain",color:SIGNAL_COLORS["Pain Signal"]},
    {label:"Buyer",key:"buyer",color:SIGNAL_COLORS["Buyer Signal"]},
    {label:"Competitor",key:"competitor",color:SIGNAL_COLORS["Competitor Signal"]},
    {label:"Timing",key:"timing",color:SIGNAL_COLORS["Timing Signal"]},
    {label:"Validation",key:"validation",color:SIGNAL_COLORS["Validation Signal"]},
    {label:"Expansion",key:"expansion",color:SIGNAL_COLORS["Market Data"]},
  ];
  return (
    <div>
      {entries.map(({label,key,color})=>{
        const val=Math.round(signals?.[key]||0);
        return (
          <div key={key} className="bar-row">
            <div className="bar-label">{label}</div>
            <div className="bar-track">
              <div className="bar-fill" style={{width:`${val}%`,background:color,"--w":`${val}%`}}/>
            </div>
            <span style={{fontSize:12,color,fontWeight:600,width:32,textAlign:"right",fontFamily:"JetBrains Mono,monospace"}}>{val}</span>
          </div>
        );
      })}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// PROGRESS OVERLAY
// ─────────────────────────────────────────────────────────────
function ProgressOverlay({ status }) {
  if (!status) return null;
  const stages=["Classify","Scraping","Scoring","Done"];
  const idx=status.stage_index||0, pct=status.progress_pct||0;
  const icons={reddit:"💬",news:"📰",web:"🌐",screener:"📊",trends:"📈",indeed:"💼"};
  return (
    <div style={{background:C.panel,border:`1px solid ${C.border}`,borderRadius:12,padding:24,marginTop:24}} className="fade-up">
      <div style={{display:"flex",gap:8,marginBottom:18,flexWrap:"wrap"}}>
        {stages.map((s,i)=>(
          <div key={s} style={{padding:"4px 14px",borderRadius:20,fontSize:12,fontWeight:600,
            background:i<idx?C.accent2+"22":i===idx?C.accent+"22":C.border,
            color:i<idx?C.accent2:i===idx?C.accent:C.muted,
            border:`1px solid ${i<idx?C.accent2+"44":i===idx?C.accent+"44":"transparent"}`}}>
            {i<idx?"✓ ":""}{s}
          </div>
        ))}
      </div>
      <div style={{height:5,background:C.border,borderRadius:3,overflow:"hidden",marginBottom:12}}>
        <div style={{height:"100%",borderRadius:3,
          background:`linear-gradient(90deg,${C.accent},${C.accent2})`,
          width:`${pct}%`,transition:"width .5s ease"}}/>
      </div>
      <div style={{fontSize:13,color:C.sub,marginBottom:12}} className="pulse">{status.message}</div>
      {status.scraper_results&&Object.keys(status.scraper_results).length>0&&(
        <div style={{display:"flex",gap:8,flexWrap:"wrap"}}>
          {Object.entries(status.scraper_results).map(([src,cnt])=>(
            <div key={src} style={{background:C.bg,border:`1px solid ${C.border}`,borderRadius:7,padding:"5px 10px",fontSize:12}}>
              {icons[src]||"🔍"} {src}: <strong style={{color:C.accent}}>{cnt}</strong>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}


// ─────────────────────────────────────────────────────────────
// MODULE SPLIT VIEW
// Splits already-scraped items by module — no new scraping
// ─────────────────────────────────────────────────────────────

const SIGNAL_COLORS_MAP = {
  "Pain Signal":       "#f75f5f",
  "Buyer Signal":      "#34c98e",
  "Competitor Signal": "#f7a94f",
  "Timing Signal":     "#4f8ef7",
  "Validation Signal": "#a78bfa",
  "Market Data":       "#38bdf8",
};
const VERDICT_BAR = { HIGH:"#34c98e", MEDIUM:"#f7a94f", LOW:"#f75f5f" };
const BAR_COLORS  = ["#4f8ef7","#34c98e","#f7a94f","#f75f5f","#a78bfa","#38bdf8","#fb923c","#a3e635"];

function ModuleSplitView({ moduleSplit, expandedMod, setExpandedMod, onModuleClick, subDomain }) {
  if (!moduleSplit) return (
    <div style={{display:"flex",alignItems:"center",gap:10,color:C.sub,fontSize:13,padding:"24px 0"}}>
      <div className="spinner"/> Splitting scraped data by module…
    </div>
  );

  const { modules=[], unmatched=[], total_items=0, total_matched=0 } = moduleSplit;

  if (!modules.length) return (
    <div style={{background:C.panel,border:`1px solid ${C.border}`,borderRadius:10,padding:24,textAlign:"center"}}>
      <div style={{fontSize:32,marginBottom:8}}>📭</div>
      <div style={{color:C.sub,fontSize:13}}>No module matches found in {total_items} scraped items.</div>
      <div style={{color:C.muted,fontSize:12,marginTop:6}}>
        Try a more specific query like "SAP S4HANA demand" or "SAP ABAP jobs".
      </div>
    </div>
  );

  const maxCount = modules[0]?.count || 1;

  return (
    <div style={{display:"flex",flexDirection:"column",gap:0}}>
      {/* Header */}
      <div style={{marginBottom:16}}>
        <h3 style={{fontSize:15,fontWeight:600,color:C.text,marginBottom:4}}>
          {subDomain} — Demand Split by Module
        </h3>
        <p style={{fontSize:12,color:C.sub}}>
          {total_matched} of {total_items} scraped items matched across {modules.length} modules.
          Click a module to see its sources. Click the name to deep-dive.
        </p>
      </div>

      {/* SVG BAR CHART — all modules overview */}
      <div className="card" style={{padding:"20px 20px 12px",marginBottom:16}}>
        <div style={{fontSize:11,fontWeight:700,color:C.muted,textTransform:"uppercase",
          letterSpacing:.5,marginBottom:14}}>Overview — Items per Module</div>
        <div style={{display:"flex",flexDirection:"column",gap:10}}>
          {modules.map((m, i) => (
            <div key={m.name}
              onClick={() => setExpandedMod(expandedMod === m.name ? null : m.name)}
              style={{cursor:"pointer"}}
            >
              <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:4}}>
                <div style={{display:"flex",alignItems:"center",gap:6}}>
                  <span style={{fontSize:16}}>{m.emoji}</span>
                  <span style={{
                    fontSize:13,fontWeight:500,color:C.text,
                    textDecoration:"underline dotted",textUnderlineOffset:3,
                  }}>{m.name}</span>
                </div>
                <div style={{display:"flex",alignItems:"center",gap:8}}>
                  <span style={{
                    fontSize:10,fontWeight:700,padding:"2px 7px",borderRadius:20,
                    background:VERDICT_BAR[m.verdict]+"22",color:VERDICT_BAR[m.verdict],
                  }}>{m.verdict}</span>
                  <span style={{fontSize:11,color:C.sub,fontFamily:"JetBrains Mono,monospace",
                    minWidth:60,textAlign:"right"}}>
                    {m.count} item{m.count!==1?"s":""} · {m.share}%
                  </span>
                  <span style={{fontSize:10,color:C.muted}}>
                    {expandedMod===m.name ? "▲" : "▼"}
                  </span>
                </div>
              </div>
              {/* Bar */}
              <div style={{height:7,background:C.border,borderRadius:4,overflow:"hidden"}}>
                <div style={{
                  height:"100%",borderRadius:4,
                  background:BAR_COLORS[i%BAR_COLORS.length],
                  width:`${(m.count/maxCount)*100}%`,
                  transition:"width 0.9s cubic-bezier(.4,0,.2,1)",
                }}/>
              </div>
              {/* Signal pill row */}
              {m.signals && Object.keys(m.signals).length > 0 && (
                <div style={{display:"flex",gap:5,marginTop:5,flexWrap:"wrap"}}>
                  {Object.entries(m.signals).map(([sig,cnt])=>(
                    <span key={sig} style={{
                      fontSize:10,padding:"1px 7px",borderRadius:20,
                      background:(SIGNAL_COLORS_MAP[sig]||C.muted)+"18",
                      color:SIGNAL_COLORS_MAP[sig]||C.muted,
                    }}>{sig}: {cnt}</span>
                  ))}
                </div>
              )}

              {/* Expanded items list */}
              {expandedMod === m.name && m.items?.length > 0 && (
                <div style={{
                  marginTop:10,borderTop:`1px solid ${C.border}`,
                  paddingTop:10,display:"flex",flexDirection:"column",gap:7,
                  animation:"fadeUp .3s ease both",
                }}>
                  {m.items.map((item, j) => (
                    <ModuleSplitItem key={item.id||j} item={item} onDeepDive={onModuleClick} moduleName={m.name}/>
                  ))}
                  {/* Deep-dive button */}
                  <button
                    onClick={e=>{e.stopPropagation();onModuleClick(m.name);}}
                    style={{
                      background:C.accent+"18",border:`1px solid ${C.accent}44`,
                      color:C.accent,borderRadius:8,padding:"7px 14px",
                      fontSize:12,fontWeight:600,cursor:"pointer",marginTop:4,
                      fontFamily:"Space Grotesk,sans-serif",transition:"all .2s",
                    }}
                    onMouseEnter={e=>e.target.style.background=C.accent+"33"}
                    onMouseLeave={e=>e.target.style.background=C.accent+"18"}
                  >
                    🔍 Deep-dive: search {m.name} specifically →
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Unmatched items */}
      {unmatched?.length > 0 && (
        <div className="card" style={{padding:"14px 18px"}}>
          <div style={{fontSize:11,fontWeight:700,color:C.muted,textTransform:"uppercase",
            letterSpacing:.5,marginBottom:10}}>
            General SAP Items ({unmatched.length}) — no specific module match
          </div>
          <div style={{display:"flex",flexDirection:"column",gap:6}}>
            {unmatched.map((item,i)=>(
              <ModuleSplitItem key={item.id||i} item={item}/>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function ModuleSplitItem({ item, onDeepDive, moduleName }) {
  const url     = item.url || "";
  const isReal  = url.startsWith("http") && !url.includes("localhost");
  const sig     = item.signal_type || "";
  const color   = SIGNAL_COLORS_MAP[sig] || C.muted;
  let domain = "";
  try { if(isReal) domain = new URL(url).hostname.replace("www.",""); } catch(_){}

  const typeIcon = {
    reddit_post:"💬", news_article:"📰", web_page:"🌐",
    financial:"📊", job_postings:"💼", trend:"📈",
  }[item.item_type] || "🔗";

  return (
    <div style={{
      display:"flex",gap:9,padding:"8px 10px",borderRadius:7,
      border:`1px solid ${C.border}`,background:C.bg,
      transition:"border-color .15s",
    }}
      onMouseEnter={e=>e.currentTarget.style.borderColor=C.accent+"55"}
      onMouseLeave={e=>e.currentTarget.style.borderColor=C.border}
    >
      <span style={{fontSize:15,flexShrink:0,marginTop:1}}>{typeIcon}</span>
      <div style={{flex:1,minWidth:0}}>
        {isReal
          ? <a href={url} target="_blank" rel="noopener noreferrer"
              style={{fontSize:12,fontWeight:500,color:C.accent,display:"block",
                overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>
              {item.title || domain}
            </a>
          : <span style={{fontSize:12,fontWeight:500,color:C.text,display:"block",
              overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>
              {item.title || "(no title)"}
            </span>
        }
        <div style={{display:"flex",gap:6,marginTop:3,flexWrap:"wrap",alignItems:"center"}}>
          {sig && <span style={{fontSize:10,padding:"1px 6px",borderRadius:20,
            background:color+"18",color}}>{sig}</span>}
          {domain && <span style={{fontSize:10,color:C.muted}}>{domain}</span>}
          {item.upvotes > 0 && <span style={{fontSize:10,color:C.muted}}>▲{item.upvotes}</span>}
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// MAIN APP
// ─────────────────────────────────────────────────────────────
export default function App() {
  const [query,     setQuery]     = useState("");
  const [jobId,     setJobId]     = useState(null);
  const [status,    setStatus]    = useState(null);
  const [result,    setResult]    = useState(null);
  const [error,     setError]     = useState(null);
  const [loading,   setLoading]   = useState(false);
  const [tab,       setTab]       = useState("modules");
  const [sigFilter, setSigFilter] = useState("All");
  const [timeline,  setTimeline]  = useState(null);
  const [locations, setLocations] = useState(null);
  const [modules,   setModules]   = useState(null);
  const [moduleSplit,setModuleSplit]= useState(null);
  const [expandedMod,setExpandedMod]= useState(null); // which module is expanded
  const [chatOpen,  setChatOpen]  = useState(false);
  const pollRef = useRef(null);

  const startPoll = useCallback((jid) => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const s = await fetch(`${API}/api/search/status/${jid}`).then(r=>r.json());
        setStatus(s);
        if (s.is_done) {
          clearInterval(pollRef.current);
          if (s.status==="complete") {
            const res = await fetch(`${API}/api/search/result/${jid}`).then(r=>r.json());
            setResult(res.result);
            setLoading(false);
            const qEnc = encodeURIComponent(res.result?.query || query);
            fetch(`${API}/api/timeline/${qEnc}`).then(r=>r.json()).then(setTimeline);
            fetch(`${API}/api/locations/${qEnc}`).then(r=>r.json()).then(setLocations);
            const domain = res.result?.primary_domain || "";
            const sub = res.result?.sub_domain || "";
            fetch(`${API}/api/modules/${qEnc}?domain=${encodeURIComponent(domain)}&sub=${encodeURIComponent(sub)}`).then(r=>r.json()).then(setModules);
            fetch(`${API}/api/module-split/${qEnc}?domain=${encodeURIComponent(domain)}&sub=${encodeURIComponent(sub)}`).then(r=>r.json()).then(setModuleSplit);
          } else {
            setError(s.error||"Search failed");
            setLoading(false);
          }
        }
      } catch(e){ console.error(e); }
    }, 1500);
  }, [query]);

  useEffect(()=>()=>clearInterval(pollRef.current),[]);

  const handleSearch = async (e) => {
    e?.preventDefault();
    if (!query.trim()||loading) return;
    setLoading(true); setResult(null); setError(null);
    setStatus(null); setTimeline(null); setLocations(null); setModules(null);
    setTab("modules"); setChatOpen(false); setModuleSplit(null); setExpandedMod(null);
    try {
      const res = await fetch(`${API}/api/search`,{
        method:"POST", headers:{"Content-Type":"application/json"},
        body:JSON.stringify({query:query.trim(),force_refresh:false}),
      }).then(r=>r.json());
      setJobId(res.job_id);
      startPoll(res.job_id);
    } catch(e){
      setError("Could not connect to server. Is it running on port 8000?");
      setLoading(false);
    }
  };

  // Handle clicking a module → run new search for that module
  const handleModuleClick = (moduleName) => {
    // Build a search query from the module name and current query context
    const primaryDomain = result?.primary_domain || "";
    const subDomain = result?.sub_domain || "";
    // Use the sub-domain name as context prefix if it's short enough
    const prefix = subDomain && subDomain.length < 30 ? subDomain.split(" ")[0] : primaryDomain.split(" ")[0];
    const newQuery = `${prefix} ${moduleName} demand`.trim();
    setQuery(newQuery);
    // Auto-submit after short delay
    setTimeout(() => {
      document.querySelector("form")?.dispatchEvent(new Event("submit", {bubbles:true}));
    }, 100);
  };

  const evidence = result?.evidence||[];
  const signals  = ["All",...new Set(evidence.map(e=>e.signal_type).filter(Boolean))];
  const filtered = sigFilter==="All" ? evidence : evidence.filter(e=>e.signal_type===sigFilter);
  const seen=new Set();
  const dedupedEvidence = filtered.filter(item=>{
    if(!item.url||seen.has(item.url)) return false;
    seen.add(item.url); return true;
  });
  const ds = result?.demand_score;

  return (
    <div style={{display:"flex",minHeight:"100vh"}}>
      {/* ── MAIN CONTENT ─────────────────────────────── */}
      <div style={{
        flex:1, maxWidth: chatOpen ? "calc(100vw - 380px)" : "960px",
        margin:"0 auto", padding:"32px 16px",
        transition:"max-width .3s ease",
      }}>
        {/* Header */}
        <div style={{marginBottom:32,textAlign:"center"}} className="fade-up">
          <h1 style={{
            fontSize:"clamp(22px,4vw,38px)",fontWeight:700,letterSpacing:-1,marginBottom:6,
            background:`linear-gradient(135deg,${C.accent},${C.accent2})`,
            WebkitBackgroundClip:"text",WebkitTextFillColor:"transparent",
          }}>Global Demand Analyser</h1>
          <p style={{color:C.sub,fontSize:13}}>
            Real-time demand intelligence from Reddit · News · Trends · Screener · Web
          </p>
        </div>

        {/* Search */}
        <form onSubmit={handleSearch} style={{display:"flex",gap:10,marginBottom:24}}>
          <input value={query} onChange={e=>setQuery(e.target.value)}
            placeholder="e.g. Is there demand for SAP, AI, Fintech — I'll show which sub-areas have demand"
            disabled={loading}
            style={{flex:1,background:C.panel,border:`1px solid ${C.border}`,borderRadius:10,
              padding:"12px 16px",fontSize:14,color:C.text,outline:"none",
              fontFamily:"Space Grotesk,sans-serif",transition:"border-color .2s"}}
            onFocus={e=>e.target.style.borderColor=C.accent}
            onBlur={e=>e.target.style.borderColor=C.border}/>
          <button type="submit" disabled={loading||!query.trim()} style={{
            background:loading?C.muted:`linear-gradient(135deg,${C.accent},#3a7bd5)`,
            color:"#fff",border:"none",borderRadius:10,padding:"12px 24px",
            fontSize:14,fontWeight:600,cursor:loading?"not-allowed":"pointer",
            fontFamily:"Space Grotesk,sans-serif",whiteSpace:"nowrap"}}>
            {loading?"Analysing…":"Analyse →"}
          </button>
          {result && (
            <button type="button" onClick={()=>setChatOpen(o=>!o)} style={{
              background:chatOpen?C.accent+"22":C.panel,
              border:`1px solid ${chatOpen?C.accent:C.border}`,
              color:chatOpen?C.accent:C.sub,
              borderRadius:10,padding:"12px 18px",fontSize:14,fontWeight:600,
              cursor:"pointer",fontFamily:"Space Grotesk,sans-serif",whiteSpace:"nowrap",
              transition:"all .2s",
            }}>
              {chatOpen?"Close Chat":"💬 Ask AI"}
            </button>
          )}
        </form>

        {loading&&status&&<ProgressOverlay status={status}/>}
        {error&&<div style={{background:"#2e0d0d",border:`1px solid ${C.danger}44`,borderRadius:10,padding:16,color:C.danger,fontSize:14}}>⚠ {error}</div>}

        {result&&(
          <div style={{display:"flex",flexDirection:"column",gap:20}} className="fade-up">

            {/* Score + signals */}
            <div style={{display:"flex",gap:20,flexWrap:"wrap"}}>
              {ds&&(
                <div className="card" style={{padding:24,display:"flex",flexDirection:"column",alignItems:"center",gap:16,minWidth:200}}>
                  <ScoreRing score={ds.overall} verdict={ds.verdict}/>
                  <div style={{fontSize:12,color:C.sub,textAlign:"center"}}>
                    <strong style={{color:C.text}}>Domain:</strong> {result.primary_domain}
                    <br/><strong style={{color:C.text}}>Sub:</strong> {result.sub_domain || Object.values(result.domains||{})[0]?.sub_domains?.[0] || ""}
                  </div>
                </div>
              )}
              {ds&&(
                <div className="card" style={{flex:1,padding:24,minWidth:280}}>
                  <h3 style={{fontSize:13,fontWeight:600,marginBottom:14,color:C.sub,textTransform:"uppercase",letterSpacing:.5}}>Signal Breakdown</h3>
                  <SignalBars signals={ds.signals}/>
                  <div style={{borderTop:`1px solid ${C.border}`,marginTop:14,paddingTop:14,display:"flex",gap:12,flexWrap:"wrap"}}>
                    {ds.why_demand&&<div style={{flex:1,minWidth:180}}>
                      <div style={{fontSize:11,color:C.accent2,fontWeight:700,marginBottom:4}}>WHY DEMAND EXISTS</div>
                      <div style={{fontSize:12,color:C.sub,lineHeight:1.6}}>{ds.why_demand}</div>
                    </div>}
                    {ds.why_no_demand&&<div style={{flex:1,minWidth:180}}>
                      <div style={{fontSize:11,color:C.warn,fontWeight:700,marginBottom:4}}>RISKS / GAPS</div>
                      <div style={{fontSize:12,color:C.sub,lineHeight:1.6}}>{ds.why_no_demand}</div>
                    </div>}
                  </div>
                  {ds.key_evidence?.length>0&&(
                    <div style={{marginTop:12}}>
                      <div style={{fontSize:11,color:C.muted,fontWeight:700,marginBottom:5}}>KEY EVIDENCE</div>
                      {ds.key_evidence.map((e,i)=>(
                        <div key={i} style={{fontSize:12,color:C.sub,padding:"2px 0",display:"flex",gap:6,alignItems:"flex-start"}}>
                          <span style={{color:C.accent,flexShrink:0}}>›</span>{e}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Stats strip */}
            <div style={{display:"flex",gap:10,flexWrap:"wrap"}}>
              {[
                {label:"Items Collected",val:result.total_collected || evidence.length},
                {label:"Evidence Items",val:evidence.length},
                {label:"Sub-areas Found",val:modules?.modules?.length||"—"},
                {label:"Domain Confidence",val:`${Object.values(result.domains||{})[0]?.confidence||0}%`},
              ].map(({label,val})=>(
                <div key={label} className="card" style={{padding:"11px 16px",textAlign:"center",flex:1,minWidth:110}}>
                  <div style={{fontSize:20,fontWeight:700,color:C.accent,fontFamily:"JetBrains Mono,monospace"}}>{val}</div>
                  <div style={{fontSize:11,color:C.sub,marginTop:2}}>{label}</div>
                </div>
              ))}
            </div>

            {/* Tabs */}
            <div style={{display:"flex",gap:6,flexWrap:"wrap",borderBottom:`1px solid ${C.border}`,paddingBottom:10}}>
              {[
                {id:"modules",  label:`🔧 Sub-area Breakdown${modules?.modules?.length?` (${modules.modules.length})`:""}` },
                {id:"sources",  label:`📋 Sources (${dedupedEvidence.length})`},
                {id:"locations",label:"🌍 Regional Demand"},
                {id:"timeline", label:"📈 6-Month Trend"},
              ].map(t=>(
                <button key={t.id} className={`tab-btn ${tab===t.id?"active":""}`} onClick={()=>setTab(t.id)}>
                  {t.label}
                </button>
              ))}
            </div>

            {/* ── MODULE BREAKDOWN TAB (default) ────────── */}
            {tab==="modules"&&(
              <div>
                <div style={{marginBottom:16}}>
                  <h3 style={{fontSize:15,fontWeight:600,color:C.text,marginBottom:4}}>
                    {result.sub_domain || Object.values(result.domains||{})[0]?.sub_domains?.[0] || result.primary_domain} — Demand by Sub-area
                  </h3>
                  <p style={{fontSize:12,color:C.sub}}>
                    Automatically detected from scraped Reddit posts, news articles and reports.
                    Click any sub-area to run a deep-dive search.
                  </p>
                </div>
                {modules ? (
                  modules.modules?.length > 0 ? (
                    <ModuleBreakdown modules={modules.modules} onModuleClick={handleModuleClick}/>
                  ) : (
                    <div style={{
                      background:C.panel,border:`1px solid ${C.border}`,
                      borderRadius:10,padding:24,textAlign:"center",color:C.sub,fontSize:13,
                    }}>
                      No specific sub-area mentions detected yet for {result.sub_domain || result.primary_domain}. Try clearing cache and running a fresh search.
                      <br/>Try a more specific query to get sub-area breakdown.
                    </div>
                  )
                ) : (
                  <div style={{display:"flex",alignItems:"center",gap:10,color:C.sub,fontSize:13}}>
                    <div className="spinner"/> Loading module analysis…
                  </div>
                )}
              </div>
            )}

            {/* ── SOURCES TAB ─────────────────────────────── */}
            {tab==="sources"&&(
              <div>
                <div style={{display:"flex",gap:6,flexWrap:"wrap",marginBottom:14}}>
                  {signals.map(s=>(
                    <button key={s} onClick={()=>setSigFilter(s)} style={{
                      padding:"4px 12px",borderRadius:20,fontSize:12,fontWeight:500,
                      cursor:"pointer",border:`1px solid ${sigFilter===s?(SIGNAL_COLORS[s]||C.accent):C.border}`,
                      background:sigFilter===s?(SIGNAL_COLORS[s]||C.accent)+"22":"transparent",
                      color:sigFilter===s?(SIGNAL_COLORS[s]||C.accent):C.sub,transition:"all .2s",
                    }}>{s}</button>
                  ))}
                </div>
                <div style={{display:"flex",flexDirection:"column",gap:8}}>
                  {dedupedEvidence.length===0
                    ? <div style={{color:C.sub,fontSize:13,padding:"16px 0"}}>No sources for this filter.</div>
                    : dedupedEvidence.map(item=><SourceCard key={item.id} item={item}/>)
                  }
                </div>
              </div>
            )}

            {/* ── LOCATIONS TAB ───────────────────────────── */}
            {tab==="locations"&&(
              <div className="card" style={{padding:24}}>
                <h3 style={{fontSize:13,fontWeight:600,color:C.sub,textTransform:"uppercase",letterSpacing:.5,marginBottom:4}}>
                  Regional Demand Distribution
                </h3>
                <p style={{fontSize:12,color:C.muted,marginBottom:18}}>
                  Regions mentioned across all collected evidence
                </p>
                {locations
                  ? <LocationChart regions={locations.regions}/>
                  : <div style={{display:"flex",alignItems:"center",gap:10,color:C.sub,fontSize:13}}><div className="spinner"/>Loading…</div>
                }
                {locations?.total_mentions>0&&(
                  <div style={{marginTop:14,fontSize:12,color:C.muted}}>
                    Total: <strong style={{color:C.text}}>{locations.total_mentions}</strong> mentions across {locations.regions?.length} regions
                  </div>
                )}
              </div>
            )}

            {/* ── TIMELINE TAB ────────────────────────────── */}
            {tab==="timeline"&&(
              <div className="card" style={{padding:24}}>
                <h3 style={{fontSize:13,fontWeight:600,color:C.sub,textTransform:"uppercase",letterSpacing:.5,marginBottom:4}}>
                  Past 6 Months — Evidence Activity
                </h3>
                <p style={{fontSize:12,color:C.muted,marginBottom:18}}>
                  Monthly count of articles, posts and reports collected
                </p>
                {timeline
                  ? timeline.labels?.length>0
                    ? <LineChart labels={timeline.labels} series={timeline.series}/>
                    : <div style={{color:C.sub,fontSize:13}}>Not enough dated evidence yet.</div>
                  : <div style={{display:"flex",alignItems:"center",gap:10,color:C.sub,fontSize:13}}><div className="spinner"/>Loading…</div>
                }
              </div>
            )}

          </div>
        )}

        {/* Empty state */}
        {!loading&&!result&&!error&&(
          <div style={{textAlign:"center",padding:"60px 0",color:C.muted}}>
            <div style={{fontSize:48,marginBottom:12}}>🔍</div>
            <div style={{fontSize:14,color:C.sub}}>Type any query — I'll automatically show which sub-areas have demand</div>
            <div style={{fontSize:12,marginTop:8,color:C.muted}}>
              Try: "is there demand for SAP" · "AI tools in healthcare" · "Fintech demand in India"
            </div>
          </div>
        )}
      </div>

      {/* ── CHAT SIDEBAR ─────────────────────────────── */}
      <ChatSidebar
        query={result?.query || ""}
        domain={result?.primary_domain || ""}
        isOpen={chatOpen}
        onClose={() => setChatOpen(false)}
      />
    </div>
  );
}

const root = createRoot(document.getElementById("root"));
root.render(<App />);
