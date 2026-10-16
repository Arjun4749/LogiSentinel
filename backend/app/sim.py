"""Simulation clock: consumption, shipment movement, delays, deliveries and
feedback of actual consumption into the forecasting model."""
from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np

from . import network as net
from .forecast import ENGINE
from .planning import add_event
from .reference import ASSET_TYPES, CATEGORIES, NODES, ROUTES
from .seed import true_demand

MAX_HISTORY = 150


def _current_route_index(s: dict) -> int:
    if not s["routes"]:
        return 0
    kms = [ROUTES[r]["km"] for r in s["routes"]]
    total = sum(kms)
    done_km = total * (s["travel_done"] / max(s["total_hours"], 1e-6))
    acc = 0
    for i, k in enumerate(kms):
        acc += k
        if done_km < acc:
            return i
    return len(kms) - 1


def apply_route_effects(state, s: dict, day: int) -> bool:
    """Apply disruption delays to a road shipment. Returns True if it must hold (route closed)."""
    idx = _current_route_index(s)
    hold = False
    for rid in s["routes"][idx:]:
        cond = net.route_condition(state, rid, day)
        if cond["closed"] and rid == s["routes"][idx]:
            hold = True
        for d in net.active_disruptions(state, route_id=rid):
            if d["id"] in s["applied_disruptions"]:
                continue
            s["applied_disruptions"].append(d["id"])
            if d.get("delay_factor", 1) > 1:
                extra = round(net.route_hours(rid) * (d["delay_factor"] - 1), 1)
                s["total_hours"] += extra
                s["delay_hours"] += extra
                s["events"].append({"time": state["sim_time"], "text": f"Delay +{extra} h: {d['title']}"})
                add_event(state, f"Shipment {s['id']} delayed {extra} h by {d['title']}", "warning", s["id"])
                s["status"] = "DELAYED"
    return hold


def _deliver(state, s: dict, now: datetime):
    s["status"] = "DELIVERED"
    s["progress"] = 1.0
    s["position"] = s["coords"][-1]
    s["actual_arrival"] = net.iso(now)
    s["eta"] = s["actual_arrival"]
    s["events"].append({"time": state["sim_time"], "text": "Delivered and received into stock"})
    inv = state["inventory"][s["dest"]][s["category"]]
    inv["on_hand"] += s["qty"]
    on_time = s["delay_hours"] <= 0.1 * s["planned_hours"] + 0.5
    state["delivery_log"].append({"id": s["id"], "dest": s["dest"], "category": s["category"], "day": net.day_index(state),
                                  "planned_hours": s["planned_hours"], "actual_hours": round(s["total_hours"], 1),
                                  "on_time": on_time})
    state["stats"]["shipments_delivered"] += 1
    a = state["assets"].get(s["asset_id"])
    if a:
        back = s["total_hours"] * 0.85 if s["mode"] in ("ROAD", "SEA") else s["planned_hours"] * 0.5
        a["status"] = "RETURNING"
        a["location"] = s["dest"]
        a["available_at"] = net.iso(now + timedelta(hours=back))
        a["odometer_km"] = a.get("odometer_km", 0) + int(sum(ROUTES[r]["km"] for r in s["routes"]) * 2) if s["routes"] else a.get("odometer_km", 0)
    req = next((r for r in state["requests"] if r["id"] == s["request_id"]), None)
    if req:
        pending = [x for x in state["shipments"] if x["request_id"] == req["id"] and x["status"] != "DELIVERED"]
        if not pending:
            req["status"] = "DELIVERED"
            req["history"].append({"time": state["sim_time"], "text": "All shipments delivered"})
    add_event(state, f"{s['id']} delivered {s['qty']:,} {CATEGORIES[s['category']]['unit']} "
                     f"{CATEGORIES[s['category']]['name'].lower()} to {NODES[s['dest']]['name']}"
                     + ("" if on_time else f" ({s['delay_hours']:.1f} h late)"), "success" if on_time else "warning", s["id"])


def _roll_day(state):
    """Close the day: append actual consumption to history (model feedback)."""
    hours = max(1, state.get("consumed_hours", 24))
    for node in NODES:
        for cat in CATEGORIES:
            v = state["consumed_today"].get(f"{node}|{cat}", 0.0) * 24.0 / hours
            h = state["history"][node][cat]
            h.append(round(v, 2))
            if len(h) > MAX_HISTORY:
                del h[0]
    state["history_end_day"] += 1
    state["consumed_today"] = {}
    state["consumed_hours"] = 0


def advance(state, hours: float, retrain: bool = True) -> dict:
    """Move the simulation forward by `hours` (fractions allowed) in steps of at most one hour."""
    hours = max(0.0, min(float(hours), 168.0))
    now = net.sim_now(state)
    day0 = datetime.fromisoformat(state["day0"])
    rolled = 0
    stockouts = []
    remaining = hours
    while remaining > 1e-6:
        step = min(1.0, remaining)
        remaining -= step
        now = now + timedelta(hours=step)
        state["sim_time"] = net.iso(now)
        day = net.day_index(state, now)
        # ---- day rollover (history covers days < history_end_day) ----
        while day > state["history_end_day"]:
            _roll_day(state)
            rolled += 1
        # ---- consumption ----
        hd = state["history_days"]
        for node in NODES:
            w = net.weather_at(state, node, day)
            ops_ser = state["ops"][node]
            ops = ops_ser[min(len(ops_ser) - 1, day + hd)]
            wd = (day0 + timedelta(days=day)).weekday()
            for cat in CATEGORIES:
                use = true_demand(node, cat, day, w, ops, wd) / 24.0 * step
                inv = state["inventory"][node][cat]
                before = inv["on_hand"]
                inv["on_hand"] = max(0.0, inv["on_hand"] - use)
                key = f"{node}|{cat}"
                state["consumed_today"][key] = state["consumed_today"].get(key, 0.0) + use
                if before > 0 and inv["on_hand"] <= 0:
                    stockouts.append((node, cat))
                    add_event(state, f"STOCK-OUT: {NODES[node]['name']} has run out of {CATEGORIES[cat]['name'].lower()}",
                              "danger", node)
        state["consumed_hours"] = state.get("consumed_hours", 0) + step
        # ---- shipments: scheduled -> loading -> in transit -> delivered ----
        for s in state["shipments"]:
            just_departed = False
            if s["status"] == "SCHEDULED" and s.get("loading_start") and net.parse_time(s["loading_start"]) <= now:
                s["status"] = "LOADING"
                s["events"].append({"time": s["loading_start"], "text": f"Vehicle at {NODES[s['source']]['name']} - loading started"})
            if s["status"] in ("SCHEDULED", "LOADING") and net.parse_time(s["planned_departure"]) <= now:
                dep = net.parse_time(s["planned_departure"])
                s["status"] = "IN_TRANSIT"
                s["actual_departure"] = s["planned_departure"]
                s["travel_done"] = max(0.0, (now - dep).total_seconds() / 3600)
                s["events"].append({"time": s["planned_departure"], "text": f"Departed {NODES[s['source']]['name']} on schedule"})
                add_event(state, f"{s['id']} departed {NODES[s['source']]['name']} for {NODES[s['dest']]['name']}", "info", s["id"])
                just_departed = True
            if s["status"] not in ("IN_TRANSIT", "DELAYED", "HOLDING"):
                continue
            if s["mode"] in ("ROAD", "SEA"):
                hold = apply_route_effects(state, s, day)
            else:
                ok, _, _ = net.air_effect(net.weather_at(state, s["dest"], day))
                hold = not ok
            if hold:
                if s["status"] != "HOLDING":
                    why = "sea lane closed" if s["mode"] == "SEA" else "route closed" if s["mode"] == "ROAD" else "no flying window"
                    s["events"].append({"time": state["sim_time"], "text": f"Holding: {why}"})
                    add_event(state, f"{s['id']} holding - {why}", "warning", s["id"])
                s["status"] = "HOLDING"
                s["delay_hours"] += step
                s["total_hours"] += step
            else:
                if s["status"] == "HOLDING":
                    s["status"] = "DELAYED" if s["delay_hours"] > 0 else "IN_TRANSIT"
                    s["events"].append({"time": state["sim_time"], "text": "Movement resumed"})
                if not just_departed:
                    s["travel_done"] += step
            s["progress"] = round(min(1.0, s["travel_done"] / max(s["total_hours"], 1e-6)), 3)
            s["position"] = net.point_along(s["coords"], s["progress"])
            s["eta"] = net.iso(now + timedelta(hours=max(0.0, s["total_hours"] - s["travel_done"])))
            if s["travel_done"] >= s["total_hours"] - 1e-6:
                _deliver(state, s, now)
        # ---- assets ----
        for a in state["assets"].values():
            if a["status"] == "RETURNING" and a.get("available_at") and net.parse_time(a["available_at"]) <= now:
                a["status"] = "AVAILABLE"
                a["location"] = a["home"]
                a["available_at"] = None
        # ---- disruptions auto-clear ----
        for d in state["disruptions"]:
            if d["status"] == "ACTIVE" and d.get("expected_end") and net.parse_time(d["expected_end"]) <= now:
                d["status"] = "RESOLVED"
                d["resolved_at"] = state["sim_time"]
                add_event(state, f"Disruption cleared: {d['title']}", "success", d["id"])
    retrained = False
    if rolled and retrain:
        ENGINE.fit(state)
        retrained = True
    return {"sim_time": state["sim_time"], "days_rolled": rolled, "model_retrained": retrained,
            "new_stockouts": [{"node": n, "category": c} for n, c in stockouts]}


def seed_in_transit(state):
    """Create a few shipments already on the road so the map is alive from the start."""
    from .planning import Ctx, dispatch, plan_options, next_id
    specs = [  # node, category, qty, source, hours already travelled, mode
        ("FP-H", "RATIONS", 1800, "HUB-L", 3, "ROAD"),
        ("FP-J", "FUEL", 3000, "HUB-M", 5, "ROAD"),
        ("HUB-K", "RATIONS", 9000, "DEP-B", 7, "ROAD"),
        ("FP-E", "SPARES", 60, "HUB-K", 2, "ROAD"),
        ("FP-I", "RATIONS", 2400, "HUB-L", 2, "ROAD"),
        ("HUB-Q", "FUEL", 60000, "DEP-Y", 20, "SEA"),
        ("HUB-P", "WATER", 20000, "DEP-D", 3, "ROAD"),
        ("FP-S", "RATIONS", 2000, "HUB-O", 4, "ROAD"),
        ("HUB-N", "FUEL", 8000, "DEP-C", 2, "ROAD"),
    ]
    now = net.sim_now(state)
    for node, cat, qty, src, done, mode in specs:
        ctx = Ctx(state)
        rid = next_id(state, "REQ")
        req = {"id": rid, "node": node, "category": cat, "qty": qty,
               "needed_by": net.iso(now + timedelta(days=3)), "declared_urgency": "MEDIUM",
               "reason": "Scheduled maintenance replenishment", "raised_by": "Auto-replenishment engine",
               "created_at": net.iso(now - timedelta(hours=done + 6)), "status": "APPROVED", "source": "SYSTEM",
               "history": [{"time": net.iso(now - timedelta(hours=done + 6)), "text": "Generated by replenishment engine and approved"}]}
        state["requests"].append(req)
        plan = plan_options(state, node, cat, qty, req["needed_by"], ctx)
        opts = [o for o in plan["options"] if o["mode"] == mode and o["source"] == src] or \
               [o for o in plan["options"] if o["mode"] == mode]
        if not opts:
            continue
        ships = dispatch(state, req, opts[0], "system")
        for s in ships:
            dep = now - timedelta(hours=done)
            s["planned_departure"] = net.iso(dep)
            s["actual_departure"] = s["planned_departure"]
            s["planned_arrival"] = net.iso(dep + timedelta(hours=s["planned_hours"]))
            s["status"] = "IN_TRANSIT"
            s["loading_start"] = net.iso(dep - timedelta(hours=s.get("loading_hours", 1.0)))
            s["travel_done"] = float(done)
            apply_route_effects(state, s, net.day_index(state))
            s["progress"] = round(min(0.95, s["travel_done"] / s["total_hours"]), 3)
            s["position"] = net.point_along(s["coords"], s["progress"])
            s["eta"] = net.iso(now + timedelta(hours=s["total_hours"] - s["travel_done"]))
            s["events"] = [{"time": s["planned_departure"], "text": f"Departed {NODES[s['source']]['name']}"}] + \
                          [e for e in s["events"] if "Delay" in e["text"]]
    state["events"] = [e for e in state["events"] if "dispatched" not in e["text"]]
