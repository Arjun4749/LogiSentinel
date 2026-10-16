import { useState } from "react";
import { Sparkles, ScanSearch, Power, Radar, LineChart, Calculator, Warehouse, Route, Send } from "lucide-react";
import { api } from "../api";
import { Badge, Btn, Empty, ErrorBox, fmt, fmtTime, inSector, Loading, PageHead, Panel, SectorChip, useAction, useApi, useApp } from "../ui";

const PIPE = [
  { icon: Radar, t: "Detect", d: "Checks every supply line at every post and hub every 10 seconds and confirms a red alert twice." },
  { icon: LineChart, t: "Forecast", d: "ML model predicts daily demand and the stock-out date." },
  { icon: Calculator, t: "Size the order", d: "Forecast x (lead time + review) + safety stock - stock held." },
  { icon: Warehouse, t: "Pick a source", d: "Nearest hub or depot in the same sector with spare stock." },
  { icon: Route, t: "Plan transport", d: "Scores road, sea, helicopter, aircraft and drone on ETA, risk and cost." },
  { icon: Send, t: "Dispatch and log", d: "Sends the best option and records its reasons for audit." },
];

export default function AiCentre() {
  const { can, go, sector } = useApp();
  const { data, error, reload } = useApi<any>("/api/ai");
  const { busy, run } = useAction();
  const [kind, setKind] = useState("all");
  if (error) return <ErrorBox msg={error} retry={reload} />;
  if (!data) return <Loading label="Connecting to the AI Autopilot" />;
  const st = data.stats || {};
  const log = (data.log || []).filter((e: any) => inSector(sector, e) && (kind === "all" || e.kind === kind));
  const cfg = (body: any, msg: string) => run("cfg", () => api("/api/ai/config", { method: "POST", body }), msg);

  return (
    <div className="page">
      <PageHead title="AI Command Centre"
        lede={`The AI Autopilot watches ${data.watching} supply lines across four sectors. When a unit goes red it raises the supply request itself, plans the transport and dispatches it, without waiting for anyone. Every decision is explained below.`}
        actions={can("planner") && <Btn kind="primary" icon={<ScanSearch size={16} />} busy={busy === "scan"}
          onClick={() => run("scan", () => api("/api/ai/scan", { method: "POST" }), (r: any) => r.actions.length ? `AI took ${r.actions.length} action(s)` : "AI scan complete - nothing needs action right now")}>Run AI scan now</Btn>} />

      <div className="ai-hero">
        <div className={`ai-switch ${data.enabled ? "on" : "off"}`}>
          <div className="ai-switch-top">
            <Sparkles size={22} />
            <div><strong>AI Autopilot is {data.enabled ? "ON" : "OFF"}</strong>
              <span>Last scan {data.last_scan ? fmtTime(data.last_scan) : "pending"} - model {data.model?.version} ({data.model?.accuracy_pct}% accurate)</span></div>
          </div>
          {can("planner") && <Btn kind={data.enabled ? "default" : "primary"} icon={<Power size={15} />} busy={busy === "cfg"}
            onClick={() => cfg({ enabled: !data.enabled }, data.enabled ? "AI Autopilot switched off - alerts will wait for humans" : "AI Autopilot switched on")}>
            {data.enabled ? "Switch off" : "Switch on"}</Btn>}
        </div>
        <div className="ai-modes">
          <div className="ai-mode">
            <span className="field-label">When a unit goes red (will run out before resupply can arrive)</span>
            <div className="seg">
              {[["dispatch", "Raise request + dispatch"], ["request", "Raise request only"], ["off", "Alert only"]].map(([k, l]) => (
                <button key={k} disabled={!can("planner")} className={data.critical_mode === k ? "on" : ""} onClick={() => cfg({ critical_mode: k }, `Red alerts: ${l.toLowerCase()}`)}>{l}</button>
              ))}
            </div>
          </div>
          <div className="ai-mode">
            <span className="field-label">When a unit goes amber (below reorder point)</span>
            <div className="seg">
              {[["request", "Raise request automatically"], ["recommend", "Recommend to planner"]].map(([k, l]) => (
                <button key={k} disabled={!can("planner")} className={data.low_mode === k ? "on" : ""} onClick={() => cfg({ low_mode: k }, `Amber alerts: ${l.toLowerCase()}`)}>{l}</button>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="sev-strip">
        <div className="sev-card static sev-ai"><strong className="num">{st.red_alerts_handled || 0}</strong><span>Red alerts handled automatically</span></div>
        <div className="sev-card static"><strong className="num">{st.auto_requests || 0}</strong><span>Requests raised by AI</span></div>
        <div className="sev-card static"><strong className="num">{st.auto_dispatches || 0}</strong><span>Dispatches by AI</span></div>
        <div className="sev-card static"><strong className="num">{fmt(st.avg_response_s || 0, 0)} s</strong><span>Average time from red alert to dispatch</span></div>
        <div className={`sev-card static ${st.escalations ? "sev-high" : ""}`}><strong className="num">{st.escalations || 0}</strong><span>Escalated to a human</span></div>
      </div>

      <Panel title="How the autopilot decides" sub="The same six steps run for every red alert, in this order">
        <ol className="pipeline">
          {PIPE.map((p, i) => { const I = p.icon; return (
            <li key={p.t}><span className="pipe-n num">{i + 1}</span><I size={20} /><strong>{p.t}</strong><span>{p.d}</span></li>
          ); })}
        </ol>
      </Panel>

      <Panel flush title={`Decision log (${log.length})`} sub="Newest first. Each entry shows what the AI saw, what it decided and why."
        actions={<select value={kind} onChange={e => setKind(e.target.value)} aria-label="Decision type">
          <option value="all">All decisions</option><option value="AUTO_DISPATCH">Handled automatically</option>
          <option value="AUTO_REQUEST">Request raised</option><option value="ESCALATION">Escalated</option></select>}>
        {log.length === 0 ? <Empty title="No AI decisions yet" detail="The autopilot acts as soon as a unit turns red. Speed up the clock or press 'Run AI scan now'." /> : (
          <ul className="ai-log">
            {log.map((e: any) => (
              <li key={e.id} className={`ai-entry k-${e.kind.toLowerCase()}`}>
                <div className="ai-entry-head">
                  <Badge level={e.kind} /><SectorChip sector={e.sector} />
                  <strong>{e.title}</strong>
                  <span className="muted small">{fmtTime(e.time)} - {e.id} - confidence {Math.round(e.confidence * 100)}%
                    {e.response_s !== null && e.response_s !== undefined ? ` - acted ${fmt(e.response_s, 0)} s after the alert` : ""}</span>
                </div>
                <ol className="reasoning">{e.reasoning.map((r: string, i: number) => <li key={i}>{r}</li>)}</ol>
                <div className="ai-links">
                  {e.request_id && <button className="link small" onClick={() => go("requests")}>Request {e.request_id}</button>}
                  {e.shipments.length > 0 && <button className="link small" onClick={() => go("shipments")}>Shipments {e.shipments.join(", ")}</button>}
                  <button className="link small" onClick={() => go("forecast", { node: e.node, category: e.category })}>Forecast behind this decision</button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}
