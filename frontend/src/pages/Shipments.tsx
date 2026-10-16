import { useState } from "react";
import { Download, Truck, Plane, Send, Ship } from "lucide-react";
import { download } from "../api";
import { Badge, Btn, CAT_SHORT, Empty, ErrorBox, fmt, fmtDuration, fmtTime, hoursFrom, inSector, KV, Loading, Meter, Modal, PageHead, Panel, RiskBreakdown, SectorChip, SectorTabs, useApi, useApp } from "../ui";

const MODE_ICON: Record<string, any> = { ROAD: Truck, AIR: Plane, DRONE: Send, SEA: Ship };
const ACTIVE = ["SCHEDULED", "LOADING", "IN_TRANSIT", "DELAYED", "HOLDING"];
const PHASES = ["SCHEDULED", "LOADING", "IN_TRANSIT", "DELIVERED"];
const PHASE_TEXT: Record<string, string> = { SCHEDULED: "Vehicle getting ready", LOADING: "Loading", IN_TRANSIT: "On the move", DELIVERED: "Delivered" };

function nextStep(s: any, now: string) {
  if (!now) return "";
  if (s.status === "SCHEDULED") return `Loading starts in ${fmtDuration(Math.max(0, hoursFrom(s.loading_start || s.planned_departure, now)))} (vehicle ready time)`;
  if (s.status === "LOADING") return `Departs in ${fmtDuration(Math.max(0, hoursFrom(s.planned_departure, now)))}`;
  if (s.status === "HOLDING") return "Waiting for the route to reopen";
  if (s.status === "DELIVERED") return `Delivered ${fmtTime(s.actual_arrival)}`;
  return `Arrives in ${fmtDuration(Math.max(0, hoursFrom(s.eta, now)))}`;
}

function Phases({ s }: { s: any }) {
  const cur = s.status === "DELAYED" || s.status === "HOLDING" ? "IN_TRANSIT" : s.status;
  const idx = PHASES.indexOf(cur);
  return (
    <ol className="phases">
      {PHASES.map((p, i) => <li key={p} className={i < idx ? "done" : i === idx ? "now" : ""}><span>{i + 1}</span>{PHASE_TEXT[p]}</li>)}
    </ol>
  );
}

export default function Shipments() {
  const { toast, go, sector, setSector, simTime } = useApp();
  const sh = useApi<any>("/api/shipments");
  const as = useApi<any>("/api/assets");
  const [filter, setFilter] = useState("active");
  const [sel, setSel] = useState<any>(null);
  if (sh.error) return <ErrorBox msg={sh.error} retry={sh.reload} />;
  if (!sh.data) return <Loading />;
  const all = sh.data.shipments.filter((s: any) => inSector(sector, s));
  const list = all.filter((s: any) => filter === "all" ? true : filter === "active" ? ACTIVE.includes(s.status) : filter === "late" ? ["DELAYED", "HOLDING"].includes(s.status) : s.status === filter);
  const c = (f: (s: any) => boolean) => all.filter(f).length;
  const assets = (as.data?.assets || []).filter((a: any) => inSector(sector, a));
  const busy = assets.filter((a: any) => ["ON_MISSION", "RETURNING"].includes(a.status)).length;
  const usable = assets.filter((a: any) => a.status !== "MAINTENANCE").length;

  return (
    <div className="page">
      <PageHead title="Transport & shipments" lede="Track every convoy, airlift and drone sortie from dispatch to delivery, and see which vehicles are free."
        actions={<><SectorTabs value={sector} onChange={setSector} /><Btn icon={<Download size={15} />} onClick={() => download("/api/export/shipments.csv", "shipments.csv").catch(e => toast(e.message, "err"))}>Export CSV</Btn></>} />
      <div className="how-timing">
        <strong>How shipment timing works:</strong> every shipment follows the mission clock through four fixed steps -
        <Phases s={{ status: "SCHEDULED" }} />
        It stays <b>Scheduled</b> until its vehicle is ready (a vehicle may first drive to the source), then <b>loads</b> (1 h for trucks and aircraft, 6 h for ships), then departs at the planned time. Nothing moves at random: each step happens exactly at the time shown.
      </div>
      <div className="sev-strip">
        {[["active", "Active", c(s => ACTIVE.includes(s.status))], ["late", "Delayed or holding", c(s => ["DELAYED", "HOLDING"].includes(s.status))],
          ["SCHEDULED", "Scheduled", c(s => s.status === "SCHEDULED")], ["DELIVERED", "Delivered", c(s => s.status === "DELIVERED")], ["all", "All", all.length]].map(([k, l, n]: any) => (
          <button key={k} className={`sev-card ${filter === k ? "on" : ""} ${k === "late" && n ? "sev-high" : ""}`} onClick={() => setFilter(k)}><strong className="num">{n}</strong><span>{l}</span></button>
        ))}
      </div>
      <Panel flush title="Shipments">
        {list.length === 0 ? <Empty title="No shipments in this view" detail="Dispatch from Stock & replenishment or Supply requests." action={<Btn small onClick={() => go("requests")}>Go to supply requests</Btn>} /> : (
          <div className="tbl-wrap"><table className="tbl">
            <thead><tr><th>Shipment</th><th>Route</th><th>Load</th><th>Vehicle</th><th>Status and next step</th><th style={{ minWidth: 130 }}>Progress</th><th>Departs</th><th>Arrives</th><th>Risk</th></tr></thead>
            <tbody>{list.map((s: any) => {
              const Icon = MODE_ICON[s.mode];
              return (
                <tr key={s.id} className="clickable" onClick={() => setSel(s)}>
                  <td><strong>{s.id}</strong><br /><small className="muted">{s.request_id}</small></td>
                  <td>{s.source_name} <span className="muted">to</span> {s.dest_name}<br /><SectorChip sector={s.sector} /></td>
                  <td className="num">{fmt(s.qty)} <small className="muted">{s.unit} {CAT_SHORT[s.category].toLowerCase()}</small></td>
                  <td><span className="mode"><Icon size={14} />{s.asset_id}</span></td>
                  <td><Badge level={s.status} /><div className="small muted next-step">{nextStep(s, simTime)}</div></td>
                  <td><Meter value={s.progress * 100} tone={s.status === "HOLDING" ? "crit" : s.status === "DELAYED" ? "warn" : "ok"} /><small className="muted">{Math.round(s.progress * 100)}%</small></td>
                  <td className="small">{fmtTime(s.planned_departure)}</td>
                  <td className="small">{fmtTime(s.eta)}{s.delay_hours > 0 && <><br /><small className="t-crit">+{fmt(s.delay_hours, 1)} h delay</small></>}</td>
                  <td><Badge level={s.risk.level}>{s.risk.score}</Badge></td>
                </tr>);
            })}</tbody>
          </table></div>
        )}
      </Panel>

      <Panel flush title="Fleet" sub={`${busy} of ${usable} serviceable assets committed (${Math.round((100 * busy) / Math.max(1, usable))}%)`}>
        <div className="tbl-wrap"><table className="tbl">
          <thead><tr><th>Asset</th><th>Type</th><th className="right">Payload</th><th>Status</th><th>Location</th><th>Mission</th><th className="right">Km to service</th></tr></thead>
          <tbody>{assets.map((a: any) => (
            <tr key={a.id}><td><strong>{a.id}</strong></td><td>{a.type_name}</td><td className="num right">{fmt(a.capacity_kg / 1000, 2)} t</td>
              <td><Badge level={a.status} /></td><td>{a.status === "RETURNING" ? `Returning to ${a.home_name}` : a.location_name}</td>
              <td>{a.mission || "-"}</td><td className={`num right ${a.km_to_service < 600 ? "t-crit" : ""}`}>{fmt(a.km_to_service)}</td></tr>))}</tbody>
        </table></div>
      </Panel>

      {sel && (
        <Modal title={`Shipment ${sel.id}`} onClose={() => setSel(null)}>
          <div className="row-gap"><Badge level={sel.status} />{sel.delay_hours > 0 && <Badge level="HIGH">Delayed {fmt(sel.delay_hours, 1)} h</Badge>}<span className="muted small">{nextStep(sel, simTime)}</span></div>
          <Phases s={sel} />
          <KV items={[["From", sel.source_name], ["To", sel.dest_name], ["Load", `${fmt(sel.qty)} ${sel.unit} ${sel.category_name.toLowerCase()} (${fmt(sel.weight_kg / 1000, 2)} t)`],
            ["Vehicle", `${sel.asset_id} (${sel.mode.toLowerCase()})`], ["Vehicle ready after", `${fmt(sel.ready_hours ?? 0, 1)} h`],
            ["Loading starts", fmtTime(sel.loading_start)], ["Planned departure", fmtTime(sel.planned_departure)],
            ["Planned arrival", fmtTime(sel.planned_arrival)], ["Current ETA", fmtTime(sel.eta)], ["Created by", sel.created_by]]} />
          <h3 className="sub-h">Route risk at dispatch</h3>
          <RiskBreakdown risk={sel.risk} />
          <h3 className="sub-h">Tracking log</h3>
          <ul className="timeline">{sel.events.map((e: any, i: number) => <li key={i}><time>{fmtTime(e.time)}</time>{e.text}</li>)}</ul>
        </Modal>
      )}
    </div>
  );
}
