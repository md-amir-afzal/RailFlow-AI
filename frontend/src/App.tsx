import { useCallback, useEffect, useMemo, useState, type ReactNode, type FormEvent } from 'react';
import {
  Activity, AlertTriangle, ArrowDownRight, ArrowRight, ArrowUpRight, BrainCircuit,
  CalendarClock, Check, ChevronDown, CircleHelp, Clock3, GitBranch, Gauge,
  LayoutDashboard, MapPinned, Menu, MessageSquare, Plus, RefreshCw, Route,
  Search, Send, ShieldAlert, ShieldCheck, SlidersHorizontal, Sparkles, TrainFront,
  Trash2, Wifi, X, Zap,
} from 'lucide-react';
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Legend, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';

const API = '/api';
type Train = {
  id: string; name: string; category: string; origin: string; destination: string;
  route: string[]; priority: number; scheduled_departure: string; delay_min: number;
  speed_kmph: number; status: string;
};
type Station = { code: string; name: string; city?: string; lat?: number; lon?: number };
type Section = { from: string; to: string; distance_km: number; tracks: number; capacity_trains_per_hour?: number; utilization_pct?: number; congestion?: string; scheduled_train_count?: number };
type Conflict = { section: string; conflict_type: string; severity: string; train_ids: string[]; train_names: string[]; entry_times: string[]; exit_times: string[]; entry_gap_min: number | null; overlap_min: number; explanation: string };
type Overview = { total_trains: number; active_trains: number; delayed_trains: number; on_time_trains: number; average_delay_min: number; stations: number; track_sections: number; track_utilization_pct: number };
type Prediction = { train_id: string; train_name: string; current_delay_min: number; predicted_delay_min: number; risk: string; confidence: string; top_factors: string[] };
type ApiState = 'connecting' | 'online' | 'offline';

const navItems = [
  { id: 'overview', label: 'Overview', icon: LayoutDashboard, group: 'Workspace' },
  { id: 'trains', label: 'Train operations', icon: TrainFront, group: 'Workspace' },
  { id: 'predictions', label: 'AI predictions', icon: BrainCircuit, group: 'Intelligence' },
  { id: 'scheduling', label: 'Smart scheduling', icon: CalendarClock, group: 'Intelligence' },
  { id: 'congestion', label: 'Congestion forecast', icon: Activity, group: 'Intelligence' },
  { id: 'conflicts', label: 'Conflict detection', icon: ShieldAlert, group: 'Intelligence' },
  { id: 'routes', label: 'Route intelligence', icon: Route, group: 'Network' },
  { id: 'scenarios', label: 'Scenario history', icon: Clock3, group: 'Network' },
  { id: 'analytics', label: 'Analytics', icon: Gauge, group: 'Network' },
  { id: 'assistant', label: 'AI assistant', icon: MessageSquare, group: 'Tools' },
] as const;
type TabId = typeof navItems[number]['id'];

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  const response = await fetch(`${API}${path}`, { ...init, headers });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || body.message || `Request failed (${response.status})`);
  return body as T;
}
function fmtDate(value?: string) {
  if (!value) return '—';
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? value : d.toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
}
function cls(...values: Array<string | false | undefined>) { return values.filter(Boolean).join(' '); }
function Panel({ title, subtitle, action, children, className = '' }: { title: string; subtitle?: string; action?: ReactNode; children: ReactNode; className?: string }) {
  return <section className={cls('panel', className)}><div className="panel-heading"><div><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div>{action}</div>{children}</section>;
}
function Empty({ title, detail }: { title: string; detail: string }) { return <div className="empty-state"><CircleHelp size={25}/><b>{title}</b><span>{detail}</span></div>; }
function Status({ value }: { value: string }) { return <span className={cls('status-pill', value.toLowerCase().includes('critical') || value.toLowerCase().includes('high') || value.toLowerCase().includes('delayed') ? 'danger' : value.toLowerCase().includes('moderate') ? 'warning' : 'success')}>{value}</span>; }

export default function App() {
  const [tab, setTab] = useState<TabId>('overview');
  const [mobileNav, setMobileNav] = useState(false);
  const [apiState, setApiState] = useState<ApiState>('connecting');
  const [busy, setBusy] = useState(false);
  const [lastUpdated, setLastUpdated] = useState('');
  const [error, setError] = useState('');
  const [toast, setToast] = useState('');
  const [overview, setOverview] = useState<Overview | null>(null);
  const [trains, setTrains] = useState<Train[]>([]);
  const [predictions, setPredictions] = useState<{ model: string; metrics: Record<string, number>; predictions: Prediction[] } | null>(null);
  const [network, setNetwork] = useState<{ stations: Station[]; sections: Section[] } | null>(null);
  const [congestion, setCongestion] = useState<{ sections: Section[]; method: string } | null>(null);
  const [conflicts, setConflicts] = useState<{ conflict_count: number; critical_count: number; conflicts: Conflict[]; method: string; safety_note: string; headway_min: number } | null>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [schedule, setSchedule] = useState<any>(null);
  const [routeOptions, setRouteOptions] = useState<any[]>([]);
  const [routeOrigin, setRouteOrigin] = useState('NDLS');
  const [routeDestination, setRouteDestination] = useState('CSMT');
  const [headway, setHeadway] = useState(8);
  const [trainSearch, setTrainSearch] = useState('');
  const [scenario, setScenario] = useState('heavy_traffic');
  const [intensity, setIntensity] = useState(30);
  const [question, setQuestion] = useState('Which trains are delayed?');
  const [answer, setAnswer] = useState('');
  const [newTrainOpen, setNewTrainOpen] = useState(false);
  const [newTrain, setNewTrain] = useState({ id: '', name: '', category: 'Express', origin: 'NDLS', destination: 'JP', route: 'NDLS,JP', priority: 3, delay_min: 0, speed_kmph: 85 });

  const notify = (message: string) => { setToast(message); window.setTimeout(() => setToast(''), 3200); };
  const load = useCallback(async (quiet = false) => {
    if (!quiet) setBusy(true);
    try {
      const [o, t, p, n, c, f, h] = await Promise.all([
        api<Overview>('/overview'), api<Train[]>('/trains'),
        api<{ model: string; metrics: Record<string, number>; predictions: Prediction[] }>('/predictions'),
        api<{ stations: Station[]; sections: Section[] }>('/network'),
        api<{ sections: Section[]; method: string }>('/congestion'),
        api<{ conflict_count: number; critical_count: number; conflicts: Conflict[]; method: string; safety_note: string; headway_min: number }>('/conflicts'),
        api<{ runs: any[] }>('/scenarios?limit=50'),
      ]);
      setOverview(o); setTrains(t); setPredictions(p); setNetwork(n); setCongestion(c); setConflicts(f); setHistory(h.runs || []);
      setApiState('online'); setError(''); setLastUpdated(new Date().toLocaleTimeString('en-IN'));
    } catch (e) {
      setApiState('offline'); setError(e instanceof Error ? e.message : 'Unable to connect to the RailFlow API.');
    } finally { setBusy(false); }
  }, []);
  useEffect(() => { void load(); const timer = window.setInterval(() => void load(true), 20000); return () => window.clearInterval(timer); }, [load]);

  const filteredTrains = useMemo(() => trains.filter(t => `${t.id} ${t.name} ${t.origin} ${t.destination}`.toLowerCase().includes(trainSearch.toLowerCase())), [trains, trainSearch]);
  const delayedTrains = trains.filter(t => t.delay_min > 5);
  const stationOptions = network?.stations || [];
  const sectionHotspots = (congestion?.sections || []).filter(s => (s.utilization_pct || 0) >= 35 || ['High', 'Critical'].includes(s.congestion || ''));

  const runOptimize = async () => {
    try { const result = await api<any>('/optimize', { method: 'POST', body: JSON.stringify({ headway_min: headway, horizon_hours: 24 }) }); setSchedule(result); setTab('scheduling'); notify('Schedule proposal generated'); }
    catch (e) { notify(e instanceof Error ? e.message : 'Optimizer failed'); }
  };
  const runSimulation = async () => {
    try { const result = await api<any>('/simulate', { method: 'POST', body: JSON.stringify({ scenario, seed: Math.floor(Math.random() * 90000) + 10000, intensity }) }); notify(`Scenario completed · ${result.total_delay_min} total delay minutes`); await load(true); setTab('scenarios'); }
    catch (e) { notify(e instanceof Error ? e.message : 'Simulation failed'); }
  };
  const fetchRoutes = async () => {
    try { const result = await api<any[]>(`/routes?origin=${encodeURIComponent(routeOrigin)}&destination=${encodeURIComponent(routeDestination)}`); setRouteOptions(result); }
    catch (e) { setRouteOptions([]); notify(e instanceof Error ? e.message : 'Route search failed'); }
  };
  const askAssistant = async () => {
    if (!question.trim()) return;
    try { const result = await api<{ answer: string }>('/assistant?q=' + encodeURIComponent(question)); setAnswer(result.answer); }
    catch (e) { setAnswer(e instanceof Error ? e.message : 'Assistant unavailable.'); }
  };
  const addTrain = async (event: FormEvent) => {
    event.preventDefault();
    const route = newTrain.route.split(',').map(x => x.trim().toUpperCase()).filter(Boolean);
    try {
      await api('/trains', { method: 'POST', body: JSON.stringify({ ...newTrain, scheduled_departure: new Date().toISOString(), id: newTrain.id.trim().toUpperCase(), origin: newTrain.origin.toUpperCase(), destination: newTrain.destination.toUpperCase(), route }) });
      setNewTrainOpen(false); setNewTrain({ id: '', name: '', category: 'Express', origin: 'NDLS', destination: 'JP', route: 'NDLS,JP', priority: 3, delay_min: 0, speed_kmph: 85 });
      notify('Train added and saved to SQLite'); await load(true);
    } catch (e) { notify(e instanceof Error ? e.message : 'Unable to add train'); }
  };
  const deleteTrain = async (id: string) => {
    if (!window.confirm(`Remove simulated train ${id}?`)) return;
    try { await api(`/trains/${encodeURIComponent(id)}`, { method: 'DELETE' }); notify(`${id} removed`); await load(true); }
    catch (e) { notify(e instanceof Error ? e.message : 'Delete failed'); }
  };
  const updateTrain = async (train: Train, key: 'priority' | 'delay_min', value: number) => {
    try { await api(`/trains/${encodeURIComponent(train.id)}`, { method: 'PATCH', body: JSON.stringify({ [key]: value }) }); notify(`${train.id} updated`); await load(true); }
    catch (e) { notify(e instanceof Error ? e.message : 'Update failed'); }
  };

  const pageTitle = navItems.find(item => item.id === tab)?.label || 'Overview';
  const navGroups = ['Workspace', 'Intelligence', 'Network', 'Tools'];
  return <div className="app-shell">
    {mobileNav && <button className="mobile-scrim" aria-label="Close navigation" onClick={() => setMobileNav(false)} />}
    <aside className={cls('sidebar', mobileNav && 'sidebar-open')}>
      <div className="brand"><div className="brand-mark"><TrainFront size={22}/></div><div><strong>RAILFLOW <em>AI</em></strong><small>TRAFFIC INTELLIGENCE</small></div><button className="mobile-close" onClick={() => setMobileNav(false)}><X size={18}/></button></div>
      <div className="network-chip"><span className="pulse-dot"/> INDIA NETWORK <b>DEMO</b></div>
      <nav className="side-nav">{navGroups.map(group => <div className="nav-group" key={group}><div className="nav-group-title">{group}</div>{navItems.filter(item => item.group === group).map(item => { const Icon = item.icon; return <button key={item.id} className={cls('nav-link', tab === item.id && 'active')} onClick={() => { setTab(item.id); setMobileNav(false); }}><Icon size={17}/><span>{item.label}</span>{tab === item.id && <span className="nav-active-dot"/>}</button>; })}</div>)}</nav>
      <div className="sidebar-bottom"><div className="safety-note"><ShieldCheck size={17}/><div><b>Safety-first workspace</b><p>Decision support only. No connection to live signalling or train control.</p></div></div><div className="operator-row"><div className="operator-avatar">RF</div><div><b>RailFlow Operator</b><small>Local demo workspace</small></div><span className="operator-state"/></div></div>
    </aside>

    <main className="main-area">
      <header className="topbar"><div className="topbar-left"><button className="menu-toggle" onClick={() => setMobileNav(true)}><Menu size={20}/></button><div className="breadcrumb">INDIAN RAILWAYS <span>/</span> <b>{pageTitle.toUpperCase()}</b></div></div><div className="topbar-right"><div className={cls('connection-state', apiState)}><span className="pulse-dot"/>{apiState === 'online' ? 'API CONNECTED' : apiState === 'connecting' ? 'CONNECTING' : 'API OFFLINE'}</div><span className="updated-label">Updated {lastUpdated || '—'}</span><button className="icon-button" onClick={() => void load()} disabled={busy} aria-label="Refresh data"><RefreshCw size={16} className={busy ? 'spin' : ''}/></button></div></header>
      <div className="page-content">
        <div className="page-header"><div><div className="eyebrow">RAILWAY OPERATIONS INTELLIGENCE</div><h1>{tab === 'overview' ? 'Command center' : pageTitle}</h1><p>{tab === 'overview' ? 'A clear operational picture of your illustrative Indian railway network.' : 'Explore the network, inspect model outputs and run controlled simulations.'}</p></div><div className="page-actions"><button className="button button-quiet" onClick={() => void load()}><RefreshCw size={15}/> Refresh</button><button className="button button-primary" onClick={runOptimize}><Zap size={15}/> Optimize network</button></div></div>
        <div className="demo-banner"><div><span className="banner-indicator"/> SYNTHETIC DATA ENVIRONMENT</div><p>All train movements, model metrics and network values are illustrative. This is not live Indian Railways data.</p></div>
        {error && <div className="error-banner"><AlertTriangle size={17}/><div><b>{apiState === 'offline' ? 'Backend connection unavailable' : 'Request error'}</b><span>{error}. Start the backend using <code>run_windows.bat</code> or the README instructions.</span></div><button onClick={() => void load()}><RefreshCw size={14}/> Retry</button></div>}
        {tab === 'overview' && <OverviewPage overview={overview} trains={trains} predictions={predictions} network={network} onNavigate={setTab}/>}
        {tab === 'trains' && <TrainPage trains={filteredTrains} query={trainSearch} setQuery={setTrainSearch} onAdd={() => setNewTrainOpen(true)} onDelete={deleteTrain} onUpdate={updateTrain}/>}
        {tab === 'predictions' && <PredictionsPage predictions={predictions} trains={trains} onUpdated={() => void load(true)} onNotify={notify}/>}
        {tab === 'scheduling' && <SchedulingPage schedule={schedule} headway={headway} setHeadway={setHeadway} onRun={runOptimize}/>}
        {tab === 'congestion' && <CongestionPage congestion={congestion}/>}
        {tab === 'conflicts' && <ConflictsPage conflicts={conflicts}/>}
        {tab === 'routes' && <RoutesPage stations={stationOptions} origin={routeOrigin} destination={routeDestination} setOrigin={setRouteOrigin} setDestination={setRouteDestination} results={routeOptions} onSearch={fetchRoutes}/>}
        {tab === 'scenarios' && <ScenariosPage history={history} scenario={scenario} setScenario={setScenario} intensity={intensity} setIntensity={setIntensity} onRun={runSimulation}/>}
        {tab === 'analytics' && <AnalyticsPage overview={overview} trains={trains} predictions={predictions} congestion={congestion}/>}
        {tab === 'assistant' && <AssistantPage question={question} setQuestion={setQuestion} answer={answer} onAsk={askAssistant}/>}
        <footer className="app-footer"><span><b>RAILFLOW AI</b> · LOCAL SIMULATION BUILD</span><span><i/> API {apiState.toUpperCase()} · SQLITE STORAGE</span><span>FOR RESEARCH & EDUCATION ONLY</span></footer>
      </div>
    </main>
    {newTrainOpen && <div className="modal-backdrop" role="presentation" onMouseDown={e => { if (e.target === e.currentTarget) setNewTrainOpen(false); }}><form className="modal" onSubmit={addTrain}><div className="modal-heading"><div><span className="eyebrow">TRAIN OPERATIONS</span><h2>Add simulated train</h2></div><button type="button" className="icon-button" onClick={() => setNewTrainOpen(false)}><X size={18}/></button></div><div className="form-grid"><label>Train ID<input required value={newTrain.id} onChange={e => setNewTrain({ ...newTrain, id: e.target.value })} placeholder="e.g. RF120"/></label><label>Train name<input required value={newTrain.name} onChange={e => setNewTrain({ ...newTrain, name: e.target.value })} placeholder="Demo Express"/></label><label>Category<select value={newTrain.category} onChange={e => setNewTrain({ ...newTrain, category: e.target.value })}><option>Express</option><option>Superfast</option><option>Passenger</option><option>Freight</option></select></label><label>Origin station<select value={newTrain.origin} onChange={e => setNewTrain({ ...newTrain, origin: e.target.value, route: `${e.target.value},${newTrain.destination}` })}>{stationOptions.map(s => <option key={s.code} value={s.code}>{s.code} · {s.name}</option>)}</select></label><label>Destination station<select value={newTrain.destination} onChange={e => setNewTrain({ ...newTrain, destination: e.target.value, route: `${newTrain.origin},${e.target.value}` })}>{stationOptions.map(s => <option key={s.code} value={s.code}>{s.code} · {s.name}</option>)}</select></label><label>Route station codes<input required value={newTrain.route} onChange={e => setNewTrain({ ...newTrain, route: e.target.value })}/></label><label>Priority (1–5)<input type="number" min="1" max="5" value={newTrain.priority} onChange={e => setNewTrain({ ...newTrain, priority: Number(e.target.value) })}/></label><label>Current delay (min)<input type="number" min="0" value={newTrain.delay_min} onChange={e => setNewTrain({ ...newTrain, delay_min: Number(e.target.value) })}/></label><label>Average speed (km/h)<input type="number" min="1" value={newTrain.speed_kmph} onChange={e => setNewTrain({ ...newTrain, speed_kmph: Number(e.target.value) })}/></label></div><div className="modal-actions"><button type="button" className="button button-quiet" onClick={() => setNewTrainOpen(false)}>Cancel</button><button type="submit" className="button button-primary"><Plus size={15}/> Save train</button></div></form></div>}
    {toast && <div className="toast"><Check size={16}/>{toast}</div>}
  </div>;
}

function OverviewPage({ overview, trains, predictions, network, onNavigate }: { overview: Overview | null; trains: Train[]; predictions: { predictions: Prediction[]; model: string; metrics: Record<string, number> } | null; network: { stations: Station[]; sections: Section[] } | null; onNavigate: (tab: TabId) => void }) {
  const delayed = trains.filter(t => t.delay_min > 5).sort((a, b) => b.delay_min - a.delay_min).slice(0, 5);
  const positions: Record<string, [number, number]> = { NDLS: [340, 64], AGC: [365, 112], GWL: [395, 161], JHS: [417, 211], BPL: [465, 257], NGP: [548, 292], MMR: [400, 300], CSMT: [300, 338], JP: [250, 112], KOTA: [315, 220], ADI: [190, 260], LKO: [430, 38] };
  const chartData = [{ time: '06:00', delay: 18 }, { time: '08:00', delay: 27 }, { time: '10:00', delay: 22 }, { time: '12:00', delay: 36 }, { time: '14:00', delay: 28 }, { time: '16:00', delay: 19 }, { time: '18:00', delay: 31 }];
  return <>
    <div className="metric-grid">
      <Metric label="TOTAL TRAINS" value={overview?.total_trains ?? '—'} note="In current sample network" icon={<TrainFront/>} tone="cyan"/>
      <Metric label="DELAYED TRAINS" value={overview?.delayed_trains ?? '—'} note="More than 5 min simulated delay" icon={<Clock3/>} tone="amber"/>
      <Metric label="AVERAGE DELAY" value={overview ? `${overview.average_delay_min} min` : '—'} note="Across current train set" icon={<Activity/>} tone="violet"/>
      <Metric label="TRACK UTILIZATION" value={overview ? `${overview.track_utilization_pct}%` : '—'} note="Illustrative capacity index" icon={<Gauge/>} tone="green"/>
    </div>
    <div className="content-grid overview-grid">
      <Panel title="Rail network schematic" subtitle="Modeled stations and track sections · not to geographic scale" action={<span className="subtle-chip"><span className="pulse-dot"/> NETWORK MODEL</span>}>
        <div className="network-map"><svg viewBox="0 0 700 380" role="img" aria-label="Schematic sample railway network"><defs><pattern id="mapdots" width="22" height="22" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="1" fill="#294154"/></pattern></defs><rect width="700" height="380" fill="url(#mapdots)"/><path d="M150 25 L265 40 L365 95 L455 85 L555 145 L590 235 L520 310 L410 345 L310 325 L225 265 L170 180 L120 105Z" fill="#10283a" stroke="#29475e" strokeWidth="2"/>
          {(network?.sections || []).map((section, i) => { const a = positions[section.from], b = positions[section.to]; return a && b ? <line key={`${section.from}-${section.to}-${i}`} x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]} stroke={section.tracks === 1 ? '#e7a34d' : '#3289ad'} strokeWidth={section.tracks === 1 ? 3 : 4} strokeLinecap="round"/> : null; })}
          {(network?.stations || []).map(station => { const p = positions[station.code]; return p ? <g key={station.code}><circle cx={p[0]} cy={p[1]} r="9" fill="#071522" stroke="#54c9ef" strokeWidth="2.5"/><circle cx={p[0]} cy={p[1]} r="3" fill="#54c9ef"/><text x={p[0] + 12} y={p[1] - 10} fill="#d3e4ef" fontSize="11">{station.code}</text></g> : null; })}
        </svg><div className="map-key"><span><i className="key-double"/> Multi-track</span><span><i className="key-single"/> Single-track</span><span><i className="key-station"/> Station</span></div></div>
        <div className="map-meta"><span><MapPinned size={14}/>{overview?.stations ?? 0} sample stations</span><span><GitBranch size={14}/>{overview?.track_sections ?? 0} modeled sections</span><span>Illustrative corridor graph</span></div>
      </Panel>
      <Panel title="Operational watchlist" subtitle="Trains with the highest current simulated delay" action={<button className="text-button" onClick={() => onNavigate('trains')}>All trains <ArrowUpRight size={14}/></button>}>
        {delayed.length ? delayed.map(train => <div className="watch-row" key={train.id}><div className="watch-icon"><AlertTriangle size={16}/></div><div className="watch-main"><b>{train.id} · {train.name}</b><span>{train.origin} → {train.destination}</span></div><div className="watch-delay"><strong>{train.delay_min}m</strong><small>DELAY</small></div></div>) : <Empty title="No delayed trains" detail="Current sample trains are within the demo on-time threshold."/>}
        <button className="wide-link" onClick={() => onNavigate('conflicts')}>Review train conflicts <ArrowRight size={15}/></button>
      </Panel>
    </div>
    <div className="content-grid two-col lower-grid">
      <Panel title="Illustrative delay trend" subtitle="Example hourly series · not a historical feed"><div className="chart-wrap"><ResponsiveContainer width="100%" height="100%"><AreaChart data={chartData}><defs><linearGradient id="delayFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#42bfe9" stopOpacity={0.32}/><stop offset="100%" stopColor="#42bfe9" stopOpacity={0}/></linearGradient></defs><CartesianGrid stroke="#20384b" strokeDasharray="4 5" vertical={false}/><XAxis dataKey="time" stroke="#7891a5" tickLine={false} axisLine={false}/><YAxis stroke="#7891a5" tickLine={false} axisLine={false}/><Tooltip contentStyle={{ background: '#102438', border: '1px solid #29475d', borderRadius: 10, color: '#e9f3f9' }}/><Area type="monotone" dataKey="delay" name="Delay minutes" stroke="#48c3eb" fill="url(#delayFill)" strokeWidth={2.5}/></AreaChart></ResponsiveContainer></div></Panel>
      <Panel title="AI model snapshot" subtitle="Synthetic holdout evaluation" action={<button className="text-button" onClick={() => onNavigate('predictions')}>Details <ArrowUpRight size={14}/></button>}>
        <div className="model-snapshot"><div className="model-logo"><BrainCircuit size={23}/></div><div><b>{predictions?.model || 'Model loading'}</b><span>Selected delay regression model</span></div></div><div className="model-stats"><div><small>MAE</small><b>{predictions?.metrics?.mae ?? '—'}</b></div><div><small>RMSE</small><b>{predictions?.metrics?.rmse ?? '—'}</b></div><div><small>R²</small><b>{predictions?.metrics?.r2 ?? '—'}</b></div></div><p className="fine-print">Metrics are calculated on generated synthetic examples and are not real-world performance claims.</p>
      </Panel>
    </div>
  </>;
}
function Metric({ label, value, note, icon, tone }: { label: string; value: ReactNode; note: string; icon: ReactNode; tone: string }) { return <div className="metric-card"><div className="metric-top"><span>{label}</span><div className={`metric-icon ${tone}`}>{icon}</div></div><strong>{value}</strong><small>{note}</small></div>; }

function TrainPage({ trains, query, setQuery, onAdd, onDelete, onUpdate }: { trains: Train[]; query: string; setQuery: (s: string) => void; onAdd: () => void; onDelete: (id: string) => void; onUpdate: (train: Train, key: 'priority' | 'delay_min', value: number) => void }) {
  return <Panel title="Train operations" subtitle={`${trains.length} trains match your current view`} action={<button className="button button-primary" onClick={onAdd}><Plus size={15}/> Add train</button>}>
    <div className="table-toolbar"><label className="search-box"><Search size={16}/><input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search train ID, name or station..."/></label><span className="fine-print">Changes save to local SQLite</span></div>
    {trains.length ? <div className="table-scroll"><table><thead><tr><th>TRAIN</th><th>ROUTE</th><th>CATEGORY</th><th>PRIORITY</th><th>DELAY</th><th>STATUS</th><th>ACTIONS</th></tr></thead><tbody>{trains.map(train => <tr key={train.id}><td><b>{train.id}</b><small>{train.name}</small></td><td>{train.origin} <span className="muted">→</span> {train.destination}<small>{train.route.join(' · ')}</small></td><td>{train.category}</td><td><select className="inline-select" value={train.priority} onChange={e => onUpdate(train, 'priority', Number(e.target.value))}>{[1,2,3,4,5].map(n => <option key={n} value={n}>{n}</option>)}</select></td><td><input className="inline-number" aria-label={`Delay for ${train.id}`} type="number" min="0" max="1000" defaultValue={train.delay_min} key={`${train.id}-${train.delay_min}`} onBlur={e => { const value = Math.max(0, Number(e.target.value)); if (value !== train.delay_min) onUpdate(train, 'delay_min', value); }}/><small>minutes</small></td><td><Status value={train.status || (train.delay_min > 5 ? 'Delayed' : 'On time')}/></td><td><button className="icon-button danger-button" onClick={() => onDelete(train.id)} aria-label={`Delete ${train.id}`}><Trash2 size={15}/></button></td></tr>)}</tbody></table></div> : <Empty title="No trains found" detail="Try a different search term or add a demo train."/>}
  </Panel>;
}
function PredictionsPage({ predictions, trains, onUpdated, onNotify }: { predictions: { model: string; metrics: Record<string, number>; predictions: Prediction[] } | null; trains: Train[]; onUpdated: () => void; onNotify: (s: string) => void }) {
  const [trainId, setTrainId] = useState(trains[0]?.id || '');
  const [actual, setActual] = useState('');
  const [learning, setLearning] = useState<any>(null);
  useEffect(() => { void api<any>('/learning').then(setLearning).catch(() => undefined); }, []);
  const addOutcome = async (event: FormEvent) => { event.preventDefault(); try { const result = await api<any>('/learning/feedback', { method: 'POST', body: JSON.stringify({ train_id: trainId, actual_delay_min: Number(actual) }) }); setLearning({ ...learning, verified_outcomes: result.verified_outcomes }); setActual(''); onNotify('Verified outcome saved for model learning'); onUpdated(); } catch (e) { onNotify(e instanceof Error ? e.message : 'Could not save outcome'); } };
  const retrain = async () => { try { const result = await api<any>('/learning/retrain', { method: 'POST' }); onNotify(`Model retrained · ${result.verified_outcomes} verified outcomes`); onUpdated(); } catch (e) { onNotify(e instanceof Error ? e.message : 'Retraining failed'); } };
  return <><div className="metric-grid compact-grid"><Metric label="SELECTED MODEL" value={predictions?.model || '—'} note="Best synthetic holdout score" icon={<BrainCircuit/>} tone="violet"/><Metric label="MAE" value={predictions?.metrics?.mae ?? '—'} note="Mean absolute error · minutes" icon={<Gauge/>} tone="cyan"/><Metric label="RMSE" value={predictions?.metrics?.rmse ?? '—'} note="Root mean squared error" icon={<Activity/>} tone="amber"/><Metric label="R² SCORE" value={predictions?.metrics?.r2 ?? '—'} note="Synthetic holdout only" icon={<Sparkles/>} tone="green"/></div><Panel title="Train delay predictions" subtitle="Predictions are estimates from a model trained on generated data.">{predictions?.predictions?.length ? <div className="table-scroll"><table><thead><tr><th>TRAIN</th><th>CURRENT DELAY</th><th>PREDICTED DELAY</th><th>RISK BAND</th><th>MODEL CONTEXT</th></tr></thead><tbody>{predictions.predictions.map(p => <tr key={p.train_id}><td><b>{p.train_id}</b><small>{p.train_name}</small></td><td>{p.current_delay_min} min</td><td><b className="prediction-value">{p.predicted_delay_min} min</b></td><td><Status value={p.risk}/></td><td className="muted">{p.top_factors.join(' · ')}</td></tr>)}</tbody></table></div> : <Empty title="Predictions unavailable" detail="Start the API and refresh this page."/>}</Panel><Panel title="Continuous learning" subtitle="Record actual arrival delays to improve future predictions with verified examples."><div className="control-row"><span>{learning?.verified_outcomes ?? 0} verified outcomes saved · automatic refit every 20</span><button className="button button-quiet" onClick={retrain} disabled={(learning?.verified_outcomes ?? 0) < 10}><RefreshCw size={15}/> Retrain model</button></div><form className="route-controls" onSubmit={addOutcome}><label>Train<select value={trainId} onChange={e => setTrainId(e.target.value)}>{trains.map(t => <option key={t.id} value={t.id}>{t.id} · {t.name}</option>)}</select></label><label>Actual arrival delay (minutes)<input type="number" min="0" max="1440" step="1" required value={actual} onChange={e => setActual(e.target.value)} placeholder="e.g. 18"/></label><button className="button button-primary" type="submit" disabled={!trainId || !actual}><Check size={15}/> Save outcome</button></form></Panel><div className="info-callout"><ShieldCheck size={18}/><span>Learning uses verified operational outcomes alongside synthetic baseline examples. Generated data is not real railway data; review model metrics before relying on predictions.</span></div></>;
}
function SchedulingPage({ schedule, headway, setHeadway, onRun }: { schedule: any; headway: number; setHeadway: (n: number) => void; onRun: () => void }) {
  return <><Panel title="Section-aware timetable optimizer" subtitle="Earliest-feasible heuristic using modeled route sections, track capacity and minimum entry headway" action={<button className="button button-primary" onClick={onRun}><Zap size={15}/> Run optimizer</button>}><div className="control-row"><label>Minimum headway <select value={headway} onChange={e => setHeadway(Number(e.target.value))}>{[4,6,8,10,12,15,20,30].map(n => <option key={n} value={n}>{n} minutes</option>)}</select></label><div className="control-explain"><SlidersHorizontal size={16}/> Search horizon: 24 hours</div></div>{schedule ? <><div className="metric-grid compact-grid result-metrics"><Metric label="ORIGINAL TOTAL DELAY" value={`${schedule.original_total_delay_min} min`} note="Current simulated delays" icon={<Clock3/>} tone="amber"/><Metric label="PROPOSED TOTAL DELAY" value={`${schedule.optimized_total_delay_min} min`} note="Heuristic schedule estimate" icon={<CalendarClock/>} tone="cyan"/><Metric label="CHANGE IN DELAY" value={`${schedule.delay_change_min > 0 ? '+' : ''}${schedule.delay_change_min} min`} note="Negative means lower total delay" icon={schedule.delay_change_min <= 0 ? <ArrowDownRight/> : <ArrowUpRight/>} tone="green"/><Metric label="SECTIONS RESERVED" value={schedule.resource_sections_reserved} note="Modeled shared resources" icon={<GitBranch/>} tone="violet"/></div><div className="result-label"><span className="subtle-chip">{schedule.status}</span><span>{schedule.method}</span></div><div className="table-scroll"><table><thead><tr><th>TRAIN</th><th>ORIGINAL DELAY</th><th>PROPOSED DEPARTURE</th><th>PROPOSED DELAY</th><th>PLANNED WAIT</th><th>CHANGE</th></tr></thead><tbody>{(schedule.trains || []).map((t: any) => <tr key={t.id}><td><b>{t.id}</b><small>{t.name}</small></td><td>{t.delay_min} min</td><td>{fmtDate(t.optimized_departure)}</td><td>{t.optimized_delay_min} min</td><td>{t.planned_wait_min} min</td><td className={t.change_min > 0 ? 'text-danger' : 'text-success'}>{t.change_min > 0 ? '+' : ''}{t.change_min} min</td></tr>)}</tbody></table></div><div className="info-callout"><ShieldCheck size={18}/><span>{schedule.safety_note}</span></div></> : <Empty title="No schedule proposal yet" detail="Choose a headway and run the optimizer to generate a proposed dispatch plan."/>}</Panel></>;
}
function CongestionPage({ congestion }: { congestion: { sections: Section[]; method: string } | null }) {
  const rows = congestion?.sections || [];
  return <><div className="metric-grid compact-grid"><Metric label="MODELED SECTIONS" value={rows.length} note="Sample graph edges" icon={<GitBranch/>} tone="cyan"/><Metric label="HIGH / CRITICAL" value={rows.filter(s => ['High','Critical'].includes(s.congestion || '') || (s.utilization_pct || 0) >= 65).length} note="Route-overlap proxy" icon={<AlertTriangle/>} tone="amber"/><Metric label="SINGLE TRACK" value={rows.filter(s => s.tracks === 1).length} note="Higher sensitivity in demo" icon={<Route/>} tone="violet"/><Metric label="FORECAST WINDOW" value="60 min" note="Illustrative proxy horizon" icon={<Clock3/>} tone="green"/></div><Panel title="Section congestion index" subtitle={congestion?.method || 'Route-overlap density proxy, not live occupancy'}>{rows.length ? <div className="table-scroll"><table><thead><tr><th>SECTION</th><th>DISTANCE</th><th>TRACKS</th><th>TRAINS ON ROUTE</th><th>UTILIZATION</th><th>LEVEL</th></tr></thead><tbody>{rows.map((s, i) => <tr key={`${s.from}-${s.to}-${i}`}><td><b>{s.from} — {s.to}</b></td><td>{s.distance_km} km</td><td>{s.tracks}</td><td>{s.scheduled_train_count ?? '—'}</td><td><div className="util-cell"><div className="util-track"><i style={{ width: `${Math.min(100, s.utilization_pct || 0)}%` }}/></div><span>{s.utilization_pct ?? 0}%</span></div></td><td><Status value={s.congestion || 'Low'}/></td></tr>)}</tbody></table></div> : <Empty title="No congestion data" detail="Connect to the backend to load modeled section values."/>}</Panel></>;
}
function ConflictsPage({ conflicts }: { conflicts: { conflict_count: number; critical_count: number; conflicts: Conflict[]; method: string; safety_note: string; headway_min: number } | null }) {
  return <><div className="metric-grid compact-grid"><Metric label="DETECTED FLAGS" value={conflicts?.conflict_count ?? '—'} note="Estimated schedule conflicts" icon={<ShieldAlert/>} tone="amber"/><Metric label="CRITICAL FLAGS" value={conflicts?.critical_count ?? '—'} note="Overlap / capacity exceedance" icon={<AlertTriangle/>} tone="violet"/><Metric label="SCREENING METHOD" value="Section" note="Entry / exit interval estimate" icon={<GitBranch/>} tone="cyan"/><Metric label="HEADWAY RULE" value={`${conflicts?.headway_min ?? 8} min`} note="Default screening threshold" icon={<Clock3/>} tone="green"/></div><Panel title="Train-to-train conflict screening" subtitle={conflicts?.method || 'Estimated section occupancy and headway checks'}>{conflicts?.conflicts?.length ? <div className="conflict-list">{conflicts.conflicts.map((c, i) => <article className="conflict-card" key={`${c.section}-${i}`}><div className="conflict-top"><div><span className="eyebrow">{c.conflict_type.replaceAll('_', ' ')}</span><h3>{c.section}</h3></div><Status value={c.severity}/></div><div className="conflict-trains">{c.train_ids.map((id, index) => <span key={`${id}-${index}`}><TrainFront size={14}/>{id}</span>)}</div><p>{c.explanation}</p><div className="conflict-meta"><span>Entry gap: {c.entry_gap_min ?? '—'} min</span><span>Overlap: {c.overlap_min} min</span></div></article>)}</div> : <Empty title="No conflicts detected" detail="The current illustrative timetable has no flags at the configured default headway. Controlled test cases validate the screening logic."/>}<div className="info-callout"><ShieldAlert size={18}/><span>{conflicts?.safety_note || 'Screening only. Never use this as an authority to dispatch trains.'}</span></div></Panel></>;
}
function RoutesPage({ stations, origin, destination, setOrigin, setDestination, results, onSearch }: { stations: Station[]; origin: string; destination: string; setOrigin: (s: string) => void; setDestination: (s: string) => void; results: any[]; onSearch: () => void }) {
  return <Panel title="Alternate route intelligence" subtitle="Compare feasible paths in the modeled corridor graph"><div className="route-controls"><label>Origin station<select value={origin} onChange={e => setOrigin(e.target.value)}>{stations.map(s => <option key={s.code} value={s.code}>{s.code} · {s.name}</option>)}</select></label><button className="swap-button" onClick={() => { setOrigin(destination); setDestination(origin); }}><ArrowRight size={16}/></button><label>Destination station<select value={destination} onChange={e => setDestination(e.target.value)}>{stations.map(s => <option key={s.code} value={s.code}>{s.code} · {s.name}</option>)}</select></label><button className="button button-primary" onClick={onSearch}><Search size={15}/> Find routes</button></div>{results.length ? <div className="route-list">{results.map((r, i) => <div className="route-option" key={i}><div className="route-number">0{i + 1}</div><div className="route-description"><b>{(r.stations || r.path || r.route || []).join('  →  ')}</b><span>{r.travel_minutes ?? '—'} estimated minutes · {(r.stations || r.path || r.route || []).length} stations · congestion penalty {r.congestion_penalty ?? 0}</span></div><div className="route-score"><strong>{r.score ?? r.estimated_time_min ?? '—'}</strong><small>{r.score !== undefined ? 'ROUTE SCORE' : 'EST. MINUTES'}</small></div></div>)}</div> : <Empty title="No route comparison yet" detail="Select an origin and destination, then find modeled paths."/>}</Panel>;
}
function ScenariosPage({ history, scenario, setScenario, intensity, setIntensity, onRun }: { history: any[]; scenario: string; setScenario: (s: string) => void; intensity: number; setIntensity: (n: number) => void; onRun: () => void }) {
  const names: Record<string, string> = { normal: 'Normal operations', heavy_traffic: 'Heavy traffic', junction_delay: 'Junction delay', single_track: 'Single-track disruption', platform_block: 'Platform blockage', maintenance: 'Maintenance window' };
  return <><Panel title="Run a disruption scenario" subtitle="Create reproducible what-if runs using synthetic train movements" action={<button className="button button-primary" onClick={onRun}><Zap size={15}/> Run simulation</button>}><div className="scenario-controls"><label>Scenario type<select value={scenario} onChange={e => setScenario(e.target.value)}>{Object.entries(names).map(([v, label]) => <option key={v} value={v}>{label}</option>)}</select></label><label>Disruption intensity <div className="range-row"><input type="range" min="0" max="180" step="5" value={intensity} onChange={e => setIntensity(Number(e.target.value))}/><b>{intensity} min</b></div></label></div></Panel><Panel title="Saved simulation runs" subtitle={`${history.length} recent runs · stored in local SQLite`}>{history.length ? <div className="table-scroll"><table><thead><tr><th>RUN</th><th>SCENARIO</th><th>RUN TIME</th><th>TRAINS</th><th>TOTAL DELAY</th><th>SEED</th></tr></thead><tbody>{history.map((run, i) => <tr key={run.id || i}><td><b>#{run.id ?? i + 1}</b></td><td>{names[run.scenario] || run.scenario}</td><td>{fmtDate(run.created_at || run.timestamp)}</td><td>{run.result?.trains?.length ?? '—'}</td><td>{run.result?.total_delay_min ?? '—'} min</td><td>{run.seed ?? run.result?.seed ?? '—'}</td></tr>)}</tbody></table></div> : <Empty title="No saved scenarios yet" detail="Run a scenario above. Its result will be saved to SQLite."/>}</Panel></>;
}
function AnalyticsPage({ overview, trains, predictions, congestion }: { overview: Overview | null; trains: Train[]; predictions: { predictions: Prediction[] } | null; congestion: { sections: Section[] } | null }) {
  const risk = ['Low', 'Moderate', 'High', 'Critical'].map(level => ({ level, trains: predictions?.predictions.filter(p => p.risk === level).length || 0 }));
  const category = [...new Set(trains.map(t => t.category))].map(name => ({ name, count: trains.filter(t => t.category === name).length }));
  const delayData = trains.map(t => ({ train: t.id, current: t.delay_min, predicted: predictions?.predictions.find(p => p.train_id === t.id)?.predicted_delay_min || 0 }));
  return <><div className="metric-grid compact-grid"><Metric label="ON-TIME TRAINS" value={overview?.on_time_trains ?? '—'} note="Delay no more than 5 minutes" icon={<Check/>} tone="green"/><Metric label="DELAYED TRAINS" value={overview?.delayed_trains ?? '—'} note="Current sample timetable" icon={<Clock3/>} tone="amber"/><Metric label="NETWORK STATIONS" value={overview?.stations ?? '—'} note="Illustrative station set" icon={<MapPinned/>} tone="cyan"/><Metric label="TRACK SECTIONS" value={overview?.track_sections ?? '—'} note="Modeled graph edges" icon={<GitBranch/>} tone="violet"/></div><div className="content-grid two-col"><Panel title="Train delay comparison" subtitle="Current vs model-predicted minutes"><div className="chart-wrap tall"><ResponsiveContainer width="100%" height="100%"><BarChart data={delayData}><CartesianGrid stroke="#20384b" strokeDasharray="4 5" vertical={false}/><XAxis dataKey="train" stroke="#7891a5"/><YAxis stroke="#7891a5"/><Tooltip contentStyle={{ background: '#102438', border: '1px solid #29475d', borderRadius: 10 }}/><Legend/><Bar dataKey="current" name="Current delay" fill="#e7a34d" radius={[4,4,0,0]}/><Bar dataKey="predicted" name="Predicted delay" fill="#43bfe9" radius={[4,4,0,0]}/></BarChart></ResponsiveContainer></div></Panel><Panel title="Prediction risk distribution" subtitle="Model risk bands · synthetic sample"><div className="chart-wrap tall"><ResponsiveContainer width="100%" height="100%"><BarChart data={risk}><CartesianGrid stroke="#20384b" strokeDasharray="4 5" vertical={false}/><XAxis dataKey="level" stroke="#7891a5"/><YAxis stroke="#7891a5" allowDecimals={false}/><Tooltip contentStyle={{ background: '#102438', border: '1px solid #29475d', borderRadius: 10 }}/><Bar dataKey="trains" name="Train count" fill="#8f83db" radius={[4,4,0,0]}/></BarChart></ResponsiveContainer></div></Panel></div><Panel title="Train category distribution" subtitle="Current demo fleet mix"><div className="category-bars">{category.map(c => <div key={c.name}><span>{c.name}</span><div className="util-track"><i style={{ width: `${trains.length ? c.count / trains.length * 100 : 0}%` }}/></div><b>{c.count}</b></div>)}</div></Panel><p className="fine-print">All visualizations are based on the small synthetic sample network. They are not operational performance statistics.</p></>;
}
function AssistantPage({ question, setQuestion, answer, onAsk }: { question: string; setQuestion: (s: string) => void; answer: string; onAsk: () => void }) {
  const suggestions = ['Which trains are delayed?', 'What sections are congested?', 'How does schedule optimization work?'];
  return <Panel title="RailFlow AI assistant" subtitle="Ask questions about the current synthetic application state"><div className="assistant-layout"><div className="assistant-avatar"><BrainCircuit size={28}/></div><h2>How can I help with your network?</h2><p>Ask about delays, congestion, conflicts or the schedule optimization workflow.</p><div className="suggestion-list">{suggestions.map(s => <button key={s} onClick={() => setQuestion(s)}>{s}</button>)}</div><form className="assistant-input" onSubmit={e => { e.preventDefault(); onAsk(); }}><input value={question} onChange={e => setQuestion(e.target.value)} placeholder="Ask RailFlow AI..."/><button className="button button-primary" type="submit"><Send size={15}/> Ask</button></form>{answer && <div className="assistant-answer"><div><Sparkles size={15}/> RAILFLOW RESPONSE</div><p>{answer}</p><small>Generated from current demo application state · synthetic data</small></div>}</div></Panel>;
}
