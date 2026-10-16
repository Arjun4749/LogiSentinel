import { useState } from "react";
import { Plus, Route, Check, X as XIcon, Truck, Plane, Send, Ship, ChevronDown, ChevronUp, Sparkles } from "lucide-react";
import { api } from "../api";
import { Badge, Btn, CAT_SHORT, Empty, ErrorBox, Field, fmt, fmtDuration, fmtTime, hoursFrom, inSector, KV, Loading, Modal, PageHead, Panel, RiskBreakdown, SECTOR_LABEL, SectorChip, SectorTabs, useAction, useApi, useApp } from "../ui";

const MODE_ICON: Record<string, any> = { ROAD: Truck, AIR: Plane, DRONE: Send, SEA: Ship };

export function PlanModal({ req, onClose }: { req: any; onClose: () => void }) {
  const { data, error } = useApi<any>(`/api/requests/${req.id}/plan`);
  const { busy, run } = useAction();
  const { can, simTime } = useApp();
  return (
    <Modal wide title={`Plan transport: ${req.id}`} onClose={onClose}>
      <p className="lede-sm">{fmt(req.qty)} {req.unit} {req.category_name.toLowerCase()} ({fmt(req.weight_kg / 1000, 1)} t) to <b>{req.node_name}</b>, needed by {fmtTime(req.needed_by)}. The planner checks every source with spare stock, every free vehicle and every mode, then scores them on arrival time, risk, cost and quantity covered.</p>
      {error && <p className="form-err">{error}</p>}
      {!data ? <Loading label="Checking sources, routes, vehicles and weather" /> : data.options.length === 0
        ? <Empty title="No feasible option right now" detail="No source has spare stock, or no vehicle is free. Move the clock forward or free up assets." />
        : <div className="options">
          {data.options.slice(0, 4).map((o: any) => {
            const Icon = MODE_ICON[o.mode];
            return (
              <article key={o.option_id} className={`option ${o.recommended ? "recommended" : ""}`}>
                {o.recommended && <div className="opt-flag">Recommended</div>}
                <header><Icon size={20} /><h3>{o.label}</h3></header>
                <p className="small muted opt-timing">{o.assets.length > 1 ? `${o.assets.length} vehicles - each leaves as soon as it is ready and loaded (${fmt(o.loading_hours ?? 1, 1)} h loading).` : `Vehicle ready in ${fmt(o.ready_hours ?? 0, 1)} h, then ${fmt(o.loading_hours ?? 1, 1)} h loading, then departs.`}</p>
                <div className="opt-figs">
                  <div><span>{o.assets.length > 1 ? "First departs" : "Departs"}</span><b>{fmtTime(o.depart)}</b></div>
                  <div><span>{o.assets.length > 1 ? "All delivered by" : "Arrives"}</span><b>{fmtTime(o.eta)}</b></div>
                  <div><span>Journey</span><b>{fmt(o.travel_hours, 1)} h, {fmt(o.km)} km</b></div>
                  <div><span>Cost</span><b>Rs {fmt(o.cost_inr)}</b></div>
                </div>
                <p className={o.on_time ? "t-ok" : "t-crit"}>{o.on_time ? `On time with ${fmtDuration(o.slack_hours)} to spare` : `Late by ${fmtDuration(o.late_hours)}`}
                  {o.shortfall_qty > 0 && <span className="t-crit"> - short by {fmt(o.shortfall_qty)} {req.unit}</span>}</p>
                <div className="opt-assets">{o.assets.map((a: any) => <span key={a.asset_id} className="chip">{a.asset_id} - {a.type_name} - {fmt(a.weight_kg / 1000, 1)} t ({a.utilisation_pct}% full){a.sorties ? `, ${a.sorties} sortie(s)` : ""}</span>)}</div>
                <RiskBreakdown risk={o.risk} />
                {o.why && <p className="why-line">{o.why}</p>}
                <div className="opt-score">Option score <b className="num">{o.score}</b>/100</div>
                {can("planner") && <Btn kind={o.recommended ? "primary" : "default"} busy={busy === o.option_id} icon={<Send size={15} />}
                  onClick={async () => { const r = await run(o.option_id, () => api(`/api/requests/${req.id}/dispatch`, { method: "POST", body: { option_id: o.option_id } }), (r: any) => `Dispatched ${r.shipments.length} shipment(s). ETA ${fmtTime(o.eta)}`); if (r) onClose(); }}>
                  Dispatch this option</Btn>}
              </article>
            );
          })}
        </div>}
    </Modal>
  );
}

function NewRequest({ onClose }: { onClose: () => void }) {
  const ref = useApi<any>("/api/reference");
  const { busy, run } = useAction();
  const [f, setF] = useState({ node: "FP-H", category: "MEDICAL", qty: 40, needed_in_days: 2, urgency: "HIGH", reason: "" });
  const set = (k: string, v: any) => setF({ ...f, [k]: v });
  return (
    <Modal title="New supply request" onClose={onClose}>
      <form className="form-grid" onSubmit={async e => { e.preventDefault(); const r = await run("c", () => api("/api/requests", { method: "POST", body: f }), (r: any) => `Request ${r.id} created and ranked`); if (r) onClose(); }}>
        <Field label="Requesting location"><select value={f.node} onChange={e => set("node", e.target.value)}>{ref.data && ["NORTH", "EAST", "WEST", "ISLANDS"].map(g => <optgroup key={g} label={SECTOR_LABEL[g]}>{Object.entries(ref.data.nodes).filter(([, n]: any) => n.type !== "depot" && n.sector === g).map(([id, n]: any) => <option key={id} value={id}>{n.name}</option>)}</optgroup>)}</select></Field>
        <Field label="Supply type"><select value={f.category} onChange={e => set("category", e.target.value)}>{ref.data && Object.entries(ref.data.categories).map(([id, c]: any) => <option key={id} value={id}>{c.name} ({c.unit})</option>)}</select></Field>
        <Field label="Quantity"><input type="number" min={1} required value={f.qty} onChange={e => set("qty", Number(e.target.value))} /></Field>
        <Field label="Needed within (days)"><input type="number" min={0.5} step={0.5} required value={f.needed_in_days} onChange={e => set("needed_in_days", Number(e.target.value))} /></Field>
        <Field label="Declared urgency"><select value={f.urgency} onChange={e => set("urgency", e.target.value)}><option>CRITICAL</option><option>HIGH</option><option>MEDIUM</option><option>LOW</option></select></Field>
        <Field label="Reason"><input value={f.reason} maxLength={300} onChange={e => set("reason", e.target.value)} placeholder="e.g. casualty evacuation stock" /></Field>
        <div className="form-actions"><Btn onClick={onClose} kind="ghost">Cancel</Btn><Btn type="submit" kind="primary" busy={busy === "c"}>Create request</Btn></div>
      </form>
    </Modal>
  );
}

export default function Requests() {
  const { can, simTime, sector, setSector } = useApp();
  const { data, error, reload } = useApi<any>("/api/requests");
  const { busy, run } = useAction();
  const [plan, setPlan] = useState<any>(null);
  const [creating, setCreating] = useState(false);
  const [open, setOpen] = useState<string | null>(null);
  if (error) return <ErrorBox msg={error} retry={reload} />;
  if (!data) return <Loading />;
  const live = data.requests.filter((r: any) => r.priority_score !== undefined && inSector(sector, r));
  const closed = data.requests.filter((r: any) => r.priority_score === undefined && inSector(sector, r)).reverse();

  return (
    <div className="page">
      <PageHead title="Supply requests" lede="Every open request is ranked by a transparent 100-point priority score so the most urgent need is served first."
        actions={<><SectorTabs value={sector} onChange={setSector} />{can("planner") && <Btn kind="primary" icon={<Plus size={16} />} onClick={() => setCreating(true)}>New request</Btn>}</>} />
      <div className="score-legend"><span><i className="seg-u" />Urgency (max 40)</span><span><i className="seg-c" />Criticality (max 30)</span><span><i className="seg-f" />Feasibility (max 20)</span><span><i className="seg-a" />Waiting time (max 10)</span></div>
      <Panel flush title={`Priority queue (${live.length} open)`}>
        {live.length === 0 ? <Empty title="No open requests" detail="All requests are dispatched. New ones appear here ranked automatically." /> : (
          <ol className="queue">
            {live.map((r: any) => (
              <li key={r.id} className="queue-item">
                <div className="q-rank num">{r.rank}</div>
                <div className="q-main">
                  <div className="q-top"><strong>{r.node_name}</strong><span>{fmt(r.qty)} {r.unit} {r.category_name.toLowerCase()}</span><Badge level={r.priority_level} /><Badge level={r.status} /><SectorChip sector={r.sector} />{r.source === "AI" && <span className="ai-chip"><Sparkles size={12} /> Raised by AI</span>}<span className="muted small">{r.id}</span></div>
                  <div className="q-scorebar" title={`Urgency ${r.breakdown.urgency}, criticality ${r.breakdown.criticality}, feasibility ${r.breakdown.feasibility}, waiting ${r.breakdown.age}`}>
                    <i className="seg-u" style={{ width: `${r.breakdown.urgency}%` }} /><i className="seg-c" style={{ width: `${r.breakdown.criticality}%` }} />
                    <i className="seg-f" style={{ width: `${r.breakdown.feasibility}%` }} /><i className="seg-a" style={{ width: `${r.breakdown.age}%` }} />
                    <b className="num">{r.priority_score}</b>
                  </div>
                  <p className="q-meta">Needed in {fmtDuration(hoursFrom(r.needed_by, simTime || r.created_at))} - stock covers {r.days_cover} days - <em>{r.reason}</em></p>
                  <p className="q-action"><b>Next step:</b> {r.recommended_action}</p>
                  <button className="link small" onClick={() => setOpen(open === r.id ? null : r.id)}>{open === r.id ? <ChevronUp size={14} /> : <ChevronDown size={14} />} Score breakdown and history</button>
                  {open === r.id && <div className="q-detail">
                    <ul className="factor-list">{r.factors.map((x: string, i: number) => <li key={i}>{x}</li>)}</ul>
                    <ul className="timeline">{r.history.map((h: any, i: number) => <li key={i}><time>{fmtTime(h.time)}</time>{h.text}</li>)}</ul>
                  </div>}
                </div>
                <div className="q-btns">
                  {can("planner") && <Btn kind="primary" small icon={<Route size={14} />} onClick={() => setPlan(r)}>Plan transport</Btn>}
                  {can("planner") && r.status === "NEW" && <Btn small icon={<Check size={14} />} busy={busy === "ap" + r.id} onClick={() => run("ap" + r.id, () => api(`/api/requests/${r.id}/approve`, { method: "POST", body: { note: "" } }), "Request approved")}>Approve</Btn>}
                  {can("admin") && <Btn small kind="ghost" icon={<XIcon size={14} />} busy={busy === "rj" + r.id} onClick={() => run("rj" + r.id, () => api(`/api/requests/${r.id}/reject`, { method: "POST", body: { note: "Not justified at this time" } }), "Request rejected")}>Reject</Btn>}
                </div>
              </li>
            ))}
          </ol>
        )}
      </Panel>
      <Panel flush title="Dispatched, delivered and rejected">
        <div className="tbl-wrap"><table className="tbl">
          <thead><tr><th>ID</th><th>Location</th><th>Supply</th><th className="right">Qty</th><th>Origin</th><th>Status</th><th>Last update</th></tr></thead>
          <tbody>{closed.map((r: any) => (
            <tr key={r.id}><td>{r.id}</td><td>{r.node_name}</td><td>{CAT_SHORT[r.category]}</td><td className="num right">{fmt(r.qty)}</td>
              <td>{r.source === "AI" ? <span className="ai-chip"><Sparkles size={12} /> AI Autopilot</span> : r.source === "PREDICTIVE" ? "Predictive engine" : r.source === "SYSTEM" ? "Scheduled" : "Field request"}</td><td><Badge level={r.status} /></td>
              <td className="muted small">{r.history[r.history.length - 1]?.text}</td></tr>))}</tbody>
        </table></div>
      </Panel>
      {plan && <PlanModal req={plan} onClose={() => setPlan(null)} />}
      {creating && <NewRequest onClose={() => setCreating(false)} />}
    </div>
  );
}
