import React, { useState, useEffect, useRef } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar } from 'recharts';

// ══════════════════════════════════════════════════════════════════════════════
// DESIGN TOKENS - corporate enterprise theme
// ══════════════════════════════════════════════════════════════════════════════
const T = {
  bg: '#0a1628', surf: '#112240', surf2: '#1a2f4a', border: '#2a4365',
  text: '#e2e8f0', dim: '#718096', blue: '#4299e1', green: '#48bb78',
  amber: '#ed8936', red: '#f56565', purple: '#9f7aea',
};

const LOADING_STEPS = [
  'Fetching carbon intensity data…',
  'Loading application metrics…',
  'Calculating SCI scores…',
  'Analysing energy consumption…',
  'Retrieving server hardware specs…',
  'Aggregating functional units…',
  'Building optimisation recommendations…',
  'Preparing enterprise dashboard…',
];

const GLOBES = ['🌍', '🌎', '🌏'];

function LoadingGlobe() {
  const [frame, setFrame] = useState(0);
  const [step,  setStep]  = useState(0);

  useEffect(() => {
    const globe = setInterval(() => setFrame(f => (f + 1) % 3), 220);
    const text  = setInterval(() => setStep(s  => (s + 1) % LOADING_STEPS.length), 1800);
    return () => { clearInterval(globe); clearInterval(text); };
  }, []);

  return (
    <div style={{
      display:'flex', alignItems:'center', justifyContent:'center',
      minHeight:'100vh', background:T.bg,
    }}>
      <div style={{ textAlign:'center' }}>
        <div style={{ fontSize:72, lineHeight:1, marginBottom:24, userSelect:'none' }}>
          {GLOBES[frame]}
        </div>
        <div style={{
          color:T.text, fontSize:17, fontWeight:600, marginBottom:10,
          letterSpacing:'0.01em',
        }}>
          Enterprise SCI Platform
        </div>
        <div style={{
          color:T.blue, fontSize:13, fontFamily:'JetBrains Mono,monospace',
          minHeight:20, transition:'opacity .4s',
        }}>
          {LOADING_STEPS[step]}
        </div>
        <div style={{ marginTop:24, display:'flex', gap:6, justifyContent:'center' }}>
          {LOADING_STEPS.map((_, i) => (
            <div key={i} style={{
              width:6, height:6, borderRadius:'50%',
              background: i === step ? T.blue : T.border,
              transition:'background .3s',
            }} />
          ))}
        </div>
      </div>
    </div>
  );
}

const CSS = `
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono&display=swap');
*{box-sizing:border-box;margin:0;padding:0}
body{background:${T.bg};color:${T.text};font-family:Inter,sans-serif;font-size:14px;line-height:1.6;min-height:100vh}
button{font-family:inherit;cursor:pointer;border:none;border-radius:6px;padding:8px 16px;font-weight:600;transition:all .2s}
button:disabled{opacity:.5;cursor:not-allowed}
.btn-primary{background:linear-gradient(135deg,${T.blue},#2c5282);color:#fff}
.btn-primary:hover:not(:disabled){transform:translateY(-1px);box-shadow:0 4px 12px ${T.blue}40}
.btn-secondary{background:${T.surf2};color:${T.text};border:1px solid ${T.border}}
.btn-secondary:hover:not(:disabled){background:${T.surf}}
`;

// ══════════════════════════════════════════════════════════════════════════════
// COMPONENTS
// ══════════════════════════════════════════════════════════════════════════════

function Card({ title, badge, children, style={} }) {
  return (
    <div style={{ background:T.surf, border:`1px solid ${T.border}`, borderRadius:8, overflow:'hidden', ...style }}>
      {title && (
        <div style={{ padding:'12px 16px', borderBottom:`1px solid ${T.border}`, display:'flex', alignItems:'center', justifyContent:'space-between', background:T.surf2 }}>
          <span style={{ fontWeight:600, fontSize:15 }}>{title}</span>
          {badge && <span style={{ fontSize:10, background:T.blue, color:'#fff', padding:'3px 8px', borderRadius:10, fontWeight:700, letterSpacing:.5, textTransform:'uppercase' }}>{badge}</span>}
        </div>
      )}
      <div style={{ padding:16 }}>{children}</div>
    </div>
  );
}

function Badge({ children, color=T.blue }) {
  return <span style={{ background:color+'22', color, padding:'2px 8px', borderRadius:4, fontSize:11, fontWeight:600 }}>{children}</span>;
}

function Metric({ label, value, unit, color=T.text }) {
  return (
    <div style={{ display:'flex', flexDirection:'column', gap:4 }}>
      <span style={{ fontSize:11, color:T.dim, textTransform:'uppercase', letterSpacing:.5 }}>{label}</span>
      <div style={{ display:'flex', alignItems:'baseline', gap:4 }}>
        <span style={{ fontSize:24, fontWeight:700, color }}>{value}</span>
        {unit && <span style={{ fontSize:12, color:T.dim }}>{unit}</span>}
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// MOCK DATA — shown when Live Data is OFF
// Numbers derived from data/apps/AzureDevOps/config.json (190 runs/day, 11 agents)
// Hour distributions represent build volume per UTC hour summed over 28 days.
// Business hours 08:00–17:00 CST = 14:00–23:00 UTC; nightly batch at 08:00 UTC (02:00 CST).
// ══════════════════════════════════════════════════════════════════════════════
const ADO_MOCK = {
  ok: true,
  agents: [
    { org:'ACME Inc', id:1,  name:'prod-server-tfsbuild01', status:'online',  current_job: null },
    { org:'ACME Inc', id:2,  name:'prod-server-tfsbuild02', status:'online',  current_job:'Build-CustomerApp' },
    { org:'ACME Inc', id:3,  name:'prod-server-tfsbuild03', status:'online',  current_job: null },
    { org:'ACME Inc', id:4,  name:'prod-server-tfsbuild04', status:'online',  current_job: null },
    { org:'ACME Inc', id:5,  name:'prod-server-tfsbuild05', status:'online',  current_job:'Build-CustomerSign' },
    { org:'ACME Inc', id:6,  name:'prod-server-tfsbuild06', status:'online',  current_job: null },
    { org:'ACME Inc', id:7,  name:'prod-server-tfsbuild07', status:'online',  current_job: null },
    { org:'ACME Inc', id:8,  name:'prod-server-tfsbuild08', status:'offline', current_job: null },
    { org:'ACME Inc', id:9,  name:'prod-server-tfsbuild09', status:'online',  current_job: null },
    { org:'ACME Inc', id:10, name:'prod-server-tfsbuild10', status:'online',  current_job: null },
    { org:'ACME Inc', id:11, name:'prod-server-tfsbuild11', status:'online',  current_job: null },
  ],
  agent_utilization: [
    { org:'ACME Inc', id:1,  name:'prod-server-tfsbuild01', pool:'Default', jobs_28d:612, avg_duration_s:872, utilization_pct:62 },
    { org:'ACME Inc', id:2,  name:'prod-server-tfsbuild02', pool:'Default', jobs_28d:584, avg_duration_s:934, utilization_pct:59 },
    { org:'ACME Inc', id:3,  name:'prod-server-tfsbuild03', pool:'Default', jobs_28d:540, avg_duration_s:780, utilization_pct:55 },
    { org:'ACME Inc', id:4,  name:'prod-server-tfsbuild04', pool:'Default', jobs_28d:498, avg_duration_s:910, utilization_pct:52 },
    { org:'ACME Inc', id:5,  name:'prod-server-tfsbuild05', pool:'Default', jobs_28d:620, avg_duration_s:855, utilization_pct:63 },
    { org:'ACME Inc', id:6,  name:'prod-server-tfsbuild06', pool:'Default', jobs_28d:456, avg_duration_s:740, utilization_pct:48 },
    { org:'ACME Inc', id:7,  name:'prod-server-tfsbuild07', pool:'Default', jobs_28d:430, avg_duration_s:820, utilization_pct:45 },
    { org:'ACME Inc', id:9,  name:'prod-server-tfsbuild09', pool:'Default', jobs_28d:380, avg_duration_s:690, utilization_pct:38 },
    { org:'ACME Inc', id:10, name:'prod-server-tfsbuild10', pool:'Default', jobs_28d:410, avg_duration_s:760, utilization_pct:41 },
    { org:'ACME Inc', id:11, name:'prod-server-tfsbuild11', pool:'Default', jobs_28d:390, avg_duration_s:800, utilization_pct:40 },
  ],
  summary_28d: {
    total_builds: 4920,
    builds_per_day: 176,
    by_project: {
      'ACME Inc/CustomerApp': {
        builds: 1420,
        // UTC hours 0-23; peak 14-22 (08:00-16:00 CST), nightly batch spike at 08 UTC
        hour_distribution: [2,1,1,1,1,2,2,4,22,8,6,5,5,6,52,68,72,80,76,64,48,32,18,8],
      },
      'ACME Inc/CustomerSign': {
        builds: 1040,
        hour_distribution: [2,1,1,1,1,2,2,4,18,6,5,4,4,5,38,50,54,60,55,48,36,24,14,6],
      },
      'ACME Inc/CustomerLeads': {
        builds: 740,
        hour_distribution: [1,0,0,0,1,1,1,3,14,4,3,3,3,4,28,36,38,42,40,34,26,18,10,4],
      },
      'ACME Inc/CustomerService': {
        builds: 860,
        hour_distribution: [1,1,0,0,1,1,1,3,16,5,4,3,3,5,32,42,44,48,46,38,30,20,12,4],
      },
      'ACME Inc/CustomerTask': {
        builds: 860,
        hour_distribution: [1,1,0,0,1,1,1,3,16,5,4,3,3,5,30,40,42,46,44,36,28,18,10,4],
      },
    },
  },
  carbon_per_agent_gco2e: 12.45,
  total_carbon_gco2e: 136.9,
  grid_intensity_gco2_kwh: 420,
};

// ══════════════════════════════════════════════════════════════════════════════
// MAIN APP
// ══════════════════════════════════════════════════════════════════════════════

export default function App() {
  const [loading, setLoading] = useState(true);
  const [apps, setApps] = useState([]);
  const [regions, setRegions] = useState([]);
  const [selectedApp, setSelectedApp] = useState(null);
  const [recommendations, setRecommendations] = useState([]);
  const [adoDetails, setAdoDetails] = useState(null);
  const [adoError,   setAdoError]   = useState(null);
  const [adoLoading, setAdoLoading] = useState(false);
  const [error, setError] = useState(null);
  const [liveMode, setLiveMode] = useState(false);
  // incremented to invalidate in-flight ADO fetches when mode changes or a different app is selected
  const adoFetchId = useRef(0);

  useEffect(() => {
    fetchData(liveMode);
    // If AzureDevOps is already selected, refresh the detail panel to match the new mode
    if (selectedApp?.app_name === 'AzureDevOps') {
      setAdoDetails(null);
      setAdoError(null);
      if (!liveMode) {
        adoFetchId.current++; // discard any in-flight live fetch
        setAdoDetails(ADO_MOCK);
        setAdoLoading(false);
      } else {
        setAdoLoading(true);
        doAdoFetch();
      }
    }
  }, [liveMode]); // eslint-disable-line react-hooks/exhaustive-deps

  const fetchData = async (live = liveMode) => {
    setLoading(true);
    setError(null);
    try {
      const url = live ? '/api/compare?live=true' : '/api/compare';
      console.log('Fetching data from', url);
      const r = await fetch(url);
      console.log('Response status:', r.status);
      
      if (!r.ok) {
        const text = await r.text();
        throw new Error(`API error ${r.status}: ${text}`);
      }
      
      const data = await r.json();
      console.log('Received data:', data);
      
      setApps(data.applications || []);
      setRegions(data.regions || []);
      
      if (!data.applications || data.applications.length === 0) {
        setError('No applications found. Check backend logs.');
      }
    } catch (e) {
      console.error('Fetch error:', e);
      setError(e.message);
    }
    setLoading(false);
  };

  // Live ADO fetch — retries while backend pre-warm is still running
  const doAdoFetch = () => {
    const myId = ++adoFetchId.current;
    const fetchOnce = () => {
      fetch('/api/ado/details')
        .then(async r => {
          const text = await r.text();
          try { return JSON.parse(text); }
          catch { return { ok: false, reason: 'proxy_error',
            message: `Backend returned a non-JSON response (HTTP ${r.status}). ` +
                     `The backend container may be down or still starting up. ` +
                     `Run: docker-compose up --build` }; }
        })
        .then(data => {
          if (adoFetchId.current !== myId) return; // stale — mode changed or app deselected
          if (data && data.reason === 'loading') {
            // pre-warm still running — retry after suggested delay
            const delay = (data.retry_after || 8) * 1000;
            setTimeout(fetchOnce, delay);
          } else if (data && data.ok === false) {
            setAdoError(data.message || 'ADO request failed.');
            setAdoLoading(false);
          } else {
            setAdoDetails(data);
            setAdoLoading(false);
          }
        })
        .catch(err => {
          if (adoFetchId.current !== myId) return;
          setAdoError('Could not reach backend: ' + err.message);
          setAdoLoading(false);
        });
    };
    fetchOnce();
  };

  const selectApp = (app) => {
    setSelectedApp(app.app);
    setRecommendations(app.recommendations || []);
    if (app.app.app_name === 'AzureDevOps') {
      setAdoDetails(null);
      setAdoError(null);
      if (!liveMode) {
        adoFetchId.current++; // discard any in-flight live fetch
        setAdoDetails(ADO_MOCK);
        setAdoLoading(false);
      } else {
        setAdoLoading(true);
        doAdoFetch();
      }
    } else {
      adoFetchId.current++; // discard any in-flight ADO fetch when navigating away
      setAdoDetails(null);
    }
  };

  const getSCIColor = (sci) => {
    if (sci < 0.01) return T.green;
    if (sci < 0.05) return T.amber;
    return T.red;
  };

  const fmt = (n, d=2) => Number(n).toFixed(d);
  const fmtLarge = n => Number(n) > 1000 ? `${(Number(n)/1000).toFixed(1)}k` : fmt(n, 0);
  const fmtSCI = (n) => {
    if (n >= 0.01)      return n.toFixed(4);
    if (n >= 0.0001)    return n.toFixed(6);
    if (n >= 0.000001)  return n.toFixed(8);
    return n.toExponential(2);
  };

  if (loading) return <LoadingGlobe />;

  if (error) {
    return (
      <>
        <style>{CSS}</style>
        <div style={{ display:'flex', alignItems:'center', justifyContent:'center', minHeight:'100vh', padding:20 }}>
          <Card title="Error Loading Data" style={{ maxWidth:600 }}>
            <div style={{ color:T.red, marginBottom:16, fontSize:16 }}>
              ⚠️ {error}
            </div>
            <div style={{ color:T.dim, fontSize:13, marginBottom:16, fontFamily:'JetBrains Mono,monospace' }}>
              <p>Possible causes:</p>
              <ul style={{ marginLeft:20, marginTop:8 }}>
                <li>Backend not running (check <code>http://localhost:5000/api/health</code>)</li>
                <li>Data files not mounted correctly in Docker</li>
                <li>CORS issue (check browser console)</li>
              </ul>
            </div>
            <button className="btn-primary" onClick={fetchData}>
              Retry
            </button>
          </Card>
        </div>
      </>
    );
  }

  if (apps.length === 0) {
    return (
      <>
        <style>{CSS}</style>
        <div style={{ display:'flex', alignItems:'center', justifyContent:'center', minHeight:'100vh', padding:20 }}>
          <Card title="No Applications Found" style={{ maxWidth:600 }}>
            <div style={{ color:T.amber, marginBottom:16, fontSize:14 }}>
              No application data loaded from backend.
            </div>
            <div style={{ color:T.dim, fontSize:13, marginBottom:16 }}>
              <p>Check that:</p>
              <ul style={{ marginLeft:20, marginTop:8 }}>
                <li>The <code>data/</code> directory is mounted correctly</li>
                <li>Backend logs show "Loaded 5 servers, 5 apps"</li>
                <li>JSON files are valid in <code>data/apps/*/config.json</code></li>
              </ul>
            </div>
            <div style={{ marginTop:16, padding:12, background:T.surf2, borderRadius:6, fontFamily:'JetBrains Mono,monospace', fontSize:12 }}>
              Backend: <a href="/api/health" target="_blank" style={{ color:T.blue }}>http://localhost:5000/api/health</a><br/>
              Test: <a href="/api/apps" target="_blank" style={{ color:T.blue }}>http://localhost:5000/api/apps</a>
            </div>
            <button className="btn-primary" onClick={fetchData} style={{ marginTop:16 }}>
              Retry
            </button>
          </Card>
        </div>
      </>
    );
  }

  // ── render ────────────────────────────────────────────────────────────────
  return (
    <>
      <style>{CSS}</style>

      {/* HEADER */}
      <div style={{ background:T.surf, borderBottom:`1px solid ${T.border}`, padding:'14px 24px', display:'flex', alignItems:'center', justifyContent:'space-between', position:'sticky', top:0, zIndex:10 }}>
        <div style={{ display:'flex', alignItems:'center', gap:12 }}>
          <span style={{ fontSize:20 }}>🌍</span>
          <span style={{ fontWeight:700, fontSize:18 }}>Enterprise <span style={{ color:T.green }}>SCI</span> Platform</span>
          <Badge color={T.purple}>Multi-App Comparison</Badge>
        </div>
        <div style={{ display:'flex', gap:8, alignItems:'center' }}>
          <button
            className={liveMode ? 'btn-primary' : 'btn-secondary'}
            onClick={() => setLiveMode(v => !v)}
            title={liveMode ? 'Using live Prometheus metrics' : 'Using static config data'}
          >
            {liveMode ? '⚡ Live Data ON' : '⚡ Live Data OFF'}
          </button>
          <button className="btn-secondary" onClick={() => fetchData(liveMode)}>
            ↻ Refresh
          </button>
        </div>
      </div>

      <div style={{ padding:20, maxWidth:1600, margin:'0 auto' }}>

        {/* APP COMPARISON GRID */}
        <Card title="Application SCI Comparison" badge={liveMode ? 'prometheus-live' : 'static'} style={{ marginBottom:20 }}>
          <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fit, minmax(280px, 1fr))', gap:12 }}>
            {apps.map((item, i) => {
              const app = item.app;
              const color = getSCIColor(app.sci);
              return (
                <div key={i}
                  onClick={() => selectApp(item)}
                  style={{ background:T.surf2, border:`2px solid ${selectedApp?.app_name===app.app_name ? T.blue : T.border}`, borderRadius:8, padding:16, cursor:'pointer', transition:'all .2s' }}
                  onMouseEnter={e => e.currentTarget.style.borderColor = T.blue}
                  onMouseLeave={e => { if(selectedApp?.app_name !== app.app_name) e.currentTarget.style.borderColor = T.border }}
                >
                  <div style={{ display:'flex', justifyContent:'space-between', alignItems:'start', marginBottom:12 }}>
                    <div style={{ fontWeight:600, fontSize:16 }}>{app.app_name}</div>
                    <div style={{ display:'flex', flexDirection:'column', alignItems:'flex-end', gap:4 }}>
                      <Badge color={color}>{i+1}</Badge>
                      <Badge color={
                        app.metrics_source === 'prometheus-live' || app.functional_unit_source === 'azure-devops-live'
                        || (liveMode && app.app_name === 'AzureDevOps')
                          ? T.green : T.dim
                      }>
                        {app.metrics_source === 'prometheus-live' || app.functional_unit_source === 'azure-devops-live'
                        || (liveMode && app.app_name === 'AzureDevOps')
                          ? '⚡ live' : '📄 static'}
                      </Badge>
                    </div>
                  </div>
                  
                  <div style={{ fontSize:32, fontWeight:700, color, marginBottom:8 }}>
                    {fmtSCI(app.sci)}
                  </div>
                  <div style={{ fontSize:11, color:T.dim, marginBottom:12 }}>gCO₂eq / {app.functional_unit}</div>
                  
                  <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:8, fontSize:12 }}>
                    <div><span style={{ color:T.dim }}>Carbon:</span> <strong>{fmtLarge(app.carbon_gco2e)}</strong> g</div>
                    <div><span style={{ color:T.dim }}>Energy:</span> <strong>{fmt(app.total_energy_kwh,3)}</strong> kWh</div>
                    <div><span style={{ color:T.dim }}>Servers:</span> <strong>{app.server_count}</strong>×{app.server_type.split('-').pop()}</div>
                    <div><span style={{ color:T.dim }}>Region:</span> <strong>{app.region}</strong></div>
                    <div><span style={{ color:T.dim }}>CPU:</span> <strong>{fmt(app.cpu_utilization_percent, 1)}</strong>%</div>
                    <div><span style={{ color:T.dim }}>Mem:</span> <strong>{fmt(app.memory_utilization_percent, 1)}</strong>%</div>
                  </div>
                  
                  {item.recommendations?.length > 0 && (
                    <div style={{ marginTop:12, padding:'6px 10px', background:T.amber+'18', border:`1px solid ${T.amber}40`, borderRadius:4, fontSize:11, color:T.amber, display:'flex', alignItems:'center', gap:6 }}>
                      💡 {item.recommendations.length} optimization{item.recommendations.length>1?'s':''} available
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </Card>

        {/* SELECTED APP DETAIL */}
        {selectedApp && (
          <>
            <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fit, minmax(350px, 1fr))', gap:20, marginBottom:20 }}>
              
              {/* CARBON BREAKDOWN */}
              <Card title={`${selectedApp.app_name} - Carbon Breakdown`}>
                <ResponsiveContainer width="100%" height={200}>
                  <PieChart>
                    <Pie data={[
                      { name:'Operational', value:selectedApp.carbon_operational_gco2e },
                      { name:'Embodied', value:selectedApp.carbon_embodied_gco2e }
                    ]} dataKey="value" cx="50%" cy="50%" innerRadius={50} outerRadius={80} paddingAngle={3}>
                      <Cell fill={T.red}/>
                      <Cell fill={T.purple}/>
                    </Pie>
                    <Tooltip contentStyle={{ background:T.surf2, border:`1px solid ${T.border}`, borderRadius:6, fontSize:12 }}/>
                    <Legend wrapperStyle={{ fontSize:12 }}/>
                  </PieChart>
                </ResponsiveContainer>
                
                <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:12, marginTop:16 }}>
                  <Metric label="Operational (O)" value={fmtLarge(selectedApp.carbon_operational_gco2e)} unit="gCO₂eq" color={T.red}/>
                  <Metric label="Embodied (M)" value={fmtLarge(selectedApp.carbon_embodied_gco2e)} unit="gCO₂eq" color={T.purple}/>
                </div>
              </Card>

              {/* KEY METRICS */}
              <Card title="Key Metrics">
                <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:16 }}>
                  <Metric label="Total Energy" value={fmt(selectedApp.total_energy_kwh,3)} unit="kWh" color={T.amber}/>
                  <Metric label="Grid Intensity" value={selectedApp.grid_intensity_gco2_kwh} unit="gCO₂/kWh" color={T.blue}/>
                  <Metric label="Server Count" value={selectedApp.server_count} unit="instances" color={T.text}/>
                  <Metric label="Functional Unit" value={fmtLarge(selectedApp.functional_unit_count)} unit={selectedApp.functional_unit} color={T.green}/>
                </div>
                {selectedApp.cost_usd && (
                  <div style={{ marginTop:16, padding:12, background:T.surf2, borderRadius:6, display:'flex', justifyContent:'space-between', alignItems:'center' }}>
                    <span style={{ fontSize:12, color:T.dim }}>Est. Cost (1 hour)</span>
                    <span style={{ fontSize:20, fontWeight:700, color:T.green }}>${fmt(selectedApp.cost_usd)}</span>
                  </div>
                )}
              </Card>
            </div>

            {/* ADO AGENT DRILL-DOWN — only for AzureDevOps card */}
            {selectedApp.app_name === 'AzureDevOps' && (
              <Card title="Azure DevOps — CI/CD Agent & Pipeline Breakdown"
                    badge={adoDetails ? (liveMode ? 'live' : 'mock data') : adoLoading ? 'loading…' : 'unavailable'}
                    style={{ marginBottom:20 }}>
                {adoLoading && (
                  <div style={{ color:T.dim, padding:16, textAlign:'center' }}>Fetching ADO data…</div>
                )}
                {!adoLoading && adoError && (
                  <div style={{ color:T.amber, fontSize:13 }}>
                    <strong style={{ display:'block', marginBottom:4 }}>⚠ ADO unavailable</strong>
                    {adoError}
                  </div>
                )}
                {!adoLoading && !adoDetails && !adoError && (
                  <div style={{ color:T.dim, fontSize:13 }}>No ADO data returned.</div>
                )}
                {adoDetails && (
                  <>
                    {/* 28-day summary strip */}
                    <div style={{ display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:12, marginBottom:20 }}>
                      {[
                        { label:'Builds (28d)',    value: adoDetails.summary_28d?.total_builds ?? '—',    unit:'', color:T.blue },
                        { label:'Agents Online',   value: (adoDetails.agents||[]).filter(a=>a.status==='online').length, unit:`of ${(adoDetails.agents||[]).length}`, color:T.green },
                        { label:'Builds/day',      value: adoDetails.summary_28d?.builds_per_day ?? '—',  unit:'avg', color:T.blue },
                        { label:'Carbon/agent/hr', value: fmt(adoDetails.carbon_per_agent_gco2e || 0, 2), unit:'gCO₂eq', color:T.green },
                      ].map(m => (
                        <div key={m.label} style={{ background:T.bg, borderRadius:6, padding:12 }}>
                          <div style={{ fontSize:11, color:T.dim, marginBottom:4, textTransform:'uppercase', letterSpacing:.5 }}>{m.label}</div>
                          <div style={{ fontSize:22, fontWeight:700, color:m.color }}>{m.value}</div>
                          {m.unit && <div style={{ fontSize:11, color:T.dim }}>{m.unit}</div>}
                        </div>
                      ))}
                    </div>

                    {/* ── SECTION 1: Agent Utilization Table ── */}
                    {(adoDetails.agent_utilization||[]).length > 0 && (() => {
                      const agentMap = {};
                      (adoDetails.agents||[]).forEach(a => { agentMap[`${a.org}:${a.id}`] = a; });
                      const fmtDur = s => {
                        if (!s) return '—';
                        const m = Math.floor(s/60), sec = s%60;
                        return m > 0 ? `${m}m ${sec}s` : `${sec}s`;
                      };
                      return (
                        <div style={{ marginBottom:20 }}>
                          <div style={{ fontSize:13, fontWeight:600, marginBottom:8, color:T.dim }}>
                            AGENT LOAD — LAST 28 DAYS ({adoDetails.agent_utilization.length} agents with activity)
                          </div>
                          <div style={{ overflowX:'auto' }}>
                            <table style={{ width:'100%', borderCollapse:'collapse', fontSize:12 }}>
                              <thead style={{ position:'sticky', top:0, background:T.surf, zIndex:1 }}>
                                <tr style={{ borderBottom:`1px solid ${T.border}` }}>
                                  {['Status','Agent','Pool','Org','Jobs (28d)','Avg Duration','Utilization'].map(h => (
                                    <th key={h} style={{ textAlign: h==='Jobs (28d)'||h==='Avg Duration'||h==='Utilization' ? 'right':'left', padding:'6px 10px', color:T.dim, fontWeight:600, whiteSpace:'nowrap', fontSize:11 }}>{h}</th>
                                  ))}
                                </tr>
                              </thead>
                              <tbody>
                                {adoDetails.agent_utilization.map((au, i) => {
                                  const live = agentMap[`${au.org}:${au.id}`];
                                  const busy   = live && !!live.current_job;
                                  const online = live && live.status === 'online';
                                  const dot    = !live ? '#666' : !online ? T.red : busy ? T.amber : T.green;
                                  const statusLabel = !live ? 'unknown' : !online ? 'offline' : busy ? 'busy' : 'idle';
                                  const util = au.utilization_pct || 0;
                                  const barColor = util > 60 ? T.red : util > 30 ? T.amber : T.green;
                                  return (
                                    <tr key={i} style={{ borderBottom:`1px solid ${T.border}22`, background: i%2===0 ? 'transparent' : T.bg+'88' }}>
                                      <td style={{ padding:'6px 10px' }}>
                                        <span style={{ display:'inline-flex', alignItems:'center', gap:5 }}>
                                          <span style={{ width:8, height:8, borderRadius:'50%', background:dot, flexShrink:0, display:'inline-block' }}/>
                                          <span style={{ fontSize:10, color:dot }}>{statusLabel}</span>
                                        </span>
                                      </td>
                                      <td style={{ padding:'6px 10px', fontWeight:600, whiteSpace:'nowrap' }}>{au.name}</td>
                                      <td style={{ padding:'6px 10px', color:T.dim, fontSize:11 }}>{au.pool}</td>
                                      <td style={{ padding:'6px 10px', color:T.dim, fontSize:11 }}>{au.org}</td>
                                      <td style={{ padding:'6px 10px', textAlign:'right', color:T.blue, fontWeight:700 }}>{(au.jobs_28d||0).toLocaleString()}</td>
                                      <td style={{ padding:'6px 10px', textAlign:'right', color:T.dim }}>{fmtDur(au.avg_duration_s)}</td>
                                      <td style={{ padding:'6px 10px', textAlign:'right', minWidth:120 }}>
                                        <div style={{ display:'flex', alignItems:'center', gap:6, justifyContent:'flex-end' }}>
                                          <div style={{ flex:1, maxWidth:70, height:6, background:T.border, borderRadius:3, overflow:'hidden' }}>
                                            <div style={{ width:`${Math.min(util,100)}%`, height:'100%', background:barColor, borderRadius:3 }}/>
                                          </div>
                                          <span style={{ fontSize:11, color:barColor, width:36, textAlign:'right' }}>{util}%</span>
                                        </div>
                                      </td>
                                    </tr>
                                  );
                                })}
                              </tbody>
                            </table>
                          </div>
                          {/* Agents with no recorded jobs */}
                          {(() => {
                            const activeNames = new Set(adoDetails.agent_utilization.map(a=>`${a.org}:${a.id}`));
                            const idle = (adoDetails.agents||[]).filter(a => !activeNames.has(`${a.org}:${a.id}`));
                            return idle.length > 0 ? (
                              <div style={{ marginTop:8, fontSize:11, color:T.dim }}>
                                {idle.length} agent{idle.length>1?'s':''} had no completed jobs in 28 days (candidates for decommission): {idle.map(a=>a.name).join(', ')}
                              </div>
                            ) : null;
                          })()}
                        </div>
                      );
                    })()}

                    {/* ── SECTION 2: Project Build-Hour Heatmap ── */}
                    {Object.keys(adoDetails.summary_28d?.by_project || {}).length > 0 && (() => {
                      // Typical ERCOT hourly relative carbon intensity (0=cleanest, 1=dirtiest)
                      // Low overnight (wind), higher midday/afternoon (demand peak)
                      const ERCOT_REL = [
                        0.22,0.18,0.16,0.16,0.20,0.30,0.46,0.60,0.70,0.72,0.68,0.62,
                        0.58,0.64,0.72,0.78,0.82,0.88,0.85,0.76,0.62,0.50,0.38,0.28,
                      ];
                      const intensityColor = r => r > 0.65 ? T.red : r > 0.42 ? T.amber : T.green;
                      const allProjects = Object.entries(adoDetails.summary_28d.by_project || {}).map(([key,v])=>({key,...v})).sort((a,b)=>(b.builds||0)-(a.builds||0));
                      const projects = allProjects.slice(0, 20);
                      const maxCount = Math.max(1, ...allProjects.flatMap(p => (p.hour_dist||p.hour_distribution||[])));
                      return (
                        <div>
                          <div style={{ fontSize:13, fontWeight:600, marginBottom:4, color:T.dim }}>
                            BUILD TIMING BY PROJECT — LAST 28 DAYS (UTC hours)
                          </div>
                          <div style={{ fontSize:11, color:T.dim, marginBottom:10, display:'flex', gap:16, flexWrap:'wrap' }}>
                            <span>Bar color = ERCOT grid intensity at that hour:</span>
                            {[['Low carbon','green'],['Medium','amber'],['Peak carbon','red']].map(([l,c])=>(
                              <span key={l} style={{ display:'flex', alignItems:'center', gap:4 }}>
                                <span style={{ width:10, height:10, borderRadius:2, background:T[c], display:'inline-block' }}/>
                                {l}
                              </span>
                            ))}
                            <span style={{ color:T.dim }}>| Bar height = build volume at that hour</span>
                          </div>
                          <div style={{ overflowX:'auto' }}>
                            <table style={{ borderCollapse:'collapse', fontSize:11, width:'100%' }}>
                              <thead style={{ position:'sticky', top:0, background:T.surf, zIndex:1 }}>
                                <tr style={{ borderBottom:`1px solid ${T.border}` }}>
                                  <th style={{ textAlign:'left', padding:'4px 8px', color:T.dim, whiteSpace:'nowrap' }}>Project</th>
                                  <th style={{ textAlign:'left', padding:'4px 8px', color:T.dim }}>Org</th>
                                  <th style={{ textAlign:'right', padding:'4px 8px', color:T.dim }}>Builds</th>
                                  <th style={{ padding:'4px 8px', color:T.dim }}>
                                    <div style={{ display:'flex', gap:0, fontSize:9 }}>
                                      {Array.from({length:24},(_,h)=>(
                                        <div key={h} style={{ width:9, textAlign:'center', color: ERCOT_REL[h]>0.65?T.red:ERCOT_REL[h]>0.42?T.amber:T.green }}>
                                          {h%6===0?h:''}
                                        </div>
                                      ))}
                                    </div>
                                  </th>
                                </tr>
                              </thead>
                              <tbody>
                                {projects.map((row, i) => {
                                  const [rowOrg, rowProject] = row.key.split('/');
                                  const dist = (row.hour_distribution||row.hour_dist||[]).length===24
                                    ? (row.hour_distribution||row.hour_dist) : Array(24).fill(0);
                                  const peakHour = dist.indexOf(Math.max(...dist));
                                  const peakCarbon = ERCOT_REL[peakHour] > 0.65;
                                  return (
                                    <tr key={i} style={{ borderBottom:`1px solid ${T.border}22`, background: i%2===0?'transparent':T.bg+'88' }}>
                                      <td style={{ padding:'4px 8px', fontWeight:500, maxWidth:180, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
                                        {peakCarbon && <span title={`Peak builds at ${peakHour}:00 UTC (high carbon hour)`} style={{ color:T.amber, marginRight:4 }}>⚠</span>}
                                        {rowProject}
                                      </td>
                                      <td style={{ padding:'4px 8px', color:T.dim, whiteSpace:'nowrap' }}>{rowOrg}</td>
                                      <td style={{ padding:'4px 8px', textAlign:'right', color:T.blue }}>{(row.builds||0).toLocaleString()}</td>
                                      <td style={{ padding:'4px 8px' }}>
                                        <div style={{ display:'flex', gap:1, alignItems:'flex-end', height:30 }}>
                                          {dist.map((cnt, h) => {
                                            const pct = maxCount > 0 ? cnt / maxCount : 0;
                                            const ht = Math.max(pct * 28, cnt > 0 ? 2 : 0);
                                            return (
                                              <div
                                                key={h}
                                                title={`${h}:00 UTC — ${cnt} build${cnt!==1?'s':''}`}
                                                style={{ width:8, height:ht, background: cnt>0 ? intensityColor(ERCOT_REL[h]) : T.border+'44', borderRadius:1, alignSelf:'flex-end', flexShrink:0 }}
                                              />
                                            );
                                          })}
                                        </div>
                                      </td>
                                    </tr>
                                  );
                                })}
                              </tbody>
                            </table>
                          </div>
                          {allProjects.length > 20 && (
                            <div style={{ fontSize:11, color:T.dim, marginTop:6 }}>
                              Showing top 20 of {allProjects.length} projects by build volume.
                            </div>
                          )}
                        </div>
                      );
                    })()}
                  </>
                )}
              </Card>
            )}

            {/* OPTIMIZATION RECOMMENDATIONS */}
            {recommendations.length > 0 && (
              <Card title="Optimization Recommendations" badge={`${recommendations.length} found`} style={{ marginBottom:20 }}>
                <div style={{ display:'flex', flexDirection:'column', gap:12 }}>
                  {recommendations.map((rec, i) => {
                    const icons = { region_relocation:'🌍', server_rightsizing:'⚙️', time_shifting:'⏰', replica_scaledown:'📉', cloud_migration:'☁️' };
                    const priorityColors = { high:T.red, medium:T.amber, low:T.blue };
                    return (
                      <div key={i} style={{ background:T.surf2, border:`1px solid ${T.border}`, borderRadius:8, padding:16 }}>
                        <div style={{ display:'flex', justifyContent:'space-between', alignItems:'start', marginBottom:12 }}>
                          <div style={{ display:'flex', alignItems:'center', gap:8 }}>
                            <span style={{ fontSize:20 }}>{icons[rec.type]}</span>
                            <span style={{ fontWeight:600, fontSize:15 }}>{rec.title}</span>
                          </div>
                          <Badge color={priorityColors[rec.priority]}>{rec.priority.toUpperCase()}</Badge>
                        </div>
                        
                        {rec.carbon_reduction_percent && (
                          <div style={{ display:'flex', alignItems:'center', gap:16, marginBottom:12 }}>
                            <div style={{ flex:1, background:T.bg, borderRadius:6, padding:12 }}>
                              <div style={{ fontSize:11, color:T.dim, marginBottom:4 }}>Carbon Reduction</div>
                              <div style={{ fontSize:24, fontWeight:700, color:T.green }}>
                                {fmt(rec.carbon_reduction_percent)}%
                              </div>
                            </div>
                            {rec.carbon_reduction_gco2e && (
                              <div style={{ flex:1, background:T.bg, borderRadius:6, padding:12 }}>
                                <div style={{ fontSize:11, color:T.dim, marginBottom:4 }}>Saved</div>
                                <div style={{ fontSize:20, fontWeight:700, color:T.green }}>
                                  {fmtLarge(rec.carbon_reduction_gco2e)} gCO₂eq
                                </div>
                              </div>
                            )}
                          </div>
                        )}
                        
                        <div style={{ fontSize:12, color:T.dim, marginBottom:8 }}>{rec.notes}</div>
                        
                        {rec.type === 'region_relocation' && (
                          <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:8, fontSize:12 }}>
                            <div><strong>Current:</strong> {rec.current_region}</div>
                            <div><strong>Recommended:</strong> <span style={{ color:T.green }}>{rec.recommended_region}</span></div>
                            <div><strong>Grid Intensity:</strong> {rec.new_grid_intensity} gCO₂/kWh</div>
                            <div><strong>Renewables:</strong> {rec.renewable_percent}%</div>
                          </div>
                        )}
                        
                        {rec.type === 'server_rightsizing' && (
                          <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:8, fontSize:12 }}>
                            <div><strong>Current:</strong> {rec.current_server}</div>
                            <div><strong>Recommended:</strong> <span style={{ color:T.green }}>{rec.recommended_server}</span></div>
                            {rec.cost_reduction_percent && (
                              <div><strong>Cost Savings:</strong> <span style={{ color:T.green }}>{fmt(rec.cost_reduction_percent)}%</span></div>
                            )}
                          </div>
                        )}
                        
                        {rec.type === 'time_shifting' && (
                          <div style={{ fontSize:12 }}>
                            <strong>Best Hours:</strong> <span style={{ color:T.green }}>{rec.best_hours}</span>
                          </div>
                        )}

                        {rec.type === 'cloud_migration' && (
                          <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:8, fontSize:12 }}>
                            <div><strong>Current:</strong> {rec.current_server} @ {rec.current_region}</div>
                            <div><strong>Target:</strong> <span style={{ color:T.green }}>{rec.recommended_server} @ {rec.recommended_region}</span></div>
                            <div><strong>PUE (on-prem → Azure):</strong> <span style={{ color:T.amber }}>{rec.pue_current}</span> → <span style={{ color:T.green }}>{rec.pue_azure}</span> <span style={{ color:T.green }}>(-{rec.pue_saving_percent}%)</span></div>
                            <div><strong>Grid Intensity:</strong> {rec.grid_intensity_gco2_kwh} gCO₂/kWh ({rec.renewable_percent}% renewable)</div>
                            <div><strong>Est. Cost:</strong> <span style={{ color:T.blue }}>${rec.estimated_cost_per_hour_usd}/hr</span></div>
                            <div><strong>Model:</strong> {rec.cost_model}</div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </Card>
            )}
          </>
        )}

        {/* REGIONAL CARBON INTENSITY */}
        <Card title="Regional Carbon Intensity Comparison">
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={regions.sort((a,b) => a.intensity_gco2_kwh - b.intensity_gco2_kwh)}>
              <XAxis dataKey="name" tick={{ fill:T.dim, fontSize:11 }} angle={-45} textAnchor="end" height={80}/>
              <YAxis tick={{ fill:T.dim, fontSize:11 }} label={{ value:'gCO₂eq/kWh', angle:-90, position:'insideLeft', fill:T.dim, fontSize:12 }}/>
              <Tooltip contentStyle={{ background:T.surf2, border:`1px solid ${T.border}`, borderRadius:6, fontSize:12 }}
                       formatter={(v,n,p) => [
                         `${v} gCO₂/kWh (${p.payload.renewable_percent}% renewable)`,
                         p.payload.location
                       ]}/>
              <Bar dataKey="intensity_gco2_kwh" fill={T.blue} radius={[6,6,0,0]}/>
            </BarChart>
          </ResponsiveContainer>
        </Card>

      </div>
    </>
  );
}
