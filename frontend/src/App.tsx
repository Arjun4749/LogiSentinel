import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  LayoutDashboard, Map as MapIcon, Bell, TrendingUp, Boxes, ClipboardList, Truck, CloudSnow, FlaskConical,
  Radio, FileText, ScrollText, Settings2, LogOut, Compass, ChevronLeft, ChevronRight, X, Menu, Moon, Sun,
  CheckCircle2, AlertOctagon, Info, Bot, FastForward, Pause, Play, ChevronDown, Sparkles,
} from "lucide-react";
import { api, getToken, setToken, setUnauthorizedHandler, User } from "./api";
import { AppContext, Btn, Page, Sector, SECTOR_LABEL, TZ_LABEL } from "./ui";
import { TOUR } from "./tour";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import AiCentre from "./pages/AiCentre";
import MapPage from "./pages/MapPage";
import Alerts from "./pages/Alerts";
import Forecast from "./pages/Forecast";
import Inventory from "./pages/Inventory";
import Requests from "./pages/Requests";
import Shipments from "./pages/Shipments";
import Disruptions from "./pages/Disruptions";
import Scenario from "./pages/Scenario";
import Iot from "./pages/Iot";
import Reports from "./pages/Reports";
import Audit from "./pages/Audit";
import System from "./pages/System";

const NAV: { group: string; items: { id: Page; label: string; icon: any }[] }[] = [
  { group: "Command", items: [
    { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
    { id: "ai", label: "AI Command Centre", icon: Bot },
    { id: "map", label: "Network map", icon: MapIcon },
    { id: "alerts", label: "Alerts", icon: Bell },
  ] },
  { group: "Plan", items: [
    { id: "forecast", label: "Demand forecast", icon: TrendingUp },
    { id: "inventory", label: "Stock & replenishment", icon: Boxes },
    { id: "requests", label: "Supply requests", icon: ClipboardList },
    { id: "shipments", label: "Transport & shipments", icon: Truck },
  ] },
  { group: "Assess", items: [
    { id: "disruptions", label: "Weather & disruptions", icon: CloudSnow },
    { id: "scenario", label: "What-if simulator", icon: FlaskConical },
    { id: "iot", label: "IoT sensors", icon: Radio },
  ] },
  { group: "Records", items: [
    { id: "reports", label: "Reports & SITREP", icon: FileText },
    { id: "audit", label: "Audit log", icon: ScrollText },
    { id: "system", label: "System & help", icon: Settings2 },
  ] },
];
const LABEL: Record<string, string> = Object.fromEntries(NAV.flatMap(g => g.items.map(i => [i.id, i.label])));
const SPEEDS: { v: number; label: string; title: string }[] = [
  { v: 0, label: "Pause", title: "Pause the simulation" },
  { v: 1, label: "Live", title: "Real time: simulation time moves exactly like a normal clock" },
  { v: 60, label: "60x", title: "Demo speed: 1 real minute = 1 simulated hour" },
  { v: 360, label: "360x", title: "Fast demo: 10 real seconds = 1 simulated hour" },
  { v: 1440, label: "1440x", title: "Very fast: 1 real minute = 1 simulated day" },
];

function parseHash(): { page: Page; params: Record<string, string> } {
  const h = window.location.hash.replace(/^#\/?/, "");
  const [p, q] = h.split("?");
  const params: Record<string, string> = {};
  new URLSearchParams(q || "").forEach((v, k) => (params[k] = v));
  return { page: (LABEL[p] ? p : "dashboard") as Page, params };
}

type Toast = { id: number; msg: string; kind: "ok" | "err" | "info" | "ai"; action?: { label: string; page: Page } };

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const pad = (n: number) => String(n).padStart(2, "0");

function MissionClock({ status, canAct, onSpeed, onSkip }: { status: any; canAct: boolean; onSpeed: (v: number) => void; onSkip: (h: number) => void }) {
  const [, setTick] = useState(0);
  const [menu, setMenu] = useState(false);
  useEffect(() => { const t = setInterval(() => setTick(x => x + 1), 1000); return () => clearInterval(t); }, []);
  if (!status?.clock) return <div className="clock"><div className="clock-read"><small>Simulation time</small><strong className="num">--:--:--</strong></div></div>;
  const c = status.clock;
  const ms = Date.parse(c.sim_time) + (c.pending_hours || 0) * 3.6e6 + (Date.now() - status._received) * c.speed;
  const d = new Date(ms);
  const ahead = (ms - Date.now()) / 3.6e6;
  const mode = c.speed === 0 ? "paused" : c.speed === 1 ? "live" : "fast";
  return (
    <div className={`clock clock-${mode}`}>
      <div className="clock-read" title="Simulation time drives stock consumption, convoy movement and AI decisions">
        <small><i className="clock-dot" />{mode === "live" ? "Live - real time" : mode === "paused" ? "Paused" : `Fast-forward ${c.speed}x`}
          {Math.abs(ahead) >= 0.25 && <em> - {ahead > 0 ? `${ahead >= 48 ? (ahead / 24).toFixed(1) + " days" : ahead.toFixed(1) + " h"} ahead of real time` : "behind real time"}</em>}</small>
        <strong className="num">{DAYS[d.getDay()]} {d.getDate()} {MONTHS[d.getMonth()]}, {pad(d.getHours())}:{pad(d.getMinutes())}<span className="secs">:{pad(d.getSeconds())}</span> <span className="tz">{TZ_LABEL}</span></strong>
      </div>
      {canAct && <>
        <div className="speed-seg" role="group" aria-label="Simulation speed">
          {SPEEDS.map(s => (
            <button key={s.v} className={c.speed === s.v ? "on" : ""} title={s.title} onClick={() => onSpeed(s.v)}>
              {s.v === 0 ? <Pause size={13} /> : s.v === 1 ? <Play size={13} /> : null}<span>{s.v === 0 ? "" : s.label}</span>
            </button>
          ))}
        </div>
        <div className="skip">
          <button className="clock-btn" onClick={() => setMenu(m => !m)} aria-expanded={menu} title="Jump the simulation forward instantly">
            <FastForward size={14} /> Skip ahead <ChevronDown size={13} />
          </button>
          {menu && <div className="skip-menu" onMouseLeave={() => setMenu(false)}>
            {[[1, "1 hour"], [6, "6 hours"], [24, "1 day"]].map(([h, l]) => (
              <button key={h} onClick={() => { setMenu(false); onSkip(h as number); }}>Skip {l}</button>
            ))}
          </div>}
        </div>
      </>}
    </div>
  );
}

export default function App() {
  const [user, setUser] = useState<User | null>(() => {
    try { const u = localStorage.getItem("ls_user"); return u && getToken() ? JSON.parse(u) : null; } catch { return null; }
  });
  const [route, setRoute] = useState(parseHash);
  const [version, setVersion] = useState(0);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [status, setStatus] = useState<any>(null);
  const [tourStep, setTourStep] = useState<number | null>(null);
  const [navOpen, setNavOpen] = useState(false);
  const [sector, setSectorState] = useState<Sector>(() => {
    try { return (localStorage.getItem("ls_sector") as Sector) || "ALL"; } catch { return "ALL"; }
  });
  const [theme, setTheme] = useState<"chart" | "night">(() => {
    try { return (localStorage.getItem("ls_theme") as any) || "chart"; } catch { return "chart"; }
  });
  const setSector = useCallback((s: Sector) => { setSectorState(s); try { localStorage.setItem("ls_sector", s); } catch { /* ignore */ } }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem("ls_theme", theme); } catch { /* ignore */ }
  }, [theme]);

  const toast = useCallback((msg: string, kind: Toast["kind"] = "info", action?: Toast["action"]) => {
    const id = Date.now() + Math.random();
    setToasts(t => [...t.slice(-3), { id, msg, kind, action }]);
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), kind === "err" ? 7000 : kind === "ai" ? 9000 : 4200);
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    try { localStorage.removeItem("ls_user"); } catch { /* ignore */ }
    setUser(null); setTourStep(null);
  }, []);
  useEffect(() => setUnauthorizedHandler(() => { logout(); }), [logout]);

  useEffect(() => {
    const h = () => setRoute(parseHash());
    window.addEventListener("hashchange", h);
    return () => window.removeEventListener("hashchange", h);
  }, []);

  const go = useCallback((p: Page, params?: Record<string, string>) => {
    const q = params ? "?" + new URLSearchParams(params).toString() : "";
    window.location.hash = `/${p}${q}`;
    setNavOpen(false);
    window.scrollTo({ top: 0 });
  }, []);
  const lastRefresh = useRef(0);
  const refresh = useCallback(() => { lastRefresh.current = Date.now(); setVersion(v => v + 1); }, []);

  // ---- status poll: live clock, alert badge, AI actions, auto-refresh ----
  const prev = useRef<{ sim: string; ai: number; alerts: number } | null>(null);
  const poll = useCallback(() => {
    api("/api/status").then((s: any) => {
      s._received = Date.now();
      setStatus(s);
      const p = prev.current;
      if (p) {
        if (s.ai.actions > p.ai && s.ai.last) {
          const n = s.ai.actions - p.ai;
          toast(n > 1 ? `AI Autopilot took ${n} actions. Latest: ${s.ai.last.title}` : `AI Autopilot: ${s.ai.last.title}`, "ai",
            { label: "See why", page: "ai" });
        }
        const changed = s.sim_time !== p.sim || s.ai.actions !== p.ai || s.alerts_new !== p.alerts;
        if (changed && Date.now() - lastRefresh.current > 7000) refresh();
      }
      prev.current = { sim: s.sim_time, ai: s.ai.actions, alerts: s.alerts_new };
    }).catch(() => {});
  }, [toast, refresh]);
  useEffect(() => {
    if (!user) return;
    poll();
    const t = setInterval(poll, 4000);
    return () => clearInterval(t);
  }, [user, poll]);

  const setSpeed = useCallback(async (v: number) => {
    try {
      await api("/api/clock", { method: "POST", body: { speed: v } });
      toast(v === 0 ? "Simulation paused" : v === 1 ? "Clock running in real time" : `Fast-forward ${v}x - ${SPEEDS.find(s => s.v === v)?.title.split(": ")[1]}`, "ok");
      poll();
    } catch (e: any) { toast(e.message, "err"); }
  }, [toast, poll]);
  const skip = useCallback(async (h: number) => {
    try {
      const r: any = await api("/api/sim/advance", { method: "POST", body: { hours: h } });
      toast(`Skipped ahead ${h} h${r.model_retrained ? " - new day: model retrained" : ""}${r.ai_actions ? ` - AI took ${r.ai_actions} action(s)` : ""}`, "ok");
      poll(); refresh();
    } catch (e: any) { toast(e.message, "err"); }
  }, [toast, poll, refresh]);

  const ctx = useMemo(() => user && ({
    user, version, refresh, toast: (m: string, k?: any) => toast(m, k), go, params: route.params, simTime: status?.sim_time || "", theme,
    sector, setSector,
    can: (role: "planner" | "admin") => role === "planner" ? user.role !== "viewer" : user.role === "admin",
  }), [user, version, refresh, toast, go, route.params, status?.sim_time, theme, sector, setSector]);

  if (!user || !ctx) {
    return <Login theme={theme} onLogin={(u, t) => { setToken(t); try { localStorage.setItem("ls_user", JSON.stringify(u)); } catch { /* ignore */ } setUser(u); setVersion(v => v + 1); }} />;
  }

  const startTour = () => { setTourStep(0); go(TOUR[0].page, TOUR[0].params); };
  const tourGo = (i: number) => { setTourStep(i); go(TOUR[i].page, TOUR[i].params); };

  const pages: Record<Page, JSX.Element> = {
    dashboard: <Dashboard />, ai: <AiCentre />, map: <MapPage />, alerts: <Alerts />, forecast: <Forecast />, inventory: <Inventory />,
    requests: <Requests />, shipments: <Shipments />, disruptions: <Disruptions />, scenario: <Scenario />, iot: <Iot />,
    reports: <Reports />, audit: <Audit />, system: <System onStartTour={startTour} />,
  };
  const canAct = user.role !== "viewer";
  const aiOn = status?.ai?.enabled !== false;

  return (
    <AppContext.Provider value={ctx}>
      <div className="shell">
        {navOpen && <button className="scrim" aria-label="Close menu" onClick={() => setNavOpen(false)} />}
        <aside className={`sidebar ${navOpen ? "open" : ""}`}>
          <div className="brand">
            <svg viewBox="0 0 64 64" className="brand-mark" aria-hidden="true"><path d="M4 50 L22 20 L32 34 L40 24 L60 50 Z" fill="currentColor" opacity=".35" /><path d="M4 50 L22 20 L32 34 L40 24 L60 50" fill="none" stroke="currentColor" strokeWidth="3" /><circle cx="48" cy="14" r="6" fill="var(--signal)" /></svg>
            <div><strong>LogiSentinel</strong><small>AI forward logistics</small></div>
            <button className="icon-btn only-mobile" onClick={() => setNavOpen(false)} aria-label="Close menu"><X size={18} /></button>
          </div>
          <button className={`ai-pill ${aiOn ? "on" : "off"}`} onClick={() => go("ai")} title="Open the AI Command Centre">
            <Sparkles size={15} /><span>AI Autopilot {aiOn ? "on" : "off"}</span>{aiOn && <i className="pulse" />}
            {status?.ai?.handled > 0 && <b>{status.ai.handled} handled</b>}
          </button>
          <nav>
            {NAV.map(g => (
              <div className="nav-group" key={g.group}>
                <div className="nav-label">{g.group}</div>
                {g.items.map(it => {
                  const Icon = it.icon;
                  return (
                    <button key={it.id} className={`nav-item ${route.page === it.id ? "active" : ""}`} onClick={() => go(it.id)}>
                      <Icon size={17} /><span>{it.label}</span>
                      {it.id === "alerts" && status?.alerts_new > 0 && <span className={`nav-count ${status.alerts_critical ? "crit" : ""}`}>{status.alerts_new}</span>}
                      {it.id === "requests" && status?.pending_requests > 0 && <span className="nav-count">{status.pending_requests}</span>}
                    </button>
                  );
                })}
              </div>
            ))}
          </nav>
          <div className="side-foot">
            <button className="tour-launch" onClick={startTour}><Compass size={17} /><span>Start guided demo</span></button>
            <div className="who">
              <div className="avatar">{user.name.split(" ").slice(-1)[0][0]}{user.name.split(" ")[1]?.[0]}</div>
              <div><strong>{user.name}</strong><small>{user.title} - {user.role}</small></div>
              <button className="icon-btn" onClick={logout} title="Sign out" aria-label="Sign out"><LogOut size={17} /></button>
            </div>
          </div>
        </aside>

        <div className="main">
          <header className="topbar">
            <button className="icon-btn only-mobile" onClick={() => setNavOpen(true)} aria-label="Open menu"><Menu size={20} /></button>
            <label className="theatre" title="Show one sector or the whole country">
              <span>Theatre</span>
              <select value={sector} onChange={e => setSector(e.target.value as Sector)}>
                {(["ALL", "NORTH", "EAST", "WEST", "ISLANDS"] as Sector[]).map(k => <option key={k} value={k}>{SECTOR_LABEL[k]}</option>)}
              </select>
            </label>
            <MissionClock status={status} canAct={canAct} onSpeed={setSpeed} onSkip={skip} />
            <div className="top-right">
              <button className="icon-btn" onClick={() => setTheme(t => t === "chart" ? "night" : "chart")} title={theme === "chart" ? "Switch to night mode" : "Switch to day mode"} aria-label="Toggle theme">
                {theme === "chart" ? <Moon size={18} /> : <Sun size={18} />}
              </button>
              <button className="icon-btn bell" onClick={() => go("alerts")} aria-label="Alerts">
                <Bell size={18} />{status?.alerts_critical > 0 && <i />}
              </button>
              <span className={`role-chip role-${user.role}`}>{user.role}</span>
            </div>
          </header>
          <main className="content" key={route.page}>{pages[route.page]}</main>
          <footer className="foot">Smart India Hackathon prototype. All locations, units and figures are synthetic. Times shown in {TZ_LABEL}.</footer>
        </div>

        {tourStep !== null && (
          <div className="tour" role="dialog" aria-label="Guided demo">
            <div className="tour-head">
              <span className="tour-count">Step {tourStep + 1} of {TOUR.length}</span>
              <button className="icon-btn" onClick={() => setTourStep(null)} aria-label="Close guided demo"><X size={16} /></button>
            </div>
            <h3>{TOUR[tourStep].title}</h3>
            <p className="tour-say">{TOUR[tourStep].say}</p>
            <p className="tour-do"><strong>Do this:</strong> {TOUR[tourStep].doThis}</p>
            <div className="tour-progress">{TOUR.map((_, i) => <button key={i} className={i === tourStep ? "on" : i < tourStep ? "done" : ""} onClick={() => tourGo(i)} aria-label={`Go to step ${i + 1}`} />)}</div>
            <div className="tour-nav">
              <Btn small kind="ghost" icon={<ChevronLeft size={15} />} disabled={tourStep === 0} onClick={() => tourGo(tourStep - 1)}>Back</Btn>
              {tourStep < TOUR.length - 1
                ? <Btn small kind="primary" onClick={() => tourGo(tourStep + 1)}>Next step <ChevronRight size={15} /></Btn>
                : <Btn small kind="primary" onClick={() => setTourStep(null)}>Finish demo</Btn>}
            </div>
          </div>
        )}

        <div className="toasts" aria-live="polite">
          {toasts.map(t => (
            <div key={t.id} className={`toast toast-${t.kind}`}>
              {t.kind === "ok" ? <CheckCircle2 size={17} /> : t.kind === "err" ? <AlertOctagon size={17} /> : t.kind === "ai" ? <Sparkles size={17} /> : <Info size={17} />}
              <span>{t.msg}</span>
              {t.action && <button className="toast-act" onClick={() => go(t.action!.page)}>{t.action.label}</button>}
            </div>
          ))}
        </div>
      </div>
    </AppContext.Provider>
  );
}
