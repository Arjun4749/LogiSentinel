import { Copy, Download, Printer, RefreshCw } from "lucide-react";
import { download } from "../api";
import { Btn, ErrorBox, fmt, KV, Loading, PageHead, Panel, useApi, useApp } from "../ui";
import { api } from "../api";
import { useEffect, useState } from "react";

const STATUS_TEXT: Record<string, string> = { NEW: "New", APPROVED: "Approved", DISPATCHED: "Dispatched", DELIVERED: "Delivered", REJECTED: "Rejected",
  SCHEDULED: "Scheduled", IN_TRANSIT: "In transit", DELAYED: "Delayed", HOLDING: "Holding" };

export default function Reports() {
  const { toast, version } = useApp();
  const sum = useApi<any>("/api/reports/summary");
  const [text, setText] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const load = () => api<string>("/api/reports/sitrep", { text: true }).then(setText).catch(e => setErr(e.message));
  useEffect(() => { load(); }, [version]);

  const saveTxt = () => {
    if (!text) return;
    const blob = new Blob([text], { type: "text/plain" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = "SITREP.txt"; a.click();
  };
  const k = sum.data?.kpis;

  return (
    <div className="page">
      <PageHead title="Reports & SITREP" lede="A situation report written automatically from live data, plus data exports for further analysis." />
      <div className="grid-2-1">
        <Panel title="Situation report (SITREP)" sub="Regenerated every time the data changes"
          actions={<>
            <Btn small icon={<RefreshCw size={14} />} onClick={load}>Refresh</Btn>
            <Btn small icon={<Copy size={14} />} onClick={() => { navigator.clipboard?.writeText(text || ""); toast("SITREP copied", "ok"); }}>Copy</Btn>
            <Btn small icon={<Download size={14} />} onClick={saveTxt}>Download</Btn>
            <Btn small icon={<Printer size={14} />} onClick={() => window.print()}>Print</Btn>
          </>}>
          {err ? <ErrorBox msg={err} /> : !text ? <Loading /> : <pre className="sitrep">{text}</pre>}
        </Panel>
        <div className="stack">
          <Panel title="Performance">
            {!k ? <Loading /> : <KV items={[["Supply readiness", `${k.readiness_index}/100`], ["Forecast accuracy", `${k.forecast_accuracy_pct}%`],
              ["On-time delivery", `${k.on_time_delivery_pct}%`], ["Transport in use", `${k.transport_utilisation_pct}%`],
              ["Stock record accuracy", `${k.inventory_accuracy_pct}%`], ["Shipments delivered (session)", k.shipments_delivered],
              ["Stock-outs prevented by early action", k.stockouts_prevented]]} />}
          </Panel>
          <Panel title="Requests and shipments">
            {sum.data && <div className="two-col-kv">
              <KV items={Object.entries(sum.data.requests_by_status).map(([s, n]) => [`Requests: ${STATUS_TEXT[s] || s}`, fmt(n as number)])} />
              <KV items={Object.entries(sum.data.shipments_by_status).map(([s, n]) => [`Shipments: ${STATUS_TEXT[s] || s}`, fmt(n as number)])} />
            </div>}
          </Panel>
          <Panel title="Export data (CSV)" sub="Opens in Excel or Google Sheets">
            <div className="btn-col">
              {[["inventory", "Stock levels"], ["shipments", "Shipments"], ["requests", "Supply requests"], ["audit", "Audit log"]].map(([k2, l]) => (
                <Btn key={k2} icon={<Download size={15} />} onClick={() => download(`/api/export/${k2}.csv`, `${k2}.csv`).catch(e => toast(e.message, "err"))}>{l}</Btn>
              ))}
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}
