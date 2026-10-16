import { useState } from "react";
import { Download, Lock } from "lucide-react";
import { download } from "../api";
import { Btn, Empty, ErrorBox, fmtTime, Loading, PageHead, Panel, useApi, useApp } from "../ui";

const ACTION_TEXT: Record<string, string> = {
  LOGIN: "Signed in", ADVANCE_CLOCK: "Moved mission clock", CREATE_REQUEST: "Created request", APPROVE_REQUEST: "Approved request",
  REJECT_REQUEST: "Rejected request", DISPATCH: "Dispatched shipment", APPROVE_REPLENISHMENT: "Approved replenishment",
  SNOOZE_REPLENISHMENT: "Deferred replenishment", ACK_ALERT: "Acknowledged alert", RESOLVE_ALERT: "Resolved alert",
  IOT_INGEST: "Sensor reading", RECONCILE_INVENTORY: "Reconciled stock", CREATE_DISRUPTION: "Reported disruption",
  RESOLVE_DISRUPTION: "Cleared disruption", RETRAIN_MODEL: "Retrained model", RESET_DEMO_DATA: "Reset demo data", RUN_SCENARIO: "Ran simulation",
};

export default function Audit() {
  const { can, toast } = useApp();
  const { data, error, reload } = useApi<any>(can("planner") ? "/api/audit" : null);
  const [q, setQ] = useState("");
  if (!can("planner")) return <div className="page"><PageHead title="Audit log" lede="Every decision, who made it and when." /><Panel><Empty title="Planner or Admin role needed" detail="Viewers cannot open the audit trail. Sign in as planner or admin." /></Panel></div>;
  if (error) return <ErrorBox msg={error} retry={reload} />;
  if (!data) return <Loading />;
  const rows = data.audit.filter((a: any) => !q || JSON.stringify(a).toLowerCase().includes(q.toLowerCase()));
  return (
    <div className="page">
      <PageHead title="Audit log" lede="Every approval, dispatch, alert action and data change is recorded with user, role, real time and mission time."
        actions={<Btn icon={<Download size={15} />} onClick={() => download("/api/export/audit.csv", "audit.csv").catch(e => toast(e.message, "err"))}>Export CSV</Btn>} />
      <Panel flush title={<span className="row-gap"><Lock size={16} /> {rows.length} records</span>} actions={<input className="search" placeholder="Search user, action, ID..." value={q} onChange={e => setQ(e.target.value)} />}>
        {rows.length === 0 ? <Empty title="No records yet" detail="Actions you take appear here immediately." /> : (
          <div className="tbl-wrap"><table className="tbl">
            <thead><tr><th>Record</th><th>Time (your clock)</th><th>Mission time</th><th>User</th><th>Role</th><th>Action</th><th>Item</th><th>Details</th></tr></thead>
            <tbody>{rows.map((a: any) => (
              <tr key={a.id}><td className="muted small">{a.id}</td><td>{fmtTime(a.time)}</td><td>{fmtTime(a.sim_time)}</td><td>{a.name || a.user}</td>
                <td><span className={`role-chip role-${a.role}`}>{a.role}</span></td><td><strong>{ACTION_TEXT[a.action] || a.action}</strong></td>
                <td className="small">{a.entity}</td><td className="small">{a.details}</td></tr>))}</tbody>
          </table></div>
        )}
      </Panel>
    </div>
  );
}
