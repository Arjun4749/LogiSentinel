import { useState } from "react";
import { Compass, RotateCcw, BookOpen } from "lucide-react";
import { api } from "../api";
import { Btn, Modal, PageHead, Panel, useAction, useApi, useApp } from "../ui";

const MAPPING: [string, string, string][] = [
  ["Act on shortages without delay", "AI Autopilot: when a unit turns red, it raises the request, plans transport and dispatches automatically, explaining each decision", "AI Command Centre"],
  ["Geographically dispersed areas", "Four sectors: northern mountains, eastern hills, western desert, islands. 26 locations, road and sea lanes, air links", "Network map"],
  ["Demand forecasting is hard because data sits in separate streams", "One data model joins consumption history, weather, exercises, stock, transport and sensors", "Dashboard"],
  ["Anticipate requirements", "Random Forest forecast per post and supply type, with 90% confidence range and plain-English reasons", "Demand forecast"],
  ["Inventory levels", "Safety stock, reorder point and order quantity from forecast + real route lead time; IoT reconciliation", "Stock & replenishment"],
  ["Competing demands from many formations", "Transparent 100-point priority score: urgency, criticality, feasibility, waiting time", "Supply requests"],
  ["Transportation capacity", "Capacity-aware vehicle assignment, split loads, road vs helicopter vs drone options with cost, ETA and risk", "Supply requests / Transport"],
  ["Terrain and weather conditions", "Route risk score from weather, road condition, altitude and past delays; 4-day pass outlook", "Weather & disruptions"],
  ["GIS-enabled logistics planning", "Interactive terrain map with route status, live convoys, disruptions and weather overlay", "Network map"],
  ["IoT-based inventory tracking", "RFID gates, fuel level, cold-chain and humidity sensors feeding stock records and alerts", "IoT sensors"],
  ["Optimise movement of critical supplies", "What-if simulator for closures, surges and fleet loss, with recommended actions", "What-if simulator"],
  ["Defence context: security and accountability", "Signed login tokens, three roles (Admin / Planner / Viewer), full audit trail", "Audit log"],
];

export default function System({ onStartTour }: { onStartTour: () => void }) {
  const { can, go } = useApp();
  const { busy, run } = useAction();
  const model = useApi<any>("/api/forecast/model");
  const [confirm, setConfirm] = useState(false);
  return (
    <div className="page">
      <PageHead title="System & help" lede="How LogiSentinel answers the problem statement, how it is built, and demo controls."
        actions={<Btn kind="primary" icon={<Compass size={16} />} onClick={onStartTour}>Start guided demo</Btn>} />
      <Panel flush title="Problem statement to feature map">
        <div className="tbl-wrap"><table className="tbl">
          <thead><tr><th>The problem says</th><th>LogiSentinel does</th><th>Where to see it</th></tr></thead>
          <tbody>{MAPPING.map(([a, b, c]) => <tr key={a}><td>{a}</td><td>{b}</td><td><strong>{c}</strong></td></tr>)}</tbody>
        </table></div>
      </Panel>
      <div className="grid-2">
        <Panel title="How it is built">
          <div className="arch">
            <div className="arch-layer"><b>Web app</b><span>React + TypeScript, Leaflet GIS map, Recharts</span></div>
            <div className="arch-arrow" aria-hidden="true" />
            <div className="arch-layer"><b>REST API</b><span>FastAPI (Python), JWT login, role checks, input validation, auto docs at /docs</span></div>
            <div className="arch-arrow" aria-hidden="true" />
            <div className="arch-layer engines"><b>Decision engines</b>
              <span className="eng">Forecasting (scikit-learn)</span><span className="eng">Replenishment</span><span className="eng">Prioritisation</span>
              <span className="eng">Transport planner (Dijkstra routing)</span><span className="eng">Risk scoring</span><span className="eng">Scenario simulator</span>
              <span className="eng">Alert engine</span><span className="eng">IoT ingestion</span><span className="eng">AI Autopilot</span><span className="eng">Mission clock</span></div>
            <div className="arch-arrow" aria-hidden="true" />
            <div className="arch-layer"><b>Data</b><span>Synthetic pan-India network: 5 depots, 7 hubs, 14 forward posts in 4 sectors, 24 road and sea routes, 41 vehicles, ships and aircraft, about 75 sensors, 90 days of history. Saved to backend/data/state.json</span></div>
          </div>
        </Panel>
        <Panel title="Roles">
          <table className="tbl compact"><tbody>
            <tr><td><span className="role-chip role-admin">admin</span></td><td>Everything a planner can do, plus report/clear disruptions, reconcile stock, reject requests, reset data</td></tr>
            <tr><td><span className="role-chip role-planner">planner</span></td><td>Approve replenishment, create and dispatch requests, run simulations, acknowledge alerts, move the clock</td></tr>
            <tr><td><span className="role-chip role-viewer">viewer</span></td><td>Read-only access to every screen</td></tr>
          </tbody></table>
          {model.data && <p className="muted small">Forecast model {model.data.version}, trained on {model.data.training_rows} rows in {model.data.train_seconds} s.</p>}
          <div className="btn-row">
            <a className="btn btn-default" href="/docs" target="_blank" rel="noreferrer"><BookOpen size={15} /><span>API documentation</span></a>
            {can("admin") && <Btn kind="danger" icon={<RotateCcw size={15} />} onClick={() => setConfirm(true)}>Reset demo data</Btn>}
          </div>
        </Panel>
      </div>
      {confirm && (
        <Modal title="Reset all demo data?" onClose={() => setConfirm(false)}>
          <p>This regenerates the synthetic network, history, stock, requests and shipments, sets the mission clock to now and retrains the model. Use it before a fresh presentation. The audit log is cleared.</p>
          <div className="form-actions"><Btn kind="ghost" onClick={() => setConfirm(false)}>Cancel</Btn>
            <Btn kind="danger" busy={busy === "r"} onClick={async () => { const r = await run("r", () => api("/api/admin/reset", { method: "POST" }), "Demo data reset. Ready for a fresh presentation."); if (r) { setConfirm(false); go("dashboard"); } }}>Reset data</Btn></div>
        </Modal>
      )}
    </div>
  );
}
