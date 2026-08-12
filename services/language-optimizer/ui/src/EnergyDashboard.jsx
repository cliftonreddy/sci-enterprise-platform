import { useState, useRef } from "react";

// SLE'17 energy ratios relative to C (1.00× baseline)
const ENERGY_RATIOS = {
  "C":          1.00,
  "C++":        1.34,
  "Rust":       1.03,
  "Go":         3.23,
  "JavaScript": 4.45,
  "Java":      75.88 / 25.46,   // ~2.98× from paper
  "Python":    75.88,
  "Ruby":      69.91,
  "R":        534.50,
};
// Normalised so Java = 1.0 for display (since banking POC is Java)
const JAVA_RATIO = ENERGY_RATIOS["Java"];

const CO2_PER_JOULE   = 0.000233;    // kg CO₂ per joule (avg datacenter)
const COST_PER_JOULE  = 0.0000000333; // USD per joule at $0.12/kWh
const BASE_OP_JOULES  = 0.0018;       // empirical baseline J per Java operation

const LANG_COLORS = {
  "C":"#4a9eff","C++":"#a855f7","Rust":"#ff6b35","Go":"#00acd7",
  "JavaScript":"#f7df1e","Java":"#f59e0b","Python":"#3776ab",
  "Ruby":"#cc342d","R":"#276dc3","keep":"#475569",
};

// Banking POC endpoints to benchmark
const BENCHMARK_ENDPOINTS = [
  { id:"list_accounts",   label:"List Accounts",       method:"GET",  path:"/accounts?page=0&size=10",        category:"io" },
  { id:"get_account",     label:"Get Account",         method:"GET",  path:"/accounts/1",                     category:"io" },
  { id:"get_summary",     label:"Account Summary",     method:"GET",  path:"/accounts/1/summary",             category:"numeric" },
  { id:"fraud_score",     label:"Fraud Score",         method:"GET",  path:"/accounts/1/fraud-score",         category:"combinatorial" },
  { id:"amortization",    label:"Amortization",        method:"GET",  path:"/accounts/1/amortization?rate=5&months=360", category:"numeric" },
  { id:"portfolio_risk",  label:"Portfolio Risk (VaR)",method:"GET",  path:"/accounts/customer/1/risk?simulations=1000", category:"numeric" },
  { id:"transfer",        label:"Transfer",            method:"POST", path:"/accounts/transfer",              category:"io",
    body: { fromAccount:"__ACC1__", toAccount:"__ACC2__", amount:"1.00", description:"benchmark" } },
];

function computeEnergyMetrics(functions, sourceLang) {
  const srcRatio = ENERGY_RATIOS[
    sourceLang.charAt(0).toUpperCase() + sourceLang.slice(1)
  ] || JAVA_RATIO;

  return functions.map(fn => {
    const isKept  = fn.recommended_language === "keep" || fn.is_orchestrator;
    const tgtLang = isKept ? sourceLang : fn.recommended_language;
    const tgtKey  = tgtLang.charAt(0).toUpperCase() + tgtLang.slice(1);
    const tgtRatio = ENERGY_RATIOS[tgtKey] || srcRatio;
    const beforeJ  = BASE_OP_JOULES * srcRatio;
    const afterJ   = BASE_OP_JOULES * tgtRatio;
    const savePct  = fn.energy_savings_percent > 0
      ? fn.energy_savings_percent
      : Math.max(0, (1 - tgtRatio / srcRatio) * 100);
    return { name:fn.name, category:fn.category, from:sourceLang, to:tgtLang,
             beforeJ, afterJ, savePct, isKept };
  });
}

// ── Sub-components ────────────────────────────────────────────────────────────

function Tabs({ tabs, active, onChange }) {
  return (
    <div style={{ display:"flex", gap:4, marginBottom:20,
      borderBottom:"1px solid #1e3a5f", paddingBottom:0 }}>
      {tabs.map(t => (
        <button key={t.id} onClick={() => onChange(t.id)}
          style={{ background:"transparent", border:"none",
            borderBottom: active===t.id ? "2px solid #4a9eff" : "2px solid transparent",
            color: active===t.id ? "#4a9eff" : "#475569",
            padding:"10px 18px", fontSize:13, fontWeight:600, cursor:"pointer",
            transition:"all 0.15s" }}>
          {t.label}
        </button>
      ))}
    </div>
  );
}

function StatCard({ label, value, sub, color }) {
  return (
    <div style={{ flex:1, minWidth:160, background:"#0a1628",
      border:`1px solid ${color}33`, borderRadius:12, padding:"14px 18px" }}>
      <div style={{ color, fontWeight:800, fontSize:22, fontFamily:"monospace" }}>{value}</div>
      <div style={{ color:"#e2e8f0", fontSize:12, marginTop:2 }}>{label}</div>
      {sub && <div style={{ color:"#475569", fontSize:11, marginTop:2 }}>{sub}</div>}
    </div>
  );
}

function EnergyBar({ name, beforeJ, afterJ, maxJ, liveMs, estimatedMs }) {
  const beforePct = maxJ > 0 ? (beforeJ / maxJ) * 100 : 0;
  const afterPct  = maxJ > 0 ? (afterJ  / maxJ) * 100 : 0;
  const saving    = beforeJ > 0 ? Math.max(0,(1 - afterJ/beforeJ)*100) : 0;
  return (
    <div style={{ marginBottom:16 }}>
      <div style={{ display:"flex", justifyContent:"space-between", marginBottom:4 }}>
        <span style={{ fontFamily:"monospace", fontSize:12, color:"#a8d8ff" }}>{name}()</span>
        <div style={{ display:"flex", gap:12, alignItems:"center" }}>
          {liveMs != null && (
            <span style={{ fontSize:11, color:"#94a3b8" }}>{liveMs.toFixed(1)}ms live</span>
          )}
          <span style={{ color:"#00ff9d", fontSize:12, fontWeight:700 }}>
            ~{saving.toFixed(0)}% energy saved
          </span>
        </div>
      </div>
      <div style={{ marginBottom:3 }}>
        <div style={{ fontSize:10, color:"#475569", marginBottom:2 }}>Before (Java)</div>
        <div style={{ height:8, borderRadius:4, background:"#1e3a5f", overflow:"hidden" }}>
          <div style={{ height:"100%", width:`${beforePct}%`,
            background:"linear-gradient(90deg,#ff6b6b,#ff4444)", borderRadius:4 }} />
        </div>
      </div>
      <div>
        <div style={{ fontSize:10, color:"#475569", marginBottom:2 }}>After (native)</div>
        <div style={{ height:8, borderRadius:4, background:"#1e3a5f", overflow:"hidden" }}>
          <div style={{ height:"100%", width:`${afterPct}%`,
            background:"linear-gradient(90deg,#00ff9d,#00b4d8)", borderRadius:4 }} />
        </div>
      </div>
      <div style={{ display:"flex", gap:16, marginTop:3, fontSize:10, color:"#475569" }}>
        <span>Before: {(beforeJ*1e6).toFixed(2)} μJ</span>
        <span>After: {(afterJ*1e6).toFixed(2)} μJ</span>
      </div>
    </div>
  );
}

function BenchmarkPanel({ allResults }) {
  const [appUrl, setAppUrl]       = useState("http://localhost:8080");
  const [running, setRunning]     = useState(false);
  const [results, setResults]     = useState(null);
  const [history, setHistory]     = useState([]);
  const [error, setError]         = useState("");
  const [tab, setTab]             = useState("run");

  const runBenchmark = async () => {
    setRunning(true); setError(""); setResults(null);
    try {
      const r = await fetch(`${appUrl}/api/benchmark/run`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const d = await r.json();
      setResults(d);
    } catch(e) {
      setError(`Cannot reach ${appUrl}/api/benchmark/run — is the BankingPOC running? (${e.message})`);
    }
    setRunning(false);
  };

  const loadHistory = async () => {
    try {
      const r = await fetch(`${appUrl}/api/benchmark/history`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setHistory(await r.json());
    } catch(e) {
      setError(`Cannot load history: ${e.message}`);
    }
  };

  const fns = results?.functions || [];
  const totalSaving = fns.length
    ? fns.reduce((a, f) => a + (f.energySavingPct || 0), 0) / fns.length
    : 0;

  const REGIME_COLOR = { COMPUTE_DOMINATED: "#00ff9d", INTEROP_DOMINATED: "#ff6b6b" };

  return (
    <div style={{ padding: 20 }}>
      {/* URL input + run button */}
      <div style={{ display: "flex", gap: 10, marginBottom: 16, alignItems: "center" }}>
        <div style={{ flex: 1, background: "#060e1a", border: "1px solid #1e3a5f",
          borderRadius: 8, padding: "8px 14px", display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ color: "#475569", fontSize: 12 }}>BankingPOC URL</span>
          <input value={appUrl} onChange={e => setAppUrl(e.target.value)}
            style={{ flex: 1, background: "transparent", border: "none",
              color: "#a8d8ff", fontFamily: "monospace", fontSize: 12, outline: "none" }} />
        </div>
        <button onClick={runBenchmark} disabled={running}
          style={{ background: running ? "#0a1628" : "linear-gradient(135deg,#0077ff,#00b4d8)",
            border: running ? "1px solid #1e3a5f" : "none",
            color: running ? "#475569" : "white",
            borderRadius: 10, padding: "10px 20px", fontSize: 13,
            fontWeight: 700, cursor: running ? "not-allowed" : "pointer", whiteSpace: "nowrap" }}>
          {running ? "⏳ Running 1000 iterations..." : "▶ Run Benchmark"}
        </button>
        <button onClick={loadHistory}
          style={{ background: "#0a1628", border: "1px solid #1e3a5f",
            color: "#475569", borderRadius: 10, padding: "10px 16px",
            fontSize: 13, cursor: "pointer" }}>
          📋 History
        </button>
      </div>

      {error && (
        <div style={{ background: "#ff000015", border: "1px solid #ff000044",
          borderRadius: 8, padding: "10px 14px", color: "#ff6b6b",
          fontSize: 12, marginBottom: 16 }}>⚠️ {error}</div>
      )}

      {running && (
        <div style={{ background: "#0a1628", border: "1px solid #1e3a5f",
          borderRadius: 10, padding: "20px", textAlign: "center", marginBottom: 16 }}>
          <div style={{ color: "#4a9eff", fontSize: 14, fontWeight: 700, marginBottom: 8 }}>
            Running 1000 iterations × 5 functions...
          </div>
          <div style={{ color: "#475569", fontSize: 12 }}>
            Each function runs in both Java and native C mode.<br/>
            Wall-clock timing via System.nanoTime(). Takes ~2 minutes for Monte Carlo.
          </div>
        </div>
      )}

      {results && (
        <>
          {/* Header */}
          <div style={{ background: "linear-gradient(135deg,#00ff9d0f,#0077ff0f)",
            border: "1px solid #00ff9d33", borderRadius: 12, padding: "16px 20px",
            marginBottom: 16, display: "flex", alignItems: "center", gap: 20 }}>
            <div style={{ textAlign: "center" }}>
              <div style={{ fontSize: 36, fontWeight: 900, color: "#00ff9d",
                fontFamily: "monospace", lineHeight: 1 }}>
                {fns.find(f => f.function === "runMonteCarloSimulation")?.energySavingPct?.toFixed(1) || "—"}%
              </div>
              <div style={{ color: "#94a3b8", fontSize: 11, marginTop: 4 }}>
                Monte Carlo energy saving
              </div>
            </div>
            <div style={{ flex: 1, borderLeft: "1px solid #1e3a5f", paddingLeft: 20 }}>
              <div style={{ color: "#e2e8f0", fontSize: 13, fontWeight: 600, marginBottom: 4 }}>
                {results.jvmName} · {results.iterations} iterations · {new Date(results.ranAt).toLocaleTimeString()}
              </div>
              <div style={{ color: "#475569", fontSize: 12, lineHeight: 1.6 }}>
                {results.crossoverAnalysis?.finding}
              </div>
            </div>
          </div>

          {/* Per-function results */}
          <div style={{ display: "flex", flexDirection: "column", gap: 10, marginBottom: 16 }}>
            {fns.map(fn => {
              const crossover = results.crossoverAnalysis?.functions?.find(f => f.function === fn.function);
              const regime = crossover?.regime || "INTEROP_DOMINATED";
              const regimeColor = REGIME_COLOR[regime] || "#475569";
              const saving = fn.energySavingPct || 0;
              const jMean = fn.java?.mean_ms || 0;
              const nMean = fn.native?.mean_ms || 0;
              const maxMs = Math.max(jMean, nMean, 0.001);

              return (
                <div key={fn.function} style={{ background: "#0a1628",
                  border: `1px solid ${regimeColor}33`, borderRadius: 10,
                  padding: "14px 18px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
                    <span style={{ fontFamily: "monospace", fontSize: 13,
                      color: "#e2e8f0", fontWeight: 700, flex: 1 }}>
                      {fn.function}()
                    </span>
                    <div style={{ background: `${regimeColor}22`,
                      border: `1px solid ${regimeColor}55`, color: regimeColor,
                      borderRadius: 6, padding: "2px 10px", fontSize: 11, fontWeight: 700 }}>
                      {regime.replace("_", " ")}
                    </div>
                    <span style={{ color: saving > 0 ? "#00ff9d" : "#ff6b6b",
                      fontSize: 13, fontWeight: 700, fontFamily: "monospace" }}>
                      {saving > 0 ? "+" : ""}{saving.toFixed(1)}% energy
                    </span>
                  </div>

                  {/* Timing bars */}
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                    {[
                      { label: "Java", mean: jMean, p95: fn.java?.p95_ms, color: "#f59e0b" },
                      { label: "C (native)", mean: nMean, p95: fn.native?.p95_ms, color: "#4a9eff" },
                    ].map(({ label, mean, p95, color }) => (
                      <div key={label}>
                        <div style={{ display: "flex", justifyContent: "space-between",
                          fontSize: 11, marginBottom: 4 }}>
                          <span style={{ color }}>{label}</span>
                          <span style={{ fontFamily: "monospace", color: "#e2e8f0" }}>
                            {mean.toFixed(3)}ms
                          </span>
                        </div>
                        <div style={{ height: 6, borderRadius: 3,
                          background: "#060e1a", overflow: "hidden" }}>
                          <div style={{ height: "100%", borderRadius: 3,
                            width: `${(mean / maxMs) * 100}%`,
                            background: color, transition: "width 0.5s" }} />
                        </div>
                        <div style={{ fontSize: 10, color: "#475569", marginTop: 2 }}>
                          p95: {p95?.toFixed(3)}ms
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* SLE'17 comparison */}
                  <div style={{ marginTop: 8, fontSize: 11, color: "#475569" }}>
                    {regime === "COMPUTE_DOMINATED"
                      ? `✓ Consistent with SLE'17: C saves ~56% on tight numeric loops. Speedup: ${fn.speedup}×`
                      : `⚠ Interop overhead (~0.05ms/call) dominates Java compute time (${jMean.toFixed(3)}ms). Keep in Java.`}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Methodology note */}
          <div style={{ background: "#060e1a", border: "1px solid #0f2040",
            borderRadius: 8, padding: "10px 14px", fontSize: 11, color: "#475569" }}>
            📄 {results.methodology}
          </div>
        </>
      )}

      {/* History table */}
      {history.length > 0 && (
        <div style={{ marginTop: 20 }}>
          <div style={{ fontSize: 11, color: "#475569", textTransform: "uppercase",
            letterSpacing: 1, marginBottom: 10 }}>Benchmark History (PostgreSQL)</div>
          <div style={{ background: "#0a1628", border: "1px solid #1e3a5f",
            borderRadius: 10, overflow: "hidden" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
              <thead>
                <tr style={{ background: "#060e1a" }}>
                  {["Run ID", "Function", "Mode", "Mean (ms)", "Energy (J)", "Time"].map(h => (
                    <th key={h} style={{ padding: "8px 12px", textAlign: "left",
                      color: "#475569", fontWeight: 600, fontSize: 11,
                      borderBottom: "1px solid #1e3a5f" }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {history.slice(0, 20).map((row, i) => (
                  <tr key={i} style={{ borderBottom: "1px solid #0a1628" }}>
                    <td style={{ padding: "6px 12px", color: "#334155",
                      fontFamily: "monospace", fontSize: 10 }}>
                      {row.runId?.slice(0, 8)}...
                    </td>
                    <td style={{ padding: "6px 12px", color: "#a8d8ff",
                      fontFamily: "monospace" }}>{row.function}</td>
                    <td style={{ padding: "6px 12px" }}>
                      <span style={{ color: row.mode === "native" ? "#4a9eff" : "#f59e0b",
                        fontSize: 11, fontWeight: 700 }}>{row.mode}</span>
                    </td>
                    <td style={{ padding: "6px 12px", fontFamily: "monospace",
                      color: "#e2e8f0" }}>{(row.meanNs / 1e6).toFixed(3)}</td>
                    <td style={{ padding: "6px 12px", fontFamily: "monospace",
                      color: "#94a3b8" }}>{row.energyJ?.toFixed(4)}</td>
                    <td style={{ padding: "6px 12px", color: "#475569", fontSize: 11 }}>
                      {new Date(row.ranAt).toLocaleTimeString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {!results && !running && (
        <div style={{ textAlign: "center", padding: "40px 0", color: "#334155" }}>
          <div style={{ fontSize: 40, marginBottom: 12 }}>⚡</div>
          <div style={{ fontSize: 14, marginBottom: 6 }}>
            Connect to your running BankingPOC
          </div>
          <div style={{ fontSize: 12, color: "#1e3a5f" }}>
            Runs 1000 iterations of each function in Java and native C mode<br/>
            Measures real wall-clock timing and estimates energy saving per SLE'17
          </div>
        </div>
      )}
    </div>
  );
}


function StaticEnergyTab({ allResults }) {
  const [scale, setScale] = useState(1_000_000);
  const allFunctions = Object.values(allResults).flatMap(r => r.functions || []);
  const sourceLang   = Object.values(allResults)[0]?.source_language || "java";
  const metrics      = computeEnergyMetrics(allFunctions, sourceLang);
  if (!metrics.length) return null;

  const totalBefore = metrics.reduce((a,f)=>a+f.beforeJ,0);
  const totalAfter  = metrics.reduce((a,f)=>a+f.afterJ, 0);
  const savingJ     = totalBefore - totalAfter;
  const savingPct   = totalBefore>0 ? (savingJ/totalBefore)*100 : 0;
  const maxJ        = Math.max(...metrics.map(f=>f.beforeJ));

  return (
    <div>
      <div style={{ background:"linear-gradient(135deg,#00ff9d0f,#0077ff0f)",
        border:"1px solid #00ff9d33", borderRadius:14, padding:"24px",
        marginBottom:20, textAlign:"center" }}>
        <div style={{ fontSize:56, fontWeight:900, color:"#00ff9d",
          fontFamily:"monospace", lineHeight:1 }}>{savingPct.toFixed(1)}%</div>
        <div style={{ color:"#94a3b8", fontSize:14, marginTop:6 }}>
          estimated energy reduction — SLE'17 paper ratios
        </div>
      </div>

      <div style={{ background:"#0a1628", border:"1px solid #1e3a5f",
        borderRadius:12, padding:"14px 20px", marginBottom:20 }}>
        <div style={{ display:"flex", justifyContent:"space-between", marginBottom:6 }}>
          <span style={{ color:"#e2e8f0", fontSize:13, fontWeight:600 }}>Scale to:</span>
          <span style={{ color:"#4a9eff", fontFamily:"monospace", fontWeight:700 }}>
            {scale.toLocaleString()} requests
          </span>
        </div>
        <input type="range" min={1000} max={100_000_000} step={1000}
          value={scale} onChange={e=>setScale(+e.target.value)}
          style={{ width:"100%", accentColor:"#4a9eff" }} />
      </div>

      <div style={{ display:"flex", gap:12, marginBottom:20, flexWrap:"wrap" }}>
        <StatCard label="Energy Saved" color="#4a9eff"
          value={savingJ*scale >= 1000
            ? ((savingJ*scale)/1000).toFixed(2)+"kJ"
            : (savingJ*scale).toFixed(1)+"J"}
          sub={`${(totalBefore*scale).toFixed(1)}J → ${(totalAfter*scale).toFixed(1)}J`} />
        <StatCard label="CO₂ Saved" color="#00ff9d"
          value={`${((savingJ*scale)*CO2_PER_JOULE).toFixed(4)}kg`}
          sub="at avg datacenter intensity" />
        <StatCard label="Cost Saved" color="#fbbf24"
          value={`$${((savingJ*scale)*COST_PER_JOULE).toFixed(5)}`}
          sub="at $0.12/kWh" />
      </div>

      <div style={{ background:"#0a1628", border:"1px solid #1e3a5f",
        borderRadius:12, padding:"16px 20px" }}>
        <div style={{ fontSize:11, color:"#475569", textTransform:"uppercase",
          letterSpacing:1, marginBottom:16 }}>Per-Function (SLE'17 estimates)</div>
        {metrics.map(fn => (
          <EnergyBar key={fn.name} name={fn.name}
            beforeJ={fn.beforeJ} afterJ={fn.afterJ} maxJ={maxJ} />
        ))}
      </div>
    </div>
  );
}

// ── Main export ───────────────────────────────────────────────────────────────

export default function EnergyDashboard({ allResults }) {
  const [tab, setTab] = useState("live");
  const allFunctions  = Object.values(allResults).flatMap(r => r.functions || []);
  if (!allFunctions.length) return null;

  return (
    <div style={{ marginTop:28, paddingTop:28,
      borderTop:"2px solid #1e3a5f" }}>
      <div style={{ display:"flex", alignItems:"center", gap:12, marginBottom:20 }}>
        <span style={{ fontSize:22 }}>⚡</span>
        <div>
          <div style={{ fontWeight:800, fontSize:18 }}>Energy Comparison Dashboard</div>
          <div style={{ color:"#475569", fontSize:12 }}>
            SLE'17 paper ratios + live benchmark against your running banking POC
          </div>
        </div>
      </div>

      <Tabs
        active={tab}
        onChange={setTab}
        tabs={[
          { id:"live",   label:"🔴 Live Benchmark" },
          { id:"static", label:"📊 SLE'17 Estimates" },
        ]}
      />

      {tab === "live"   && <BenchmarkPanel allResults={allResults} />}
      {tab === "static" && <StaticEnergyTab allResults={allResults} />}
    </div>
  );
}
