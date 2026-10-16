"""LogiSentinel - Predictive Logistics & Forward Supply Chain API (FastAPI)."""
from __future__ import annotations

import csv
from contextlib import asynccontextmanager
import io
import json
import os
import urllib.request
from datetime import timedelta
from pathlib import Path
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import alerts as alerts_mod
from . import ai as ai_mod
from . import clock, iot, network as net, planning, reports, scenario, sim
from .auth import authenticate, create_token, current_user, require
from .forecast import ENGINE
from .reference import ASSET_TYPES, CATEGORIES, NODES, ROUTES, SECTORS, USERS
from .store import STORE

@asynccontextmanager
async def lifespan(_app):
    STORE.init()
    clock.start()
    yield
    clock.stop()


app = FastAPI(title="LogiSentinel API", version="3.0.0", lifespan=lifespan,
              description="Predictive logistics & forward supply chain decision-support system (synthetic demo data).")

origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


def S() -> dict:
    return STORE.state


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class LoginIn(BaseModel):
    username: str = Field(..., max_length=40)
    password: str = Field(..., max_length=80)


class RequestIn(BaseModel):
    node: str
    category: str
    qty: float = Field(..., gt=0, le=1_000_000)
    needed_in_days: float = Field(3, gt=0, le=60)
    urgency: str = "MEDIUM"
    reason: str = Field("", max_length=300)


class NoteIn(BaseModel):
    note: str = Field("", max_length=300)


class ApproveRecIn(BaseModel):
    auto_dispatch: bool = False
    qty: Optional[float] = Field(None, gt=0)


class DispatchIn(BaseModel):
    option_id: str = "OPT-1"


class DisruptionIn(BaseModel):
    type: str = "WEATHER"
    title: str = Field(..., max_length=120)
    route_id: Optional[str] = None
    node_id: Optional[str] = None
    severity: str = "HIGH"
    closes_route: bool = False
    delay_factor: float = Field(1.5, ge=1.0, le=4.0)
    duration_hours: float = Field(24, gt=0, le=720)
    description: str = Field("", max_length=400)


class AdvanceIn(BaseModel):
    hours: float = Field(6, gt=0, le=168)


class ClockIn(BaseModel):
    speed: int = Field(1, ge=0, le=1440)


class AiConfigIn(BaseModel):
    enabled: Optional[bool] = None
    critical_mode: Optional[str] = None   # dispatch | request | off
    low_mode: Optional[str] = None        # request | recommend


class IngestIn(BaseModel):
    device_id: str
    value: float


class ScenarioIn(BaseModel):
    name: str = "Custom scenario"
    demand_change_pct: float = Field(0, ge=-50, le=200)
    demand_nodes: List[str] = []
    demand_categories: List[str] = []
    closed_routes: List[str] = []
    unavailable_assets: List[str] = []
    severe_weather: bool = False
    extra_lead_hours: float = Field(0, ge=0, le=240)
    horizon_days: int = Field(14, ge=3, le=30)


def _check_node(n):
    if n not in NODES:
        raise HTTPException(404, f"Unknown location '{n}'")


def _check_cat(c):
    if c not in CATEGORIES:
        raise HTTPException(404, f"Unknown category '{c}'")


def _find_request(rid):
    r = next((x for x in S()["requests"] if x["id"] == rid), None)
    if not r:
        raise HTTPException(404, f"Request {rid} not found")
    return r


# ---------------------------------------------------------------------------
# Public
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    return {"status": "ok", "sim_time": S().get("sim_time"), "model": ENGINE.meta.get("model")}


@app.get("/api/config/demo-info")
def demo_info():
    return {"name": "LogiSentinel", "version": app.version,
            "note": "All locations, units and figures are synthetic and for demonstration only.",
            "demo_users": [{"username": u, "password": d["password"], "role": d["role"], "name": d["name"], "title": d["title"]}
                           for u, d in USERS.items()]}


@app.post("/api/auth/login")
def login(body: LoginIn):
    user = authenticate(body.username, body.password)
    if not user:
        raise HTTPException(401, "Wrong username or password")
    with STORE.lock:
        STORE.audit(user, "LOGIN", user["username"], "Signed in")
        STORE.save()
    return {"access_token": create_token(user), "token_type": "bearer", "user": user}


@app.get("/api/auth/me")
def me(user=Depends(current_user)):
    return user


# ---------------------------------------------------------------------------
# Read endpoints (any logged-in role)
# ---------------------------------------------------------------------------

@app.get("/api/status")
def status(user=Depends(current_user)):
    with STORE.lock:
        st = S()
        al = [a for a in alerts_mod.generate(st) if a["status"] == "NEW"]
        ai = st.get("ai", {})
        last = ai.get("log", [None])[0] if ai.get("log") else None
        return {"sim_time": st["sim_time"], "alerts_new": len(al), "clock": clock.info(st),
                "ai": {"enabled": ai.get("enabled", True), "critical_mode": ai.get("critical_mode"),
                       "actions": len(ai.get("log", [])), "last": last, "handled": ai.get("stats", {}).get("red_alerts_handled", 0)},
                "alerts_critical": sum(1 for a in al if a["severity"] == "CRITICAL"),
                "pending_requests": sum(1 for r in st["requests"] if r["status"] in ("NEW", "APPROVED")),
                "model_version": ENGINE.meta.get("version")}


@app.get("/api/reference")
def reference(user=Depends(current_user)):
    return {"nodes": NODES, "routes": {k: {kk: vv for kk, vv in v.items() if kk != "wp"} for k, v in ROUTES.items()},
            "categories": CATEGORIES, "asset_types": ASSET_TYPES, "sectors": SECTORS, "sim_time": S()["sim_time"]}


@app.get("/api/dashboard")
def dashboard(user=Depends(current_user)):
    with STORE.lock:
        return reports.dashboard(S())


@app.get("/api/map")
def network_map(user=Depends(current_user)):
    with STORE.lock:
        return reports.network_map(S())


@app.get("/api/forecast/model")
def forecast_model(user=Depends(current_user)):
    return ENGINE.meta


@app.get("/api/forecast/overview")
def forecast_overview(user=Depends(current_user)):
    with STORE.lock:
        st = S()
        fc = ENGINE.forecast_all(st, 30)
        rows = []
        for (n, c), f in fc.items():
            last7 = sum(st["history"][n][c][-7:])
            next7 = sum(f["mean"][:7])
            rows.append({"node": n, "node_name": NODES[n]["name"], "type": NODES[n]["type"], "sector": NODES[n]["sector"], "category": c,
                         "category_name": CATEGORIES[c]["name"], "unit": CATEGORIES[c]["unit"],
                         "last7": round(last7, 1), "next7": round(next7, 1), "next30": round(sum(f["mean"]), 1),
                         "change_pct": round((next7 / max(last7, 1e-6) - 1) * 100, 1), "confidence": f["confidence"]})
        return {"rows": rows, "model": ENGINE.meta}


@app.get("/api/forecast")
def forecast(node: str, category: str, horizon: int = Query(14, ge=7, le=30), user=Depends(current_user)):
    _check_node(node)
    _check_cat(category)
    with STORE.lock:
        st = S()
        f = ENGINE.forecast_all(st, 30)[(node, category)]
        end = st["history_end_day"]
        day0 = net.parse_time(st["day0"])
        hd = st["history_days"]
        hist = st["history"][node][category]
        series = []
        for i in range(45, 0, -1):
            d = end - i
            w = net.weather_at(st, node, d)
            series.append({"date": (day0 + timedelta(days=d)).date().isoformat(), "actual": round(hist[-i], 2),
                           "temp": w["temp"], "ops": st["ops"][node][d + hd]})
        for h in range(horizon):
            d = end + h
            w = net.weather_at(st, node, d)
            series.append({"date": (day0 + timedelta(days=d)).date().isoformat(), "forecast": f["mean"][h],
                           "lower": f["lower"][h], "upper": f["upper"][h], "band": [f["lower"][h], f["upper"][h]],
                           "temp": w["temp"], "cond": w["cond"], "ops": st["ops"][node][min(len(st["ops"][node]) - 1, d + hd)]})
        ctx = planning.Ctx(st)
        inv = ctx.status(node, category)
        total = sum(f["mean"][:horizon])
        return {"node": node, "node_name": NODES[node]["name"], "category": category,
                "category_name": CATEGORIES[category]["name"], "unit": CATEGORIES[category]["unit"],
                "horizon": horizon, "series": series, "total": round(total, 1),
                "total_lower": round(sum(f["lower"][:horizon]), 1), "total_upper": round(sum(f["upper"][:horizon]), 1),
                "avg_daily": round(total / horizon, 1), "confidence": f["confidence"],
                "factors": ENGINE.explain(st, node, category, f), "inventory": inv, "model": ENGINE.meta}


@app.get("/api/inventory")
def inventory(user=Depends(current_user)):
    with STORE.lock:
        ctx = planning.Ctx(S())
        rows = []
        for n, meta in NODES.items():
            for c, cm in CATEGORIES.items():
                st = ctx.status(n, c)
                rows.append({**st, "node_name": meta["name"], "node_type": meta["type"], "sector": meta["sector"],
                             "category_name": cm["name"],
                             "weight_t": round(st["on_hand"] * cm["kg_per_unit"] / 1000, 2)})
        return {"rows": rows}


@app.get("/api/replenishment")
def replenishment(user=Depends(current_user)):
    with STORE.lock:
        st = S()
        recs = planning.recommendations(st)
        snoozed = st.get("snoozed", {})
        now = net.sim_now(st)
        recs = [r for r in recs if not (r["id"] in snoozed and net.parse_time(snoozed[r["id"]]) > now)]
        return {"recommendations": recs}


@app.get("/api/requests")
def requests_list(user=Depends(current_user)):
    with STORE.lock:
        return {"requests": planning.prioritise(S())}


@app.get("/api/requests/{rid}/plan")
def request_plan(rid: str, user=Depends(current_user)):
    with STORE.lock:
        r = _find_request(rid)
        return planning.plan_options(S(), r["node"], r["category"], r["qty"], r["needed_by"])


@app.get("/api/shipments")
def shipments(user=Depends(current_user)):
    with STORE.lock:
        st = S()
        out = []
        for s in sorted(st["shipments"], key=lambda x: x["created_at"], reverse=True):
            out.append({**s, "source_name": NODES[s["source"]]["name"], "dest_name": NODES[s["dest"]]["name"],
                        "sector": NODES[s["dest"]]["sector"],
                        "category_name": CATEGORIES[s["category"]]["name"], "unit": CATEGORIES[s["category"]]["unit"]})
        return {"shipments": out}


@app.get("/api/assets")
def assets(user=Depends(current_user)):
    with STORE.lock:
        st = S()
        out = []
        for a in st["assets"].values():
            mission = next((s for s in st["shipments"] if s["asset_id"] == a["id"] and
                            s["status"] in ("SCHEDULED", "LOADING", "IN_TRANSIT", "DELAYED", "HOLDING")), None)
            out.append({**a, "location_name": NODES[a["location"]]["name"], "home_name": NODES[a["home"]]["name"],
                        "sector": NODES[a["home"]]["sector"],
                        "mission": mission["id"] if mission else None,
                        "km_to_service": a["next_service_km"] - a["odometer_km"]})
        return {"assets": out}


@app.get("/api/weather")
def weather(user=Depends(current_user)):
    with STORE.lock:
        st = S()
        day = net.day_index(st)
        nodes = []
        for n, meta in NODES.items():
            nodes.append({"node": n, "name": meta["name"], "alt": meta["alt"], "type": meta["type"], "sector": meta["sector"],
                          "terrain": meta["terrain"],
                          "days": [net.weather_at(st, n, day + k) for k in range(7)]})
        routes = []
        for rid, r in ROUTES.items():
            outlook = []
            for k in range(4):
                c = net.route_condition(st, rid, day + k)
                outlook.append({"day": k, "status": c["status"], "time_mult": c["time_mult"], "weather": c["weather"],
                                "risk": net.assess_road_risk(st, [rid], day + k)["score"]})
            routes.append({"id": rid, "name": r["name"], "a": NODES[r["a"]]["name"], "b": NODES[r["b"]]["name"],
                           "mode": r["mode"], "sector": NODES[r["a"]]["sector"],
                           "km": r["km"], "max_alt": r["max_alt"], "snow_prone": r["snow_prone"], "outlook": outlook,
                           "factors": net.route_condition(st, rid, day)["factors"]})
        return {"nodes": nodes, "routes": routes}


@app.get("/api/weather/live")
def weather_live(user=Depends(current_user)):
    """Optional: real current weather for the same coordinates from Open-Meteo (needs internet)."""
    ids = list(NODES)
    lat = ",".join(str(NODES[i]["lat"]) for i in ids)
    lon = ",".join(str(NODES[i]["lon"]) for i in ids)
    url = (f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
           f"&current=temperature_2m,wind_speed_10m,weather_code,snowfall,precipitation")
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        if isinstance(data, dict):
            data = [data]
        out = []
        for i, d in zip(ids, data):
            cur = d.get("current", {})
            out.append({"node": i, "name": NODES[i]["name"], "temp": cur.get("temperature_2m"),
                        "wind": cur.get("wind_speed_10m"), "code": cur.get("weather_code"),
                        "snowfall": cur.get("snowfall"), "precip": cur.get("precipitation")})
        return {"available": True, "source": "Open-Meteo", "data": out}
    except Exception as exc:  # offline venues are common - fail gracefully
        return {"available": False, "reason": f"Live weather not reachable ({type(exc).__name__}). Using simulated weather."}


@app.get("/api/disruptions")
def disruptions(user=Depends(current_user)):
    with STORE.lock:
        st = S()
        out = []
        for d in st["disruptions"]:
            affected = [s["id"] for s in st["shipments"] if d.get("route_id") and d["route_id"] in s["routes"]
                        and s["status"] in ("SCHEDULED", "LOADING", "IN_TRANSIT", "DELAYED", "HOLDING")]
            out.append({**d, "route_name": ROUTES[d["route_id"]]["name"] if d.get("route_id") else None,
                        "sector": NODES[d["node_id"] or ROUTES[d["route_id"]]["a"]]["sector"],
                        "node_name": NODES[d["node_id"]]["name"] if d.get("node_id") else None, "affected_shipments": affected})
        return {"disruptions": sorted(out, key=lambda d: (d["status"] != "ACTIVE", d["start"]), reverse=False)}


@app.get("/api/alerts")
def alerts(user=Depends(current_user)):
    with STORE.lock:
        return {"alerts": alerts_mod.generate(S())}


@app.get("/api/iot")
def iot_list(user=Depends(current_user)):
    with STORE.lock:
        st = S()
        return {"devices": iot.all_readings(st), "inventory_accuracy_pct": iot.inventory_accuracy(st)}


@app.get("/api/scenarios/presets")
def scenario_presets(user=Depends(current_user)):
    return {"presets": scenario.PRESETS}


@app.post("/api/scenarios/run")
def scenario_run(body: ScenarioIn, user=Depends(require("planner"))):
    with STORE.lock:
        res = scenario.run(S(), body.model_dump() if hasattr(body, "model_dump") else body.dict())
        STORE.audit(user, "RUN_SCENARIO", body.name, f"Impact {res['impact']}; readiness "
                    f"{res['baseline']['readiness_index']} -> {res['scenario']['readiness_index']}")
        STORE.save()
        return res


@app.get("/api/reports/sitrep", response_class=PlainTextResponse)
def sitrep(user=Depends(current_user)):
    with STORE.lock:
        return reports.sitrep(S())


@app.get("/api/reports/summary")
def report_summary(user=Depends(current_user)):
    with STORE.lock:
        st = S()
        ctx = planning.Ctx(st)
        k = reports.kpis(st, ctx)
        by_status = {}
        for r in st["requests"]:
            by_status[r["status"]] = by_status.get(r["status"], 0) + 1
        ship_status = {}
        for s in st["shipments"]:
            ship_status[s["status"]] = ship_status.get(s["status"], 0) + 1
        actions = {}
        for a in st["audit"]:
            actions[a["action"]] = actions.get(a["action"], 0) + 1
        return {"kpis": k, "requests_by_status": by_status, "shipments_by_status": ship_status,
                "audit_actions": actions, "model": ENGINE.meta, "sim_time": st["sim_time"]}


@app.get("/api/export/{kind}.csv")
def export_csv(kind: str, user=Depends(current_user)):
    with STORE.lock:
        st = S()
        buf = io.StringIO()
        w = csv.writer(buf)
        if kind == "inventory":
            ctx = planning.Ctx(st)
            w.writerow(["location", "category", "on_hand", "unit", "days_of_supply", "safety_stock", "reorder_point",
                        "incoming", "status"])
            for n in NODES:
                for c in CATEGORIES:
                    s = ctx.status(n, c)
                    w.writerow([NODES[n]["name"], CATEGORIES[c]["name"], s["on_hand"], s["unit"], s["days_of_supply"],
                                s["safety_stock"], s["reorder_point"], s["incoming_qty"], s["status"]])
        elif kind == "shipments":
            w.writerow(["id", "request", "from", "to", "category", "qty", "mode", "asset", "status", "planned_departure",
                        "eta", "delay_hours", "risk"])
            for s in st["shipments"]:
                w.writerow([s["id"], s["request_id"], NODES[s["source"]]["name"], NODES[s["dest"]]["name"],
                            CATEGORIES[s["category"]]["name"], s["qty"], s["mode"], s["asset_id"], s["status"],
                            s["planned_departure"], s["eta"], s["delay_hours"], s["risk"]["score"]])
        elif kind == "requests":
            w.writerow(["id", "location", "category", "qty", "needed_by", "status", "reason", "raised_by"])
            for r in st["requests"]:
                w.writerow([r["id"], NODES[r["node"]]["name"], CATEGORIES[r["category"]]["name"], r["qty"],
                            r["needed_by"], r["status"], r["reason"], r["raised_by"]])
        elif kind == "audit":
            w.writerow(["id", "time_utc", "sim_time", "user", "role", "action", "entity", "details"])
            for a in st["audit"]:
                w.writerow([a["id"], a["time"], a["sim_time"], a["user"], a["role"], a["action"], a["entity"], a["details"]])
        else:
            raise HTTPException(404, "Unknown export")
        return Response(buf.getvalue(), media_type="text/csv",
                        headers={"Content-Disposition": f"attachment; filename=logisentinel_{kind}.csv"})


@app.get("/api/audit")
def audit(user=Depends(require("planner"))):
    return {"audit": S()["audit"][:300]}


@app.get("/api/events")
def events(user=Depends(current_user)):
    return {"events": S()["events"][:60], "sim_time": S()["sim_time"]}


# ---------------------------------------------------------------------------
# Actions (planner+)
# ---------------------------------------------------------------------------

@app.post("/api/sim/advance")
def advance(body: AdvanceIn, user=Depends(require("planner"))):
    """Skip ahead: jump the simulation forward instantly (the AI Autopilot reacts right after)."""
    with STORE.lock:
        res = sim.advance(S(), body.hours)
        acted = ai_mod.scan(S(), trigger="skip")
        res["ai_actions"] = len(acted)
        STORE.audit(user, "SKIP_AHEAD", "simulation", f"+{body.hours} h -> {res['sim_time']}")
        STORE.save()
        return res


@app.post("/api/clock")
def set_clock(body: ClockIn, user=Depends(require("planner"))):
    if body.speed not in clock.SPEEDS:
        raise HTTPException(422, f"Speed must be one of {list(clock.SPEEDS)}")
    with STORE.lock:
        c = S().setdefault("clock", {})
        c["speed"] = body.speed
        STORE.audit(user, "SET_CLOCK_SPEED", "simulation", clock.SPEEDS[body.speed])
        STORE.save()
        return clock.info(S())


@app.get("/api/ai")
def ai_status(user=Depends(current_user)):
    with STORE.lock:
        st = S()
        a = st.get("ai", {})
        return {"enabled": a.get("enabled", True), "critical_mode": a.get("critical_mode", "dispatch"),
                "low_mode": a.get("low_mode", "recommend"), "stats": a.get("stats", {}), "log": a.get("log", [])[:150],
                "last_scan": a.get("last_scan"), "model": ENGINE.meta, "sim_time": st["sim_time"],
                "watching": sum(1 for n in NODES.values() if n["type"] != "depot") * len(CATEGORIES)}


@app.post("/api/ai/config")
def ai_config(body: AiConfigIn, user=Depends(require("planner"))):
    with STORE.lock:
        a = S().setdefault("ai", {})
        if body.enabled is not None:
            a["enabled"] = body.enabled
        if body.critical_mode in ("dispatch", "request", "off"):
            a["critical_mode"] = body.critical_mode
        if body.low_mode in ("request", "recommend"):
            a["low_mode"] = body.low_mode
        a["cooldown"] = {}
        STORE.audit(user, "AI_CONFIG", "autopilot", f"enabled={a.get('enabled')} critical={a.get('critical_mode')} amber={a.get('low_mode')}")
        STORE.save()
        return {"enabled": a.get("enabled"), "critical_mode": a.get("critical_mode"), "low_mode": a.get("low_mode")}


@app.post("/api/ai/scan")
def ai_scan(user=Depends(require("planner"))):
    with STORE.lock:
        acted = ai_mod.scan(S(), trigger="manual")
        STORE.audit(user, "AI_SCAN", "autopilot", f"{len(acted)} action(s)")
        STORE.save()
        return {"actions": acted}


@app.post("/api/requests")
def create_request(body: RequestIn, user=Depends(require("planner"))):
    _check_node(body.node)
    _check_cat(body.category)
    with STORE.lock:
        st = S()
        rid = planning.next_id(st, "REQ")
        now = net.sim_now(st)
        r = {"id": rid, "node": body.node, "category": body.category, "qty": round(body.qty),
             "needed_by": net.iso(now + timedelta(days=body.needed_in_days)), "declared_urgency": body.urgency.upper(),
             "reason": body.reason or "Field demand", "raised_by": user["name"], "created_at": st["sim_time"],
             "status": "NEW", "source": "FIELD", "history": [{"time": st["sim_time"], "text": f"Raised by {user['name']}"}]}
        st["requests"].append(r)
        planning.add_event(st, f"New supply request {rid}: {r['qty']:,} {CATEGORIES[body.category]['unit']} "
                               f"{CATEGORIES[body.category]['name'].lower()} for {NODES[body.node]['name']}", "info", rid)
        STORE.audit(user, "CREATE_REQUEST", rid, f"{r['qty']} {body.category} for {body.node}")
        STORE.save()
        return r


@app.post("/api/requests/{rid}/approve")
def approve_request(rid: str, body: NoteIn = NoteIn(), user=Depends(require("planner"))):
    with STORE.lock:
        r = _find_request(rid)
        if r["status"] != "NEW":
            raise HTTPException(409, f"Request is {r['status']}, only NEW requests can be approved")
        r["status"] = "APPROVED"
        r["approved_by"] = user["name"]
        r["history"].append({"time": S()["sim_time"], "text": f"Approved by {user['name']}" + (f": {body.note}" if body.note else "")})
        STORE.audit(user, "APPROVE_REQUEST", rid, body.note or "Approved")
        STORE.save()
        return r


@app.post("/api/requests/{rid}/reject")
def reject_request(rid: str, body: NoteIn = NoteIn(), user=Depends(require("admin"))):
    with STORE.lock:
        r = _find_request(rid)
        if r["status"] not in ("NEW", "APPROVED"):
            raise HTTPException(409, f"Request is {r['status']}")
        r["status"] = "REJECTED"
        r["history"].append({"time": S()["sim_time"], "text": f"Rejected by {user['name']}: {body.note or 'no reason'}"})
        STORE.audit(user, "REJECT_REQUEST", rid, body.note or "Rejected")
        STORE.save()
        return r


@app.post("/api/requests/{rid}/dispatch")
def dispatch_request(rid: str, body: DispatchIn, user=Depends(require("planner"))):
    with STORE.lock:
        st = S()
        r = _find_request(rid)
        if r["status"] not in ("NEW", "APPROVED"):
            raise HTTPException(409, f"Request is already {r['status']}")
        plan = planning.plan_options(st, r["node"], r["category"], r["qty"], r["needed_by"])
        opt = next((o for o in plan["options"] if o["option_id"] == body.option_id), None)
        if not opt:
            raise HTTPException(409, "No feasible transport option - check stock at sources and asset availability")
        if r["status"] == "NEW":
            r["approved_by"] = user["name"]
            r["history"].append({"time": st["sim_time"], "text": f"Approved by {user['name']}"})
        ships = planning.dispatch(st, r, opt, user["name"])
        STORE.audit(user, "DISPATCH", rid, f"{opt['label']}; {len(ships)} shipment(s); ETA {opt['eta']}; risk {opt['risk']['score']}")
        STORE.save()
        return {"request": r, "shipments": ships, "option": opt}


@app.post("/api/replenishment/{rec_id}/approve")
def approve_rec(rec_id: str, body: ApproveRecIn, user=Depends(require("planner"))):
    with STORE.lock:
        st = S()
        recs = {r["id"]: r for r in planning.recommendations(st)}
        rec = recs.get(rec_id)
        if not rec:
            raise HTTPException(404, "Recommendation no longer applies (stock already covered)")
        rid = planning.next_id(st, "REQ")
        now = net.sim_now(st)
        need_h = max(12.0, (rec["stockout_in_days"] or 7) * 24)
        qty = round(body.qty or rec["recommended_qty"])
        req = {"id": rid, "node": rec["node"], "category": rec["category"], "qty": qty,
               "needed_by": net.iso(now + timedelta(hours=need_h)), "declared_urgency": rec["urgency"],
               "reason": f"Predictive replenishment: {rec['reason']}", "raised_by": "Replenishment engine",
               "created_at": st["sim_time"], "status": "APPROVED", "source": "PREDICTIVE", "approved_by": user["name"],
               "history": [{"time": st["sim_time"], "text": f"Generated from {rec_id}; approved by {user['name']}"}]}
        st["requests"].append(req)
        st["stats"]["recommendations_approved"] = st["stats"].get("recommendations_approved", 0) + 1
        if rec["urgency"] in ("CRITICAL", "HIGH"):
            st["stats"]["stockouts_prevented"] = st["stats"].get("stockouts_prevented", 0) + 1
        result = {"request": req, "shipments": []}
        detail = f"{qty} {rec['category']} to {rec['node']}"
        if body.auto_dispatch:
            plan = planning.plan_options(st, req["node"], req["category"], req["qty"], req["needed_by"])
            if plan["options"]:
                opt = plan["options"][0]
                result["shipments"] = planning.dispatch(st, req, opt, user["name"])
                result["option"] = opt
                detail += f"; auto-dispatched: {opt['label']}"
        planning.add_event(st, f"Replenishment approved: {qty:,} {rec['unit']} {rec['category_name'].lower()} for {rec['node_name']}",
                           "success", rid)
        STORE.audit(user, "APPROVE_REPLENISHMENT", rec_id, detail)
        STORE.save()
        return result


@app.post("/api/replenishment/{rec_id}/snooze")
def snooze_rec(rec_id: str, body: NoteIn = NoteIn(), user=Depends(require("planner"))):
    with STORE.lock:
        st = S()
        st.setdefault("snoozed", {})[rec_id] = net.iso(net.sim_now(st) + timedelta(hours=24))
        STORE.audit(user, "SNOOZE_REPLENISHMENT", rec_id, body.note or "Deferred 24 h")
        STORE.save()
        return {"ok": True}


@app.post("/api/alerts/{aid}/ack")
def ack_alert(aid: str, body: NoteIn = NoteIn(), user=Depends(require("planner"))):
    with STORE.lock:
        S()["alert_status"][aid] = {"status": "ACKNOWLEDGED", "by": user["name"], "time": S()["sim_time"], "note": body.note}
        STORE.audit(user, "ACK_ALERT", aid, body.note or "Acknowledged")
        STORE.save()
        return {"ok": True}


@app.post("/api/alerts/{aid}/resolve")
def resolve_alert(aid: str, body: NoteIn = NoteIn(), user=Depends(require("planner"))):
    with STORE.lock:
        S()["alert_status"][aid] = {"status": "RESOLVED", "by": user["name"], "time": S()["sim_time"], "note": body.note}
        STORE.audit(user, "RESOLVE_ALERT", aid, body.note or "Resolved")
        STORE.save()
        return {"ok": True}


@app.post("/api/iot/ingest")
def iot_ingest(body: IngestIn, user=Depends(require("planner"))):
    with STORE.lock:
        if body.device_id not in S()["devices"]:
            raise HTTPException(404, "Unknown device")
        r = iot.ingest(S(), body.device_id, body.value, user["name"])
        STORE.audit(user, "IOT_INGEST", body.device_id, f"value={body.value}")
        STORE.save()
        return r


# ---------------------------------------------------------------------------
# Admin actions
# ---------------------------------------------------------------------------

@app.post("/api/iot/{device_id}/reconcile")
def iot_reconcile(device_id: str, user=Depends(require("admin"))):
    with STORE.lock:
        d = S()["devices"].get(device_id)
        if not d or d["type"] != "RFID_GATE":
            raise HTTPException(404, "RFID device not found")
        res = iot.reconcile(S(), device_id)
        STORE.audit(user, "RECONCILE_INVENTORY", device_id, f"Rations {res['old']} -> {res['new']}")
        STORE.save()
        return res


@app.post("/api/disruptions")
def create_disruption(body: DisruptionIn, user=Depends(require("admin"))):
    if body.route_id and body.route_id not in ROUTES:
        raise HTTPException(404, "Unknown route")
    if body.node_id:
        _check_node(body.node_id)
    if not body.route_id and not body.node_id:
        raise HTTPException(422, "Choose a route or a location")
    with STORE.lock:
        st = S()
        did = planning.next_id(st, "DIS")
        now = net.sim_now(st)
        d = {"id": did, "type": body.type.upper(), "title": body.title, "route_id": body.route_id, "node_id": body.node_id,
             "severity": body.severity.upper(), "delay_factor": body.delay_factor, "closes_route": body.closes_route,
             "status": "ACTIVE", "start": st["sim_time"], "expected_end": net.iso(now + timedelta(hours=body.duration_hours)),
             "source": f"Reported by {user['name']}", "description": body.description or body.title}
        st["disruptions"].append(d)
        # apply immediately to moving shipments
        for s in st["shipments"]:
            if s["status"] in ("IN_TRANSIT", "DELAYED", "HOLDING") and s["mode"] == "ROAD" and body.route_id in s["routes"]:
                sim.apply_route_effects(st, s, net.day_index(st))
                s["eta"] = net.iso(now + timedelta(hours=max(0.0, s["total_hours"] - s["travel_done"])))
        planning.add_event(st, f"New disruption reported: {body.title}", "danger", did)
        STORE.audit(user, "CREATE_DISRUPTION", did, f"{body.type} {body.severity} {body.route_id or body.node_id}")
        STORE.save()
        return d


@app.post("/api/disruptions/{did}/resolve")
def resolve_disruption(did: str, user=Depends(require("admin"))):
    with STORE.lock:
        st = S()
        d = next((x for x in st["disruptions"] if x["id"] == did), None)
        if not d:
            raise HTTPException(404, "Disruption not found")
        d["status"] = "RESOLVED"
        d["resolved_at"] = st["sim_time"]
        planning.add_event(st, f"Disruption cleared: {d['title']}", "success", did)
        STORE.audit(user, "RESOLVE_DISRUPTION", did, d["title"])
        STORE.save()
        return d


@app.post("/api/forecast/retrain")
def retrain(user=Depends(require("planner"))):
    with STORE.lock:
        meta = ENGINE.fit(S())
        STORE.audit(user, "RETRAIN_MODEL", meta["version"], f"Accuracy {meta['accuracy_pct']}%")
        STORE.save()
        return meta


@app.post("/api/admin/reset")
def reset(user=Depends(require("admin"))):
    STORE.reset()
    with STORE.lock:
        STORE.audit(user, "RESET_DEMO_DATA", "system", "Synthetic demo data regenerated")
        STORE.save()
    return {"ok": True, "sim_time": S()["sim_time"]}


# ---------------------------------------------------------------------------
# Serve the built web app (single-command run)
# ---------------------------------------------------------------------------

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if (STATIC_DIR / "index.html").exists():
    if (STATIC_DIR / "assets").exists():
        app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        if full_path.startswith("api/"):
            return JSONResponse({"detail": "Not found"}, status_code=404)
        f = STATIC_DIR / full_path
        if full_path and f.is_file():
            return FileResponse(f)
        return FileResponse(STATIC_DIR / "index.html")
