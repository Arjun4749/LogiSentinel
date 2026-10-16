import { useState } from "react";
import { AlertTriangle, CheckCircle, Satellite, CloudSnow, Cloud, Sun, CloudRain, CloudFog, Wind, CloudLightning, Tornado, Flame, Ship, Truck } from "lucide-react";
import { api } from "../api";
import { Badge, Btn, Empty, ErrorBox, Field, fmt, fmtTime, inSector, Loading, Modal, PageHead, Panel, SECTOR_LABEL, SectorChip, SectorTabs, useAction, useApi, useApp } from "../ui";

const WX_ICON: Record<string, any> = { Clear: Sun, Cloudy: Cloud, Rain: CloudRain, Snow: CloudSnow, Blizzard: Wind, Fog: CloudFog,
  Storm: CloudLightning, "Dust storm": Tornado, Heatwave: Flame };
const WEEKDAY = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MONTH = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const dayLabel = (iso: string, i: number) => {
  const d = new Date(iso + "T12:00:00");
  return `${i === 0 ? "Today" : i === 1 ? "Tomorrow" : WEEKDAY[d.getDay()]}, ${d.getDate()} ${MONTH[d.getMonth()]}`;
};

function ReportForm({ onClose }: { onClose: () => void }) {
  const ref = useApi<any>("/api/reference");
  const { busy, run } = useAction();
  const [f, setF] = useState({ type: "AVALANCHE", title: "Avalanche blocks Indus Valley Road", target: "route", route_id: "R10", node_id: "FP-I",
    severity: "CRITICAL", closes_route: true, delay_factor: 1.5, duration_hours: 24, description: "" });
  const set = (k: string, v: any) => setF({ ...f, [k]: v });
  const submit = async (e: any) => {
    e.preventDefault();
    const body: any = { type: f.type, title: f.title, severity: f.severity, closes_route: f.target === "route" && f.closes_route, delay_factor: f.delay_factor,
      duration_hours: f.duration_hours, description: f.description };
    if (f.target === "route") body.route_id = f.route_id; else body.node_id = f.node_id;
    const r = await run("s", () => api("/api/disruptions", { method: "POST", body }), "Disruption reported - routes, shipments and alerts updated");
    if (r) onClose();
  };
  return (
    <Modal title="Report a disruption" onClose={onClose}>
      <form className="form-grid" onSubmit={submit}>
        <Field label="Type"><select value={f.type} onChange={e => set("type", e.target.value)}>{["AVALANCHE", "LANDSLIDE", "WEATHER", "ROAD_DAMAGE", "SECURITY", "CONNECTIVITY", "SUPPLIER"].map(t => <option key={t} value={t}>{t.replace("_", " ").toLowerCase()}</option>)}</select></Field>
        <Field label="Severity"><select value={f.severity} onChange={e => set("severity", e.target.value)}>{["CRITICAL", "HIGH", "MEDIUM", "LOW"].map(t => <option key={t}>{t}</option>)}</select></Field>
        <Field label="Title"><input required maxLength={120} value={f.title} onChange={e => set("title", e.target.value)} /></Field>
        <Field label="Affects"><div className="seg"><button type="button" className={f.target === "route" ? "on" : ""} onClick={() => set("target", "route")}>A route</button><button type="button" className={f.target === "node" ? "on" : ""} onClick={() => set("target", "node")}>A location</button></div></Field>
        {f.target === "route"
          ? <Field label="Route"><select value={f.route_id} onChange={e => set("route_id", e.target.value)}>{ref.data && Object.entries(ref.data.routes).map(([id, r]: any) => <option key={id} value={id}>{r.name}</option>)}</select></Field>
          : <Field label="Location"><select value={f.node_id} onChange={e => set("node_id", e.target.value)}>{ref.data && Object.entries(ref.data.nodes).map(([id, n]: any) => <option key={id} value={id}>{n.name}</option>)}</select></Field>}
        {f.target === "route" && <label className="toggle"><input type="checkbox" checked={f.closes_route} onChange={e => set("closes_route", e.target.checked)} /><span>Route fully closed (vehicles must hold)</span></label>}
        {f.target === "route" && !f.closes_route && <Field label="Travel time multiplier" hint="1.5 = journeys take 50% longer"><input type="number" min={1} max={4} step={0.1} value={f.delay_factor} onChange={e => set("delay_factor", Number(e.target.value))} /></Field>}
        <Field label="Expected duration (hours)"><input type="number" min={1} max={720} value={f.duration_hours} onChange={e => set("duration_hours", Number(e.target.value))} /></Field>
        <Field label="Details"><input maxLength={400} value={f.description} onChange={e => set("description", e.target.value)} placeholder="What happened, who reported it" /></Field>
        <div className="form-actions"><Btn kind="ghost" onClick={onClose}>Cancel</Btn><Btn type="submit" kind="danger" busy={busy === "s"}>Report disruption</Btn></div>
      </form>
    </Modal>
  );
}

export default function Disruptions() {
  const { can, sector, setSector } = useApp();
  const dis = useApi<any>("/api/disruptions");
  const wx = useApi<any>("/api/weather");
  const { busy, run } = useAction();
  const [form, setForm] = useState(false);
  const [live, setLive] = useState<any>(null);
  const [liveBusy, setLiveBusy] = useState(false);
  if (dis.error) return <ErrorBox msg={dis.error} retry={dis.reload} />;
  const sectorOf = (d: any) => d.sector;
  const active = (dis.data?.disruptions || []).filter((d: any) => d.status === "ACTIVE" && inSector(sector, { sector: sectorOf(d) }));
  const past = (dis.data?.disruptions || []).filter((d: any) => d.status !== "ACTIVE" && inSector(sector, { sector: sectorOf(d) }));
  const wxNodes = (wx.data?.nodes || []).filter((n: any) => inSector(sector, n));
  const wxRoutes = (wx.data?.routes || []).filter((r: any) => inSector(sector, r));
  const groups = ["NORTH", "EAST", "WEST", "ISLANDS"].filter(g => wxNodes.some((n: any) => n.sector === g));
  const days = wx.data?.nodes[0]?.days || [];

  return (
    <div className="page">
      <PageHead title="Weather & disruptions" lede="Mountain passes, landslides and storms decide whether supplies get through. Route risk combines weather, road condition, altitude and past delays."
        actions={<><SectorTabs value={sector} onChange={setSector} />{can("admin") && <Btn kind="danger" icon={<AlertTriangle size={15} />} onClick={() => setForm(true)}>Report disruption</Btn>}</>} />

      <Panel title={`Active disruptions (${active.length})`}>
        {!dis.data ? <Loading /> : active.length === 0 ? <Empty title="No active disruptions" detail="All routes are clear of reported incidents." /> : (
          <div className="dis-grid">
            {active.map((d: any) => (
              <article key={d.id} className={`dis-card sevline-${d.severity.toLowerCase()}`}>
                <header><Badge level={d.severity} /><SectorChip sector={d.sector} /><span className="muted small">{d.type.replace("_", " ").toLowerCase()} - {d.id}</span></header>
                <h3>{d.title}</h3>
                <p>{d.description}</p>
                <p className="small"><b>{d.route_name || d.node_name}</b>{d.closes_route ? " - route closed" : d.delay_factor > 1 ? ` - journeys x${d.delay_factor}` : ""}</p>
                <p className="small muted">Started {fmtTime(d.start)}, expected to clear {fmtTime(d.expected_end)}. Source: {d.source}</p>
                {d.affected_shipments.length > 0 && <p className="small t-crit">Affects shipments: {d.affected_shipments.join(", ")}</p>}
                {can("admin") && <Btn small icon={<CheckCircle size={14} />} busy={busy === d.id} onClick={() => run(d.id, () => api(`/api/disruptions/${d.id}/resolve`, { method: "POST" }), "Disruption cleared")}>Mark cleared</Btn>}
              </article>
            ))}
          </div>
        )}
      </Panel>

      <Panel flush title="Route outlook - next 4 days" sub="For each road and sea lane: whether it is open, the worst weather expected on it, and its risk score out of 100. Send convoys on green days.">
        {!wx.data ? <Loading /> : (
          <div className="tbl-wrap"><table className="tbl outlook">
            <thead><tr><th>Route</th><th>Type</th><th className="right">Length</th><th className="right">Highest point</th>{days.slice(0, 4).map((d: any, i: number) => <th key={d.date}>{dayLabel(d.date, i)}</th>)}</tr></thead>
            <tbody>{wxRoutes.map((r: any) => (
              <tr key={r.id}>
                <td><strong>{r.name}</strong> <SectorChip sector={r.sector} /><br /><small className="muted">From {r.a} to {r.b}{r.snow_prone ? " - snow-prone pass" : ""}</small></td>
                <td><span className="mode">{r.mode === "SEA" ? <Ship size={14} /> : <Truck size={14} />}{r.mode === "SEA" ? "Sea lane" : "Road"}</span></td>
                <td className="num right">{fmt(r.km)} km</td><td className="num right">{r.mode === "SEA" ? "Sea level" : `${fmt(r.max_alt)} m`}</td>
                {r.outlook.map((o: any) => (
                  <td key={o.day} className={`ol-cell ol-${o.status.toLowerCase()}`}>
                    <span className="ol-status">{o.status === "OPEN" ? "Open" : o.status === "RESTRICTED" ? "Restricted" : "Closed"}</span>
                    <small>{o.weather} - risk {Math.round(o.risk)}/100</small>
                    {o.time_mult > 1.05 && o.status !== "CLOSED" && <small>Journey x{o.time_mult}</small>}
                  </td>
                ))}
              </tr>
            ))}</tbody>
          </table></div>
        )}
      </Panel>

      <Panel flush title="7-day weather by location" sub="Daily minimum and maximum temperature in °C, sky condition, snow in cm and wind in km/h. Simulated forecast used by the planning engines."
        actions={<Btn small icon={<Satellite size={14} />} busy={liveBusy} onClick={async () => { setLiveBusy(true); try { setLive(await api("/api/weather/live")); } catch (e: any) { setLive({ available: false, reason: e.message }); } setLiveBusy(false); }}>Check live weather</Btn>}>
        {live && (live.available
          ? <div className="live-wx"><b>Live now (Open-Meteo):</b> {live.data.filter((d: any) => wxNodes.some((n: any) => n.node === d.node)).map((d: any) => <span key={d.node} className="chip">{d.name}: {d.temp} °C, wind {d.wind} km/h</span>)}</div>
          : <div className="live-wx muted">{live.reason}</div>)}
        {!wx.data ? <Loading /> : (
          <div className="tbl-wrap"><table className="tbl wx">
            <thead><tr><th>Location</th>{days.map((d: any, i: number) => <th key={d.date}>{dayLabel(d.date, i)}</th>)}</tr></thead>
            {groups.map(g => (
              <tbody key={g}>
                <tr className="group-row"><td colSpan={8}>{SECTOR_LABEL[g]}</td></tr>
                {wxNodes.filter((n: any) => n.sector === g).map((n: any) => (
                  <tr key={n.node}>
                    <td><strong>{n.name}</strong><br /><small className="muted">{n.type === "post" ? "Forward post" : n.type === "hub" ? "Supply hub" : "Base depot"} - {fmt(n.alt)} m - {n.terrain}</small></td>
                    {n.days.map((d: any) => {
                      const Icon = WX_ICON[d.cond] || Cloud;
                      return (
                        <td key={d.date} className={`wx-cell wx-${d.cond.replace(" ", "")}`} title={`${d.cond}: min ${d.temp_min} °C, max ${d.temp_max} °C, wind ${d.wind} km/h, visibility ${d.vis_km} km`}>
                          <Icon size={16} /><b className="wx-cond">{d.cond}</b>
                          <span className="num wx-temp">{Math.round(d.temp_min)}° / {Math.round(d.temp_max)}°C</span>
                          <small>{d.snow_cm ? `Snow ${d.snow_cm} cm` : d.precip_mm ? `Rain ${Math.round(d.precip_mm)} mm` : `Wind ${Math.round(d.wind)} km/h`}</small>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            ))}
          </table></div>
        )}
      </Panel>

      {past.length > 0 && <Panel title="Cleared disruptions"><ul className="plain-list">{past.map((d: any) => <li key={d.id}><Badge level="RESOLVED" /> {d.title} <span className="muted small">cleared {fmtTime(d.resolved_at)}</span></li>)}</ul></Panel>}
      {form && <ReportForm onClose={() => setForm(false)} />}
    </div>
  );
}
