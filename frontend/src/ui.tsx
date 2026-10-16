import { createContext, ReactNode, useCallback, useContext, useEffect, useRef, useState } from "react";
import { Loader2, X, AlertTriangle, Inbox } from "lucide-react";
import { api, User } from "./api";

// ---------------------------------------------------------------------------
// App context
// ---------------------------------------------------------------------------
export type Page =
  | "dashboard" | "ai" | "map" | "alerts" | "forecast" | "inventory" | "requests" | "shipments"
  | "disruptions" | "scenario" | "iot" | "reports" | "audit" | "system";

export type Sector = "ALL" | "NORTH" | "EAST" | "WEST" | "ISLANDS";
export const SECTOR_LABEL: Record<string, string> = {
  ALL: "All India", NORTH: "Northern sector", EAST: "Eastern sector", WEST: "Western sector", ISLANDS: "Island sector",
};
export const SECTOR_SHORT: Record<string, string> = { NORTH: "North", EAST: "East", WEST: "West", ISLANDS: "Islands" };
export const inSector = (sector: Sector, item: { sector?: string | null }) => sector === "ALL" || !item.sector || item.sector === sector;

export type Ctx = {
  user: User;
  version: number;
  refresh: () => void;
  toast: (msg: string, kind?: "ok" | "err" | "info") => void;
  go: (p: Page, params?: Record<string, string>) => void;
  params: Record<string, string>;
  can: (role: "planner" | "admin") => boolean;
  simTime: string;
  theme: "chart" | "night";
  sector: Sector;
  setSector: (s: Sector) => void;
};
export const AppContext = createContext<Ctx>(null as any);
export const useApp = () => useContext(AppContext);

export function useApi<T = any>(path: string | null, extraDeps: any[] = []) {
  const { version } = useApp();
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const seq = useRef(0);
  const load = useCallback(() => {
    if (!path) return;
    const my = ++seq.current;
    setLoading(true);
    api<T>(path).then(d => { if (my === seq.current) { setData(d); setError(null); } })
      .catch(e => { if (my === seq.current) setError(e.message); })
      .finally(() => { if (my === seq.current) setLoading(false); });
  }, [path]);
  useEffect(load, [load, version, ...extraDeps]);
  return { data, error, loading, reload: load };
}

// Run an action with toast + global refresh
export function useAction() {
  const { toast, refresh } = useApp();
  const [busy, setBusy] = useState<string | null>(null);
  const run = async (key: string, fn: () => Promise<any>, okMsg?: string | ((r: any) => string)) => {
    setBusy(key);
    try {
      const r = await fn();
      if (okMsg) toast(typeof okMsg === "function" ? okMsg(r) : okMsg, "ok");
      refresh();
      return r;
    } catch (e: any) {
      toast(e.message, "err");
      return null;
    } finally {
      setBusy(null);
    }
  };
  return { busy, run };
}

// ---------------------------------------------------------------------------
// Formatting
// ---------------------------------------------------------------------------
export const fmt = (n: number | null | undefined, d = 0) =>
  n === null || n === undefined || Number.isNaN(n) ? "-" : Number(n).toLocaleString("en-IN", { maximumFractionDigits: d, minimumFractionDigits: 0 });

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
export const TZ_LABEL = (() => {
  try {
    const off = -new Date().getTimezoneOffset();
    if (off === 330) return "IST";
    const p = new Intl.DateTimeFormat("en", { timeZoneName: "short" }).formatToParts(new Date()).find(x => x.type === "timeZoneName");
    return p?.value || "local";
  } catch { return "local"; }
})();
export function fmtTime(iso?: string | null, withDate = true) {
  if (!iso) return "-";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const hh = String(d.getHours()).padStart(2, "0"), mm = String(d.getMinutes()).padStart(2, "0");
  return withDate ? `${d.getDate()} ${MONTHS[d.getMonth()]}, ${hh}:${mm}` : `${hh}:${mm}`;
}
export function hoursFrom(iso: string, nowIso: string) {
  return (new Date(iso).getTime() - new Date(nowIso).getTime()) / 3.6e6;
}
export function fmtDuration(h: number) {
  const neg = h < 0; h = Math.abs(h);
  const s = h >= 24 ? `${(h / 24).toFixed(1)} days` : h >= 1 ? `${Math.floor(h)} h ${Math.round((h % 1) * 60)} min` : `${Math.round(h * 60)} min`;
  return neg ? `${s} ago` : s;
}

export const CAT_COLORS: Record<string, string> = {
  WATER: "#2f8fd8", RATIONS: "#d9a21b", FUEL: "#e2701f", MEDICAL: "#cf3b3b", AMMO: "#7f5bd6", SPARES: "#3a86c8", WINTER: "#2fa6b0",
};
export const CAT_SHORT: Record<string, string> = {
  RATIONS: "Rations", WATER: "Water", FUEL: "Fuel", MEDICAL: "Medical", AMMO: "Ammo", SPARES: "Spares", WINTER: "Winter kit",
};

// ---------------------------------------------------------------------------
// Components
// ---------------------------------------------------------------------------
export function Panel({ title, sub, actions, children, className = "", id, flush }: {
  title?: ReactNode; sub?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string; id?: string; flush?: boolean;
}) {
  return (
    <section className={`panel ${className}`} id={id}>
      {(title || actions) && (
        <header className="panel-head">
          <div>{title && <h2>{title}</h2>}{sub && <p className="panel-sub">{sub}</p>}</div>
          {actions && <div className="panel-actions">{actions}</div>}
        </header>
      )}
      <div className={flush ? "panel-body flush" : "panel-body"}>{children}</div>
    </section>
  );
}

const LEVEL_CLASS: Record<string, string> = {
  CRITICAL: "lv-crit", HIGH: "lv-high", MEDIUM: "lv-med", MODERATE: "lv-med", LOW: "lv-low", OK: "lv-ok",
  EXCESS: "lv-info", SEVERE: "lv-crit", SIGNIFICANT: "lv-high", MINIMAL: "lv-ok",
  NEW: "lv-info", APPROVED: "lv-ok", DISPATCHED: "lv-info", DELIVERED: "lv-ok", REJECTED: "lv-low",
  SCHEDULED: "lv-low", IN_TRANSIT: "lv-info", DELAYED: "lv-high", HOLDING: "lv-crit",
  ACTIVE: "lv-high", RESOLVED: "lv-ok", ACKNOWLEDGED: "lv-low", LOADING: "lv-med",
  AI: "lv-ai", SENSOR: "lv-info", SYSTEM: "lv-low", AUTO_DISPATCH: "lv-ai", AUTO_REQUEST: "lv-info", ESCALATION: "lv-crit",
  OPEN: "lv-ok", RESTRICTED: "lv-high", CLOSED: "lv-crit",
  AVAILABLE: "lv-ok", ON_MISSION: "lv-info", RETURNING: "lv-low", MAINTENANCE: "lv-high",
  BREACH: "lv-crit", WARN: "lv-high", OFFLINE: "lv-crit", ONLINE: "lv-ok",
};
const LEVEL_TEXT: Record<string, string> = {
  LOW: "Low", OK: "OK", IN_TRANSIT: "In transit", ON_MISSION: "On mission", CRITICAL: "Critical", HIGH: "High",
  MEDIUM: "Medium", MODERATE: "Moderate", EXCESS: "Excess", NEW: "New", APPROVED: "Approved", DISPATCHED: "Dispatched",
  DELIVERED: "Delivered", REJECTED: "Rejected", SCHEDULED: "Scheduled", DELAYED: "Delayed", HOLDING: "Holding",
  ACTIVE: "Active", RESOLVED: "Resolved", ACKNOWLEDGED: "Acknowledged", OPEN: "Open", RESTRICTED: "Restricted",
  CLOSED: "Closed", AVAILABLE: "Available", LOADING: "Loading", AI: "AI", SENSOR: "Sensor", SYSTEM: "System",
  AUTO_DISPATCH: "Handled automatically", AUTO_REQUEST: "Request raised", ESCALATION: "Escalated to planner", RETURNING: "Returning", MAINTENANCE: "Maintenance", BREACH: "Breach",
  WARN: "Warning", OFFLINE: "Offline", ONLINE: "Online", SEVERE: "Severe", SIGNIFICANT: "Significant", MINIMAL: "Minimal",
};
export function Badge({ level, children }: { level: string; children?: ReactNode }) {
  return <span className={`badge ${LEVEL_CLASS[level] || "lv-low"}`}>{children ?? LEVEL_TEXT[level] ?? level}</span>;
}
export function Dot({ level }: { level: string }) {
  return <span className={`dot ${LEVEL_CLASS[level] || "lv-low"}`} aria-hidden="true" />;
}

export function Btn({ children, onClick, kind = "default", busy, disabled, icon, title, small, type = "button" }: {
  children?: ReactNode; onClick?: () => void; kind?: "default" | "primary" | "danger" | "ghost"; busy?: boolean;
  disabled?: boolean; icon?: ReactNode; title?: string; small?: boolean; type?: "button" | "submit";
}) {
  return (
    <button type={type} className={`btn btn-${kind} ${small ? "btn-sm" : ""}`} onClick={onClick} disabled={disabled || busy} title={title}>
      {busy ? <Loader2 size={15} className="spin" /> : icon}
      {children && <span>{children}</span>}
    </button>
  );
}

export function Modal({ title, onClose, children, wide }: { title: ReactNode; onClose: () => void; children: ReactNode; wide?: boolean }) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);
  return (
    <div className="modal-back" onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <div className={`modal ${wide ? "modal-wide" : ""}`} role="dialog" aria-modal="true">
        <header className="modal-head"><h2>{title}</h2><button className="icon-btn" onClick={onClose} aria-label="Close"><X size={18} /></button></header>
        <div className="modal-body">{children}</div>
      </div>
    </div>
  );
}

export function Loading({ label = "Loading" }: { label?: string }) {
  return <div className="state-box"><Loader2 className="spin" size={20} /><span>{label}...</span></div>;
}
export function ErrorBox({ msg, retry }: { msg: string; retry?: () => void }) {
  return <div className="state-box err"><AlertTriangle size={20} /><span>{msg}</span>{retry && <Btn small onClick={retry}>Try again</Btn>}</div>;
}
export function Empty({ title, detail, action }: { title: string; detail?: string; action?: ReactNode }) {
  return <div className="state-box"><Inbox size={22} /><strong>{title}</strong>{detail && <span>{detail}</span>}{action}</div>;
}

export function Meter({ value, max = 100, tone, marker, label }: { value: number; max?: number; tone?: string; marker?: number; label?: string }) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div className="meter" aria-label={label}>
      <span className={`meter-fill ${tone || ""}`} style={{ width: `${pct}%` }} />
      {marker !== undefined && <i className="meter-mark" style={{ left: `${Math.min(100, (marker / max) * 100)}%` }} />}
    </div>
  );
}

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return <label className="field"><span className="field-label">{label}</span>{children}{hint && <span className="field-hint">{hint}</span>}</label>;
}

export function PageHead({ title, lede, actions }: { title: string; lede: string; actions?: ReactNode }) {
  return (
    <div className="page-head">
      <div><h1>{title}</h1><p>{lede}</p></div>
      {actions && <div className="page-head-actions">{actions}</div>}
    </div>
  );
}

export function KV({ items }: { items: [string, ReactNode][] }) {
  return <dl className="kv">{items.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>;
}

export function RiskBreakdown({ risk }: { risk: any }) {
  if (!risk) return null;
  const parts: [string, number, number][] = [
    ["Weather", risk.breakdown?.weather ?? 0, 40], ["Road condition", risk.breakdown?.road_condition ?? 0, 30],
    ["Terrain / altitude", risk.breakdown?.terrain_altitude ?? 0, 15], ["Past delays", risk.breakdown?.historical_delays ?? 0, 15],
  ];
  return (
    <div className="risk-box">
      <div className="risk-top"><strong className="num">{fmt(risk.score, 1)}</strong><span>/100 risk</span><Badge level={risk.level} /></div>
      <div className="risk-parts">
        {parts.map(([k, v, m]) => (
          <div key={k} className="risk-part"><span>{k}</span><Meter value={v} max={m} tone={v / m > 0.6 ? "crit" : v / m > 0.3 ? "warn" : "ok"} /><b className="num">{fmt(v, 1)}</b></div>
        ))}
      </div>
      {risk.factors?.length > 0 && <ul className="factor-list">{risk.factors.map((f: string, i: number) => <li key={i}>{f}</li>)}</ul>}
    </div>
  );
}

export function SectorChip({ sector }: { sector?: string | null }) {
  if (!sector) return null;
  return <span className={`sector-chip sc-${sector.toLowerCase()}`}>{SECTOR_SHORT[sector] || sector}</span>;
}

export function SectorTabs({ value, onChange, counts }: { value: Sector; onChange: (s: Sector) => void; counts?: Record<string, number> }) {
  return (
    <div className="seg sector-tabs" role="tablist" aria-label="Sector">
      {(["ALL", "NORTH", "EAST", "WEST", "ISLANDS"] as Sector[]).map(k => (
        <button key={k} role="tab" aria-selected={value === k} className={value === k ? "on" : ""} onClick={() => onChange(k)}>
          {k === "ALL" ? "All India" : SECTOR_SHORT[k]}{counts && counts[k] !== undefined ? <b className="tab-count">{counts[k]}</b> : null}
        </button>
      ))}
    </div>
  );
}
