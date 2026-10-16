"""Simulated IoT layer: RFID stock gates, fuel level sensors, cold-chain
loggers and storehouse humidity sensors. Readings feed inventory accuracy and alerts."""
from __future__ import annotations

from datetime import timedelta

import numpy as np

from . import network as net
from .planning import add_event
from .reference import CATEGORIES, NODES
from .seed import _rng


def _base_value(state, d: dict) -> float:
    node = d["node"]
    if d["type"] == "RFID_GATE":
        return 100.0 + d["variance_pct"]
    if d["type"] == "FUEL_LEVEL":
        inv = state["inventory"][node]["FUEL"]
        return round(100.0 * inv["on_hand"] / max(1, inv["capacity"]), 1)
    if d["type"] == "COLD_CHAIN":
        return 5.0
    if d["type"] == "STORE_HUMIDITY":
        return 52.0
    return 0.0


def reading(state, d: dict) -> dict:
    now = net.sim_now(state)
    hour_idx = int(now.timestamp() // 3600)
    base = d["override"] if d.get("override") is not None else _base_value(state, d)
    hist = []
    for k in range(23, -1, -1):
        r = _rng("iot", d["id"], hour_idx - k)
        jitter = {"COLD_CHAIN": 0.35, "STORE_HUMIDITY": 2.0, "FUEL_LEVEL": 0.0, "RFID_GATE": 0.15}[d["type"]]
        v = base + float(r.normal(0, jitter))
        if d["type"] == "FUEL_LEVEL":  # level was higher in the past (consumption)
            v = base + k * 0.15
        hist.append({"time": net.iso(now - timedelta(hours=k)), "value": round(v, 2)})
    value = hist[-1]["value"]
    link_down = bool(net.active_disruptions(state, node=d["node"]))
    status = "OK"
    issue = None
    if d["status"] == "OFFLINE":
        status, issue = "OFFLINE", "No data received - check power/link"
    elif value < d["min"] or value > d["max"]:
        status = "BREACH"
        issue = {"COLD_CHAIN": f"Cold chain {value:.1f} C outside 2-8 C - vaccines/blood products at risk",
                 "RFID_GATE": f"Physical count differs from system record by {value - 100:+.1f}%",
                 "FUEL_LEVEL": f"Fuel bladder at {value:.0f}% - below 8% minimum",
                 "STORE_HUMIDITY": f"Humidity {value:.0f}% RH - risk of spoilage/corrosion"}[d["type"]]
    elif d["battery"] < 20:
        status, issue = "WARN", f"Battery low ({d['battery']}%)"
    elif link_down:
        status, issue = "WARN", "Data link degraded - readings delayed"
    last_seen = d.get("last_seen") or net.iso(now - timedelta(minutes=int(_rng("seen", d["id"]).randint(1, 9))))
    if d["status"] == "OFFLINE":
        last_seen = net.iso(now - timedelta(hours=14))
    out = {k: v for k, v in d.items() if k not in ("override",)}
    out.update({"value": None if d["status"] == "OFFLINE" else value, "history": hist, "health": status,
                "issue": issue, "last_seen": last_seen, "node_name": NODES[d["node"]]["name"],
                "sector": NODES[d["node"]]["sector"]})
    if d["type"] == "RFID_GATE":
        sys_total = sum(state["inventory"][d["node"]][c]["on_hand"] for c in ("RATIONS",))
        out["system_qty"] = round(sys_total)
        out["counted_qty"] = round(sys_total * value / 100.0)
        out["tracked_item"] = "Rations (kg)"
    return out


def all_readings(state) -> list:
    return [reading(state, d) for d in state["devices"].values()]


def inventory_accuracy(state) -> float:
    vals = [100 - abs(d["variance_pct"]) for d in state["devices"].values() if d["type"] == "RFID_GATE"]
    return round(float(np.mean(vals)), 1) if vals else 100.0


def ingest(state, device_id: str, value: float, user: str) -> dict:
    d = state["devices"][device_id]
    d["status"] = "ONLINE"
    d["last_seen"] = state["sim_time"]
    if d["type"] == "FUEL_LEVEL":
        inv = state["inventory"][d["node"]]["FUEL"]
        old = inv["on_hand"]
        inv["on_hand"] = round(inv["capacity"] * max(0.0, min(100.0, value)) / 100.0)
        d["override"] = None
        add_event(state, f"IoT fuel sensor at {NODES[d['node']]['name']} updated stock "
                         f"{old:,.0f} -> {inv['on_hand']:,.0f} L", "info", device_id)
    elif d["type"] == "RFID_GATE":
        d["variance_pct"] = round(value - 100.0, 2)
    else:
        d["override"] = value
        add_event(state, f"IoT reading {device_id}: {value} {d['unit']}", "info", device_id)
    return reading(state, d)


def reconcile(state, device_id: str) -> dict:
    """Accept the RFID physical count as the true stock (inventory reconciliation)."""
    d = state["devices"][device_id]
    inv = state["inventory"][d["node"]]["RATIONS"]
    old = inv["on_hand"]
    inv["on_hand"] = round(old * (100 + d["variance_pct"]) / 100.0)
    d["variance_pct"] = 0.0
    add_event(state, f"Inventory reconciled at {NODES[d['node']]['name']} from RFID count: "
                     f"{old:,.0f} -> {inv['on_hand']:,.0f} kg rations", "success", device_id)
    return {"old": round(old), "new": inv["on_hand"]}
