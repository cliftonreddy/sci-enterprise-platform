import React, { useState, useEffect } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar } from 'recharts';

// ══════════════════════════════════════════════════════════════════════════════
// DESIGN TOKENS - corporate enterprise theme
// ══════════════════════════════════════════════════════════════════════════════
const T = {
  bg: '#0a1628', surf: '#112240', surf2: '#1a2f4a', border: '#2a4365',
  text: '#e2e8f0', dim: '#718096', blue: '#4299e1', green: '#48bb78',
  amber: '#ed8936', red: '#f56565', purple: '#9f7aea',
};

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
// MAIN APP
// ══════════════════════════════════════════════════════════════════════════════

export default function App() {
  const [loading, setLoading] = useState(true);
  const [apps, setApps] = useState([]);
  const [regions, setRegions] = useState([]);
  const [selectedApp, setSelectedApp] = useState(null);
  const [recommendations, setRecommendations] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      console.log('Fetching data from /api/compare...');
      const r = await fetch('/api/compare');
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

  const selectApp = (app) => {
    setSelectedApp(app.app);
    setRecommendations(app.recommendations || []);
  };

  const getSCIColor = (sci) => {
    if (sci < 0.01) return T.green;
    if (sci < 0.05) return T.amber;
    return T.red;
  };

  const fmt = (n, d=2) => Number(n).toFixed(d);
  const fmtLarge = n => Number(n) > 1000 ? `${(Number(n)/1000).toFixed(1)}k` : fmt(n, 0);

  if (loading) {
    return (
      <div style={{ display:'flex', alignItems:'center', justifyContent:'center', minHeight:'100vh', color:T.dim }}>
        <div style={{ textAlign:'center' }}>
          <div style={{ fontSize:48, marginBottom:16 }}>🌍</div>
          <div>Loading Enterprise SCI Platform...</div>
        </div>
      </div>
    );
  }

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
        <button className="btn-secondary" onClick={fetchData}>
          ↻ Refresh Data
        </button>
      </div>

      <div style={{ padding:20, maxWidth:1600, margin:'0 auto' }}>

        {/* APP COMPARISON GRID */}
        <Card title="Application SCI Comparison" badge="live" style={{ marginBottom:20 }}>
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
                    <Badge color={color}>{i+1}</Badge>
                  </div>
                  
                  <div style={{ fontSize:32, fontWeight:700, color, marginBottom:8 }}>
                    {app.sci < 0.001 ? app.sci.toExponential(2) : fmt(app.sci, 4)}
                  </div>
                  <div style={{ fontSize:11, color:T.dim, marginBottom:12 }}>gCO₂eq / {app.functional_unit}</div>
                  
                  <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:8, fontSize:12 }}>
                    <div><span style={{ color:T.dim }}>Carbon:</span> <strong>{fmtLarge(app.carbon_gco2e)}</strong> g</div>
                    <div><span style={{ color:T.dim }}>Energy:</span> <strong>{fmt(app.total_energy_kwh,3)}</strong> kWh</div>
                    <div><span style={{ color:T.dim }}>Servers:</span> <strong>{app.server_count}</strong>×{app.server_type.split('-').pop()}</div>
                    <div><span style={{ color:T.dim }}>Region:</span> <strong>{app.region}</strong></div>
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

            {/* OPTIMIZATION RECOMMENDATIONS */}
            {recommendations.length > 0 && (
              <Card title="Optimization Recommendations" badge={`${recommendations.length} found`} style={{ marginBottom:20 }}>
                <div style={{ display:'flex', flexDirection:'column', gap:12 }}>
                  {recommendations.map((rec, i) => {
                    const icons = { region_relocation:'🌍', server_rightsizing:'⚙️', time_shifting:'⏰' };
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
