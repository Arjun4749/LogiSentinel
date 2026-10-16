import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { FlaskConical, Play } from "lucide-react";
import { api } from "../api";
import { Badge, Btn, CAT_SHORT, Empty, Field, fmt, Loading, PageHead, Panel, SECTOR_SHORT, useApi, useApp } from "../ui";

const EMPTY = { name: "Custom scenario", demand_change_pct: 0, demand_nodes: [] as string[], demand_categories: [] as string[], closed_routes: [] as string[],
  unavailable_assets: [] as string[], severe_weather: false, extra_lead_hours: 0, horizon_days: 14 };

const METRICS: [string, string, string, boolean][] = [
  ["readiness_index", "Supply readiness", "/100", true],
  ["posts_at_risk", "Posts facing stock-out", "", false],
  ["stockout_items", "Supply lines that run out", "", false],
  ["unmet_demand_t", "Unmet demand", " t", false],
  ["required_lift_t", "Tonnage to move", " t", false],
  ["transport_utilisation_pct", "Transport needed vs available", "%", false],
  ["avg_post_lead_hours", "Average lead time to posts", " h", false],
];

function toggle(list: string[], v: string) { return list.includes(v) ? list.filter(x => x !== v) : [...list, v]; }

export default function Scenario() {
  const { can, toast } = useApp();
  const presets = useApi<any>("/api/scenarios/presets");
  const ref = useApi<any>("/api/reference");
  const fleet = useApi<any>("/api/assets");
  const [p, setP] = useState<any>(EMPTY);
  const [res, setRes] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [active, setActive] = useState<string | null>(null);

  const runIt = async (params: any, id: string | null) => {
    setBusy(true); setActive(id);
    try { setRes(await api("/api/scenarios/run", { method: "POST", body: params })); }
    catch (e: any) { toast(e.message, "err"); }
    finally { setBusy(false); }
  };
  const nodes = ref.data ? Object.entries(ref.data.nodes).filter(([, n]: any) => n.type !== "depot") : [];
  const chart = res ? res.scenario.nodes.map((n: any) => {
    const b = res.baseline.nodes.find((x: any) => x.node === n.node);
    return { name: n.node_name.replace("Supply ", "").replace("Island ", "").replace("Post ", ""), Baseline: b?.min_days_cover, Scenario: n.min_days_cover };
  }) : [];

  return (
    <div className="page">
      <PageHead title="What-if simulator" lede="Test a crisis before it happens. The same forecasting, stock and transport engines run on a sandbox copy, so live data is never changed." />
      <div className="scen-layout">
        <div className="stack">
          <Panel title="Ready-made scenarios">
            {!presets.data ? <Loading /> : <div className="preset-list">
              {presets.data.presets.map((pr: any) => (
                <button key={pr.id} className={`preset ${active === pr.id ? "on" : ""}`} disabled={busy || !can("planner")}
                  onClick={() => { const np = { ...EMPTY, ...pr.params, name: pr.name }; setP(np); runIt(np, pr.id); }}>
                  <strong>{pr.name}</strong><span>{pr.description}</span>
                </button>
              ))}
            </div>}
          </Panel>
          <Panel title="Build your own">
            <div className="form-grid one">
              <Field label={`Demand change: ${p.demand_change_pct > 0 ? "+" : ""}${p.demand_change_pct}%`}>
                <input type="range" min={-30} max={150} step={5} value={p.demand_change_pct} onChange={e => setP({ ...p, demand_change_pct: Number(e.target.value) })} /></Field>
              <Field label="Apply demand change to" hint="Leave empty for all locations">
                <div className="check-grid">{nodes.map(([id, n]: any) => <label key={id} className="toggle"><input type="checkbox" checked={p.demand_nodes.includes(id)} onChange={() => setP({ ...p, demand_nodes: toggle(p.demand_nodes, id) })} /><span>{n.name} <small className="muted">{SECTOR_SHORT[n.sector]}</small></span></label>)}</div></Field>
              <Field label="Close these routes">
                <div className="check-grid">{ref.data && Object.entries(ref.data.routes).map(([id, r]: any) => <label key={id} className="toggle"><input type="checkbox" checked={p.closed_routes.includes(id)} onChange={() => setP({ ...p, closed_routes: toggle(p.closed_routes, id) })} /><span>{r.name}</span></label>)}</div></Field>
              <Field label="Vehicles out of action">
                <div className="check-grid assets">{(fleet.data?.assets || []).map((x: any) => x.id).map((a: string) => <label key={a} className="toggle"><input type="checkbox" checked={p.unavailable_assets.includes(a)} onChange={() => setP({ ...p, unavailable_assets: toggle(p.unavailable_assets, a) })} /><span>{a}</span></label>)}</div></Field>
              <label className="toggle"><input type="checkbox" checked={p.severe_weather} onChange={e => setP({ ...p, severe_weather: e.target.checked })} /><span>Severe weather on all snow-prone passes (helicopters grounded)</span></label>
              <Field label="Extra delay on every delivery (hours)"><input type="number" min={0} max={240} value={p.extra_lead_hours} onChange={e => setP({ ...p, extra_lead_hours: Number(e.target.value) })} /></Field>
              <Field label="Planning window"><div className="seg">{[7, 14, 21].map(h => <button key={h} type="button" className={p.horizon_days === h ? "on" : ""} onClick={() => setP({ ...p, horizon_days: h })}>{h} days</button>)}</div></Field>
              <div className="form-actions">
                <Btn kind="ghost" onClick={() => { setP(EMPTY); setRes(null); setActive(null); }}>Reset</Btn>
                <Btn kind="primary" icon={<Play size={15} />} busy={busy} disabled={!can("planner")} onClick={() => runIt({ ...p, name: "Custom scenario" }, null)}>Run simulation</Btn>
              </div>
              {!can("planner") && <p className="muted small">Viewers can look but not run simulations.</p>}
            </div>
          </Panel>
        </div>

        <div className="stack">
          {!res && !busy && <Panel><Empty title="Pick a scenario to see its impact" detail="Results compare the scenario with today's baseline plan, side by side." /></Panel>}
          {busy && <Panel><Loading label="Simulating" /></Panel>}
          {res && !busy && <>
            <Panel title={res.params.name} actions={<Badge level={res.impact}>{res.impact.toLowerCase()} impact</Badge>}>
              <div className="compare">
                <div className="cmp-head"><span /><span>Baseline</span><span>Scenario</span><span>Change</span></div>
                {METRICS.map(([k, label, unit, higherBetter]) => {
                  const b = res.baseline[k], s = res.scenario[k];
                  const d = b !== null && s !== null ? s - b : null;
                  const worse = d !== null && (higherBetter ? d < -0.05 : d > 0.05);
                  const better = d !== null && (higherBetter ? d > 0.05 : d < -0.05);
                  return (
                    <div className="cmp-row" key={k}>
                      <span>{label}</span><b className="num">{b === null ? "-" : fmt(b, 1)}{unit}</b><b className="num">{s === null ? "-" : fmt(s, 1)}{unit}</b>
                      <em className={`num ${worse ? "t-crit" : better ? "t-ok" : "muted"}`}>{d === null || Math.abs(d) < 0.05 ? "no change" : `${d > 0 ? "+" : ""}${fmt(d, 1)}${unit}`}</em>
                    </div>
                  );
                })}
              </div>
              {(res.scenario.isolated_posts.length > 0 || res.scenario.air_only_posts.length > 0) && (
                <p className="callout">{res.scenario.isolated_posts.length > 0 && <>Cut off completely: <b>{res.scenario.isolated_posts.join(", ")}</b>. </>}
                  {res.scenario.air_only_posts.length > 0 && <>Reachable by air only: <b>{res.scenario.air_only_posts.join(", ")}</b>.</>}</p>
              )}
            </Panel>
            <Panel title="What to do now" sub="Generated from the simulation results">
              <ol className="steps">{res.recommendations.map((r: string, i: number) => <li key={i}>{r}</li>)}</ol>
            </Panel>
            <Panel title="Lowest days of cover per location" sub="Worst supply line at each location, before resupply">
              <div className="chart-m">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chart} margin={{ top: 8, right: 8, left: -14, bottom: 0 }}>
                    <CartesianGrid stroke="var(--grid)" vertical={false} />
                    <XAxis dataKey="name" tick={{ fontSize: 11, fill: "var(--ink-3)" }} interval={0} angle={-40} textAnchor="end" height={64} />
                    <YAxis tick={{ fontSize: 11, fill: "var(--ink-3)" }} unit="d" />
                    <Tooltip contentStyle={{ background: "var(--panel)", border: "1px solid var(--line)", borderRadius: 8 }} />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Bar dataKey="Baseline" fill="var(--ink-3)" radius={[3, 3, 0, 0]} isAnimationActive={false} />
                    <Bar dataKey="Scenario" fill="var(--crit)" radius={[3, 3, 0, 0]} isAnimationActive={false} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Panel>
            {res.scenario.stockouts.length > 0 && (
              <Panel flush title={`Supply lines that run out (${res.scenario.stockouts.length})`}>
                <div className="tbl-wrap"><table className="tbl">
                  <thead><tr><th>Location</th><th>Supply</th><th className="right">Runs out on day</th><th className="right">Resupply takes</th><th className="right">Shortfall</th></tr></thead>
                  <tbody>{res.scenario.stockouts.map((s: any, i: number) => (
                    <tr key={i}><td>{s.node_name}</td><td>{CAT_SHORT[s.category]}</td><td className="num right t-crit">{s.stockout_day}</td>
                      <td className="num right">{s.lead_days === null ? "cut off" : `${s.lead_days} d`}</td><td className="num right">{fmt(s.unmet_qty)} {s.unit}</td></tr>))}</tbody>
                </table></div>
              </Panel>
            )}
          </>}
        </div>
      </div>
    </div>
  );
}
