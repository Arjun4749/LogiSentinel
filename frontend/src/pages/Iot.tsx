import { useState } from "react";
import { Line, LineChart, ResponsiveContainer, YAxis } from "recharts";
import { Battery, BatteryLow, Radio, ScanLine, Thermometer, Droplets, Fuel } from "lucide-react";
import { api } from "../api";
import { Badge, Btn, ErrorBox, Field, fmt, fmtTime, inSector, Loading, Modal, PageHead, Panel, SectorChip, SectorTabs, useAction, useApi, useApp } from "../ui";

const TYPES: Record<string, { label: string; icon: any }> = {
  RFID_GATE: { label: "RFID stock gates", icon: ScanLine }, FUEL_LEVEL: { label: "Fuel level sensors", icon: Fuel },
  COLD_CHAIN: { label: "Medical cold chain", icon: Thermometer }, STORE_HUMIDITY: { label: "Storehouse humidity", icon: Droplets },
};

function SendReading({ d, onClose }: { d: any; onClose: () => void }) {
  const { busy, run } = useAction();
  const [v, setV] = useState<number>(d.value ?? (d.min + d.max) / 2);
  return (
    <Modal title={`Send a test reading: ${d.id}`} onClose={onClose}>
      <p className="lede-sm">This simulates a message arriving from the sensor at {d.node_name}. {d.type === "FUEL_LEVEL" ? "A fuel level reading also corrects the stock record automatically." : ""}</p>
      <form className="form-grid one" onSubmit={async e => { e.preventDefault(); const r = await run("s", () => api("/api/iot/ingest", { method: "POST", body: { device_id: d.id, value: v } }), "Reading received"); if (r) onClose(); }}>
        <Field label={`Value (${d.unit})`} hint={`Normal range ${d.min} to ${d.max} ${d.unit}`}><input type="number" step="0.1" value={v} onChange={e => setV(Number(e.target.value))} /></Field>
        <div className="form-actions"><Btn kind="ghost" onClick={onClose}>Cancel</Btn><Btn type="submit" kind="primary" busy={busy === "s"}>Send reading</Btn></div>
      </form>
    </Modal>
  );
}

export default function Iot() {
  const { can, sector, setSector } = useApp();
  const { data, error, reload } = useApi<any>("/api/iot");
  const { busy, run } = useAction();
  const [type, setType] = useState("all");
  const [onlyIssues, setOnlyIssues] = useState(false);
  const [send, setSend] = useState<any>(null);
  if (error) return <ErrorBox msg={error} retry={reload} />;
  if (!data) return <Loading />;
  const rank: Record<string, number> = { BREACH: 0, OFFLINE: 1, WARN: 2, OK: 3 };
  const devs = data.devices.filter((d: any) => inSector(sector, d) && (type === "all" || d.type === type) && (!onlyIssues || d.health !== "OK"))
    .sort((a: any, b: any) => rank[a.health] - rank[b.health]);
  const n = (h: string) => data.devices.filter((d: any) => d.health === h).length;

  return (
    <div className="page">
      <PageHead title="IoT sensors" lede="RFID gates, fuel sensors, cold-chain loggers and humidity sensors keep the stock record honest and raise alerts on their own."
        actions={<SectorTabs value={sector} onChange={setSector} />} />
      <div className="sev-strip">
        <div className="sev-card static"><strong className="num">{data.devices.length}</strong><span>Devices</span></div>
        <div className="sev-card static"><strong className="num">{n("OK")}</strong><span>Normal</span></div>
        <div className={`sev-card static ${n("BREACH") ? "sev-critical" : ""}`}><strong className="num">{n("BREACH")}</strong><span>Out of range</span></div>
        <div className={`sev-card static ${n("OFFLINE") ? "sev-high" : ""}`}><strong className="num">{n("OFFLINE") + n("WARN")}</strong><span>Offline or warning</span></div>
        <div className="sev-card static"><strong className="num">{data.inventory_accuracy_pct}%</strong><span>Stock record accuracy</span></div>
      </div>
      <div className="filters">
        <div className="seg">
          <button className={type === "all" ? "on" : ""} onClick={() => setType("all")}>All</button>
          {Object.entries(TYPES).map(([k, t]) => <button key={k} className={type === k ? "on" : ""} onClick={() => setType(k)}>{t.label}</button>)}
        </div>
        <label className="toggle"><input type="checkbox" checked={onlyIssues} onChange={e => setOnlyIssues(e.target.checked)} /><span>Only show problems</span></label>
      </div>
      <div className="device-grid">
        {devs.map((d: any) => {
          const T = TYPES[d.type];
          const Icon = T.icon;
          return (
            <article key={d.id} className={`device health-${d.health.toLowerCase()}`}>
              <header><Icon size={18} /><div><strong>{d.node_name} <SectorChip sector={d.sector} /></strong><small>{d.label}</small></div><Badge level={d.health === "OK" ? "OK" : d.health} /></header>
              <div className="dev-value">
                <strong className="num">{d.value === null ? "--" : fmt(d.value, 1)}</strong><span>{d.unit}</span>
                <div className="spark">
                  {d.value !== null && <ResponsiveContainer width="100%" height="100%"><LineChart data={d.history}><YAxis hide domain={["dataMin - 1", "dataMax + 1"]} /><Line dataKey="value" dot={false} stroke={d.health === "BREACH" ? "var(--crit)" : "var(--primary)"} strokeWidth={1.6} isAnimationActive={false} /></LineChart></ResponsiveContainer>}
                </div>
              </div>
              {d.type === "RFID_GATE" && <p className="small">System record {fmt(d.system_qty)} kg rations, gate count {fmt(d.counted_qty)} kg.</p>}
              {d.issue && <p className="dev-issue">{d.issue}</p>}
              <footer>
                <span className="small muted">{d.battery < 20 ? <BatteryLow size={14} /> : <Battery size={14} />} {d.battery}% - seen {fmtTime(d.last_seen)}</span>
                <span className="dev-btns">
                  {d.type === "RFID_GATE" && can("admin") && Math.abs(d.variance_pct) > 0.5 && <Btn small busy={busy === d.id} onClick={() => run(d.id, () => api(`/api/iot/${d.id}/reconcile`, { method: "POST" }), (r: any) => `Stock reconciled: ${fmt(r.old)} -> ${fmt(r.new)} kg`)}>Reconcile stock</Btn>}
                  {can("planner") && <Btn small kind="ghost" icon={<Radio size={13} />} onClick={() => setSend(d)}>Test reading</Btn>}
                </span>
              </footer>
            </article>
          );
        })}
      </div>
      {send && <SendReading d={send} onClose={() => setSend(null)} />}
    </div>
  );
}
