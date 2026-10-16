import { Fragment, useState } from "react";
import { Zap, FilePlus2, Clock3, Download, ChevronDown, ChevronUp } from "lucide-react";
import { api, download } from "../api";
import { Badge, Btn, CAT_SHORT, Empty, ErrorBox, fmt, inSector, Loading, Meter, PageHead, Panel, SectorChip, SectorTabs, useAction, useApi, useApp } from "../ui";

function RecRow({ r }: { r: any }) {
  const { can } = useApp();
  const { busy, run } = useAction();
  const [qty, setQty] = useState<number>(r.recommended_qty);
  const [open, setOpen] = useState(false);
  return (
    <Fragment>
      <tr className={`rec-row sevrow-${r.urgency.toLowerCase()}`}>
        <td><Badge level={r.urgency} /></td>
        <td>
          <strong>{r.node_name}</strong> <SectorChip sector={r.sector} />
          <div className="muted small">{r.category_name}</div>
          <button className="link small" onClick={() => setOpen(!open)}>{open ? <ChevronUp size={13} /> : <ChevronDown size={13} />} Why</button>
        </td>
        <td className="num right">{fmt(r.on_hand)}<div className="muted small">{r.unit}</div></td>
        <td className="num right">{fmt(r.avg_daily_forecast, 1)}<div className="muted small">{r.unit}/day</div></td>
        <td className="num right">{r.days_of_supply}<div className="muted small">days</div></td>
        <td className="num right t-crit">{r.stockout_in_days ?? "-"}<div className="muted small">days</div></td>
        <td className="num right">{fmt(r.lead_time_hours / 24, 1)}<div className="muted small">days</div></td>
        <td className="right">
          {can("planner") ? <input className="qty-in num" type="number" min={1} value={qty} onChange={e => setQty(Number(e.target.value))} aria-label="Order quantity" />
            : <b className="num">{fmt(r.recommended_qty)}</b>}
          <div className="muted small">{r.unit} - {fmt((qty * r.weight_kg / Math.max(1, r.recommended_qty)) / 1000, 1)} t</div>
        </td>
        <td>{r.suggested_source_name || <span className="muted">Depot (rail)</span>}<div className="muted small">{r.suggested_source ? `${fmt(r.source_available)} spare` : ""}</div></td>
        <td>
          {can("planner") && <div className="row-actions">
            <Btn kind="primary" small icon={<Zap size={14} />} busy={busy === "d"}
              onClick={() => run("d", () => api(`/api/replenishment/${r.id}/approve`, { method: "POST", body: { auto_dispatch: true, qty } }),
                (res: any) => res.shipments.length ? `Approved and dispatched: ${res.option?.label}` : "Approved - no transport free yet, request created")}>Approve & dispatch</Btn>
            <Btn small icon={<FilePlus2 size={14} />} busy={busy === "a"} title="Create the request and plan transport yourself"
              onClick={() => run("a", () => api(`/api/replenishment/${r.id}/approve`, { method: "POST", body: { auto_dispatch: false, qty } }),
                (res: any) => `Request ${res.request.id} created - plan transport on Supply requests`)}>Request only</Btn>
            <Btn small kind="ghost" icon={<Clock3 size={14} />} busy={busy === "s"} title="Hide for 24 hours"
              onClick={() => run("s", () => api(`/api/replenishment/${r.id}/snooze`, { method: "POST", body: { note: "Deferred by planner" } }), "Deferred for 24 hours")}>Defer</Btn>
          </div>}
        </td>
      </tr>
      {open && <tr className="rec-why-row"><td /><td colSpan={9}>
        <div className="rec-why"><p>{r.reason}</p><p className="formula">{r.formula}</p>
          <p className="muted small">Safety stock {fmt(r.safety_stock)} = 1.65 x day-to-day demand variation x square root of resupply time + buffer days. Reorder point {fmt(r.reorder_point)}. Model confidence {Math.round(r.confidence * 100)}%.</p></div>
      </td></tr>}
    </Fragment>
  );
}

export default function Inventory() {
  const recs = useApi<any>("/api/replenishment");
  const inv = useApi<any>("/api/inventory");
  const { toast, sector, setSector } = useApp();
  const [type, setType] = useState("forward");
  const [status, setStatus] = useState("all");
  const [cat, setCat] = useState("all");
  const [showAll, setShowAll] = useState(false);
  if (inv.error) return <ErrorBox msg={inv.error} retry={inv.reload} />;
  const rows = (inv.data?.rows || []).filter((r: any) => inSector(sector, r)
    && (type === "all" || r.node_type === type || (type === "forward" && r.node_type !== "depot"))
    && (status === "all" || r.status === status) && (cat === "all" || r.category === cat));
  const order: Record<string, number> = { CRITICAL: 0, LOW: 1, OK: 2, EXCESS: 3 };
  rows.sort((a: any, b: any) => order[a.status] - order[b.status] || a.days_of_supply - b.days_of_supply);
  const recList = (recs.data?.recommendations || []).filter((r: any) => inSector(sector, r));

  return (
    <div className="page">
      <PageHead title="Stock & replenishment" lede="The forecast turns into orders here: how much to send, from where, and why. Red lines are handled by the AI Autopilot; amber lines wait for your approval."
        actions={<SectorTabs value={sector} onChange={setSector} />} />
      <Panel flush title={`Replenishment recommendations (${recList.length})`} sub="From forecast demand, safety stock and real route lead times. Change the quantity before approving if needed.">
        {!recs.data ? <Loading /> : recList.length === 0
          ? <Empty title="No replenishment needed here" detail="Every location in this view holds enough stock to cover its resupply time." />
          : <div className="tbl-wrap"><table className="tbl rec-table">
            <thead><tr><th>Urgency</th><th>Location and supply</th><th className="right">On hand</th><th className="right">Forecast use</th>
              <th className="right">Days held</th><th className="right">Runs out in</th><th className="right">Resupply time</th><th className="right">Order quantity</th><th>From</th><th>Action</th></tr></thead>
            <tbody>{recList.map((r: any) => <RecRow key={r.id} r={r} />)}</tbody>
          </table></div>}
      </Panel>

      <Panel flush title="Stock levels" sub={`${rows.length} lines`}
        actions={<>
          <select value={type} onChange={e => setType(e.target.value)} aria-label="Location type"><option value="forward">Posts and hubs</option><option value="all">All locations</option><option value="post">Forward posts</option><option value="hub">Hubs</option><option value="depot">Depots</option></select>
          <select value={cat} onChange={e => setCat(e.target.value)} aria-label="Supply type"><option value="all">All supplies</option>{Object.entries(CAT_SHORT).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
          <select value={status} onChange={e => setStatus(e.target.value)} aria-label="Status"><option value="all">Any status</option><option value="CRITICAL">Critical</option><option value="LOW">Low</option><option value="OK">OK</option></select>
          <Btn small icon={<Download size={14} />} onClick={() => download("/api/export/inventory.csv", "inventory.csv").catch(e => toast(e.message, "err"))}>CSV</Btn>
        </>}>
        {!inv.data ? <Loading /> : (
          <div className="tbl-wrap">
            <table className="tbl stock-table">
              <colgroup><col style={{ width: "17%" }} /><col style={{ width: "13%" }} /><col style={{ width: "11%" }} /><col style={{ width: "11%" }} />
                <col style={{ width: "8%" }} /><col style={{ width: "9%" }} /><col style={{ width: "9%" }} /><col style={{ width: "8%" }} /><col style={{ width: "7%" }} /><col style={{ width: "7%" }} /></colgroup>
              <thead><tr><th>Location</th><th>Supply</th><th className="right">On hand</th><th>Store filled</th><th className="right">Days held</th><th className="right">Safety stock</th><th className="right">Reorder point</th><th className="right">On the way</th><th className="right">Resupply</th><th>Status</th></tr></thead>
              <tbody>
                {(showAll ? rows : rows.slice(0, 30)).map((r: any) => (
                  <tr key={r.node + r.category}>
                    <td><strong>{r.node_name}</strong> <SectorChip sector={r.sector} /></td><td>{r.category_name}</td>
                    <td className="num right">{fmt(r.on_hand)} <small className="muted">{r.unit}</small></td>
                    <td><Meter value={r.fill_pct} tone={r.status === "CRITICAL" ? "crit" : r.status === "LOW" ? "warn" : "ok"} /><small className="muted">{fmt(r.fill_pct, 0)}%</small></td>
                    <td className="num right">{r.days_of_supply >= 99 ? "99+" : r.days_of_supply}</td>
                    <td className="num right">{fmt(r.safety_stock)}</td><td className="num right">{fmt(r.reorder_point)}</td>
                    <td className="num right">{r.incoming_qty ? fmt(r.incoming_qty) : "-"}</td>
                    <td className="num right">{fmt(r.lead_time_hours / 24, 1)} d</td>
                    <td><Badge level={r.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
            {rows.length > 30 && <div className="show-more"><Btn small kind="ghost" onClick={() => setShowAll(!showAll)}>{showAll ? "Show the 30 most urgent lines" : `Show all ${rows.length} lines`}</Btn></div>}
          </div>
        )}
      </Panel>
    </div>
  );
}
