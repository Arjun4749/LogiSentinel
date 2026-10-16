import { Area, Bar, BarChart, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis, Cell } from "recharts";
import { useState } from "react";
import { Zap, HelpCircle, Sparkles } from "lucide-react";
import { api } from "../api";
import { Badge, Btn, CAT_SHORT, ErrorBox, fmt, fmtTime, inSector, Loading, PageHead, Panel, SECTOR_LABEL, SectorTabs, useAction, useApi, useApp } from "../ui";

const SCALE = 30; // days shown across a board cell

function readinessWord(v: number) {
  if (v >= 90) return "Ready";
  if (v >= 75) return "Mostly ready";
  if (v >= 55) return "At risk";
  return "Not ready";
}

function Gauge({ value, tone }: { value: number; tone: string }) {
  const r = 52, c = 2 * Math.PI * r, f = Math.max(0, Math.min(100, value)) / 100;
  return (
    <svg viewBox="0 0 128 128" className={`gauge tone-${tone}`} role="img" aria-label={`Readiness ${value} out of 100`}>
      <circle cx="64" cy="64" r={r} className="g-track" />
      <circle cx="64" cy="64" r={r} className="g-fill" strokeDasharray={`${c * f} ${c}`} transform="rotate(-90 64 64)" />
      <text x="64" y="62" textAnchor="middle" className="g-num">{value.toFixed(1)}</text>
      <text x="64" y="82" textAnchor="middle" className="g-sub">out of 100</text>
    </svg>
  );
}

const SECTOR_NAMES: Record<string, string> = { NORTH: "North", EAST: "East", WEST: "West", ISLANDS: "Islands" };

export default function Dashboard() {
  const { go, can, sector, setSector } = useApp();
  const { data, error, loading, reload } = useApi<any>("/api/dashboard");
  const { busy, run } = useAction();
  const [explain, setExplain] = useState(false);
  if (error) return <ErrorBox msg={error} retry={reload} />;
  if (!data) return <Loading label="Building the operating picture" />;
  const k = data.kpis;
  const L = k.readiness_lines;
  const cats = Object.keys(data.matrix[0]?.cells || {});
  const tone = k.readiness_index >= 90 ? "ok" : k.readiness_index >= 75 ? "warn" : "crit";
  const rows = data.matrix.filter((r: any) => inSector(sector, r));
  const groups = ["NORTH", "EAST", "WEST", "ISLANDS"].filter(sg => rows.some((r: any) => r.sector === sg));

  return (
    <div className="page">
      <PageHead title="Command dashboard" lede="Forecasts, stock, transport, weather and sensors for all four sectors in one operating picture. It updates on its own as the mission clock runs." />

      <div className="hero-row">
        <div className={`readiness tone-${tone}`}>
          <Gauge value={k.readiness_index} tone={tone} />
          <div className="readiness-text">
            <small>Supply Readiness Index</small>
            <strong>{readinessWord(k.readiness_index)}</strong>
            <span><b>{L.safe}</b> of {L.total} forward-post supply lines are safe for the next 14 days, <b>{L.watch}</b> need watching and <b className={L.risk ? "t-crit-l" : ""}>{L.risk}</b> will run out before resupply can arrive.</span>
            <button className="link-light" onClick={() => setExplain(x => !x)}><HelpCircle size={14} /> {explain ? "Hide explanation" : "What does this number mean?"}</button>
          </div>
          <div className="sector-bars">
            {Object.entries(k.sector_readiness || {}).map(([sg, v]: any) => (
              <button key={sg} className={sector === sg ? "on" : ""} onClick={() => setSector(sector === sg ? "ALL" : sg as any)} title={`Show ${SECTOR_NAMES[sg]} only`}>
                <span>{SECTOR_NAMES[sg]}</span><i><em style={{ width: `${v}%` }} className={v >= 90 ? "ok" : v >= 75 ? "warn" : "crit"} /></i><b className="num">{fmt(v, 0)}</b>
              </button>
            ))}
          </div>
          {explain && <div className="readiness-explain">
            A score out of 100, like a fuel gauge for the whole supply chain. For every forward post and every supply type the system asks: <em>will the stock last longer than the time it takes to resupply it?</em>
            Stock that lasts more than a week beyond the resupply time counts fully, stock that runs out before resupply counts zero, and anything in between counts partly.
            Medicine and water weigh more than spares. 90 or more = ready, 75 to 90 = mostly ready, below 75 = at risk.
          </div>}
        </div>
        <Panel className="briefing" title={<span className="row-gap" style={{ margin: 0 }}><Sparkles size={17} /> AI briefing</span>}
          actions={<Btn small kind="ghost" onClick={() => go("ai")}>AI Command Centre</Btn>}>
          <ul className="brief-list">{data.briefing.map((b: string, i: number) => <li key={i}>{b}</li>)}</ul>
          {data.ai_log.length > 0 && <div className="brief-recent">
            <span className="field-label">Latest autopilot actions</span>
            {data.ai_log.slice(0, 3).map((e: any) => (
              <button key={e.id} className="brief-act" onClick={() => go("ai")}><Badge level={e.kind} /><span>{e.title}</span><time>{fmtTime(e.time, false)}</time></button>
            ))}
          </div>}
        </Panel>
      </div>

      <div className="kpi-grid six">
        <button className="kpi" onClick={() => go("inventory")}><span>Posts at stock-out risk</span><strong className={`num ${k.posts_at_risk ? "t-crit" : ""}`}>{k.posts_at_risk}<small>/{k.posts_total}</small></strong></button>
        <button className="kpi" onClick={() => go("ai")}><span>Red alerts handled by AI</span><strong className="num t-ai">{k.ai_handled}</strong><em>{k.ai_requests} requests raised automatically</em></button>
        <button className="kpi" onClick={() => go("forecast")}><span>Forecast accuracy</span><strong className="num">{fmt(k.forecast_accuracy_pct, 1)}%</strong><em>{fmt(k.forecast_improvement_pct, 0)}% better than simple average</em></button>
        <button className="kpi" onClick={() => go("shipments")}><span>On-time delivery</span><strong className="num">{fmt(k.on_time_delivery_pct, 1)}%</strong><em>{k.active_shipments} moving, {k.delayed_shipments} delayed</em></button>
        <button className="kpi" onClick={() => go("shipments")}><span>Transport in use</span><strong className="num">{fmt(k.transport_utilisation_pct, 0)}%</strong></button>
        <button className="kpi" onClick={() => go("alerts")}><span>Critical alerts open</span><strong className={`num ${k.alerts_critical ? "t-crit" : ""}`}>{k.alerts_critical}<small> of {k.alerts_total}</small></strong></button>
      </div>

      <Panel title="Days-of-supply board" sub="Bar = days of stock held at forecast demand. Dark tick = resupply time. Red = runs out before resupply can arrive (the AI Autopilot acts on these). Click any cell for its forecast."
        actions={<SectorTabs value={sector} onChange={setSector} />}>
        <div className="legend board-legend"><span><i className="sw crit" />Red: will run out before resupply</span><span><i className="sw warn" />Amber: below reorder point</span><span><i className="sw ok" />Healthy</span><span><i className="sw inc" />Stock on the way</span></div>
        <div className="board" role="table">
          <div className="board-row board-headrow" role="row">
            <div className="board-node" role="columnheader">Location</div>
            {cats.map(c => <div key={c} className="board-cat" role="columnheader">{CAT_SHORT[c]}</div>)}
          </div>
          {groups.map(sg => (
            <div key={sg} className="board-group">
              <div className="board-sector">{SECTOR_LABEL[sg]}</div>
              {rows.filter((r: any) => r.sector === sg).map((row: any) => (
                <div className={`board-row type-${row.type}`} key={row.node} role="row">
                  <div className="board-node" role="rowheader"><strong>{row.name}</strong><small>{row.type === "post" ? "Forward post" : "Supply hub"}</small></div>
                  {cats.map(c => {
                    const cell = row.cells[c];
                    const st = cell.status === "CRITICAL" ? "crit" : cell.status === "LOW" ? "warn" : "ok";
                    const incDays = cell.cover > cell.days ? Math.min(SCALE, cell.cover) : 0;
                    return (
                      <button key={c} className={`board-cell ${st}`} role="cell" onClick={() => go("forecast", { node: row.node, category: c })}
                        title={`${row.name} - ${CAT_SHORT[c]}: ${fmt(cell.on_hand)} ${cell.unit}, ${cell.days} days held, resupply takes ${cell.lead} days${cell.incoming ? `, ${fmt(cell.incoming)} on the way` : ""}`}>
                        <span className="cell-days num">{cell.days >= 99 ? "99+" : fmt(cell.days, 1)}<small>d</small></span>
                        <span className="cell-track">
                          {incDays > 0 && <span className="cell-inc" style={{ width: `${(incDays / SCALE) * 100}%` }} />}
                          <span className="cell-bar" style={{ width: `${Math.min(100, (cell.days / SCALE) * 100)}%` }} />
                          <i className="cell-lead" style={{ left: `${Math.min(100, (cell.lead / SCALE) * 100)}%` }} />
                        </span>
                      </button>
                    );
                  })}
                </div>
              ))}
            </div>
          ))}
        </div>
      </Panel>

      <div className="grid-2-1">
        <Panel title="Network demand: last 30 days and 14-day forecast" sub="Total tonnes per day across all 26 locations. Shaded band is the 90% confidence range.">
          <div className="chart-h">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={data.demand_chart} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
                <CartesianGrid stroke="var(--grid)" vertical={false} />
                <XAxis dataKey="date" tickFormatter={d => d.slice(5)} tick={{ fontSize: 11, fill: "var(--ink-3)" }} interval={5} />
                <YAxis tick={{ fontSize: 11, fill: "var(--ink-3)" }} unit=" t" />
                <Tooltip contentStyle={{ background: "var(--panel)", border: "1px solid var(--line)", borderRadius: 8 }} formatter={(v: any) => Array.isArray(v) ? `${v[0]} - ${v[1]} t` : `${v} t`} />
                <Area dataKey={(d: any) => d.lower !== undefined ? [d.lower, d.upper] : null} name="90% range" fill="var(--primary)" fillOpacity={0.14} stroke="none" isAnimationActive={false} />
                <Line dataKey="actual" name="Actual" stroke="var(--ink)" strokeWidth={2} dot={false} isAnimationActive={false} />
                <Line dataKey="forecast" name="Forecast" stroke="var(--primary)" strokeWidth={2.4} strokeDasharray="6 4" dot={false} isAnimationActive={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </Panel>
        <Panel title="Approve before it turns red" sub={`${data.recommendation_count} amber recommendation(s). Red alerts are handled by the AI Autopilot; amber ones wait for your decision.`}
          actions={<Btn small kind="ghost" onClick={() => go("inventory")}>All recommendations</Btn>}>
          {data.top_recommendations.length === 0 && <p className="muted">Nothing amber right now. Every post holds more than its reorder point.</p>}
          <ul className="action-list">
            {data.top_recommendations.map((r: any) => (
              <li key={r.id}>
                <div className="action-top"><Badge level={r.urgency} /><strong>{r.node_name}: {r.category_name}</strong></div>
                <p>{fmt(r.recommended_qty)} {r.unit} from {r.suggested_source_name || "depot"}.{" "}
                  {r.stockout_in_days !== null ? <>Runs out in <b>{r.stockout_in_days} days</b>.</> : null}</p>
                {can("planner") && (
                  <Btn small kind="primary" icon={<Zap size={14} />} busy={busy === r.id}
                    onClick={() => run(r.id, () => api(`/api/replenishment/${r.id}/approve`, { method: "POST", body: { auto_dispatch: true } }),
                      (res: any) => `Approved. ${res.shipments.length} shipment(s) dispatched to ${r.node_name}`)}>
                    Approve & dispatch
                  </Btn>
                )}
              </li>
            ))}
          </ul>
        </Panel>
      </div>

      <div className="grid-3">
        <Panel title="Top alerts" actions={<Btn small kind="ghost" onClick={() => go("alerts")}>Open alerts</Btn>}>
          <ul className="mini-alerts">
            {data.top_alerts.map((a: any) => (
              <li key={a.id}><Badge level={a.severity} /><button className="link" onClick={() => go(a.page as any)}>{a.title}</button></li>
            ))}
          </ul>
        </Panel>
        <Panel title="Next 7 days demand by supply type" sub="Forward posts and hubs, tonnes">
          <div className="chart-s">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.category_mix} layout="vertical" margin={{ top: 0, right: 30, left: 10, bottom: 0 }}>
                <XAxis type="number" hide />
                <YAxis type="category" dataKey="name" width={110} tick={{ fontSize: 12, fill: "var(--ink-2)" }} axisLine={false} tickLine={false} />
                <Tooltip cursor={{ fill: "var(--hover)" }} contentStyle={{ background: "var(--panel)", border: "1px solid var(--line)", borderRadius: 8 }} formatter={(v: any) => `${v} t`} />
                <Bar dataKey="tonnes" radius={[0, 4, 4, 0]} label={{ position: "right", fontSize: 11, fill: "var(--ink-2)" }} isAnimationActive={false}>
                  {data.category_mix.map((c: any) => <Cell key={c.category} fill={c.color} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Panel>
        <Panel title="Activity log" sub="Latest system events">
          <ul className="feed">
            {data.events.length === 0 && <li className="muted">No events yet. Move the mission clock or dispatch a shipment.</li>}
            {data.events.slice(0, 9).map((e: any) => (
              <li key={e.id} className={`feed-${e.kind}`}><time>{fmtTime(e.time)}</time><span>{e.text}</span></li>
            ))}
          </ul>
        </Panel>
      </div>
    </div>
  );
}
