import { useEffect, useMemo, useState } from "react";
import { MapContainer, TileLayer, Polyline, CircleMarker, Marker, Tooltip, useMap, useMapEvents } from "react-leaflet";
import L from "leaflet";
import { AlertTriangle, Crosshair } from "lucide-react";
import { Badge, CAT_SHORT, ErrorBox, fmt, fmtTime, inSector, KV, Loading, Meter, PageHead, Panel, SectorChip, SectorTabs, useApi, useApp } from "../ui";

const STATUS_COLOR: Record<string, string> = { OPEN: "#2e8b57", RESTRICTED: "#e09a00", CLOSED: "#d03a2f" };
const NODE_COLOR: Record<string, string> = { OK: "#2e8b57", LOW: "#e09a00", CRITICAL: "#d03a2f" };
const LABEL_DIR: Record<string, "left" | "right" | "top" | "bottom"> = {
  "FP-E": "bottom", "FP-F": "top", "HUB-M": "left", "HUB-K": "left", "FP-G": "left", "FP-H": "top", "DEP-B": "left",
  "FP-R": "top", "HUB-N": "left", "DEP-C": "bottom", "FP-W": "bottom", "HUB-P": "left", "DEP-Y": "left", "FP-U": "top",
};
const SECTOR_VIEW: Record<string, { c: [number, number]; z: number }> = {
  ALL: { c: [22.5, 82.5], z: 5 }, NORTH: { c: [33.3, 76.6], z: 7 }, EAST: { c: [27.1, 90.9], z: 7 },
  WEST: { c: [26.6, 72.0], z: 7 }, ISLANDS: { c: [11.5, 87.0], z: 6 },
};

function shipIcon(s: any) {
  const glyph = s.mode === "AIR" ? "H" : s.mode === "DRONE" ? "D" : s.mode === "SEA" ? "S" : "R";
  const cls = s.status === "HOLDING" ? "hold" : s.status === "DELAYED" ? "late" : ["SCHEDULED", "LOADING"].includes(s.status) ? "sched" : "";
  return L.divIcon({ className: "", html: `<div class="ship-pin ${cls} m-${s.mode.toLowerCase()}">${glyph}</div>`, iconSize: [26, 26], iconAnchor: [13, 13] });
}
const disIcon = L.divIcon({ className: "", html: `<div class="dis-pin">!</div>`, iconSize: [26, 26], iconAnchor: [13, 13] });
const pulseIcon = (sev: string) => L.divIcon({ className: "", html: `<div class="alert-pulse ${sev}"></div>`, iconSize: [54, 54], iconAnchor: [27, 27] });
function wxIcon(w: any) {
  return L.divIcon({ className: "", html: `<div class="wx-pin wx-${w.cond.replace(" ", "")}">${Math.round(w.temp)}&deg;C ${w.cond}</div>`, iconSize: [110, 20], iconAnchor: [-10, 30] });
}

function TileWatch({ onFail }: { onFail: () => void }) {
  const map = useMap();
  useEffect(() => {
    let fails = 0;
    const h = () => { fails++; if (fails > 6) onFail(); };
    map.on("tileerror", h);
    return () => { map.off("tileerror", h); };
  }, [map]);
  return null;
}
function ZoomWatch({ onZoom }: { onZoom: (z: number) => void }) {
  const map = useMapEvents({ zoomend: () => onZoom(map.getZoom()) });
  useEffect(() => { onZoom(map.getZoom()); }, []);
  return null;
}
const SECTOR_NAME: Record<string, string> = { NORTH: "Northern sector", EAST: "Eastern sector", WEST: "Western sector", ISLANDS: "Island sector" };
const SECTOR_LABEL_POS: Record<string, [number, number]> = { NORTH: [33.6, 84.6], EAST: [24.8, 90.8], WEST: [29.7, 69.6], ISLANDS: [14.6, 88.2] };
const sectorIcon = (name: string, red: number) => L.divIcon({ className: "", iconSize: [170, 30], iconAnchor: [85, 15],
  html: `<div class="sector-pin">${name}${red ? `<b>${red} on alert</b>` : ""}</div>` });

function FlyTo({ target }: { target: { c: [number, number]; z: number; key: string } }) {
  const map = useMap();
  useEffect(() => { map.flyTo(target.c, target.z, { duration: 0.8 }); }, [target.key]);
  return null;
}

export default function MapPage() {
  const { theme, go, sector, setSector } = useApp();
  const { data, error, reload } = useApi<any>("/api/map");
  const [sel, setSel] = useState<{ kind: string; id: string } | null>(null);
  const [layers, setLayers] = useState({ routes: true, shipments: true, disruptions: true, alerts: true, weather: false, labels: true });
  const [tilesFailed, setTilesFailed] = useState(false);
  const [zoom, setZoom] = useState(SECTOR_VIEW[sector].z);
  const [focus, setFocus] = useState<{ c: [number, number]; z: number; key: string }>(() => ({ ...SECTOR_VIEW[sector], key: sector }));
  useEffect(() => { setFocus({ ...SECTOR_VIEW[sector], key: sector + Date.now() }); }, [sector]);

  const alerted = useMemo(() => {
    if (!data) return [];
    const sevRank = (n: any) => n.status === "CRITICAL" || n.alerts.CRITICAL ? 0 : n.status === "LOW" || n.alerts.HIGH ? 1 : 2;
    return data.nodes.filter((n: any) => n.status !== "OK" || n.alerts.CRITICAL || n.alerts.HIGH)
      .filter((n: any) => inSector(sector, n)).sort((a: any, b: any) => sevRank(a) - sevRank(b));
  }, [data, sector]);

  if (error) return <ErrorBox msg={error} retry={reload} />;
  if (!data) return <Loading label="Loading supply network" />;

  const node = sel?.kind === "node" ? data.nodes.find((n: any) => n.id === sel.id) : null;
  const route = sel?.kind === "route" ? data.routes.find((r: any) => r.id === sel.id) : null;
  const ship = sel?.kind === "ship" ? data.shipments.find((s: any) => s.id === sel.id) : null;
  const dis = sel?.kind === "dis" ? data.disruptions.find((d: any) => d.id === sel.id) : null;
  const nodeName = (id: string) => data.nodes.find((n: any) => n.id === id)?.name || id;
  const focusNode = (n: any) => { setSel({ kind: "node", id: n.id }); setFocus({ c: [n.lat, n.lon], z: 9, key: n.id + Date.now() }); };

  // label-free terrain tiles (no borders or place names drawn)
  const tiles = theme === "night"
    ? { url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", attr: "Tiles &copy; Esri", max: 17 }
    : { url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Shaded_Relief/MapServer/tile/{z}/{y}/{x}", attr: "Tiles &copy; Esri", max: 13 };
  const critCount = alerted.filter((n: any) => n.status === "CRITICAL").length;

  return (
    <div className="page">
      <PageHead title="Supply network map" lede="All four sectors on real terrain. Pulsing rings mark units on alert. Routes show live condition; icons show convoys (R), ships (S), helicopters and aircraft (H) and drones (D)."
        actions={<SectorTabs value={sector} onChange={setSector} />} />
      <div className="map-layout">
        <div className={`map-wrap ${tilesFailed ? "no-tiles" : ""}`}>
          <MapContainer center={SECTOR_VIEW[sector].c} zoom={SECTOR_VIEW[sector].z} minZoom={4} maxZoom={12} scrollWheelZoom style={{ height: "100%", width: "100%" }}>
            {!tilesFailed && <TileLayer key={theme} url={tiles.url} attribution={tiles.attr} maxNativeZoom={tiles.max} maxZoom={17} className={theme === "night" ? "tiles-night" : ""} />}
            <TileWatch onFail={() => setTilesFailed(true)} />
            <FlyTo target={focus} />
            <ZoomWatch onZoom={setZoom} />
            {zoom < 6 && Object.entries(SECTOR_LABEL_POS).map(([sg, pos]) => (
              <Marker key={"sec" + sg} position={pos} icon={sectorIcon(SECTOR_NAME[sg], alerted.filter((n: any) => n.sector === sg).length)}
                eventHandlers={{ click: () => setSector(sg as any) }} />
            ))}
            {layers.routes && data.routes.map((r: any) => (
              <Polyline key={r.id} positions={r.coords} eventHandlers={{ click: () => setSel({ kind: "route", id: r.id }) }}
                pathOptions={{ color: r.mode === "SEA" && r.status === "OPEN" ? "#2b7bb9" : STATUS_COLOR[r.status], weight: sel?.id === r.id ? 8 : r.mode === "SEA" ? 4 : 5,
                  opacity: 0.9, dashArray: r.status === "CLOSED" ? "8 8" : r.mode === "SEA" ? "2 9" : undefined, lineCap: "round" }}>
                <Tooltip sticky>{r.name} ({r.mode === "SEA" ? "sea lane" : "road"}): {r.status.toLowerCase()} - risk {r.risk}/100</Tooltip>
              </Polyline>
            ))}
            {layers.shipments && data.shipments.filter((s: any) => ["AIR", "DRONE"].includes(s.mode)).map((s: any) => (
              <Polyline key={"p" + s.id} positions={s.coords} pathOptions={{ color: "#5a4fcf", weight: 2, dashArray: "4 6" }} />
            ))}
            {layers.alerts && alerted.map((n: any) => (
              <Marker key={"al" + n.id} position={[n.lat, n.lon]} icon={pulseIcon(n.status === "CRITICAL" || n.alerts.CRITICAL ? "crit" : "warn")} interactive={false} />
            ))}
            {data.nodes.map((n: any) => (
              <CircleMarker key={n.id} center={[n.lat, n.lon]} radius={n.type === "depot" ? 12 : n.type === "hub" ? 10 : 8}
                eventHandlers={{ click: () => setSel({ kind: "node", id: n.id }) }}
                pathOptions={{ color: "#17262e", weight: 2, fillColor: NODE_COLOR[n.status], fillOpacity: 1 }}>
                {layers.labels && zoom >= 6 && <Tooltip permanent direction={LABEL_DIR[n.id] || "right"} offset={LABEL_DIR[n.id] === "left" ? [-10, 0] : LABEL_DIR[n.id] === "bottom" ? [0, 10] : LABEL_DIR[n.id] === "top" ? [0, -10] : [10, 0]} className={`node-label nl-${n.status.toLowerCase()}`}>{n.name}</Tooltip>}
              </CircleMarker>
            ))}
            {layers.weather && data.nodes.map((n: any) => <Marker key={"w" + n.id} position={[n.lat, n.lon]} icon={wxIcon(n.weather)} interactive={false} />)}
            {layers.shipments && data.shipments.map((s: any) => (
              <Marker key={s.id} position={s.position} icon={shipIcon(s)} eventHandlers={{ click: () => setSel({ kind: "ship", id: s.id }) }}>
                <Tooltip>{s.id}: {fmt(s.qty)} {CAT_SHORT[s.category]} to {nodeName(s.dest)} ({s.status.toLowerCase().replace("_", " ")})</Tooltip>
              </Marker>
            ))}
            {layers.disruptions && data.disruptions.map((d: any) => (
              <Marker key={d.id} position={d.position} icon={disIcon} eventHandlers={{ click: () => setSel({ kind: "dis", id: d.id }) }}>
                <Tooltip>{d.title}</Tooltip>
              </Marker>
            ))}
          </MapContainer>
          {tilesFailed && <div className="map-note">Background map needs internet. Units, routes and convoys still work offline.</div>}
          <div className="map-legend">
            <span><i style={{ background: STATUS_COLOR.OPEN }} />Road open</span><span><i style={{ background: STATUS_COLOR.RESTRICTED }} />Restricted</span>
            <span><i style={{ background: STATUS_COLOR.CLOSED }} />Closed</span><span><i className="sea-key" />Sea lane</span>
            <span><b className="dot-l pulse-key" />Unit on alert</span>
          </div>
        </div>

        <div className="map-side">
          <Panel title={<span className="row-gap" style={{ margin: 0 }}><AlertTriangle size={17} /> Units on alert ({alerted.length})</span>}
            sub={critCount ? `${critCount} red - the AI Autopilot is acting on them` : "No red units right now"}>
            {alerted.length === 0 ? <p className="muted">All units in this view are healthy.</p> : (
              <ul className="alert-units">
                {alerted.map((n: any) => (
                  <li key={n.id}>
                    <button onClick={() => focusNode(n)} className={`au au-${n.status.toLowerCase()}`}>
                      <span className="au-dot" />
                      <span className="au-main"><strong>{n.name}</strong>
                        <small>{n.critical_items.length ? `Red: ${n.critical_items.join(", ")}` : n.low_items.length ? `Amber: ${n.low_items.join(", ")}` : `${(n.alerts.CRITICAL || 0) + (n.alerts.HIGH || 0)} high alert(s)`}</small></span>
                      <SectorChip sector={n.sector} /><Crosshair size={14} />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          {node && (
            <Panel title={node.name} sub={`${node.type === "post" ? "Forward post" : node.type === "hub" ? "Supply hub" : "Base depot"} - ${fmt(node.alt)} m - ${node.terrain}`}>
              <div className="row-gap"><SectorChip sector={node.sector} /><Badge level={node.status} />{Object.entries(node.alerts).map(([sev, n]: any) => <Badge key={sev} level={sev}>{n} {sev.toLowerCase()}</Badge>)}</div>
              <KV items={[["Personnel", fmt(node.personnel)], ["Weather today", `${node.weather.cond}, ${node.weather.temp} °C, wind ${node.weather.wind} km/h`],
                ["Vehicles available here", node.assets_here.join(", ") || "None"]]} />
              <div className="inv-list">
                {node.inventory.map((i: any) => (
                  <div key={i.category} className="inv-line">
                    <span>{CAT_SHORT[i.category]}</span>
                    <Meter value={Math.min(i.days, 30)} max={30} tone={i.status === "CRITICAL" ? "crit" : i.status === "LOW" ? "warn" : "ok"} />
                    <b className="num">{i.days >= 99 ? "99+" : fmt(i.days, 1)} days</b>
                  </div>
                ))}
              </div>
              <button className="link" onClick={() => go("inventory")}>Open stock & replenishment</button>
            </Panel>
          )}
          {route && (
            <Panel title={route.name} sub={`${nodeName(route.a)} to ${nodeName(route.b)} - ${route.mode === "SEA" ? "sea lane" : "road"}`}>
              <div className="row-gap"><Badge level={route.status} /><Badge level={route.risk_level}>Risk {route.risk}/100</Badge></div>
              <KV items={[["Distance", `${fmt(route.km)} km`], ["Highest point", route.mode === "SEA" ? "Sea level" : `${fmt(route.max_alt)} m`],
                ["Travel time now", `${route.hours} h (normal x${route.time_mult})`], ["Snow-prone pass", route.snow_prone ? "Yes" : "No"]]} />
              {route.factors.length > 0 ? <ul className="factor-list">{route.factors.map((f: string, i: number) => <li key={i}>{f}</li>)}</ul> : <p className="muted">No weather or road issues today.</p>}
            </Panel>
          )}
          {ship && (
            <Panel title={`Shipment ${ship.id}`} sub={`${nodeName(ship.source)} to ${nodeName(ship.dest)}`}>
              <div className="row-gap"><Badge level={ship.status} />{ship.delay_hours > 0 && <Badge level="HIGH">+{fmt(ship.delay_hours, 1)} h delay</Badge>}</div>
              <KV items={[["Load", `${fmt(ship.qty)} ${CAT_SHORT[ship.category]}`], ["Vehicle", `${ship.asset_id} (${ship.mode.toLowerCase()})`], ["Arrives", fmtTime(ship.eta)]]} />
              <Meter value={ship.progress * 100} />
              <p className="muted">{Math.round(ship.progress * 100)}% of the journey complete</p>
              <button className="link" onClick={() => go("shipments")}>Open shipment tracking</button>
            </Panel>
          )}
          {dis && (
            <Panel title={dis.title} sub={dis.type.toLowerCase().replace("_", " ")}>
              <Badge level={dis.severity} />
              <p>{dis.description}</p>
              <KV items={[["Expected to clear", fmtTime(dis.expected_end)], ["Closes route", dis.closes_route ? "Yes" : "No"], ["Source", dis.source]]} />
              <button className="link" onClick={() => go("disruptions")}>Open weather & disruptions</button>
            </Panel>
          )}

          <Panel title="Layers">
            <div className="toggles two">
              {(Object.keys(layers) as (keyof typeof layers)[]).map(k => (
                <label key={k} className="toggle"><input type="checkbox" checked={layers[k]} onChange={e => setLayers({ ...layers, [k]: e.target.checked })} />
                  <span>{{ routes: "Routes", shipments: "Shipments", disruptions: "Disruptions", alerts: "Alert rings", weather: "Weather", labels: "Names" }[k]}</span></label>
              ))}
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}
