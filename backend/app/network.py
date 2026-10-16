"""GIS network helpers: distances, weather effects, route conditions, routing and risk."""
from __future__ import annotations

import heapq
import math
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from .reference import NODES, ROUTES

HANDLING_HOURS = 3.0  # loading / unloading / checkpoint time per leg


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def node_distance(a: str, b: str) -> float:
    na, nb = NODES[a], NODES[b]
    return haversine_km(na["lat"], na["lon"], nb["lat"], nb["lon"])


def sim_now(state) -> datetime:
    return parse_time(state["sim_time"])


def day_index(state, when: Optional[datetime] = None) -> int:
    when = when or sim_now(state)
    day0 = parse_time(state["day0"])
    return int(math.floor((when - day0).total_seconds() / 86400.0))


def weather_at(state, node: str, day: int) -> dict:
    series = state["weather"][node]
    idx = max(0, min(len(series) - 1, day + state["history_days"]))
    return series[idx]


# ---------------------------------------------------------------------------
# Weather and disruption effects
# ---------------------------------------------------------------------------

def sea_effect(w: dict) -> Tuple[float, float, List[str], bool]:
    """Sea-state effect for ships: (time multiplier, risk 0-40, factors, closed?)."""
    cond, wind = w["cond"], w["wind"]
    if cond == "Storm" or wind >= 60:
        return 1.0, 40.0, [f"Cyclonic storm at sea, wind {wind} km/h - sailing suspended"], True
    if wind >= 42:
        return 1.35, 26.0, [f"Rough sea, wind {wind} km/h"], False
    if cond == "Rain":
        return 1.1, 8.0, [f"Rain squalls {w['precip_mm']} mm"], False
    return 1.0, 0.0, [], False


def weather_effect(w: dict, snow_prone: bool, landslide_prone: bool) -> Tuple[float, float, List[str], bool]:
    """Return (travel time multiplier, risk points 0-40, factor strings, closed?) for road travel."""
    cond = w["cond"]
    mult, risk, factors, closed = 1.0, 0.0, [], False
    if cond == "Storm":
        mult, risk = 1.6, 30
        factors.append(f"Cyclonic storm, {w['precip_mm']} mm rain, wind {w['wind']} km/h")
        if landslide_prone:
            closed = True
            factors.append("Landslide-prone road closed in storm")
    elif cond == "Dust storm":
        mult, risk = 1.35, 18
        factors.append(f"Dust storm, visibility {w['vis_km']} km")
    elif cond == "Heatwave":
        mult, risk = 1.08, 6
        factors.append(f"Heatwave {w['temp_max']} C - vehicle overheating and crew fatigue")
    elif cond == "Blizzard":
        mult, risk = 1.9, 38
        factors.append(f"Blizzard ({w['snow_cm']} cm snow, wind {w['wind']} km/h)")
        if snow_prone:
            closed = True
            factors.append("Snow-prone pass likely closed in blizzard")
    elif cond == "Snow":
        mult, risk = (1.45 if snow_prone else 1.2), (26 if snow_prone else 14)
        factors.append(f"Snowfall {w['snow_cm']} cm expected")
    elif cond == "Rain":
        mult, risk = 1.15, 8
        factors.append(f"Rain {w['precip_mm']} mm")
        if landslide_prone:
            risk += 7
            factors.append("Landslide-prone stretch in rain")
    elif cond == "Fog":
        mult, risk = 1.12, 6
        factors.append(f"Fog, visibility {w['vis_km']} km")
    if w["temp_min"] < -8 and cond not in ("Blizzard",):
        risk += 4
        factors.append(f"Black-ice risk (min {w['temp_min']} C)")
    return mult, min(risk, 40.0), factors, closed


def air_effect(w: dict) -> Tuple[bool, float, List[str]]:
    """Helicopter/drone flyability. Returns (can_fly, risk 0-40, factors)."""
    factors = []
    if w["cond"] in ("Blizzard", "Storm", "Dust storm") or w["vis_km"] < 2.5 or w["wind"] > 50:
        return False, 40, [f"Grounded: {w['cond']}, vis {w['vis_km']} km, wind {w['wind']} km/h"]
    risk = 0
    if w["cond"] == "Snow":
        risk += 18
        factors.append("Snow showers: reduced flying window")
    if w["wind"] > 35:
        risk += 10
        factors.append(f"Strong winds {w['wind']} km/h")
    if w["vis_km"] < 5:
        risk += 8
        factors.append(f"Low visibility {w['vis_km']} km")
    return True, float(risk), factors


def active_disruptions(state, route_id: Optional[str] = None, node: Optional[str] = None) -> List[dict]:
    now = sim_now(state)
    out = []
    for d in state["disruptions"]:
        if d["status"] != "ACTIVE":
            continue
        if d.get("expected_end") and parse_time(d["expected_end"]) <= now:
            continue
        if route_id and d.get("route_id") != route_id:
            continue
        if node and d.get("node_id") != node:
            continue
        out.append(d)
    return out


def route_condition(state, rid: str, day: int, overrides: Optional[dict] = None) -> dict:
    """Combined weather + disruption condition of a road route for a given day."""
    overrides = overrides or {}
    r = ROUTES[rid]
    wa, wb = weather_at(state, r["a"], day), weather_at(state, r["b"], day)
    if overrides.get("severe_weather") and r["mode"] == "SEA":
        pass
    elif overrides.get("severe_weather") and r["snow_prone"]:
        wa = dict(wa, cond="Blizzard", snow_cm=max(wa["snow_cm"], 40), wind=max(wa["wind"], 55), vis_km=1.0)
    elif overrides.get("severe_weather"):
        terr = NODES[r["a"]]["terrain"]
        cond = "Dust storm" if terr == "Desert" else "Snow" if NODES[r["a"]]["alt"] > 1500 else "Storm" if terr in ("Island", "Coastal") else "Rain"
        wa = dict(wa, cond=cond, snow_cm=10, precip_mm=40, vis_km=1.0 if cond == "Dust storm" else wa["vis_km"])
    if overrides.get("severe_weather") and r["mode"] == "SEA":
        wa = dict(wa, cond="Storm", wind=70, precip_mm=60, vis_km=1.0)
    worst = max([wa, wb], key=lambda w: (_cond_rank(w["cond"]), w["wind"]))
    if r["mode"] == "SEA":
        mult, wrisk, factors, closed = sea_effect(worst)
    else:
        mult, wrisk, factors, closed = weather_effect(worst, r["snow_prone"], r["landslide_prone"])
    drisk = 0.0
    disruptions = []
    for d in active_disruptions(state, route_id=rid):
        disruptions.append(d)
        mult *= d.get("delay_factor", 1.0)
        drisk = max(drisk, {"LOW": 8, "MEDIUM": 15, "HIGH": 24, "CRITICAL": 30}.get(d["severity"], 10))
        factors.append(f"{d['type']}: {d['title']}")
        if d.get("closes_route"):
            closed = True
    if rid in overrides.get("closed_routes", []):
        closed = True
        drisk = 30
        factors.append("Route closed in scenario")
    status = "CLOSED" if closed else ("RESTRICTED" if (mult > 1.3 or drisk >= 15) else "OPEN")
    return {"route_id": rid, "mode": r["mode"], "status": status, "time_mult": round(mult, 2), "weather_risk": wrisk,
            "disruption_risk": drisk, "factors": factors, "closed": closed,
            "weather": worst["cond"], "disruptions": [d["id"] for d in disruptions]}


_COND_CACHE: Dict[tuple, dict] = {}


def all_conditions(state, day: int, overrides: Optional[dict] = None) -> Dict[str, dict]:
    """Route conditions for every route, cached per (time, day, disruptions, overrides)."""
    dsig = tuple((d["id"], d["status"], d.get("expected_end")) for d in state["disruptions"])
    key = (state["sim_time"], state.get("day0"), day, dsig, repr(sorted((overrides or {}).items())))
    hit = _COND_CACHE.get(key)
    if hit is None:
        if len(_COND_CACHE) > 400:
            _COND_CACHE.clear()
        hit = {rid: route_condition(state, rid, day, overrides) for rid in ROUTES}
        _COND_CACHE[key] = hit
    return hit


def _cond_rank(c: str) -> int:
    return {"Clear": 0, "Cloudy": 1, "Heatwave": 2, "Fog": 2, "Rain": 3, "Dust storm": 4, "Snow": 4,
            "Storm": 5, "Blizzard": 5}.get(c, 0)


def neighbours(node: str, modes=("ROAD", "SEA")):
    for rid, r in ROUTES.items():
        if r["mode"] not in modes:
            continue
        if r["a"] == node:
            yield rid, r["b"]
        elif r["b"] == node:
            yield rid, r["a"]


def route_hours(rid: str, mult: float = 1.0, speed_factor: float = 1.0) -> float:
    r = ROUTES[rid]
    return r["km"] / (r["speed"] * speed_factor) * mult


def shortest_path(state, src: str, dst: str, day: Optional[int] = None, overrides: Optional[dict] = None,
                  speed_factor: float = 1.0, allow_closed: bool = False, modes=("ROAD", "SEA")) -> Optional[dict]:
    """Dijkstra on the transport graph (road and/or sea lanes). Cost = travel hours weighted by risk."""
    if src == dst:
        return {"nodes": [src], "routes": [], "hours": 0.0, "km": 0.0, "conditions": []}
    day = day_index(state) if day is None else day
    conds = all_conditions(state, day, overrides)
    dist = {src: 0.0}
    prev: Dict[str, Tuple[str, str]] = {}
    pq = [(0.0, src)]
    while pq:
        cost, u = heapq.heappop(pq)
        if u == dst:
            break
        if cost > dist.get(u, math.inf):
            continue
        for rid, v in neighbours(u, modes):
            c = conds[rid]
            if c["closed"] and not allow_closed:
                continue
            hrs = route_hours(rid, c["time_mult"], speed_factor)
            risk_w = 1 + (ROUTES[rid]["base_risk"] + c["weather_risk"] + c["disruption_risk"]) / 200.0
            nc = cost + hrs * risk_w
            if nc < dist.get(v, math.inf):
                dist[v] = nc
                prev[v] = (u, rid)
                heapq.heappush(pq, (nc, v))
    if dst not in dist:
        return None
    nodes, routes = [dst], []
    cur = dst
    while cur != src:
        p, rid = prev[cur]
        nodes.append(p)
        routes.append(rid)
        cur = p
    nodes.reverse()
    routes.reverse()
    hours = sum(route_hours(r, conds[r]["time_mult"], speed_factor) for r in routes) + HANDLING_HOURS
    km = sum(ROUTES[r]["km"] for r in routes)
    return {"nodes": nodes, "routes": routes, "hours": round(hours, 1), "km": km,
            "conditions": [conds[r] for r in routes]}


def polyline(nodes: List[str], routes: List[str]) -> List[List[float]]:
    """Ordered list of [lat, lon] along a path."""
    coords = [[NODES[nodes[0]]["lat"], NODES[nodes[0]]["lon"]]]
    for i, rid in enumerate(routes):
        r = ROUTES[rid]
        wp = list(r["wp"])
        if r["a"] != nodes[i]:
            wp = wp[::-1]
        coords.extend(wp)
        coords.append([NODES[nodes[i + 1]]["lat"], NODES[nodes[i + 1]]["lon"]])
    return coords


def straight_line(a: str, b: str) -> List[List[float]]:
    return [[NODES[a]["lat"], NODES[a]["lon"]], [NODES[b]["lat"], NODES[b]["lon"]]]


def point_along(coords: List[List[float]], fraction: float) -> List[float]:
    fraction = max(0.0, min(1.0, fraction))
    segs = []
    total = 0.0
    for i in range(len(coords) - 1):
        d = haversine_km(coords[i][0], coords[i][1], coords[i + 1][0], coords[i + 1][1])
        segs.append(d)
        total += d
    if total == 0:
        return coords[0]
    target = total * fraction
    acc = 0.0
    for i, d in enumerate(segs):
        if acc + d >= target:
            t = (target - acc) / d if d else 0
            return [coords[i][0] + (coords[i + 1][0] - coords[i][0]) * t,
                    coords[i][1] + (coords[i + 1][1] - coords[i][1]) * t]
        acc += d
    return coords[-1]


def risk_level(score: float) -> str:
    if score >= 65:
        return "CRITICAL"
    if score >= 45:
        return "HIGH"
    if score >= 25:
        return "MODERATE"
    return "LOW"


def assess_road_risk(state, routes: List[str], day: int, overrides: Optional[dict] = None) -> dict:
    """Risk score 0-100 with explainable breakdown for a road journey."""
    if not routes:
        return {"score": 0, "level": "LOW", "breakdown": {}, "factors": ["Same location"]}
    allc = all_conditions(state, day, overrides)
    conds = [allc[r] for r in routes]
    weather = max(c["weather_risk"] for c in conds)
    road = max(c["disruption_risk"] for c in conds)
    max_alt = max(ROUTES[r]["max_alt"] for r in routes)
    terrain = min(15.0, max(0.0, (max_alt - 1500) / 260.0))
    on_time = min(ROUTES[r]["on_time_rate"] for r in routes)
    hist = round((1 - on_time) * 50, 1)
    hist = min(hist, 15.0)
    score = round(min(100.0, weather + road + terrain + hist), 1)
    factors = []
    for c in conds:
        for f in c["factors"]:
            factors.append(f"{ROUTES[c['route_id']]['name']}: {f}")
    factors.append(f"Highest point on route: {max_alt} m")
    factors.append(f"Historical on-time rate on worst leg: {int(on_time * 100)}%")
    return {"score": score, "level": risk_level(score),
            "breakdown": {"weather": round(weather, 1), "road_condition": round(road, 1),
                          "terrain_altitude": round(terrain, 1), "historical_delays": hist},
            "factors": factors}


def assess_air_risk(state, a: str, b: str, day: int, overrides: Optional[dict] = None) -> dict:
    wa, wb = weather_at(state, a, day), weather_at(state, b, day)
    if overrides and overrides.get("severe_weather"):
        wb = dict(wb, cond="Blizzard", vis_km=1.0, wind=60)
    ok1, r1, f1 = air_effect(wa)
    ok2, r2, f2 = air_effect(wb)
    alt = max(NODES[a]["alt"], NODES[b]["alt"])
    terrain = min(15.0, max(0.0, (alt - 2000) / 200.0))
    weather = max(r1, r2)
    score = round(min(100, weather + terrain + 5), 1)
    return {"score": score, "level": risk_level(score), "can_fly": ok1 and ok2,
            "breakdown": {"weather": weather, "road_condition": 0, "terrain_altitude": round(terrain, 1),
                          "historical_delays": 5},
            "factors": (f1 + f2) or ["Flying conditions acceptable"]}
