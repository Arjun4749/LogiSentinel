import { useEffect, useState } from "react";
import { Area, Bar, BarChart, CartesianGrid, ComposedChart, Line, ReferenceArea, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { RefreshCw, Brain } from "lucide-react";
import { api } from "../api";
import { Badge, Btn, CAT_SHORT, ErrorBox, Field, fmt, KV, Loading, PageHead, Panel, useAction, useApi, useApp, SECTOR_LABEL } from "../ui";

export default function Forecast() {
  const { params, can } = useApp();
  const [node, setNode] = useState(params.node || "FP-E");
  const [cat, setCat] = useState(params.category || "FUEL");
  const [horizon, setHorizon] = useState(14);
  useEffect(() => { if (params.node) setNode(params.node); if (params.category) setCat(params.category); }, [params.node, params.category]);
  const ref = useApi<any>("/api/reference");
  const fc = useApi<any>(`/api/forecast?node=${node}&category=${cat}&horizon=${horizon}`);
  const ov = useApi<any>("/api/forecast/overview");
  const { busy, run } = useAction();

  if (fc.error) return <ErrorBox msg={fc.error} retry={fc.reload} />;
  const f = fc.data;
  const m = f?.model || ov.data?.model;
  const opsRanges: [string, string][] = [];
  if (f) {
    let start: string | null = null, prev: string | null = null;
    for (const p of f.series) {
      if (p.ops && !start) start = p.date;
      if (!p.ops && start) { opsRanges.push([start, prev!]); start = null; }
      prev = p.date;
    }
    if (start) opsRanges.push([start, prev!]);
  }
  const today = f?.series.find((p: any) => p.forecast !== undefined)?.date;
  const movers = (ov.data?.rows || []).filter((r: any) => r.type !== "depot").sort((a: any, b: any) => Math.abs(b.change_pct) - Math.abs(a.change_pct)).slice(0, 8);
  const drivers = m ? Object.entries(m.driver_importance || {}).map(([k, v]) => ({ name: k, value: v })).sort((a: any, b: any) => b.value - a.value) : [];

  return (
    <div className="page">
      <PageHead title="Demand forecast" lede="Machine-learning forecast of daily consumption for every location and supply type, with a confidence range and the reasons behind it."
        actions={can("planner") && <Btn icon={<RefreshCw size={15} />} busy={busy === "rt"} onClick={() => run("rt", () => api("/api/forecast/retrain", { method: "POST" }), (r: any) => `Model retrained: ${r.accuracy_pct}% accuracy on held-back days`)}>Retrain model</Btn>} />
      <div className="filters">
        <Field label="Location">
          <select value={node} onChange={e => setNode(e.target.value)}>
            {ref.data && ["NORTH", "EAST", "WEST", "ISLANDS"].map(g => <optgroup key={g} label={SECTOR_LABEL[g]}>{Object.entries(ref.data.nodes).filter(([, n]: any) => n.sector === g).map(([id, n]: any) => <option key={id} value={id}>{n.name} ({n.type === "post" ? "forward post" : n.type})</option>)}</optgroup>)}
          </select>
        </Field>
        <Field label="Supply type">
          <select value={cat} onChange={e => setCat(e.target.value)}>
            {ref.data && Object.entries(ref.data.categories).map(([id, c]: any) => <option key={id} value={id}>{c.name}</option>)}
          </select>
        </Field>
        <Field label="Forecast horizon">
          <div className="seg">{[7, 14, 30].map(h => <button key={h} className={horizon === h ? "on" : ""} onClick={() => setHorizon(h)}>{h} days</button>)}</div>
        </Field>
      </div>

      {!f ? <Loading label="Running forecast" /> : (
        <>
          <div className="grid-2-1">
            <Panel title={`${f.node_name}: ${f.category_name}`} sub={`Daily ${f.unit}. Solid = actual consumption, dashed = forecast, band = 90% confidence range, shaded columns = planned exercises.`}>
              <div className="chart-l">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={f.series} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                    <CartesianGrid stroke="var(--grid)" vertical={false} />
                    <XAxis dataKey="date" tickFormatter={d => d.slice(5)} tick={{ fontSize: 11, fill: "var(--ink-3)" }} minTickGap={24} />
                    <YAxis yAxisId="q" tick={{ fontSize: 11, fill: "var(--ink-3)" }} width={56} tickFormatter={v => fmt(v)} />
                    <YAxis yAxisId="t" orientation="right" tick={{ fontSize: 11, fill: "var(--ink-3)" }} width={36} unit="°" />
                    {opsRanges.map(([a, b]) => <ReferenceArea key={a} yAxisId="q" x1={a} x2={b} fill="var(--signal)" fillOpacity={0.14} />)}
                    {today && <ReferenceLine yAxisId="q" x={today} stroke="var(--ink-3)" strokeDasharray="3 3" label={{ value: "Today", fontSize: 11, fill: "var(--ink-3)", position: "insideTopLeft" }} />}
                    <Tooltip contentStyle={{ background: "var(--panel)", border: "1px solid var(--line)", borderRadius: 8 }}
                      formatter={(v: any, n: any) => [Array.isArray(v) ? `${fmt(v[0], 1)} - ${fmt(v[1], 1)}` : n === "Temperature" ? `${v} C` : fmt(v, 1), n]} />
                    <Area yAxisId="q" dataKey="band" name="90% range" fill="var(--primary)" fillOpacity={0.16} stroke="none" isAnimationActive={false} />
                    <Line yAxisId="t" dataKey="temp" name="Temperature" stroke="var(--cold)" strokeWidth={1.2} dot={false} strokeOpacity={0.7} isAnimationActive={false} />
                    <Line yAxisId="q" dataKey="actual" name="Actual" stroke="var(--ink)" strokeWidth={2} dot={false} isAnimationActive={false} />
                    <Line yAxisId="q" dataKey="forecast" name="Forecast" stroke="var(--primary)" strokeWidth={2.6} strokeDasharray="6 4" dot={false} isAnimationActive={false} />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
              <div className="chart-key"><span><i className="k-actual" />Actual</span><span><i className="k-fc" />Forecast</span><span><i className="k-band" />90% range</span><span><i className="k-temp" />Temperature (right axis)</span><span><i className="k-ops" />Planned exercise</span></div>
            </Panel>
            <div className="stack">
              <Panel title={`Next ${horizon} days`}>
                <div className="big-figure"><strong className="num">{fmt(f.total)}</strong><span>{f.unit} expected</span></div>
                <p className="muted">90% range {fmt(f.total_lower)} to {fmt(f.total_upper)} {f.unit}. About {fmt(f.avg_daily, 1)} {f.unit} per day.</p>
                <KV items={[["Model confidence", `${Math.round(f.confidence * 100)}%`],
                  ["Stock on hand", `${fmt(f.inventory.on_hand)} ${f.unit}`],
                  ["Days of supply", <span key="d">{f.inventory.days_of_supply} days <Badge level={f.inventory.status} /></span>],
                  ["Runs out in", f.inventory.stockout_in_days !== null ? `${f.inventory.stockout_in_days} days (incl. incoming)` : `Not within 30 days`]]} />
              </Panel>
              <Panel title="Why this forecast" sub="Drivers the model reacted to">
                <ul className="why-list">{f.factors.map((x: string, i: number) => <li key={i}>{x}</li>)}</ul>
              </Panel>
            </div>
          </div>

          <div className="grid-3">
            <Panel title="Model card" sub={m?.model}>
              {m && <>
                <div className="acc-compare">
                  <div><span>LogiSentinel model error</span><div className="acc-bar"><i style={{ width: `${m.wape_pct * 4}%` }} className="good" /><b className="num">{m.wape_pct}%</b></div></div>
                  <div><span>Simple 7-day average error</span><div className="acc-bar"><i style={{ width: `${m.naive_wape_pct * 4}%` }} /><b className="num">{m.naive_wape_pct}%</b></div></div>
                </div>
                <p className="muted">Tested on the last {m.holdout_days} days the model never saw. {m.improvement_vs_naive_pct}% less error than the simple average.</p>
                <KV items={[["Accuracy", `${m.accuracy_pct}%`], ["Version", m.version], ["Training rows", fmt(m.training_rows)], ["History used", `${m.history_days} days x ${m.series} series`], ["Training time", `${m.train_seconds} s`]]} />
              </>}
            </Panel>
            <Panel title="What drives demand" sub="Share of the model's decisions (feature importance)">
              <div className="chart-s">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={drivers} layout="vertical" margin={{ top: 0, right: 34, left: 0, bottom: 0 }}>
                    <XAxis type="number" hide />
                    <YAxis type="category" dataKey="name" width={150} tick={{ fontSize: 11, fill: "var(--ink-2)" }} axisLine={false} tickLine={false} />
                    <Bar dataKey="value" fill="var(--primary)" radius={[0, 4, 4, 0]} label={{ position: "right", fontSize: 11, fill: "var(--ink-2)", formatter: (v: any) => `${v}%` }} isAnimationActive={false} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Panel>
            <Panel title="Biggest changes next week" sub="Forecast vs last 7 days actual">
              <table className="tbl compact">
                <tbody>
                  {movers.map((r: any) => (
                    <tr key={r.node + r.category} className="clickable" onClick={() => { setNode(r.node); setCat(r.category); window.scrollTo({ top: 0, behavior: "smooth" }); }}>
                      <td>{r.node_name}</td><td>{CAT_SHORT[r.category]}</td>
                      <td className={`num right ${r.change_pct > 0 ? "t-up" : "t-down"}`}>{r.change_pct > 0 ? "+" : ""}{r.change_pct}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Panel>
          </div>
        </>
      )}
    </div>
  );
}
