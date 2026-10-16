"""What-if scenario simulator. Runs the forecasting / inventory / transport
logic on an isolated copy of the plan and compares it with the baseline.
The live system state is never modified."""
from __future__ import annotations

import math
from typing import Dict, List

import numpy as np

from . import network as net
from .planning import Ctx
from .reference import ASSET_TYPES, CATEGORIES, NODES, ROUTES

PRESETS = [
    {"id": "winter_closure", "name": "Early winter closure of Zoji Pass",
     "description": "Snow closes Zoji and Razdan passes for the planning window; cold raises demand 15%.",
     "params": {"closed_routes": ["R4", "R8"], "demand_change_pct": 15, "horizon_days": 14}},
    {"id": "exercise_surge", "name": "Exercise surge +60% (northern sector)",
     "description": "Large exercise raises consumption by 60% at all northern posts.",
     "params": {"demand_change_pct": 60, "demand_nodes": ["FP-E", "FP-F", "FP-G", "FP-H"], "horizon_days": 14}},
    {"id": "fleet_grounded", "name": "Helicopters grounded + 6 vehicles down",
     "description": "Both helicopters unserviceable and six road vehicles off-road for repairs.",
     "params": {"unavailable_assets": ["HEL-01", "HEL-02", "TRK-01", "TRK-03", "TRK-05", "TRK-06", "LTV-01", "LTV-03"], "horizon_days": 14}},
    {"id": "cyclone_islands", "name": "Cyclone closes island sea lanes",
     "description": "A cyclonic storm suspends all sailings to the island hub and posts for the planning window.",
     "params": {"closed_routes": ["S1", "S2"], "demand_change_pct": 10, "demand_nodes": ["HUB-Q", "FP-Z", "FP-U"], "horizon_days": 14}},
    {"id": "desert_heat", "name": "Desert heatwave: water +50%",
     "description": "A heatwave in the western desert raises water and fuel use by 50% at every post.",
     "params": {"demand_change_pct": 50, "demand_nodes": ["HUB-P", "FP-V", "FP-W", "FP-X"], "demand_categories": ["WATER", "FUEL"],
                "horizon_days": 14}},
    {"id": "blizzard_combo", "name": "Blizzard + landslide (worst case)",
     "description": "Severe weather on all snow-prone passes, High Passes Highway closed, demand +20%.",
     "params": {"severe_weather": True, "closed_routes": ["R7"], "demand_change_pct": 20, "horizon_days": 14,
                "extra_lead_hours": 12}},
]


def _project(state, ctx: Ctx, p: dict) -> dict:
    H = int(p.get("horizon_days", 14))
    mult = 1 + float(p.get("demand_change_pct", 0)) / 100.0
    dnodes = set(p.get("demand_nodes") or [])
    dcats = set(p.get("demand_categories") or [])
    closed = set(p.get("closed_routes") or [])
    unavailable = set(p.get("unavailable_assets") or [])
    severe = bool(p.get("severe_weather"))
    extra = float(p.get("extra_lead_hours", 0))
    overrides = {"closed_routes": list(closed), "severe_weather": severe}
    day = net.day_index(state)
    now = net.sim_now(state)

    helis_ok = (not severe) and any(a["type"] in ("HELICOPTER", "AIRCRAFT") and a["id"] not in unavailable
                                    and a["status"] != "MAINTENANCE" for a in state["assets"].values())
    sec_num: Dict[str, float] = {}
    sec_den: Dict[str, float] = {}
    lines = {"safe": 0, "watch": 0, "risk": 0}
    rows, items = [], []
    total_demand_kg = required_kg = air_required_kg = unmet_kg = 0.0
    lead_posts = []
    readiness_num = readiness_den = 0.0
    for node, n in NODES.items():
        if n["type"] == "depot":
            continue
        path = net.shortest_path(state, n["parent"], node, day=day, overrides=overrides)
        if path is None:  # try any other source
            alts = [net.shortest_path(state, s, node, day=day, overrides=overrides)
                    for s, sn in NODES.items() if sn["type"] != "post" and s != node and sn["sector"] == n["sector"]]
            alts = [a for a in alts if a]
            path = min(alts, key=lambda a: a["hours"]) if alts else None
        if path is not None:
            lead_h, mode = path["hours"] + 6 + extra, "ROAD"
        elif helis_ok and n["helipad"]:
            lead_h, mode = 30 + extra, "AIR ONLY"
        else:
            lead_h, mode = math.inf, "ISOLATED"
        if n["type"] == "post" and lead_h < math.inf:
            lead_posts.append(lead_h)
        worst = None
        node_stockouts = 0
        min_cover = 99.0
        for cat, c in CATEGORIES.items():
            fc = ctx.fc[(node, cat)]["mean"][:H]
            m = mult if ((not dnodes or node in dnodes) and (not dcats or cat in dcats)) else 1.0
            if severe and cat in ("FUEL", "WINTER", "MEDICAL"):
                m *= 1.15
            demand = [v * m for v in fc]
            # scheduled arrivals
            arrivals: Dict[int, float] = {}
            for s in state["shipments"]:
                if s["dest"] != node or s["category"] != cat or s["status"] not in ("SCHEDULED", "LOADING", "IN_TRANSIT", "DELAYED", "HOLDING"):
                    continue
                blocked = any(r in closed for r in s["routes"]) or (unavailable and s["asset_id"] in unavailable and s["status"] == "SCHEDULED")
                if blocked:
                    continue
                eta = net.parse_time(s["eta"])
                d = max(0, int((eta - now).total_seconds() // 86400 + extra / 24))
                arrivals[d] = arrivals.get(d, 0) + s["qty"]
            stock = state["inventory"][node][cat]["on_hand"]
            st0 = ctx.status(node, cat)
            ss = st0["safety_stock"] * m
            so_day = None
            s_run = stock
            for d in range(H):
                s_run += arrivals.get(d, 0)
                if s_run - demand[d] < 0 and so_day is None:
                    so_day = d + (s_run / demand[d] if demand[d] else 0)
                s_run -= demand[d]
            cover = so_day if so_day is not None else float(H)
            min_cover = min(min_cover, cover)
            need = max(0.0, sum(demand) + ss - stock - sum(arrivals.values()))
            kg = need * c["kg_per_unit"]
            total_demand_kg += sum(demand) * c["kg_per_unit"]
            required_kg += kg
            if mode == "AIR ONLY":
                air_required_kg += kg
            lead_d = lead_h / 24.0
            unavoidable = so_day is not None and so_day < min(lead_d, H)
            if unavoidable:
                gap_days = min(H, lead_d) - so_day
                unmet = sum(demand[int(so_day):int(min(H, math.ceil(so_day + gap_days)))])
                unmet_kg += unmet * c["kg_per_unit"]
                node_stockouts += 1
                items.append({"node": node, "node_name": n["name"], "category": cat, "category_name": c["name"],
                              "stockout_day": round(so_day, 1), "lead_days": None if lead_h == math.inf else round(lead_d, 1),
                              "unmet_qty": round(unmet), "unit": c["unit"]})
            if n["type"] == "post":
                w = c["criticality"]
                readiness_den += w
                fragile = 0.7 if mode == "AIR ONLY" else 1.0  # air-only resupply is weather-fragile
                # full credit when stock outlasts lead time by a week; partial credit in between
                if cover >= min(H, lead_d + 7):
                    credit = w * fragile
                    lines["safe"] += 1
                elif cover > lead_d:
                    credit = w * fragile * (cover - lead_d) / max(0.1, min(H, lead_d + 7) - lead_d)
                    lines["watch"] += 1
                else:
                    credit = 0.0
                    lines["risk"] += 1
                readiness_num += credit
                sec = n["sector"]
                sec_num[sec] = sec_num.get(sec, 0.0) + credit
                sec_den[sec] = sec_den.get(sec, 0.0) + w
            if worst is None or cover < worst[1]:
                worst = (c["name"], cover)
        rows.append({"node": node, "node_name": n["name"], "type": n["type"], "mode": mode,
                     "lead_hours": None if lead_h == math.inf else round(lead_h, 1),
                     "worst_category": worst[0], "min_days_cover": round(min_cover, 1), "stockouts": node_stockouts})
    # transport capacity over the horizon
    cap_kg = 0.0
    for a in state["assets"].values():
        if a["id"] in unavailable or a["status"] == "MAINTENANCE":
            continue
        t = ASSET_TYPES[a["type"]]
        if t["mode"] in ("AIR", "DRONE") and severe:
            continue
        cycle = 48.0 if t["mode"] == "ROAD" else 120.0 if t["mode"] == "SEA" else 8.0
        if t["mode"] == "ROAD" and severe:
            cycle *= 1.5
        trips = max(0, math.floor(H * 24 / cycle))
        cap_kg += trips * t["capacity_kg"] * (0.55 if t["mode"] == "ROAD" else 0.6)  # share available for this task
    air_cap_kg = 0.0
    for a in state["assets"].values():
        if a["type"] in ("HELICOPTER", "AIRCRAFT") and a["id"] not in unavailable and not severe and a["status"] != "MAINTENANCE":
            cycle = 8.0 if a["type"] == "HELICOPTER" else 12.0
            air_cap_kg += math.floor(H * 24 / cycle) * ASSET_TYPES[a["type"]]["capacity_kg"] * 0.6
    air_short_kg = max(0.0, air_required_kg - air_cap_kg)
    util = required_kg / max(1.0, cap_kg) * 100
    transport_short_kg = max(0.0, required_kg - cap_kg)
    readiness = round(100 * readiness_num / max(1e-6, readiness_den), 1)
    if util > 100:
        readiness = round(readiness * 100 / util, 1)
    if air_short_kg > 0:
        readiness = round(readiness * max(0.5, 1 - air_short_kg / max(1.0, air_required_kg) * 0.4), 1)
    isolated = [r["node_name"] for r in rows if r["mode"] == "ISOLATED"]
    air_only = [r["node_name"] for r in rows if r["mode"] == "AIR ONLY"]
    return {
        "horizon_days": H,
        "readiness_index": readiness,
        "readiness_lines": {**lines, "total": sum(lines.values())},
        "sector_readiness": {k: round(100 * sec_num[k] / max(1e-6, sec_den[k]), 1) for k in sec_den},
        "total_demand_t": round(total_demand_kg / 1000, 1),
        "required_lift_t": round(required_kg / 1000, 1),
        "transport_capacity_t": round(cap_kg / 1000, 1),
        "transport_utilisation_pct": round(util, 1),
        "transport_shortfall_t": round(transport_short_kg / 1000, 1),
        "air_lift_required_t": round(air_required_kg / 1000, 1),
        "air_lift_capacity_t": round(air_cap_kg / 1000, 1),
        "air_lift_shortfall_t": round(air_short_kg / 1000, 1),
        "stockout_items": len(items),
        "unmet_demand_t": round(unmet_kg / 1000 + transport_short_kg / 1000 * 0.3 + air_short_kg / 1000, 1),
        "avg_post_lead_hours": round(float(np.mean(lead_posts)), 1) if lead_posts else None,
        "isolated_posts": isolated,
        "air_only_posts": air_only,
        "posts_at_risk": len({i["node"] for i in items if NODES[i["node"]]["type"] == "post"}),
        "stockouts": sorted(items, key=lambda i: i["stockout_day"]),
        "nodes": rows,
    }


def run(state, params: dict) -> dict:
    ctx = Ctx(state)
    base = _project(state, ctx, {"horizon_days": params.get("horizon_days", 14)})
    scen = _project(state, ctx, params)
    recs: List[str] = []
    if scen["isolated_posts"]:
        recs.append(f"Pre-position stock now at {', '.join(scen['isolated_posts'])} - they become unreachable by road and air.")
    if scen["air_only_posts"]:
        recs.append(f"Plan air sorties (helicopters and transport aircraft): {scen['air_lift_required_t']} t must be air-lifted to {', '.join(scen['air_only_posts'])}"
                    f" (air capacity {scen['air_lift_capacity_t']} t).")
        if scen["air_lift_shortfall_t"] > 0:
            recs.append(f"Air-lift shortfall of {scen['air_lift_shortfall_t']} t - request additional helicopters or push road convoys before closure.")
    if scen["transport_utilisation_pct"] > 90:
        trucks = math.ceil(scen["transport_shortfall_t"] * 1000 / (10000 * 0.55 * max(1, math.floor(scen['horizon_days'] * 24 / 48)))) if scen["transport_shortfall_t"] else 1
        recs.append(f"Transport is {scen['transport_utilisation_pct']}% committed - mobilise about {max(1, trucks)} extra heavy truck(s) or hire civil transport.")
    elif scen["transport_utilisation_pct"] > 45:
        recs.append(f"Transport load rises to {scen['transport_utilisation_pct']}% (baseline {base['transport_utilisation_pct']}%) - "
                    f"consolidate loads and give CRITICAL requests first call on vehicles.")
    extra_t = round(scen["total_demand_t"] - base["total_demand_t"], 1)
    if extra_t > 1:
        recs.append(f"Pre-stock an additional {extra_t} t of supplies at affected posts before the surge starts.")
    for s in scen["stockouts"][:4]:
        recs.append(f"Expedite {s['category_name'].lower()} to {s['node_name']} - stock-out on day {s['stockout_day']} before resupply can arrive.")
    if params.get("demand_change_pct", 0) >= 20:
        recs.append(f"Raise safety stock norms by {int(params['demand_change_pct'] / 2)}% for affected posts during the surge.")
    if params.get("severe_weather"):
        recs.append("Use the weather window: dispatch all snow-pass convoys within the next 24 h and stage winter kit forward.")
    if not recs:
        recs.append("Network absorbs this scenario with the current plan - no extra action required.")
    delta = {k: (round(scen[k] - base[k], 1) if isinstance(base[k], (int, float)) and isinstance(scen[k], (int, float)) else None)
             for k in ("readiness_index", "required_lift_t", "transport_utilisation_pct", "stockout_items",
                       "unmet_demand_t", "avg_post_lead_hours", "posts_at_risk", "total_demand_t")
             if base.get(k) is not None and scen.get(k) is not None}
    drop = base["readiness_index"] - scen["readiness_index"]
    new_so = scen["stockout_items"] - base["stockout_items"]
    util_up = scen["transport_utilisation_pct"] - base["transport_utilisation_pct"]
    if drop >= 25 or scen["isolated_posts"]:
        impact = "SEVERE"
    elif drop >= 8 or new_so >= 3 or scen["transport_utilisation_pct"] > 90 or scen["air_lift_shortfall_t"] > 0:
        impact = "SIGNIFICANT"
    elif drop >= 2 or new_so >= 1 or util_up >= 15 or scen["air_only_posts"]:
        impact = "MODERATE"
    else:
        impact = "MINIMAL"
    return {"params": params, "baseline": base, "scenario": scen, "delta": delta, "impact": impact,
            "recommendations": recs}
