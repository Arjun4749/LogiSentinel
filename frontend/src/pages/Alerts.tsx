import { useState } from "react";
import { Check, CheckCheck, ExternalLink } from "lucide-react";
import { api } from "../api";
import { Badge, Btn, Empty, ErrorBox, fmtTime, inSector, Loading, PageHead, Panel, SectorChip, SectorTabs, useAction, useApi, useApp } from "../ui";

const TYPE_LABEL: Record<string, string> = {
  STOCKOUT_RISK: "Stock-out risk", BELOW_REORDER: "Below reorder point", SHIPMENT_HOLD: "Shipment holding", SHIPMENT_DELAY: "Shipment delay",
  DISRUPTION: "Disruption", WEATHER_WINDOW: "Weather window", CAPACITY: "Transport capacity", ASSET_MAINTENANCE: "Maintenance",
  SERVICE_DUE: "Service due", DEVICE_OFFLINE: "Sensor offline", DEVICE_BATTERY: "Sensor battery",
  PREDICTED_SHORTAGE: "AI shortage forecast", PREDICTED_DELAY: "AI delay prediction", DEMAND_ANOMALY: "AI anomaly detection",
};

export default function Alerts() {
  const { go, can, sector, setSector } = useApp();
  const aiLog = useApi<any>("/api/ai");
  const [source, setSource] = useState("all");
  const { data, error, reload } = useApi<any>("/api/alerts");
  const { busy, run } = useAction();
  const [view, setView] = useState<"open" | "ACKNOWLEDGED" | "RESOLVED" | "all" | "ai">("open");
  const [sev, setSev] = useState<string>("ALL");
  if (error) return <ErrorBox msg={error} retry={reload} />;
  if (!data) return <Loading />;
  const all: any[] = data.alerts.filter((a: any) => inSector(sector, a) && (source === "all" || a.source === source));
  const handled = (aiLog.data?.log || []).filter((e: any) => inSector(sector, e));
  const list = all.filter(a => (view === "all" ? true : view === "open" ? a.status === "NEW" : a.status === view))
    .filter(a => sev === "ALL" || a.severity === sev);
  const count = (s: string) => all.filter(a => a.status === "NEW" && a.severity === s).length;

  return (
    <div className="page">
      <PageHead title="Alerts & recommendations" lede="Raised automatically by the AI (forecasts, anomalies, weather and delay predictions), by IoT sensors and by convoy tracking. Each alert says what to do next. Red stock-out alerts are acted on by the AI Autopilot."
        actions={<SectorTabs value={sector} onChange={setSector} />} />
      <div className="sev-strip">
        {["CRITICAL", "HIGH", "MEDIUM", "LOW"].map(s => (
          <button key={s} className={`sev-card sev-${s.toLowerCase()} ${sev === s ? "on" : ""}`} onClick={() => setSev(sev === s ? "ALL" : s)}>
            <strong className="num">{count(s)}</strong><span>{s[0] + s.slice(1).toLowerCase()} - new</span>
          </button>
        ))}
      </div>
      <Panel flush title={
        <div className="tabs" role="tablist">
          {([["open", "New"], ["ACKNOWLEDGED", "Acknowledged"], ["RESOLVED", "Resolved"], ["all", "All"], ["ai", `Handled by AI (${handled.length})`]] as const).map(([k, l]) => (
            <button key={k} role="tab" aria-selected={view === k} className={view === k ? "on" : ""} onClick={() => setView(k as any)}>{l}</button>
          ))}
        </div>}
        actions={view !== "ai" && <select value={source} onChange={e => setSource(e.target.value)} aria-label="Alert source">
          <option value="all">All sources</option><option value="AI">Raised by AI</option><option value="SENSOR">IoT sensors</option><option value="SYSTEM">Tracking and reports</option></select>}>
        {view === "ai" ? (handled.length === 0 ? <Empty title="The AI has not acted yet" detail="It acts within about 10 to 20 seconds of a unit turning red." /> : (
          <ul className="alert-list">
            {handled.map((e: any) => (
              <li key={e.id} className="alert-item sevline-ai">
                <div className="alert-main">
                  <div className="alert-top"><Badge level={e.kind} /><SectorChip sector={e.sector} /><span className="muted small">{fmtTime(e.time)} - {e.id}</span></div>
                  <h3>{e.title}</h3>
                  <p>{e.reasoning[0]}</p>
                  <p className="rec-action"><b>AI action:</b> {e.request_id ? `request ${e.request_id}` : ""}{e.shipments.length ? `, shipments ${e.shipments.join(", ")}` : ""}</p>
                </div>
                <div className="alert-btns"><Btn small onClick={() => go("ai")}>See full reasoning</Btn></div>
              </li>
            ))}
          </ul>)) : <>
        {list.length === 0 ? <Empty title="Nothing here" detail="No alerts match this filter." /> : (
          <ul className="alert-list">
            {list.map(a => (
              <li key={a.id} className={`alert-item sevline-${a.severity.toLowerCase()}`}>
                <div className="alert-main">
                  <div className="alert-top"><Badge level={a.severity} />{a.source === "AI" && <Badge level="AI">AI</Badge>}{a.source === "SENSOR" && <Badge level="SENSOR">IoT</Badge>}<SectorChip sector={a.sector} /><span className="alert-type">{TYPE_LABEL[a.type] || a.type.replace(/_/g, " ").toLowerCase()}</span>
                    {a.status !== "NEW" && <span className="muted small">{a.status.toLowerCase()} by {a.acknowledged_by} at {fmtTime(a.status_time)}</span>}</div>
                  <h3>{a.title}</h3>
                  <p>{a.message}</p>
                  <p className="rec-action"><b>Recommended:</b> {a.recommended_action}</p>
                </div>
                <div className="alert-btns">
                  <Btn small icon={<ExternalLink size={14} />} onClick={() => go(a.page)}>Open</Btn>
                  {can("planner") && a.status === "NEW" && <Btn small icon={<Check size={14} />} busy={busy === "a" + a.id}
                    onClick={() => run("a" + a.id, () => api(`/api/alerts/${encodeURIComponent(a.id)}/ack`, { method: "POST", body: { note: "" } }), "Alert acknowledged")}>Acknowledge</Btn>}
                  {can("planner") && a.status !== "RESOLVED" && <Btn small kind="ghost" icon={<CheckCheck size={14} />} busy={busy === "r" + a.id}
                    onClick={() => run("r" + a.id, () => api(`/api/alerts/${encodeURIComponent(a.id)}/resolve`, { method: "POST", body: { note: "" } }), "Alert resolved")}>Resolve</Btn>}
                </div>
              </li>
            ))}
          </ul>
        )}
        </>}
      </Panel>
    </div>
  );
}
