"""Synthetic demonstration data generator (deterministic).

Generates 90 days of history, a 45-day weather outlook, inventory, assets,
supply requests, disruptions and IoT devices for the fictional network.
"""
from __future__ import annotations

import math
import zlib
from datetime import datetime, timedelta, timezone

import numpy as np

from .reference import ASSET_TYPES, ASSETS, CATEGORIES, NODES, ROUTES

HISTORY_DAYS = 90
FUTURE_DAYS = 45


def _rng(*parts) -> np.random.RandomState:
    key = "|".join(str(p) for p in parts)
    return np.random.RandomState(zlib.crc32(key.encode()) & 0x7FFFFFFF)


# ---------------------------------------------------------------------------
# Weather
# ---------------------------------------------------------------------------

def _sea_level_temp(doy: int) -> float:
    return 22.0 + 9.0 * math.cos(2 * math.pi * (doy - 200) / 365.0)


def generate_weather(day0: datetime) -> dict:
    """Sector-aware synthetic weather: snow storms in the north, heavy rain in the east,
    dust storms and heat in the western desert, cyclonic storms over the islands."""
    out = {}
    for nid, n in NODES.items():
        rng = _rng("weather", nid)
        sector, terr = n["sector"], n["terrain"]
        series = []
        anomaly = 0.0
        for day in range(-HISTORY_DAYS, FUTURE_DAYS):
            date = day0 + timedelta(days=day)
            doy = date.timetuple().tm_yday
            anomaly = 0.7 * anomaly + rng.normal(0, 1.4)
            temp = (_sea_level_temp(doy) + (30 - n["lat"]) * 0.35 - 6.5 * n["alt"] / 1000.0 + anomaly
                    + (3.0 if terr == "Desert" else 0.0))
            precip_chance = {"NORTH": 0.10 + (0.08 if n["alt"] > 2000 else 0.03), "EAST": 0.30,
                             "WEST": 0.03, "ISLANDS": 0.32}[sector]
            precip = rng.rand() < precip_chance
            precip_mm = round(float(rng.gamma(2.0, 4.0 if sector != "EAST" else 7.0)), 1) if precip else 0.0
            wind = round(float(abs(rng.normal(14 + n["alt"] / 400.0, 7))), 0)
            special = None
            # Northern western-disturbance snow storms
            if sector == "NORTH" and (day in (-21, -20, -19) or day in (1, 2, 3)) and n["lat"] > 33.9 and n["alt"] > 1500:
                precip = True
                precip_mm = round(float(rng.uniform(18, 35)), 1)
                temp -= 5.0
                wind = round(float(rng.uniform(40, 62)), 0) if day == 2 and n["alt"] > 2300 else max(wind, 30)
            # Eastern heavy-rain spells (landslides)
            if sector == "EAST" and (day in (-33, -32) or day in (4, 5)):
                precip = True
                precip_mm = round(float(rng.uniform(55, 90)), 1)
            # Western dust storm and heat spell
            if sector == "WEST" and day in (-40, 2) and n["type"] != "depot":
                special, wind = "Dust storm", round(float(rng.uniform(48, 58)), 0)
            if sector == "WEST" and day in (6, 7, 8):
                temp += 5.0
            # Island cyclonic storm
            if sector == "ISLANDS" and (day in (-28, -27) or day in (4, 5)):
                special, precip, precip_mm = "Storm", True, round(float(rng.uniform(70, 120)), 1)
                wind = round(float(rng.uniform(62, 85)), 0)
            if sector == "ISLANDS" and day == 3:
                wind = max(wind, 46)
            t_min = round(temp - rng.uniform(4, 8) - (4 if terr == "Desert" else 0), 1)
            t_max = round(temp + rng.uniform(4, 7) + (3 if terr == "Desert" else 0), 1)
            cond = "Clear"
            snow_cm = 0
            vis = round(float(rng.uniform(8, 20)), 1)
            if special == "Storm":
                cond, vis = "Storm", round(float(rng.uniform(0.8, 2.0)), 1)
            elif special == "Dust storm":
                cond, vis, precip_mm = "Dust storm", round(float(rng.uniform(0.4, 1.2)), 1), 0.0
            elif precip:
                if temp < 1.5:
                    snow_cm = int(precip_mm * 1.2)
                    cond = "Blizzard" if (snow_cm >= 25 and wind >= 45) else "Snow"
                    vis = round(float(rng.uniform(0.5, 2.0)), 1) if cond == "Blizzard" else round(float(rng.uniform(2, 6)), 1)
                else:
                    cond = "Rain"
                    vis = round(float(rng.uniform(3, 9)), 1)
            elif terr == "Desert" and t_max >= 39:
                cond = "Heatwave"
            elif rng.rand() < 0.08 and n["alt"] < 2200:
                cond = "Fog"
                vis = round(float(rng.uniform(0.8, 3.0)), 1)
            elif rng.rand() < 0.35:
                cond = "Cloudy"
            series.append({
                "day": day, "date": date.date().isoformat(), "temp": round(temp, 1),
                "temp_min": t_min, "temp_max": t_max,
                "cond": cond, "precip_mm": precip_mm, "snow_cm": snow_cm, "wind": wind, "vis_km": vis,
            })
        out[nid] = series
    return out


# ---------------------------------------------------------------------------
# Operations calendar (exercises / surges) - an external factor for forecasting
# ---------------------------------------------------------------------------

FUTURE_OPS = {"FP-F": [(3, 6)], "FP-I": [(8, 11)], "HUB-L": [(10, 12)], "FP-H": [(16, 18)],
              "FP-V": [(2, 5)], "FP-S": [(6, 8)], "FP-Z": [(9, 11)]}


def generate_ops() -> dict:
    out = {}
    for nid in NODES:
        rng = _rng("ops", nid)
        flags = [0] * (HISTORY_DAYS + FUTURE_DAYS)
        for _ in range(2):
            start = int(rng.randint(-85, -10))
            length = int(rng.randint(3, 6))
            for d in range(start, start + length):
                flags[d + HISTORY_DAYS] = 1
        for (a, b) in FUTURE_OPS.get(nid, []):
            for d in range(a, b + 1):
                flags[d + HISTORY_DAYS] = 1
        out[nid] = flags
    return out


# ---------------------------------------------------------------------------
# Ground-truth consumption model (the ML model never sees this formula)
# ---------------------------------------------------------------------------

OPS_MULT = {"AMMO": 2.2, "FUEL": 1.4, "RATIONS": 1.12, "MEDICAL": 1.3, "SPARES": 1.35, "WINTER": 1.0, "WATER": 1.3}


def base_daily(node: str, cat: str) -> float:
    return CATEGORIES[cat]["per_person_day"] * NODES[node]["personnel"]


def true_demand(node: str, cat: str, day: int, w: dict, ops: int, date_weekday: int, noise: bool = True) -> float:
    n = NODES[node]
    base = base_daily(node, cat)
    temp = w["temp"]
    cold = w["cond"] in ("Snow", "Blizzard")
    if cat == "FUEL":
        f = 1 + max(0.0, 12 - temp) * 0.045
    elif cat == "RATIONS":
        f = (1 + n["alt"] / 12000.0) * (1 + max(0.0, 5 - temp) * 0.01)
    elif cat == "WINTER":
        f = max(0.15, 1 + (6 - temp) * 0.09) if temp > 6 else 1 + (6 - temp) * 0.09
    elif cat == "WATER":
        f = 1 + max(0.0, temp - 22) * 0.035 + (0.25 if w["cond"] in ("Heatwave", "Dust storm") else 0)
    elif cat == "MEDICAL":
        f = (1 + (0.25 if n["alt"] > 3000 else 0) + (0.2 if cold else 0) + (0.35 if n["terrain"] == "Jungle" else 0)
             + (0.2 if w["cond"] == "Storm" else 0))
    elif cat == "SPARES":
        f = 1 + (0.25 if w["cond"] in ("Snow", "Blizzard", "Rain", "Storm") else 0) + (0.3 if w["cond"] == "Dust storm" else 0)
    else:
        f = 1.0
    if ops:
        f *= OPS_MULT[cat]
    dow = {6: 0.85, 0: 1.06}.get(date_weekday, 1.0)
    val = base * f * dow
    if noise:
        sigma = 0.15 if cat in ("MEDICAL", "AMMO", "WINTER") else 0.07
        val *= float(_rng("noise", node, cat, day).lognormal(0, sigma))
    return max(0.0, val)


def generate_history(day0: datetime, weather: dict, ops: dict) -> dict:
    hist = {}
    for nid in NODES:
        hist[nid] = {}
        for cat in CATEGORIES:
            vals = []
            for day in range(-HISTORY_DAYS, 0):
                w = weather[nid][day + HISTORY_DAYS]
                wd = (day0 + timedelta(days=day)).weekday()
                vals.append(round(true_demand(nid, cat, day, w, ops[nid][day + HISTORY_DAYS], wd), 2))
            hist[nid][cat] = vals
    return hist


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------

SPECIAL_DAYS = {
    ("FP-E", "FUEL"): 2.0, ("FP-G", "RATIONS"): 3.0, ("FP-I", "MEDICAL"): 1.6, ("FP-J", "WINTER"): 4.0,
    ("FP-H", "AMMO"): 5.0, ("FP-F", "FUEL"): 5.5, ("FP-F", "AMMO"): 7.5, ("HUB-L", "FUEL"): 9.0, ("FP-I", "FUEL"): 7.0,
    ("FP-G", "FUEL"): 8.0, ("FP-H", "RATIONS"): 6.0, ("FP-J", "FUEL"): 6.5,
    # other sectors
    ("FP-W", "WATER"): 1.2, ("FP-T", "MEDICAL"): 1.4, ("FP-Z", "RATIONS"): 1.6, ("FP-R", "WINTER"): 4.5,
    ("HUB-Q", "FUEL"): 8.0, ("FP-V", "WATER"): 6.0, ("FP-X", "FUEL"): 5.5, ("FP-U", "MEDICAL"): 5.0,
    ("FP-V", "AMMO"): 6.0, ("FP-S", "SPARES"): 6.5,
}


def generate_inventory(history: dict) -> dict:
    inv = {}
    for nid, n in NODES.items():
        rng = _rng("inv", nid)
        inv[nid] = {}
        for cat in CATEGORIES:
            avg = float(np.mean(history[nid][cat][-14:]))
            if (nid, cat) in SPECIAL_DAYS:
                days = SPECIAL_DAYS[(nid, cat)]
            elif n["type"] == "post":
                days = float(rng.uniform(11, 22))
            elif n["type"] == "hub":
                days = float(rng.uniform(26, 45))
            else:
                days = float(rng.uniform(70, 95))
            cap_days = {"post": 60, "hub": 90, "depot": 160}[n["type"]]
            inv[nid][cat] = {"on_hand": round(avg * days), "capacity": round(avg * cap_days)}
            # hubs also hold stock for the posts they feed
            if n["type"] == "hub":
                inv[nid][cat]["on_hand"] = round(inv[nid][cat]["on_hand"] * 1.6)
                inv[nid][cat]["capacity"] = round(inv[nid][cat]["capacity"] * 1.6)
            if n["type"] == "depot":
                inv[nid][cat]["on_hand"] = round(inv[nid][cat]["on_hand"] * 3)
                inv[nid][cat]["capacity"] = round(inv[nid][cat]["capacity"] * 3)
    return inv


def generate_assets() -> dict:
    out = {}
    for aid, atype, home in ASSETS:
        t = ASSET_TYPES[atype]
        rng = _rng("asset", aid)
        out[aid] = {
            "id": aid, "type": atype, "type_name": t["name"], "mode": t["mode"], "capacity_kg": t["capacity_kg"],
            "home": home, "location": home, "status": "AVAILABLE", "available_at": None,
            "odometer_km": int(rng.randint(8000, 60000)), "next_service_km": 0, "missions_30d": int(rng.randint(3, 14)),
        }
        out[aid]["next_service_km"] = out[aid]["odometer_km"] + int(rng.randint(400, 5000))
    out["TRK-04"]["status"] = "MAINTENANCE"
    out["TRK-04"]["note"] = "Scheduled engine overhaul"
    out["TRK-04"]["next_service_km"] = out["TRK-04"]["odometer_km"]
    return out


def generate_devices() -> dict:
    devices = {}
    for nid, n in NODES.items():
        if n["type"] in ("post", "hub"):
            devices[f"RFID-{nid}"] = {"id": f"RFID-{nid}", "node": nid, "type": "RFID_GATE",
                                      "label": "RFID stock gate", "unit": "% match", "min": 97, "max": 103}
            devices[f"COLD-{nid}"] = {"id": f"COLD-{nid}", "node": nid, "type": "COLD_CHAIN",
                                      "label": "Medical cold-chain temperature", "unit": "C", "min": 2, "max": 8}
            devices[f"FUEL-{nid}"] = {"id": f"FUEL-{nid}", "node": nid, "type": "FUEL_LEVEL",
                                      "label": "Fuel bladder level sensor", "unit": "%", "min": 8, "max": 100}
        if n["type"] in ("hub", "depot"):
            devices[f"ENV-{nid}"] = {"id": f"ENV-{nid}", "node": nid, "type": "STORE_HUMIDITY",
                                     "label": "Storehouse humidity", "unit": "% RH", "min": 30, "max": 70}
    for d in devices.values():
        rng = _rng("dev", d["id"])
        d.update({"status": "ONLINE", "battery": int(rng.randint(55, 100)), "override": None,
                  "variance_pct": round(float(rng.normal(0, 0.8)), 2), "last_seen": None})
    devices["COLD-FP-I"]["override"] = 9.6
    devices["FUEL-FP-I"]["status"] = "OFFLINE"
    devices["FUEL-FP-I"]["battery"] = 11
    devices["RFID-FP-G"]["variance_pct"] = -4.6
    devices["ENV-HUB-K"]["override"] = 78
    devices["ENV-HUB-Q"]["override"] = 83
    devices["RFID-FP-W"]["variance_pct"] = -3.8
    devices["RFID-FP-J"]["battery"] = 18
    return devices


def generate_delivery_log(day0: datetime) -> list:
    rng = _rng("deliveries")
    log = []
    posts = [n for n, v in NODES.items() if v["type"] != "depot"]
    for i in range(48):
        planned = float(rng.uniform(6, 30))
        late = rng.rand() < 0.12
        actual = planned * (float(rng.uniform(1.12, 1.6)) if late else float(rng.uniform(0.85, 1.08)))
        log.append({"id": f"HIST-{i+1:03d}", "dest": posts[int(rng.randint(0, len(posts)))],
                    "category": list(CATEGORIES)[int(rng.randint(0, len(CATEGORIES)))],
                    "day": -int(rng.randint(1, 30)), "planned_hours": round(planned, 1),
                    "actual_hours": round(actual, 1), "on_time": actual <= planned * 1.1})
    return log


def seed_requests(sim: datetime) -> list:
    def t(hours):
        return (sim + timedelta(hours=hours)).isoformat(timespec="minutes")
    spec = [
        ("FP-I", "MEDICAL", 60, 1, "CRITICAL", "Rising acclimatisation cases; medical stock below safety level", "Post India Medical Officer", -5),
        ("FP-F", "AMMO", 220, 3, "HIGH", "Field firing exercise scheduled for days 3 to 6", "Post Foxtrot Quartermaster", -9),
        ("FP-G", "RATIONS", 2600, 3, "HIGH", "Pre-winter stocking before Razdan Pass snow closure", "Post Golf Quartermaster", -14),
        ("FP-J", "WINTER", 320, 4, "HIGH", "Night temperatures below -12 C; winter kit shortfall", "Post Juliet Commander", -20),
        ("FP-H", "SPARES", 90, 6, "MEDIUM", "Generator and vehicle overhaul before winter", "Post Hotel Transport Officer", -26),
        ("HUB-L", "FUEL", 30000, 5, "HIGH", "Hub reserve below winter stocking norm", "Hub Lima Logistics Cell", -30),
        ("HUB-M", "RATIONS", 8000, 8, "LOW", "Routine monthly maintenance replenishment", "Hub Mike Logistics Cell", -40),
        ("FP-F", "MEDICAL", 25, 9, "MEDIUM", "Exercise medical cover", "Post Foxtrot Medical Officer", -3),
        ("FP-V", "AMMO", 260, 2, "HIGH", "Desert field firing exercise on days 2 to 5", "Post Victor Quartermaster", -6),
        ("HUB-Q", "RATIONS", 20000, 3, "HIGH", "Stock up before the cyclone closes the sea lanes", "Island Hub Logistics Cell", -8),
        ("FP-S", "SPARES", 70, 7, "MEDIUM", "Vehicle repairs after landslide damage", "Post Sierra Transport Officer", -12),
        ("FP-R", "WINTER", 200, 5, "MEDIUM", "Early snowfall at 2,900 m", "Post Romeo Commander", -18),
    ]
    reqs = []
    for i, (node, cat, qty, need_days, urg, reason, by, age) in enumerate(spec, start=1):
        reqs.append({"id": f"REQ-{1000+i}", "node": node, "category": cat, "qty": qty,
                     "needed_by": t(need_days * 24), "declared_urgency": urg, "reason": reason,
                     "raised_by": by, "created_at": t(age), "status": "NEW", "source": "FIELD",
                     "history": [{"time": t(age), "text": f"Request raised by {by}"}]})
    return reqs


def seed_disruptions(sim: datetime) -> list:
    def t(hours):
        return (sim + timedelta(hours=hours)).isoformat(timespec="minutes")
    return [
        {"id": "DIS-001", "type": "WEATHER", "title": "Heavy snowfall at Zoji Pass", "route_id": "R4", "node_id": None,
         "severity": "HIGH", "delay_factor": 1.5, "closes_route": False, "status": "ACTIVE",
         "start": t(-6), "expected_end": t(36), "source": "Met forecast + convoy report",
         "description": "30-40 cm fresh snow, one-way convoy movement only. Expect 50% longer transit."},
        {"id": "DIS-002", "type": "LANDSLIDE", "title": "Landslide at km 51, High Passes Highway", "route_id": "R7",
         "node_id": None, "severity": "CRITICAL", "delay_factor": 1.0, "closes_route": True, "status": "ACTIVE",
         "start": t(-10), "expected_end": t(42), "source": "Road maintenance task force",
         "description": "Road fully blocked. Clearance crew deployed, estimated 42 hours to reopen."},
        {"id": "DIS-003", "type": "CONNECTIVITY", "title": "Satellite data link degraded at Post India", "route_id": None,
         "node_id": "FP-I", "severity": "MEDIUM", "delay_factor": 1.0, "closes_route": False, "status": "ACTIVE",
         "start": t(-4), "expected_end": t(20), "source": "Signals",
         "description": "IoT sensor sync intermittent. Stock figures may be up to 12 hours old."},
        {"id": "DIS-004", "type": "LANDSLIDE", "title": "Landslide debris on Teesta Valley Highway", "route_id": "R13",
         "node_id": None, "severity": "HIGH", "delay_factor": 1.4, "closes_route": False, "status": "ACTIVE",
         "start": t(-3), "expected_end": t(30), "source": "Border roads task force",
         "description": "One lane open after heavy rain. Convoys escorted; expect 40% longer transit."},
        {"id": "DIS-005", "type": "ROAD_DAMAGE", "title": "Sand drift over Southern Desert Road", "route_id": "R20",
         "node_id": None, "severity": "MEDIUM", "delay_factor": 1.25, "closes_route": False, "status": "ACTIVE",
         "start": t(-2), "expected_end": t(26), "source": "Desert patrol",
         "description": "Dunes drifted across 3 km of road after strong winds. Clearance underway."},
    ]


def build_state(now: datetime | None = None) -> dict:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    sim = now.replace(second=0, microsecond=0)  # simulation starts at the real current time
    ist = timezone(timedelta(hours=5, minutes=30))
    day0 = sim.astimezone(ist).replace(hour=0, minute=0)  # days roll over at IST midnight
    weather = generate_weather(day0)
    ops = generate_ops()
    history = generate_history(day0, weather, ops)
    state = {
        "version": 3,
        "seeded_at": now.isoformat(timespec="seconds"),
        "day0": day0.isoformat(),
        "sim_time": sim.isoformat(),
        "history_days": HISTORY_DAYS,
        "weather": weather,
        "ops": ops,
        "history": history,
        "history_end_day": 0,  # history covers days < history_end_day
        "inventory": generate_inventory(history),
        "assets": generate_assets(),
        "requests": seed_requests(sim),
        "shipments": [],
        "disruptions": seed_disruptions(sim),
        "devices": generate_devices(),
        "delivery_log": generate_delivery_log(day0),
        "audit": [],
        "alert_status": {},
        "events": [],
        "counters": {"REQ": 1100, "SHP": 2000, "DIS": 5, "AUD": 0, "EVT": 0, "AI": 0},
        "stats": {"recommendations_approved": 0, "stockouts_prevented": 0, "shipments_delivered": 0},
        "consumed_today": {},
        "clock": {"speed": 1, "last_real": now.isoformat(), "pending_hours": 0.0},
        "ai": {"enabled": True, "critical_mode": "dispatch", "low_mode": "recommend",
               "log": [], "stats": {"auto_requests": 0, "auto_dispatches": 0, "escalations": 0, "scans": 0,
                                    "red_alerts_handled": 0, "avg_response_s": 0.0},
               "cooldown": {}, "first_seen": {}},
    }
    return state
