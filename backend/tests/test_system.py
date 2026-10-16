"""End-to-end tests for LogiSentinel engines and API.  Run:  python -m pytest -q  (from backend/)"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOGISENTINEL_CLOCK"] = "0"  # tests drive the clock themselves

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.store import STORE  # noqa: E402

client = TestClient(app)
client.__enter__()  # run startup
STORE.reset()


def login(user="admin", pw="admin123"):
    r = client.post("/api/auth/login", json={"username": user, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


ADMIN = login()
VIEWER = login("viewer", "viewer123")


def test_auth_required_and_bad_password():
    assert client.get("/api/dashboard").status_code == 401
    assert client.post("/api/auth/login", json={"username": "admin", "password": "x"}).status_code == 401


def test_rbac_viewer_cannot_act():
    r = client.post("/api/sim/advance", json={"hours": 1}, headers=VIEWER)
    assert r.status_code == 403


def test_forecast_model_beats_naive_baseline():
    m = client.get("/api/forecast/model", headers=ADMIN).json()
    assert m["accuracy_pct"] > 80
    assert m["wape_pct"] < m["naive_wape_pct"]


def test_forecast_endpoint_has_bands_and_explanations():
    f = client.get("/api/forecast?node=FP-E&category=FUEL&horizon=14", headers=ADMIN).json()
    fc = [p for p in f["series"] if "forecast" in p]
    assert len(fc) == 14
    assert all(p["lower"] <= p["forecast"] <= p["upper"] for p in fc)
    assert len(f["factors"]) >= 2


def test_dashboard_kpis():
    d = client.get("/api/dashboard", headers=ADMIN).json()
    assert 0 <= d["kpis"]["readiness_index"] <= 100
    assert d["kpis"]["alerts_critical"] >= 1
    assert len(d["matrix"]) == 21  # 14 forward posts + 7 hubs across 4 sectors
    assert set(d["kpis"]["sector_readiness"]) == {"NORTH", "EAST", "WEST", "ISLANDS"}


def test_ai_autopilot_handles_red_alerts_automatically():
    before = client.get("/api/dashboard", headers=ADMIN).json()
    red = [(r["node"], c) for r in before["matrix"] for c, v in r["cells"].items() if v["status"] == "CRITICAL"]
    assert red, "seed data should start with red alerts"
    acted = client.post("/api/ai/scan", headers=ADMIN).json()["actions"]
    assert any(a["kind"] == "AUTO_DISPATCH" and a["shipments"] for a in acted)
    reqs = client.get("/api/requests", headers=ADMIN).json()["requests"]
    assert any(r["source"] == "AI" for r in reqs), "AI should raise requests on its own"
    after = client.get("/api/dashboard", headers=ADMIN).json()
    still_red = [(r["node"], c) for r in after["matrix"] for c, v in r["cells"].items() if v["status"] == "CRITICAL"]
    assert len(still_red) < len(red)
    audit = client.get("/api/audit", headers=ADMIN).json()["audit"]
    assert any(a["role"] == "ai" for a in audit)


def test_island_post_gets_sea_option():
    r = client.post("/api/requests", json={"node": "HUB-Q", "category": "RATIONS", "qty": 30000, "needed_in_days": 5,
                                            "reason": "test"}, headers=ADMIN).json()
    plan = client.get(f"/api/requests/{r['id']}/plan", headers=ADMIN).json()
    assert any(o["mode"] == "SEA" for o in plan["options"])


def test_clock_speed_and_skip():
    assert client.post("/api/clock", json={"speed": 60}, headers=ADMIN).json()["speed"] == 60
    assert client.post("/api/clock", json={"speed": 7}, headers=ADMIN).status_code == 422
    client.post("/api/clock", json={"speed": 1}, headers=ADMIN)


def test_replenishment_and_auto_dispatch_flow():
    recs = client.get("/api/replenishment", headers=ADMIN).json()["recommendations"]
    assert recs, "expected at least one recommendation"
    rec = recs[0]
    assert rec["recommended_qty"] > 0 and rec["reason"]
    r = client.post(f"/api/replenishment/{rec['id']}/approve", json={"auto_dispatch": True}, headers=ADMIN)
    assert r.status_code == 200, r.text
    assert r.json()["shipments"], "auto dispatch should create shipments"


def test_request_prioritisation_and_dispatch():
    reqs = client.get("/api/requests", headers=ADMIN).json()["requests"]
    open_reqs = [r for r in reqs if "priority_score" in r]
    scores = [r["priority_score"] for r in open_reqs]
    assert scores == sorted(scores, reverse=True)
    top = open_reqs[0]
    plan = client.get(f"/api/requests/{top['id']}/plan", headers=ADMIN).json()
    assert plan["options"] and plan["options"][0]["recommended"]
    r = client.post(f"/api/requests/{top['id']}/dispatch", json={"option_id": "OPT-1"}, headers=ADMIN)
    assert r.status_code == 200, r.text


def test_create_request_validation():
    bad = client.post("/api/requests", json={"node": "NOPE", "category": "FUEL", "qty": 5}, headers=ADMIN)
    assert bad.status_code == 404
    ok = client.post("/api/requests", json={"node": "FP-H", "category": "MEDICAL", "qty": 20, "needed_in_days": 2,
                                            "reason": "test"}, headers=ADMIN)
    assert ok.status_code == 200


def test_disruption_creates_delay_and_closure():
    d = client.post("/api/disruptions", json={"type": "AVALANCHE", "title": "Test avalanche", "route_id": "R10",
                                              "severity": "CRITICAL", "closes_route": True, "duration_hours": 12},
                    headers=ADMIN)
    assert d.status_code == 200
    m = client.get("/api/map", headers=ADMIN).json()
    assert next(r for r in m["routes"] if r["id"] == "R10")["status"] == "CLOSED"
    client.post(f"/api/disruptions/{d.json()['id']}/resolve", headers=ADMIN)


def test_scenario_worst_case_is_worse_than_baseline():
    r = client.post("/api/scenarios/run", json={"severe_weather": True, "closed_routes": ["R7"],
                                                "demand_change_pct": 20, "horizon_days": 14}, headers=ADMIN).json()
    assert r["scenario"]["readiness_index"] < r["baseline"]["readiness_index"]
    assert r["recommendations"]


def test_simulation_clock_delivers_and_retrains():
    before = client.get("/api/forecast/model", headers=ADMIN).json()["history_days"]
    r = client.post("/api/sim/advance", json={"hours": 30}, headers=ADMIN).json()
    assert r["days_rolled"] >= 1 and r["model_retrained"]
    after = client.get("/api/forecast/model", headers=ADMIN).json()["history_days"]
    assert after == before + r["days_rolled"]
    ships = client.get("/api/shipments", headers=ADMIN).json()["shipments"]
    assert any(s["status"] == "DELIVERED" for s in ships)


def test_iot_ingest_updates_inventory():
    r = client.post("/api/iot/ingest", json={"device_id": "FUEL-FP-H", "value": 50}, headers=ADMIN)
    assert r.status_code == 200 and abs(r.json()["value"] - 50) < 1


def test_alert_ack_and_audit_trail():
    alerts = client.get("/api/alerts", headers=ADMIN).json()["alerts"]
    aid = alerts[0]["id"]
    assert client.post(f"/api/alerts/{aid}/ack", json={"note": "seen"}, headers=ADMIN).status_code == 200
    audit = client.get("/api/audit", headers=ADMIN).json()["audit"]
    assert any(a["action"] == "ACK_ALERT" for a in audit)


def test_sitrep_and_exports():
    assert "SITREP" in client.get("/api/reports/sitrep", headers=ADMIN).text
    for kind in ("inventory", "shipments", "requests", "audit"):
        assert client.get(f"/api/export/{kind}.csv", headers=ADMIN).status_code == 200
