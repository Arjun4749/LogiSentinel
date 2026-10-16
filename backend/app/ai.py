"""LogiSentinel AI Autopilot.

Watches every location and supply line continuously. When a unit goes RED
(forecast says it will run out before normal resupply can arrive) the autopilot:

  1. detects the red alert,
  2. works out how much is needed from the ML demand forecast,
  3. raises a supply request on the unit's behalf (or takes over an open field request),
  4. plans transport across road, sea, helicopter, aircraft and drone options,
  5. dispatches the best option automatically,
  6. records its reasoning, confidence and actions in the AI decision log and audit trail.

If no transport is feasible it escalates to a human planner instead of guessing.
Amber (below reorder point) lines are, by default, left as recommendations for a
human, but can be switched to automatic requests too.
"""
from __future__ import annotations

import time
from datetime import timedelta
from typing import List, Optional

from . import network as net
from .planning import Ctx, add_event, dispatch, nice_round, next_id, open_requests, plan_options
from .reference import CATEGORIES, NODES

AI_ACTOR = {"username": "ai-autopilot", "name": "LogiSentinel AI", "role": "ai"}
ACTIVE = ("SCHEDULED", "LOADING", "IN_TRANSIT", "DELAYED", "HOLDING")


def _cfg(state) -> dict:
    return state.setdefault("ai", {"enabled": True, "critical_mode": "dispatch", "low_mode": "recommend", "log": [],
                                   "stats": {}, "cooldown": {}, "first_seen": {}})


def _log(state, kind: str, title: str, node: str, cat: Optional[str], reasoning: List[str], confidence: float,
         request_id=None, shipments=None, severity="CRITICAL", response_s=None) -> dict:
    ai = _cfg(state)
    state["counters"]["AI"] = state["counters"].get("AI", 0) + 1
    entry = {"id": f"AI-{state['counters']['AI']:04d}", "time": state["sim_time"], "kind": kind, "title": title,
             "node": node, "node_name": NODES[node]["name"], "sector": NODES[node]["sector"],
             "category": cat, "category_name": CATEGORIES[cat]["name"] if cat else None,
             "reasoning": reasoning, "confidence": round(confidence, 2), "request_id": request_id,
             "shipments": shipments or [], "severity": severity, "response_s": response_s}
    ai["log"].insert(0, entry)
    del ai["log"][300:]
    return entry


def _audit(state, action, entity, details):
    s = state
    s["counters"]["AUD"] = s["counters"].get("AUD", 0) + 1
    from datetime import datetime, timezone
    s["audit"].insert(0, {"id": f"AUD-{s['counters']['AUD']:05d}",
                          "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                          "sim_time": s["sim_time"], "user": AI_ACTOR["username"], "name": AI_ACTOR["name"],
                          "role": "ai", "action": action, "entity": entity, "details": details})
    del s["audit"][1000:]


def _has_active_supply(state, node: str, cat: str) -> bool:
    for s in state["shipments"]:
        if s["dest"] == node and s["category"] == cat and s["status"] in ACTIVE:
            return True
    return False


def _dispatch_best(state, req: dict, ctx: Ctx):
    plan = plan_options(state, req["node"], req["category"], req["qty"], req["needed_by"], ctx)
    if not plan["options"]:
        return None, plan
    best = plan["options"][0]
    ships = dispatch(state, req, best, AI_ACTOR["name"])
    return (best, ships), plan


DETECT_TO_ACT_S = 8  # the autopilot confirms a red alert on two consecutive scans before acting


def scan(state, trigger: str = "auto") -> List[dict]:
    """One autopilot cycle. Returns the AI log entries created in this cycle."""
    ai = _cfg(state)
    stats = ai.setdefault("stats", {})
    stats["scans"] = stats.get("scans", 0) + 1
    ai["last_scan"] = state["sim_time"]
    if not ai.get("enabled", True):
        return []
    ctx = Ctx(state)
    now = net.sim_now(state)
    created: List[dict] = []
    first_seen = ai.setdefault("first_seen", {})
    cooldown = ai.setdefault("cooldown", {})
    for node, n in NODES.items():
        if n["type"] == "depot":
            continue
        for cat, c in CATEGORIES.items():
            st = ctx.status(node, cat)
            key = f"{node}|{cat}"
            if st["status"] not in ("CRITICAL", "LOW"):
                first_seen.pop(key, None)
                continue
            prev = first_seen.get(key)
            if prev is not None and (not isinstance(prev, dict) or prev.get("status") != st["status"]):
                first_seen.pop(key, None)  # changed colour (amber -> red): the response clock restarts
            if key not in first_seen:
                first_seen[key] = {"sim": state["sim_time"], "real": time.time(), "status": st["status"]}
                if trigger == "clock":
                    continue  # detected now - confirm on the next scan
            fs = first_seen[key] if isinstance(first_seen[key], dict) else {"sim": first_seen[key], "real": time.time()}
            if trigger == "clock" and time.time() - fs["real"] < DETECT_TO_ACT_S:
                continue
            if st["status"] == "LOW" and ai.get("low_mode") != "request":
                continue
            if st["status"] == "CRITICAL" and ai.get("critical_mode") == "off":
                continue
            if _has_active_supply(state, node, cat) and (st["status"] == "LOW" or st["position"] >= st["reorder_point"]):
                continue  # enough is already on the way
            if key in cooldown and net.parse_time(cooldown[key]) > now:
                continue
            seen_s = max(0.0, time.time() - fs["real"])
            so = st["stockout_in_days"]
            fc_conf = st["confidence"]
            reasoning = [
                f"{'Red' if st['status'] == 'CRITICAL' else 'Amber'} alert: {n['name']} holds {st['on_hand']:,} {st['unit']} "
                f"of {c['name'].lower()} = {st['days_of_supply']} days at the forecast rate of {st['avg_daily_forecast']:,} {st['unit']}/day.",
                (f"ML forecast projects a stock-out in {so} days" if so is not None else "Stock falls below safety level")
                + f"; normal resupply takes {st['lead_time_hours'] / 24:.1f} days.",
            ]
            if st["incoming_qty"]:
                reasoning.append(f"{st['incoming_qty']:,} {st['unit']} already on the way is not enough.")
            existing = open_requests(state, node, cat)
            if existing:
                req = existing[0]
                reasoning.append(f"Open request {req['id']} found - autopilot takes it over instead of creating a duplicate.")
            else:
                qty = nice_round(max(st["target_level"] - st["position"], st["avg_daily_forecast"] * 3), st["unit"])
                need_h = max(10.0, (so if so is not None else 7) * 24 - 2)
                rid = next_id(state, "REQ")
                req = {"id": rid, "node": node, "category": cat, "qty": qty,
                       "needed_by": net.iso(now + timedelta(hours=need_h)),
                       "declared_urgency": "CRITICAL" if st["status"] == "CRITICAL" else "HIGH",
                       "reason": f"Raised automatically by AI Autopilot: {reasoning[0]}",
                       "raised_by": AI_ACTOR["name"], "created_at": state["sim_time"],
                       "status": "NEW", "source": "AI",
                       "history": [{"time": state["sim_time"], "text": "Raised automatically by LogiSentinel AI after a "
                                    f"{'red' if st['status'] == 'CRITICAL' else 'amber'} alert"}]}
                state["requests"].append(req)
                stats["auto_requests"] = stats.get("auto_requests", 0) + 1
                reasoning.append(f"Order quantity {qty:,} {st['unit']} = forecast demand over lead time + review period "
                                 f"+ safety stock - stock on hand and incoming.")
                _audit(state, "AI_CREATE_REQUEST", rid, f"{qty} {cat} for {node}")
            # ----- act -----
            if st["status"] == "CRITICAL" and ai.get("critical_mode", "dispatch") == "dispatch":
                result, plan = _dispatch_best(state, req, ctx)
                if result:
                    best, ships = result
                    if req["status"] == "DISPATCHED":
                        req.setdefault("approved_by", AI_ACTOR["name"])
                    reasoning.append(f"Compared {len(plan['options'])} transport option(s); chose {best['label'].lower()} - "
                                     f"ETA {best['eta'][:16].replace('T', ' ')} UTC, risk {best['risk']['score']}/100, "
                                     f"score {best['score']}/100.")
                    if best.get("why"):
                        reasoning.append(best["why"])
                    stats["auto_dispatches"] = stats.get("auto_dispatches", 0) + 1
                    cooldown[key] = net.iso(now + timedelta(hours=6))
                    stats["red_alerts_handled"] = stats.get("red_alerts_handled", 0) + 1
                    state["stats"]["stockouts_prevented"] = state["stats"].get("stockouts_prevented", 0) + 1
                    n_h = stats["red_alerts_handled"]
                    stats["avg_response_s"] = round(((stats.get("avg_response_s", 0.0) * (n_h - 1)) + seen_s) / n_h, 1)
                    state["alert_status"][f"STOCKOUT:{node}:{cat}"] = {"status": "RESOLVED", "by": AI_ACTOR["name"],
                                                                       "time": state["sim_time"], "note": f"Handled via {req['id']}"}
                    entry = _log(state, "AUTO_DISPATCH", f"Red alert handled: {n['name']} - {c['name']}", node, cat, reasoning,
                                 fc_conf, req["id"], [s["id"] for s in ships], "CRITICAL", round(seen_s, 1))
                    add_event(state, f"AI Autopilot: red alert at {n['name']} ({c['name'].lower()}) - request {req['id']} "
                                     f"raised and {len(ships)} shipment(s) dispatched automatically", "ai", req["id"])
                    _audit(state, "AI_DISPATCH", req["id"], best["label"])
                else:
                    stats["escalations"] = stats.get("escalations", 0) + 1
                    cooldown[key] = net.iso(now + timedelta(hours=2))
                    reasoning.append("No feasible transport right now (no spare stock at sources in this sector, or no free "
                                     "vehicle / flying window). Escalated to a human planner; autopilot will retry in 2 hours.")
                    entry = _log(state, "ESCALATION", f"Escalated: {n['name']} - {c['name']}", node, cat, reasoning,
                                 fc_conf, req["id"], [], "CRITICAL", round(seen_s, 1))
                    add_event(state, f"AI Autopilot escalated {n['name']} {c['name'].lower()} to planners - no transport available",
                              "danger", req["id"])
                    _audit(state, "AI_ESCALATE", req["id"], "No feasible transport option")
            else:
                cooldown[key] = net.iso(now + timedelta(hours=6))
                entry = _log(state, "AUTO_REQUEST", f"Request raised: {n['name']} - {c['name']}", node, cat,
                             reasoning + ["Waiting for planner approval (amber alerts need a human decision in current settings)."],
                             fc_conf, req["id"], [], "HIGH" if st["status"] == "CRITICAL" else "MEDIUM", round(seen_s, 1))
                add_event(state, f"AI Autopilot raised request {req['id']} for {n['name']} ({c['name'].lower()}) - awaiting approval",
                          "ai", req["id"])
            created.append(entry)
            ctx = Ctx(state)  # stock and fleet changed - refresh the picture for the next decision
    return created


def briefing(state, ctx: Ctx, kpis: dict) -> List[str]:
    """Short plain-English AI briefing for the dashboard."""
    ai = _cfg(state)
    lines = []
    now = net.sim_now(state)
    recent = [e for e in ai.get("log", []) if (now - net.parse_time(e["time"])).total_seconds() <= 86400]
    handled = [e for e in recent if e["kind"] == "AUTO_DISPATCH"]
    if handled:
        names = ", ".join(sorted({e["node_name"] for e in handled})[:4])
        lines.append(f"In the last 24 h the autopilot handled {len(handled)} red alert(s) on its own ({names}), "
                     f"responding {ai['stats'].get('avg_response_s', 0):.0f} seconds after each alert on average.")
    esc = [e for e in recent if e["kind"] == "ESCALATION"]
    if esc:
        lines.append(f"{len(esc)} shortage(s) need a human decision: {', '.join(e['node_name'] for e in esc[:3])}.")
    # biggest upcoming risk
    worst = None
    for node, n in NODES.items():
        if n["type"] != "post":
            continue
        for cat in CATEGORIES:
            st = ctx.status(node, cat)
            so = st["stockout_in_days"]
            if so is not None and st["status"] in ("LOW", "CRITICAL") and (worst is None or so < worst[2]):
                worst = (n["name"], CATEGORIES[cat]["name"].lower(), so)
    if worst:
        lines.append(f"Next risk: {worst[0]} {worst[1]} runs out in {worst[2]} days unless resupplied.")
    day = net.day_index(state)
    storms = []
    for node, n in NODES.items():
        for k in range(1, 4):
            w = net.weather_at(state, node, day + k)
            if w["cond"] in ("Blizzard", "Storm", "Dust storm"):
                storms.append((k, w["cond"].lower(), n["sector"]))
                break
    if storms:
        k, cond, sector = min(storms)
        sec = {"NORTH": "northern", "EAST": "eastern", "WEST": "western", "ISLANDS": "island"}[sector]
        lines.append(f"Weather: {cond} expected in the {sec} sector in {k} day(s) - push supplies before the window closes.")
    lines.append(f"Forecast model accuracy is {kpis.get('forecast_accuracy_pct')}% on held-back days; "
                 f"supply readiness stands at {kpis.get('readiness_index')}/100.")
    return lines
