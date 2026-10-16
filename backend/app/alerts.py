"""Alert & recommendation engine. Alerts are derived live from the system
state; acknowledgement / resolution status is persisted separately."""
from __future__ import annotations

from typing import List

from . import network as net
from .iot import all_readings
from .planning import Ctx, open_requests
from .reference import CATEGORIES, NODES, ROUTES

SEV_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


def generate(state, ctx: Ctx = None) -> List[dict]:
    ctx = ctx or Ctx(state)
    alerts = []

    import numpy as np
    ai_cfg = state.get("ai", {})
    autopilot = ai_cfg.get("enabled", True) and ai_cfg.get("critical_mode", "dispatch") == "dispatch"

    def add(aid, typ, sev, title, message, action, page, entity=None, data=None, source="SYSTEM", node=None):
        node = node or (entity if entity in NODES else None)
        alerts.append({"id": aid, "type": typ, "severity": sev, "title": title, "message": message,
                       "recommended_action": action, "page": page, "entity": entity, "data": data or {},
                       "source": source, "node": node, "sector": NODES[node]["sector"] if node else None})

    # 1. Stock-out risk
    for node, n in NODES.items():
        if n["type"] == "depot":
            continue
        for cat, c in CATEGORIES.items():
            st = ctx.status(node, cat)
            if st["status"] == "CRITICAL":
                reqs = open_requests(state, node, cat)
                act = (f"Request {reqs[0]['id']} is open - plan and dispatch it now" if reqs
                       else f"Approve replenishment recommendation REC-{node}-{cat}")
                if autopilot:
                    act = "AI Autopilot is raising a request and dispatching the best transport automatically"
                so = st["stockout_in_days"]
                add(f"STOCKOUT:{node}:{cat}", "STOCKOUT_RISK", "CRITICAL",
                    f"Stock-out risk: {n['name']} - {c['name']}",
                    f"{st['on_hand']:,} {c['unit']} on hand = {st['days_of_supply']} days at forecast "
                    f"{st['avg_daily_forecast']:,}/day. " + (f"Runs out in {so} days; " if so is not None else "")
                    + f"resupply lead time {st['lead_time_hours'] / 24:.1f} days.",
                    act, "ai" if autopilot else ("requests" if reqs else "inventory"), node, {"category": cat}, "AI")
            elif st["status"] == "LOW" and n["type"] == "post":
                so = st["stockout_in_days"]
                add(f"LOW:{node}:{cat}", "PREDICTED_SHORTAGE", "MEDIUM",
                    f"AI forecast: {n['name']} {c['name'].lower()} " + (f"runs out in {so} days" if so is not None else "below reorder point"),
                    f"Stock position {st['position']:,} {c['unit']} is below the reorder point {st['reorder_point']:,}. "
                    f"Forecast use {st['avg_daily_forecast']:,} {c['unit']}/day.",
                    "Approve the replenishment recommendation before this turns red", "inventory", node, {"category": cat}, "AI")
            # AI anomaly detection on yesterday's actual consumption
            hist = state["history"][node][cat]
            if len(hist) > 30:
                base = np.array(hist[-29:-1])
                mu, sd = float(base.mean()), float(base.std()) or 1e-6
                z = (hist[-1] - mu) / sd
                if abs(z) >= 2.6 and mu > 0:
                    hd = state["history_days"]
                    yday = state["history_end_day"] - 1
                    ops = state["ops"][node][min(len(state["ops"][node]) - 1, yday + hd)]
                    pct = (hist[-1] / mu - 1) * 100
                    add(f"ANOM:{node}:{cat}:{yday}", "DEMAND_ANOMALY", "LOW" if ops else "MEDIUM",
                        f"AI detected unusual {c['name'].lower()} use at {n['name']}",
                        f"Yesterday {hist[-1]:,.1f} {c['unit']} vs normal {mu:,.1f} ({pct:+.0f}%, {abs(z):.1f} standard deviations)."
                        + (" Explained by a planned exercise." if ops else " No planned exercise explains it."),
                        "Verify the consumption report; check for loss, pilferage or data-entry error" if not ops
                        else "No action - forecast already includes the exercise", "forecast", node, {"category": cat}, "AI")
    # 2. Shipments
    for s in state["shipments"]:
        if s["status"] == "HOLDING":
            add(f"HOLD:{s['id']}", "SHIPMENT_HOLD", "HIGH", f"Shipment {s['id']} holding",
                f"{s['qty']:,} {CATEGORIES[s['category']]['unit']} to {NODES[s['dest']]['name']} cannot move - route closed or not flyable. "
                f"Delay so far {s['delay_hours']:.0f} h.", "Consider air delivery for critical items or reroute", "shipments", s["id"], node=s["dest"])
        elif s["status"] == "DELAYED":
            add(f"DELAY:{s['id']}", "SHIPMENT_DELAY", "HIGH" if s["delay_hours"] >= 4 else "MEDIUM",
                f"Shipment {s['id']} delayed {s['delay_hours']:.1f} h",
                f"{CATEGORIES[s['category']]['name']} to {NODES[s['dest']]['name']}; new ETA {s['eta'][11:16]} UTC.",
                "Check destination stock covers the delay; notify receiving post", "shipments", s["id"], node=s["dest"])
    # 2b. AI delay prediction for moving shipments
    day_now = net.day_index(state)
    now = net.sim_now(state)
    seen_req = set()
    for s in state["shipments"]:
        if s["status"] not in ("SCHEDULED", "LOADING", "IN_TRANSIT", "DELAYED") or s["mode"] not in ("ROAD", "SEA"):
            continue
        if s["request_id"] in seen_req:
            continue
        eta_day = net.day_index(state, net.parse_time(s["eta"]))
        bad = None
        for d in range(day_now + 1, eta_day + 1):
            for rid in s["routes"]:
                cnd = net.all_conditions(state, d)[rid]
                if cnd["closed"] or cnd["weather"] in ("Blizzard", "Storm"):
                    bad = (d - day_now, ROUTES[rid]["name"], cnd["weather"])
                    break
            if bad:
                break
        if bad:
            seen_req.add(s["request_id"])
            group = [x["id"] for x in state["shipments"] if x["request_id"] == s["request_id"] and x["status"] != "DELIVERED"]
            add(f"PRED:{s['request_id']}", "PREDICTED_DELAY", "HIGH",
                f"AI predicts delay for {', '.join(group[:3])}{' +' + str(len(group) - 3) if len(group) > 3 else ''}",
                f"{bad[2]} forecast on {bad[1]} in {bad[0]} day(s), before this delivery to {NODES[s['dest']]['name']} arrives.",
                "Push the convoy through before the weather window closes, or switch critical items to air",
                "shipments", s["id"], source="AI", node=s["dest"])
    # 3. Disruptions
    for d in net.active_disruptions(state):
        affected = [s["id"] for s in state["shipments"] if s["status"] in ("SCHEDULED", "LOADING", "IN_TRANSIT", "DELAYED", "HOLDING")
                    and d.get("route_id") in s["routes"]]
        where = ROUTES[d["route_id"]]["name"] if d.get("route_id") else NODES[d["node_id"]]["name"]
        add(f"DIS:{d['id']}", "DISRUPTION", d["severity"], f"{d['type'].title()}: {d['title']}",
            f"{where}. {d['description']} Affects {len(affected)} active shipment(s).",
            "Re-route via alternative road or use helicopter for critical loads" if d.get("route_id") else "Verify stock manually by radio",
            "disruptions", d["id"], {"affected": affected}, node=d.get("node_id") or ROUTES[d["route_id"]]["b"] if d.get("route_id") or d.get("node_id") else None)
    # 4. Weather windows
    day = net.day_index(state)
    for node, n in NODES.items():
        if n["type"] != "post":
            continue
        for k in range(0, 3):
            w = net.weather_at(state, node, day + k)
            if w["cond"] in ("Blizzard", "Storm", "Dust storm"):
                detail = {"Blizzard": f"{w['snow_cm']} cm snow, wind {w['wind']} km/h. Road and air movement likely stopped.",
                          "Storm": f"cyclonic storm, wind {w['wind']} km/h, {w['precip_mm']} mm rain. Sea lanes and flying suspended.",
                          "Dust storm": f"dust storm, visibility {w['vis_km']} km, wind {w['wind']} km/h. Flying suspended, convoys slowed."}[w["cond"]]
                add(f"WX:{node}:{day + k}", "WEATHER_WINDOW", "HIGH", f"AI weather warning: window closing at {n['name']}",
                    f"{w['cond']} forecast in {k} day(s): {detail}",
                    "Push critical supplies before the weather; pre-position stock", "disruptions", node, source="AI")
                break
    # 5. IoT
    for r in all_readings(state):
        if r["health"] == "BREACH":
            sev = "HIGH" if r["type"] in ("COLD_CHAIN", "FUEL_LEVEL") else "MEDIUM"
            add(f"IOT:{r['id']}", "IOT_" + r["type"], sev, f"Sensor alert: {r['label']} at {r['node_name']}", r["issue"],
                "Reconcile stock with RFID count" if r["type"] == "RFID_GATE" else "Dispatch technician / check storage",
                "iot", r["id"], node=r["node"], source="SENSOR")
        elif r["health"] == "OFFLINE":
            add(f"IOT:{r['id']}", "DEVICE_OFFLINE", "MEDIUM", f"Sensor offline: {r['id']}", r["issue"],
                "Verify stock by radio; replace battery", "iot", r["id"], node=r["node"], source="SENSOR")
        elif r["health"] == "WARN" and r["battery"] < 20:
            add(f"BAT:{r['id']}", "DEVICE_BATTERY", "LOW", f"Low battery: {r['id']}", r["issue"], "Replace battery on next convoy", "iot", r["id"], node=r["node"], source="SENSOR")
    # 6. Fleet
    assets = list(state["assets"].values())
    busy = sum(1 for a in assets if a["status"] in ("ON_MISSION", "RETURNING"))
    usable = sum(1 for a in assets if a["status"] != "MAINTENANCE")
    util = busy / max(1, usable)
    if util > 0.75:
        add("FLEET:UTIL", "CAPACITY", "MEDIUM", f"Transport utilisation {util * 100:.0f}%",
            "Most transport assets are committed. New requests may wait.", "Request additional transport or consolidate loads", "shipments")
    for a in assets:
        if a["status"] == "MAINTENANCE":
            add(f"MAINT:{a['id']}", "ASSET_MAINTENANCE", "LOW", f"{a['id']} under maintenance",
                a.get("note", "Asset unavailable"), "Plan without this asset", "shipments", a["id"], node=a["home"])
        elif a["next_service_km"] - a["odometer_km"] < 600:
            add(f"SVC:{a['id']}", "SERVICE_DUE", "LOW", f"{a['id']} service due",
                f"{a['next_service_km'] - a['odometer_km']} km to next service.", "Schedule service after current mission", "shipments", a["id"], node=a["home"], source="AI")
    # merge persisted status
    st_map = state["alert_status"]
    for a in alerts:
        s = st_map.get(a["id"], {})
        a["status"] = s.get("status", "NEW")
        a["acknowledged_by"] = s.get("by")
        a["status_time"] = s.get("time")
        a["note"] = s.get("note")
    alerts.sort(key=lambda a: (a["status"] == "RESOLVED", SEV_ORDER[a["severity"]], a["status"] != "NEW"))
    return alerts
