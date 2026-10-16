"""Dashboard aggregation, KPIs and the auto-generated Situation Report (SITREP)."""
from __future__ import annotations

from datetime import timedelta

import numpy as np

from . import network as net
from .alerts import generate as gen_alerts
from .forecast import ENGINE
from .iot import inventory_accuracy
from .planning import Ctx, prioritise, recommendations
from .reference import CATEGORIES, NODES, ROUTES
from .scenario import _project


def kpis(state, ctx: Ctx, alerts=None) -> dict:
    alerts = alerts if alerts is not None else gen_alerts(state, ctx)
    active = [a for a in alerts if a["status"] != "RESOLVED"]
    log = state["delivery_log"][-60:]
    on_time = 100.0 * sum(1 for d in log if d["on_time"]) / max(1, len(log))
    assets = list(state["assets"].values())
    busy = sum(1 for a in assets if a["status"] in ("ON_MISSION", "RETURNING"))
    usable = sum(1 for a in assets if a["status"] != "MAINTENANCE")
    posts_at_risk = set()
    for node, n in NODES.items():
        if n["type"] == "post":
            for cat in CATEGORIES:
                if ctx.status(node, cat)["status"] == "CRITICAL":
                    posts_at_risk.add(node)
    proj = _project(state, ctx, {"horizon_days": 14})
    ships = state["shipments"]
    ai = state.get("ai", {})
    return {
        "readiness_index": proj["readiness_index"],
        "readiness_lines": proj["readiness_lines"],
        "sector_readiness": proj["sector_readiness"],
        "ai_enabled": ai.get("enabled", True),
        "ai_handled": ai.get("stats", {}).get("red_alerts_handled", 0),
        "ai_requests": ai.get("stats", {}).get("auto_requests", 0),
        "ai_avg_response_s": ai.get("stats", {}).get("avg_response_s", 0),
        "forecast_accuracy_pct": ENGINE.meta.get("accuracy_pct"),
        "forecast_improvement_pct": ENGINE.meta.get("improvement_vs_naive_pct"),
        "on_time_delivery_pct": round(on_time, 1),
        "transport_utilisation_pct": round(100 * busy / max(1, usable), 1),
        "posts_at_risk": len(posts_at_risk),
        "posts_total": sum(1 for n in NODES.values() if n["type"] == "post"),
        "alerts_critical": sum(1 for a in active if a["severity"] == "CRITICAL"),
        "alerts_high": sum(1 for a in active if a["severity"] == "HIGH"),
        "alerts_total": len(active),
        "alerts_new": sum(1 for a in active if a["status"] == "NEW"),
        "pending_requests": sum(1 for r in state["requests"] if r["status"] in ("NEW", "APPROVED")),
        "active_shipments": sum(1 for s in ships if s["status"] in ("SCHEDULED", "LOADING", "IN_TRANSIT", "DELAYED", "HOLDING")),
        "delayed_shipments": sum(1 for s in ships if s["status"] in ("DELAYED", "HOLDING")),
        "active_disruptions": len(net.active_disruptions(state)),
        "inventory_accuracy_pct": inventory_accuracy(state),
        "stockouts_prevented": state["stats"].get("stockouts_prevented", 0),
        "shipments_delivered": state["stats"].get("shipments_delivered", 0),
    }


def dashboard(state) -> dict:
    ctx = Ctx(state)
    alerts = gen_alerts(state, ctx)
    k = kpis(state, ctx, alerts)
    matrix = []
    for node, n in NODES.items():
        if n["type"] == "depot":
            continue
        row = {"node": node, "name": n["name"], "type": n["type"], "sector": n["sector"], "cells": {}}
        for cat in CATEGORIES:
            st = ctx.status(node, cat)
            row["cells"][cat] = {"status": st["status"], "days": st["days_of_supply"],
                                 "cover": st["days_cover_incl_incoming"], "incoming": st["incoming_qty"],
                                 "lead": round(st["lead_time_hours"] / 24, 1), "on_hand": st["on_hand"], "unit": st["unit"]}
        matrix.append(row)
    # aggregated tonnage: last 30 days actual + 14 days forecast
    end = state["history_end_day"]
    day0 = net.parse_time(state["day0"])
    chart = []
    for i in range(30, 0, -1):
        tot = sum(state["history"][n][c][-i] * CATEGORIES[c]["kg_per_unit"] for n in NODES for c in CATEGORIES)
        chart.append({"date": (day0 + timedelta(days=end - i)).date().isoformat(), "actual": round(tot / 1000, 2)})
    for h in range(14):
        m = lo = up = 0.0
        for (n, c), f in ctx.fc.items():
            kg = CATEGORIES[c]["kg_per_unit"]
            m += f["mean"][h] * kg
            lo += f["lower"][h] * kg
            up += f["upper"][h] * kg
        chart.append({"date": (day0 + timedelta(days=end + h)).date().isoformat(), "forecast": round(m / 1000, 2),
                      "lower": round(lo / 1000, 2), "upper": round(up / 1000, 2)})
    mix = []
    for c, meta in CATEGORIES.items():
        t = sum(sum(ctx.fc[(n, c)]["mean"][:7]) for n in NODES if NODES[n]["type"] != "depot") * meta["kg_per_unit"] / 1000
        mix.append({"category": c, "name": meta["name"], "tonnes": round(t, 1), "color": meta["color"]})
    fleet = {}
    for a in state["assets"].values():
        fleet[a["status"]] = fleet.get(a["status"], 0) + 1
    recs = recommendations(state, ctx)
    from .ai import briefing
    return {"sim_time": state["sim_time"], "kpis": k, "briefing": briefing(state, ctx, k),
            "ai_log": state.get("ai", {}).get("log", [])[:5], "matrix": matrix, "demand_chart": chart, "category_mix": mix,
            "fleet": fleet, "events": state["events"][:14], "top_alerts": [a for a in alerts if a["status"] != "RESOLVED"][:6],
            "top_recommendations": recs[:4], "recommendation_count": len(recs)}


def network_map(state) -> dict:
    ctx = Ctx(state)
    day = net.day_index(state)
    alert_count = {}
    for a in gen_alerts(state, ctx):
        if a["status"] == "RESOLVED" or not a.get("node"):
            continue
        d = alert_count.setdefault(a["node"], {})
        d[a["severity"]] = d.get(a["severity"], 0) + 1
    nodes = []
    for nid, n in NODES.items():
        cats = {c: ctx.status(nid, c) for c in CATEGORIES}
        worst = "OK"
        for st in cats.values():
            if st["status"] == "CRITICAL":
                worst = "CRITICAL"
            elif st["status"] == "LOW" and worst != "CRITICAL":
                worst = "LOW"
        w = net.weather_at(state, nid, day)
        nodes.append({"id": nid, **n, "status": worst, "weather": w, "alerts": alert_count.get(nid, {}),
                      "critical_items": [CATEGORIES[c]["name"] for c, st in cats.items() if st["status"] == "CRITICAL"],
                      "low_items": [CATEGORIES[c]["name"] for c, st in cats.items() if st["status"] == "LOW"],
                      "inventory": [{"category": c, "name": CATEGORIES[c]["name"], "unit": st["unit"], "on_hand": st["on_hand"],
                                     "days": st["days_of_supply"], "status": st["status"], "fill_pct": st["fill_pct"]}
                                    for c, st in cats.items()],
                      "assets_here": [a["id"] for a in state["assets"].values() if a["location"] == nid and a["status"] == "AVAILABLE"]})
    routes = []
    for rid, r in ROUTES.items():
        cond = net.route_condition(state, rid, day)
        risk = net.assess_road_risk(state, [rid], day)
        routes.append({"id": rid, "name": r["name"], "a": r["a"], "b": r["b"], "km": r["km"], "mode": r["mode"],
                       "coords": net.polyline([r["a"], r["b"]], [rid]), "status": cond["status"],
                       "time_mult": cond["time_mult"], "risk": risk["score"], "risk_level": risk["level"],
                       "factors": cond["factors"], "snow_prone": r["snow_prone"], "max_alt": r["max_alt"],
                       "hours": round(net.route_hours(rid, cond["time_mult"]), 1)})
    ships = [{k: s[k] for k in ("id", "source", "dest", "category", "qty", "mode", "status", "progress", "position",
                                "eta", "coords", "asset_id", "delay_hours")}
             for s in state["shipments"] if s["status"] in ("SCHEDULED", "LOADING", "IN_TRANSIT", "DELAYED", "HOLDING")]
    dis = []
    for d in net.active_disruptions(state):
        if d.get("route_id"):
            coords = net.polyline([ROUTES[d["route_id"]]["a"], ROUTES[d["route_id"]]["b"]], [d["route_id"]])
            pos = coords[len(coords) // 2]
        else:
            pos = [NODES[d["node_id"]]["lat"], NODES[d["node_id"]]["lon"]]
        dis.append({**d, "position": pos})
    return {"nodes": nodes, "routes": routes, "shipments": ships, "disruptions": dis}


def k_sec(k):
    return k.get("sector_readiness", {})


def sitrep(state) -> str:
    ctx = Ctx(state)
    alerts = gen_alerts(state, ctx)
    k = kpis(state, ctx, alerts)
    now = net.sim_now(state)
    lines = []
    lines.append("LOGISTICS SITUATION REPORT (SITREP) - SYNTHETIC DEMO DATA")
    lines.append(f"DTG: {now.strftime('%d%H%MZ %b %Y').upper()}    PREPARED BY: LogiSentinel decision-support system")
    lines.append("=" * 78)
    lines.append("1. OVERALL STATUS")
    lines.append(f"   Supply Readiness Index : {k['readiness_index']}/100")
    lines.append(f"   Posts at stock-out risk: {k['posts_at_risk']} of {k['posts_total']}")
    lines.append(f"   Active alerts          : {k['alerts_total']} ({k['alerts_critical']} critical, {k['alerts_high']} high)")
    lines.append(f"   Forecast accuracy      : {k['forecast_accuracy_pct']}% (beats naive baseline by {k['forecast_improvement_pct']}%)")
    lines.append(f"   On-time delivery       : {k['on_time_delivery_pct']}%   Transport utilisation: {k['transport_utilisation_pct']}%")
    names = {"NORTH": "Northern", "EAST": "Eastern", "WEST": "Western", "ISLANDS": "Island"}
    lines.append("   Readiness by sector   : " + ", ".join(f"{names[k]} {v}" for k, v in k_sec(k).items()))
    ai = state.get("ai", {})
    lines.append(f"   AI Autopilot          : {'ON' if ai.get('enabled', True) else 'OFF'} - "
                 f"{ai.get('stats', {}).get('red_alerts_handled', 0)} red alerts handled automatically, "
                 f"{ai.get('stats', {}).get('auto_requests', 0)} requests raised by AI")
    for e in ai.get("log", [])[:4]:
        lines.append(f"     - {e['time'][5:16].replace('T', ' ')}Z {e['title']} ({e['request_id'] or '-'})")
    lines.append("")
    lines.append("2. CRITICAL SUPPLY SITUATION")
    crit = [(n, c, ctx.status(n, c)) for n in NODES for c in CATEGORIES
            if NODES[n]["type"] != "depot" and ctx.status(n, c)["status"] == "CRITICAL"]
    if not crit:
        lines.append("   Nil.")
    for n, c, st in crit:
        lines.append(f"   - {NODES[n]['name']:<16} {CATEGORIES[c]['name']:<17} {st['days_of_supply']:>5} days held, "
                     f"lead time {st['lead_time_hours'] / 24:.1f} days" + (f", incoming {st['incoming_qty']:,}" if st['incoming_qty'] else ""))
    lines.append("")
    lines.append("3. MOVEMENTS")
    act = [s for s in state["shipments"] if s["status"] in ("SCHEDULED", "LOADING", "IN_TRANSIT", "DELAYED", "HOLDING")]
    if not act:
        lines.append("   Nil.")
    for s in act:
        lines.append(f"   - {s['id']} {s['mode']:<5} {NODES[s['source']]['name']} -> {NODES[s['dest']]['name']}: "
                     f"{s['qty']:,} {CATEGORIES[s['category']]['unit']} {CATEGORIES[s['category']]['name'].lower()}, "
                     f"{s['status'].lower()}, ETA {s['eta'][5:16].replace('T', ' ')}Z"
                     + (f" (delay {s['delay_hours']:.1f} h)" if s["delay_hours"] > 0 else ""))
    lines.append("")
    lines.append("4. ROUTES, WEATHER AND DISRUPTIONS")
    for d in net.active_disruptions(state):
        lines.append(f"   - [{d['severity']}] {d['title']}. Expected clear {d['expected_end'][5:16].replace('T', ' ')}Z")
    day = net.day_index(state)
    for n, meta in NODES.items():
        for kday in range(0, 3):
            w = net.weather_at(state, n, day + kday)
            if w["cond"] in ("Blizzard",) and meta["type"] == "post":
                lines.append(f"   - Blizzard forecast at {meta['name']} on D+{kday} ({w['snow_cm']} cm, wind {w['wind']} km/h)")
                break
    lines.append("")
    lines.append("5. RECOMMENDED ACTIONS")
    recs = recommendations(state, ctx)
    pri = [r for r in prioritise(state, ctx) if "priority_score" in r][:3]
    i = 1
    for r in recs[:4]:
        lines.append(f"   {i}. Replenish {r['node_name']} with {r['recommended_qty']:,} {r['unit']} {r['category_name'].lower()} "
                     f"from {r['suggested_source_name'] or 'depot'} [{r['urgency']}]")
        i += 1
    for r in pri:
        lines.append(f"   {i}. Action request {r['id']} ({r['node_name']}, {r['category_name']}) - score {r['priority_score']}: {r['recommended_action']}")
        i += 1
    lines.append("")
    lines.append("6. EQUIPMENT / SENSORS")
    iot_alerts = [a for a in alerts if a["type"].startswith("IOT") or a["type"].startswith("DEVICE")]
    for a in iot_alerts[:5]:
        lines.append(f"   - {a['title']}: {a['message']}")
    if not iot_alerts:
        lines.append("   All sensors nominal.")
    lines.append("=" * 78)
    lines.append("END OF SITREP. All locations and figures are synthetic and for demonstration only.")
    return "\n".join(lines)
