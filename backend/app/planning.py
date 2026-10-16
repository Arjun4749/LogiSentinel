"""Decision engines: inventory risk, replenishment, request prioritisation,
transport planning (capacity-aware asset assignment) and dispatch."""
from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import numpy as np

from . import network as net
from .forecast import ENGINE
from .reference import ASSET_TYPES, CATEGORIES, NODES, ROUTES

Z_SERVICE = 1.65  # ~95% cycle service level
BUFFER_DAYS = {"post": 3, "hub": 5, "depot": 7}
REVIEW_DAYS = {"post": 14, "hub": 21, "depot": 30}
RAIL_LEAD_HOURS = 48.0


def fmt_qty(v: float) -> str:
    return f"{v:,.0f}"


def next_id(state, prefix: str) -> str:
    state["counters"][prefix] = state["counters"].get(prefix, 0) + 1
    return f"{prefix}-{state['counters'][prefix]}"


def add_event(state, text: str, kind: str = "info", entity: Optional[str] = None):
    state["counters"]["EVT"] = state["counters"].get("EVT", 0) + 1
    state["events"].insert(0, {"id": state["counters"]["EVT"], "time": state["sim_time"], "text": text,
                               "kind": kind, "entity": entity})
    del state["events"][120:]


# ---------------------------------------------------------------------------
# Lead time and inventory status
# ---------------------------------------------------------------------------

class Ctx:
    """Per-request cache so the heavy calculations run once per API call."""

    def __init__(self, state):
        self.state = state
        self.fc = ENGINE.forecast_all(state, 30)
        self.paths: Dict[tuple, Optional[dict]] = {}
        self._status: Dict[tuple, dict] = {}

    def path(self, a, b, modes=("ROAD", "SEA")):
        k = (a, b, modes)
        if k not in self.paths:
            self.paths[k] = net.shortest_path(self.state, a, b, modes=modes)
        return self.paths[k]

    def lead_time_hours(self, node: str) -> float:
        n = NODES[node]
        if n["type"] == "depot":
            return RAIL_LEAD_HOURS
        p = self.path(n["parent"], node)
        if p is None:  # parent route blocked: try any hub/depot
            best = None
            for src, sn in NODES.items():
                if sn["type"] == "post" or src == node or sn["sector"] != n["sector"]:
                    continue
                q = self.path(src, node)
                if q and (best is None or q["hours"] < best):
                    best = q["hours"]
            return float(best + 6) if best else 96.0
        return float(p["hours"] + 6)  # +6h order processing

    def status(self, node: str, cat: str) -> dict:
        k = (node, cat)
        if k not in self._status:
            self._status[k] = inventory_status(self.state, node, cat, self)
        return self._status[k]


def incoming(state, node: str, cat: str) -> List[dict]:
    out = []
    for s in state["shipments"]:
        if s["dest"] == node and s["category"] == cat and s["status"] in ("SCHEDULED", "LOADING", "IN_TRANSIT", "DELAYED", "HOLDING"):
            out.append({"shipment_id": s["id"], "qty": s["qty"], "eta": s["eta"], "status": s["status"]})
    return out


def open_requests(state, node: str, cat: str) -> List[dict]:
    return [r for r in state["requests"] if r["node"] == node and r["category"] == cat
            and r["status"] in ("NEW", "APPROVED")]


def inventory_status(state, node: str, cat: str, ctx: Ctx) -> dict:
    inv = state["inventory"][node][cat]
    fc = ctx.fc[(node, cat)]
    n = NODES[node]
    hist = state["history"][node][cat]
    avg = float(np.mean(fc["mean"][:7]))
    sd = float(np.std(hist[-28:]))
    lt_h = ctx.lead_time_hours(node)
    lt_d = lt_h / 24.0
    ss = Z_SERVICE * sd * math.sqrt(max(lt_d, 0.5)) + BUFFER_DAYS[n["type"]] * avg
    rop = avg * lt_d + ss
    target = avg * (lt_d + REVIEW_DAYS[n["type"]]) + ss
    inc = incoming(state, node, cat)
    inc_qty = sum(i["qty"] for i in inc)
    now = net.sim_now(state)
    # day-by-day projection with scheduled arrivals
    arrivals = {}
    for i in inc:
        d = max(0, int((net.parse_time(i["eta"]) - now).total_seconds() // 86400))
        arrivals[d] = arrivals.get(d, 0) + i["qty"]
    stock = inv["on_hand"]
    stockout_day = None
    stockout_no_resupply = None
    s2 = inv["on_hand"]
    projection = []
    day0 = net.parse_time(state["day0"])
    hour_frac = 1 - (((now - day0).total_seconds() / 3600.0) % 24) / 24.0
    for d, dem in enumerate(fc["mean"]):
        use = dem * (hour_frac if d == 0 else 1.0)
        stock += arrivals.get(d, 0)
        if stock - use < 0 and stockout_day is None:
            stockout_day = d + (stock / use if use else 0) - (1 - hour_frac if d == 0 else 0)
        stock -= use
        if s2 - use < 0 and stockout_no_resupply is None:
            stockout_no_resupply = d + (s2 / use if use else 0)
        s2 -= use
        projection.append(round(stock, 1))
    position = inv["on_hand"] + inc_qty
    days_supply = inv["on_hand"] / avg if avg > 0 else 99.0
    days_cover = (stockout_day if stockout_day is not None else 30.0)
    if inv["on_hand"] <= 0 or days_cover < lt_d + 2:
        st = "CRITICAL"
    elif position < rop or days_cover < lt_d + 6:
        st = "LOW"
    elif inv["on_hand"] > 0.92 * inv["capacity"]:
        st = "EXCESS"
    else:
        st = "OK"
    return {
        "node": node, "category": cat, "on_hand": round(inv["on_hand"]), "capacity": inv["capacity"],
        "unit": CATEGORIES[cat]["unit"], "avg_daily_forecast": round(avg, 1), "days_of_supply": round(days_supply, 1),
        "days_cover_incl_incoming": round(days_cover, 1), "stockout_in_days": None if stockout_day is None else round(stockout_day, 1),
        "safety_stock": round(ss), "reorder_point": round(rop), "target_level": round(target),
        "lead_time_hours": round(lt_h, 1), "incoming_qty": round(inc_qty), "incoming": inc,
        "position": round(position), "status": st, "fill_pct": round(100 * inv["on_hand"] / max(1, inv["capacity"]), 1),
        "projection": projection[:14], "confidence": fc["confidence"],
    }


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

def reserved_at(state, node: str, cat: str) -> float:
    return 0.0  # stock is deducted at dispatch, so nothing is double-counted


def candidate_sources(state, ctx: Ctx, dest: str, cat: str, qty: float, limit: int = 3) -> List[dict]:
    out = []
    for src, sn in NODES.items():
        if src == dest or sn["type"] == "post" or sn["sector"] != NODES[dest]["sector"]:
            continue
        inv = state["inventory"][src][cat]
        st = ctx.status(src, cat)
        keep = st["safety_stock"] + st["avg_daily_forecast"] * 5
        avail = max(0.0, inv["on_hand"] - keep)
        if avail <= 0:
            continue
        p = ctx.path(src, dest)
        hours = p["hours"] if p else None
        dist = net.node_distance(src, dest)
        out.append({"source": src, "available": round(avail), "road_hours": hours, "road_open": p is not None,
                    "air_km": round(dist), "covers_full": avail >= qty})
    out.sort(key=lambda c: (not c["covers_full"], c["road_hours"] if c["road_hours"] is not None else 999 + c["air_km"]))
    return out[:limit]


# ---------------------------------------------------------------------------
# Replenishment recommendations
# ---------------------------------------------------------------------------

def nice_round(q: float, unit: str) -> int:
    if q <= 0:
        return 0
    step = 1 if q < 50 else 10 if q < 1000 else 100 if q < 20000 else 500
    return int(math.ceil(q / step) * step)


def recommendations(state, ctx: Optional[Ctx] = None) -> List[dict]:
    ctx = ctx or Ctx(state)
    recs = []
    for node, n in NODES.items():
        if n["type"] == "depot":
            continue
        for cat in CATEGORIES:
            st = ctx.status(node, cat)
            if st["status"] not in ("CRITICAL", "LOW"):
                continue
            covering = open_requests(state, node, cat)
            if covering:
                continue
            qty = nice_round(st["target_level"] - st["position"], st["unit"])
            if qty <= 0:
                continue
            srcs = candidate_sources(state, ctx, node, cat, qty, limit=2)
            src = srcs[0] if srcs else None
            lt = st["lead_time_hours"] / 24
            so = st["stockout_in_days"]
            if so is not None and so <= lt + 2:
                urgency = "CRITICAL"
            elif so is not None and so <= lt + 3:
                urgency = "HIGH"
            elif so is not None and so <= 10:
                urgency = "MEDIUM"
            else:
                urgency = "LOW"
            cat_name = CATEGORIES[cat]["name"]
            reason = (f"{n['name']} holds {fmt_qty(st['on_hand'])} {st['unit']} of {cat_name.lower()} "
                      f"= {st['days_of_supply']} days at the forecast rate of {st['avg_daily_forecast']:,} {st['unit']}/day"
                      + (f" (+{fmt_qty(st['incoming_qty'])} incoming)" if st["incoming_qty"] else "")
                      + f". Lead time is {lt:.1f} days. "
                      + (f"Projected stock-out in {so} days. " if so is not None else "")
                      + f"Order up to target level {fmt_qty(st['target_level'])} (safety stock {fmt_qty(st['safety_stock'])}).")
            recs.append({
                "id": f"REC-{node}-{cat}", "node": node, "node_name": n["name"], "sector": n["sector"], "category": cat,
                "category_name": cat_name, "unit": st["unit"], "on_hand": st["on_hand"], "incoming": st["incoming_qty"],
                "avg_daily_forecast": st["avg_daily_forecast"], "days_of_supply": st["days_of_supply"],
                "stockout_in_days": so, "safety_stock": st["safety_stock"], "reorder_point": st["reorder_point"],
                "target_level": st["target_level"], "recommended_qty": qty,
                "weight_kg": round(qty * CATEGORIES[cat]["kg_per_unit"]),
                "suggested_source": src["source"] if src else None,
                "suggested_source_name": NODES[src["source"]]["name"] if src else None,
                "source_available": src["available"] if src else 0,
                "lead_time_hours": st["lead_time_hours"], "urgency": urgency, "reason": reason,
                "confidence": st["confidence"], "formula": "Order qty = (daily forecast x (lead time + review period)) + safety stock - (on hand + incoming)",
            })
    order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    recs.sort(key=lambda r: (order[r["urgency"]], r["stockout_in_days"] if r["stockout_in_days"] is not None else 99))
    return recs


# ---------------------------------------------------------------------------
# Request prioritisation
# ---------------------------------------------------------------------------

def _clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


def prioritise(state, ctx: Optional[Ctx] = None) -> List[dict]:
    ctx = ctx or Ctx(state)
    now = net.sim_now(state)
    out = []
    for r in state["requests"]:
        item = dict(r)
        item["node_name"] = NODES[r["node"]]["name"]
        item["sector"] = NODES[r["node"]]["sector"]
        item["category_name"] = CATEGORIES[r["category"]]["name"]
        item["unit"] = CATEGORIES[r["category"]]["unit"]
        item["weight_kg"] = round(r["qty"] * CATEGORIES[r["category"]]["kg_per_unit"])
        if r["status"] not in ("NEW", "APPROVED"):
            out.append(item)
            continue
        st = ctx.status(r["node"], r["category"])
        hrs_to_need = (net.parse_time(r["needed_by"]) - now).total_seconds() / 3600
        days_cover = st["days_cover_incl_incoming"]
        time_p = 40 * _clamp(1 - hrs_to_need / (7 * 24))
        stock_p = 40 * _clamp(1 - days_cover / 10)
        urgency = round(max(time_p, stock_p), 1)
        cat = CATEGORIES[r["category"]]
        pers = NODES[r["node"]]["personnel"]
        criticality = round(22 * cat["criticality"] + 8 * _clamp(pers / 250), 1)
        srcs = candidate_sources(state, ctx, r["node"], r["category"], r["qty"], limit=3)
        feas, ff = 0.0, []
        if srcs and srcs[0]["covers_full"]:
            feas += 8
            ff.append(f"Stock available at {NODES[srcs[0]['source']]['name']} (+8)")
        elif srcs:
            feas += 4
            ff.append("Only partial stock available at sources (+4)")
        else:
            ff.append("No source has surplus stock (+0)")
        if srcs and any(s["road_open"] for s in srcs):
            feas += 6
            ff.append("Road route open (+6)")
        elif NODES[r["node"]]["helipad"]:
            feas += 3
            ff.append("Road closed - air delivery possible (+3)")
        avail_assets = [a for a in state["assets"].values() if a["status"] == "AVAILABLE"]
        if avail_assets:
            feas += 6
            ff.append(f"{len(avail_assets)} transport assets available (+6)")
        created = net.parse_time(r["created_at"])
        age_h = max(0.0, (now - created).total_seconds() / 3600)
        age = round(min(10.0, age_h / 4), 1)
        score = round(urgency + criticality + feas + age, 1)
        level = "CRITICAL" if score >= 75 else "HIGH" if score >= 60 else "MEDIUM" if score >= 40 else "LOW"
        factors = [
            f"Needed in {hrs_to_need / 24:.1f} days; stock covers {days_cover} days (urgency +{urgency})",
            f"{cat['name']} criticality {int(cat['criticality'] * 100)}%, {pers} personnel (criticality +{criticality})",
            *ff,
            f"Waiting {age_h:.0f} h - ageing boost +{age} prevents requests stalling",
        ]
        action = ("Dispatch immediately - use fastest mode" if level == "CRITICAL" else
                  "Plan shipment today" if level == "HIGH" else
                  "Consolidate with next scheduled convoy" if level == "MEDIUM" else "Schedule in routine run")
        item.update({"priority_score": score, "priority_level": level,
                     "breakdown": {"urgency": urgency, "criticality": criticality, "feasibility": feas, "age": age},
                     "factors": factors, "recommended_action": action, "days_cover": days_cover,
                     "hours_to_needed": round(hrs_to_need, 1)})
        out.append(item)
    open_items = sorted([i for i in out if "priority_score" in i], key=lambda i: -i["priority_score"])
    for rank, i in enumerate(open_items, start=1):
        i["rank"] = rank
    return open_items + [i for i in out if "priority_score" not in i]


# ---------------------------------------------------------------------------
# Transport planning
# ---------------------------------------------------------------------------

def _asset_ready_hours(state, a: dict, now: datetime) -> float:
    if a["status"] == "AVAILABLE":
        return 0.0
    if a["status"] == "RETURNING" and a.get("available_at"):
        return max(0.0, (net.parse_time(a["available_at"]) - now).total_seconds() / 3600)
    return math.inf


def plan_options(state, dest: str, cat: str, qty: float, needed_by: Optional[str] = None,
                 ctx: Optional[Ctx] = None, exclude_assets: Optional[set] = None) -> dict:
    ctx = ctx or Ctx(state)
    now = net.sim_now(state)
    day = net.day_index(state)
    kgpu = CATEGORIES[cat]["kg_per_unit"]
    need_dt = net.parse_time(needed_by) if needed_by else now + timedelta(days=5)
    exclude_assets = exclude_assets or set()
    options = []
    sources = candidate_sources(state, ctx, dest, cat, qty, limit=3)
    for src in sources:
        sqty = min(qty, src["available"])
        weight = sqty * kgpu
        s_id = src["source"]
        for mode in ("ROAD", "SEA"):
            p = ctx.path(s_id, dest, (mode,))
            if p and p["routes"]:
                o = _surface_option(state, ctx, mode, s_id, dest, cat, p, weight, sqty, qty, kgpu, now, day, need_dt,
                                    exclude_assets)
                if o:
                    options.append(o)
        for atype in ("HELICOPTER", "AIRCRAFT", "DRONE"):
            o = _air_option(state, atype, s_id, dest, cat, weight, sqty, qty, now, day, need_dt, exclude_assets)
            if o:
                options.append(o)
    # score options
    if options:
        max_cost = max(300000, max(o["cost_inr"] for o in options))
        max_eta = max((net.parse_time(o["eta"]) - now).total_seconds() / 3600 for o in options) or 1
        # urgent or life-critical loads value speed; routine loads value economy
        urgent = (need_dt - now).total_seconds() / 3600 < 36 or CATEGORIES[cat]["criticality"] >= 1.0
        w_speed, w_cost = (20, 5) if urgent else (5, 20)
        for o in options:
            on_time = 1.0 if o["on_time"] else max(0.0, 1 - o["late_hours"] / 48)
            fill = 1 - min(1.0, o["shortfall_qty"] / max(qty, 1))
            eta_h = (net.parse_time(o["eta"]) - now).total_seconds() / 3600
            o["score"] = round(35 * on_time + 25 * (1 - o["risk"]["score"] / 100) + w_cost * (1 - o["cost_inr"] / max_cost)
                               + 15 * fill + w_speed * (1 - eta_h / max_eta), 1)
            o["priority_basis"] = "speed" if urgent else "economy"
        options.sort(key=lambda o: -o["score"])
        for i, o in enumerate(options):
            o["option_id"] = f"OPT-{i + 1}"
        options[0]["recommended"] = True
        best = options[0]
        best["why"] = _why(best, options)
    return {"dest": dest, "category": cat, "qty": qty, "needed_by": need_dt.isoformat(timespec="minutes"),
            "sources_considered": sources, "options": options}


LOAD_HOURS = {"ROAD": 1.0, "SEA": 6.0, "AIR": 1.0, "DRONE": 0.25}


def _surface_option(state, ctx, mode, src, dest, cat, p, weight, sqty, qty, kgpu, now, day, need_dt, exclude):
    """Road convoy or sea lift: pick ready vehicles/ships nearest the source and fill them in order."""
    sector = NODES[src]["sector"]
    cands = []
    for a in state["assets"].values():
        t = ASSET_TYPES[a["type"]]
        if t["mode"] != mode or a["id"] in exclude:
            continue
        if t["categories"] and cat not in t["categories"]:
            continue
        ready = _asset_ready_hours(state, a, now)
        if ready == math.inf:
            continue
        loc = a["location"] if a["status"] == "AVAILABLE" else a["home"]
        if NODES[loc]["sector"] != sector:
            continue
        rep = 0.0
        if loc != src:
            rp = ctx.path(loc, src, (mode,))
            if not rp:
                continue
            rep = rp["hours"]
        cands.append((ready + rep, -a["capacity_kg"], a))
    cands.sort(key=lambda x: (x[0], x[1]))
    chosen, remaining = [], weight
    for ready, _, a in cands:
        if remaining <= 0:
            break
        load = min(remaining, a["capacity_kg"])
        chosen.append({"asset_id": a["id"], "type_name": a["type_name"], "weight_kg": round(load),
                       "qty": round(load / kgpu), "ready_in_hours": round(ready, 1),
                       "utilisation_pct": round(100 * load / a["capacity_kg"])})
        remaining -= load
    if not chosen:
        return None
    load_h = LOAD_HOURS[mode]
    # each vehicle leaves as soon as it is ready and loaded - nobody waits for the slowest truck
    for c in chosen:
        sf = ASSET_TYPES[state["assets"][c["asset_id"]]["type"]].get("speed_factor", 1.0)
        c_travel = round((p["hours"] - net.HANDLING_HOURS) / sf + net.HANDLING_HOURS, 1)
        c_dep = now + timedelta(hours=c["ready_in_hours"] + load_h)
        c["depart"] = net.iso(c_dep)
        c["eta"] = net.iso(c_dep + timedelta(hours=c_travel))
        c["travel_hours"] = c_travel
    ready_h = max(c["ready_in_hours"] for c in chosen)
    depart = min(net.parse_time(c["depart"]) for c in chosen)
    eta = max(net.parse_time(c["eta"]) for c in chosen)
    travel = max(c["travel_hours"] for c in chosen)
    # risk is judged over every day the convoy will be on the move, not just departure day
    d0 = day + int((ready_h + load_h) // 24)
    d1 = day + int((ready_h + load_h + travel) // 24)
    risk = max((net.assess_road_risk(state, p["routes"], d) for d in range(d0, d1 + 1)), key=lambda r: r["score"])
    if d1 > d0:
        risk["factors"].append(f"Risk checked for every day of the journey (day {d0 - day} to day {d1 - day})")
    cost = sum(p["km"] * ASSET_TYPES[state["assets"][c["asset_id"]]["type"]]["cost_per_km"] for c in chosen)
    shortfall = max(0.0, remaining) / kgpu + (qty - sqty)
    via = ", ".join(ROUTES[r]["name"] for r in p["routes"])
    if mode == "SEA":
        label = f"Sea lift ({chosen[0]['type_name']}) from {NODES[src]['name']} via {via}"
    else:
        label = f"Road convoy ({len(chosen)} vehicle{'s' if len(chosen) > 1 else ''}) from {NODES[src]['name']} via {via}"
    o = _option(mode, src, dest, cat, chosen, depart, eta, travel, p["km"], risk, cost, shortfall, need_dt,
                p["nodes"], p["routes"], net.polyline(p["nodes"], p["routes"]), label)
    o["ready_hours"], o["loading_hours"] = round(ready_h, 1), load_h
    return o


def _air_option(state, atype, src, dest, cat, weight, sqty, qty, now, day, need_dt, exclude):
    """Helicopter, transport aircraft or drone option between two locations."""
    t = ASSET_TYPES[atype]
    dist = net.node_distance(src, dest)
    if dist > t["range_km"]:
        return None
    if t.get("categories") and cat not in t["categories"]:
        return None
    need = t.get("needs")
    if need and not (NODES[src].get(need) and NODES[dest].get(need)):
        return None
    max_sorties = 6 if atype == "DRONE" else 4 if atype == "HELICOPTER" else 3
    sorties = max(1, math.ceil(weight / t["capacity_kg"]))
    if sorties > max_sorties:
        return None
    fleet = [a for a in state["assets"].values() if a["type"] == atype and a["id"] not in exclude
             and _asset_ready_hours(state, a, now) < math.inf]
    if atype == "DRONE":
        fleet = [a for a in fleet if a["status"] == "AVAILABLE" and net.node_distance(a["location"], src) < 5]
    elif atype == "HELICOPTER":  # helicopters stay within their own sector
        fleet = [a for a in fleet if NODES[a["home"]]["sector"] == NODES[src]["sector"]]
    if not fleet:
        return None
    def ready_of(a):
        loc = a["location"] if a["status"] == "AVAILABLE" else a["home"]
        return _asset_ready_hours(state, a, now) + net.node_distance(loc, src) / t["speed_kmh"]
    a = min(fleet, key=ready_of)
    ready = ready_of(a)
    if ready > 24:
        return None
    air = net.assess_air_risk(state, src, dest, day)
    leg = dist / t["speed_kmh"] + (0.3 if atype == "DRONE" else 1.0)
    total = sorties * leg + (sorties - 1) * leg
    load_h = LOAD_HOURS["DRONE" if atype == "DRONE" else "AIR"]
    depart = now + timedelta(hours=ready + load_h)
    if not air["can_fly"]:
        depart += timedelta(hours=24)
        air["factors"].append("Grounded by weather now - departure moved to the next flying window (24 h)")
    eta = depart + timedelta(hours=total)
    cost = dist * 2 * sorties * t["cost_per_km"]
    assets = [{"asset_id": a["id"], "type_name": a["type_name"], "weight_kg": round(weight), "qty": round(sqty),
               "ready_in_hours": round(ready, 1), "sorties": sorties,
               "utilisation_pct": round(100 * weight / (sorties * t["capacity_kg"]))}]
    kind = {"HELICOPTER": "Helicopter airlift", "AIRCRAFT": "Transport aircraft airlift", "DRONE": "Drone shuttle"}[atype]
    o = _option("DRONE" if atype == "DRONE" else "AIR", src, dest, cat, assets, depart, eta, total, round(dist), air,
                cost, qty - sqty, need_dt, [src, dest], [], net.straight_line(src, dest),
                f"{kind} ({sorties} sortie{'s' if sorties > 1 else ''}) from {NODES[src]['name']}")
    o["ready_hours"], o["loading_hours"] = round(ready, 1), load_h
    return o


def _option(mode, src, dest, cat, assets, depart, eta, hours, km, risk, cost, shortfall, need_dt, nodes, routes,
            coords, label):
    slack = (need_dt - eta).total_seconds() / 3600
    return {"mode": mode, "source": src, "source_name": NODES[src]["name"], "dest": dest, "category": cat,
            "label": label, "assets": assets, "depart": depart.isoformat(timespec="minutes"),
            "eta": eta.isoformat(timespec="minutes"), "travel_hours": round(hours, 1), "km": km,
            "risk": risk, "cost_inr": round(cost), "shortfall_qty": round(max(0.0, shortfall)),
            "on_time": slack >= 0, "slack_hours": round(slack, 1), "late_hours": round(max(0.0, -slack), 1),
            "path": nodes, "routes": routes, "coords": coords, "recommended": False,
            "total_qty": sum(a["qty"] for a in assets)}


def _why(best, options) -> str:
    parts = []
    parts.append("arrives before the needed-by time" if best["on_time"] else f"is the least late ({best['late_hours']} h)")
    parts.append(f"risk {best['risk']['score']}/100 ({best['risk']['level'].lower()})")
    if best["shortfall_qty"] == 0:
        parts.append("covers the full quantity")
    alts = [o for o in options if o is not best]
    if alts:
        a = alts[0]
        parts.append(f"next best: {a['mode'].lower()} option with risk {a['risk']['score']} and ETA {a['eta'][11:16]}")
    basis = ("This is an urgent or life-critical load, so speed is weighted above cost. " if best.get("priority_basis") == "speed"
             else "This is a routine load, so cost is weighted above speed. ")
    return basis + "Recommended because it " + ", ".join(parts) + "."


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

def dispatch(state, request: dict, option: dict, user: str) -> List[dict]:
    cat = option["category"]
    src = option["source"]
    inv = state["inventory"][src][cat]
    created = []
    total = 0
    for a in option["assets"]:
        q = min(a["qty"], max(0, round(inv["on_hand"])))
        if q <= 0:
            continue
        inv["on_hand"] -= q
        total += q
        sid = next_id(state, "SHP")
        asset = state["assets"][a["asset_id"]]
        asset["status"] = "ON_MISSION"
        asset["location"] = src
        asset["missions_30d"] = asset.get("missions_30d", 0) + 1
        ship = {
            "id": sid, "request_id": request["id"], "source": src, "dest": option["dest"], "category": cat,
            "qty": q, "weight_kg": round(q * CATEGORIES[cat]["kg_per_unit"]), "asset_id": a["asset_id"],
            "mode": option["mode"], "path": option["path"], "routes": option["routes"], "coords": option["coords"],
            "planned_departure": a.get("depart", option["depart"]), "planned_arrival": a.get("eta", option["eta"]),
            "eta": a.get("eta", option["eta"]),
            "loading_start": net.iso(net.parse_time(a.get("depart", option["depart"])) - timedelta(hours=option.get("loading_hours", 1.0))),
            "loading_hours": option.get("loading_hours", 1.0), "ready_hours": a.get("ready_in_hours", option.get("ready_hours", 0.0)),
            "planned_hours": a.get("travel_hours", option["travel_hours"]), "total_hours": a.get("travel_hours", option["travel_hours"]),
            "travel_done": 0.0,
            "status": "SCHEDULED", "progress": 0.0, "position": option["coords"][0], "delay_hours": 0.0,
            "risk": option["risk"], "applied_disruptions": [], "created_by": user,
            "created_at": state["sim_time"], "events": [{"time": state["sim_time"], "text": f"Shipment planned by {user}; "
                                                       f"{a['type_name']} {a['asset_id']} assigned. "
                                                       f"Vehicle ready in {a.get('ready_in_hours', 0):.1f} h, "
                                                       f"then {option.get('loading_hours', 1):.1f} h loading before departure"}],
        }
        state["shipments"].append(ship)
        created.append(ship)
    request["status"] = "DISPATCHED"
    request["dispatched_qty"] = total
    request["source_node"] = src
    request["history"].append({"time": state["sim_time"], "text": f"Dispatched {total:,} via {option['mode'].lower()} "
                                                                  f"from {NODES[src]['name']} ({len(created)} shipment(s))"})
    add_event(state, f"{len(created)} shipment(s) dispatched to {NODES[option['dest']]['name']}: "
                     f"{total:,} {CATEGORIES[cat]['unit']} {CATEGORIES[cat]['name'].lower()} ({option['mode'].lower()})",
              "success", request["id"])
    return created
