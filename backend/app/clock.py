"""Mission clock: a background thread that keeps simulation time moving.

* Speed 1 = real time: simulation time follows the wall clock (it starts at the real current time).
* Faster speeds are for demos (1 real minute = 1 simulated hour, etc.).
* Speed 0 pauses the simulation.
The AI Autopilot is run on a fixed real-time rhythm, independent of speed.
"""
from __future__ import annotations

import copy
import os
import threading
import time
from datetime import datetime, timezone

from . import ai, sim
from . import network as net
from .forecast import ENGINE
from .store import STORE

SPEEDS = {0: "Paused", 1: "Real time", 60: "1 min = 1 hour", 360: "10 s = 1 hour", 1440: "1 min = 1 day"}
AI_FIRST_SCAN_S = 5      # after start or reset - long enough to see the red alerts appear first
AI_SCAN_EVERY_S = 10


class ClockThread(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True, name="mission-clock")
        self.stop_flag = threading.Event()
        self.last_save = time.time()
        STORE.ai_due = time.time() + AI_FIRST_SCAN_S

    def run(self):
        while not self.stop_flag.wait(1.0):
            try:
                self.tick()
            except Exception as exc:  # never let the clock die during a demo
                print("[clock] error:", repr(exc))

    def tick(self):
        need_fit = False
        changed = False
        with STORE.lock:
            st = STORE.state
            if not st:
                return
            c = st.setdefault("clock", {"speed": 1, "last_real": datetime.now(timezone.utc).isoformat(), "pending_hours": 0.0})
            real_now = datetime.now(timezone.utc)
            last = datetime.fromisoformat(c["last_real"])
            elapsed = max(0.0, (real_now - last).total_seconds())
            c["last_real"] = real_now.isoformat()
            speed = c.get("speed", 1)
            if speed > 0:
                c["pending_hours"] = c.get("pending_hours", 0.0) + elapsed * speed / 3600.0
            threshold = 0.05 if speed <= 1 else 0.2  # 3 simulated minutes in real time
            if c.get("pending_hours", 0.0) >= threshold:
                res = sim.advance(st, c["pending_hours"], retrain=False)
                c["pending_hours"] = 0.0
                changed = True
                need_fit = res["days_rolled"] > 0
            if time.time() >= getattr(STORE, "ai_due", 0):
                acted = ai.scan(st, trigger="clock")
                STORE.ai_due = time.time() + AI_SCAN_EVERY_S
                changed = changed or bool(acted)
            snapshot = None
            if need_fit:
                snapshot = {k: st[k] for k in ("weather", "ops", "day0", "history_days", "history_end_day", "sim_time")}
                snapshot["history"] = copy.deepcopy(st["history"])
        if snapshot is not None:
            ENGINE.fit(snapshot)  # retrain outside the lock so the app stays responsive
            with STORE.lock:
                net_time = STORE.state.get("sim_time")
                from .planning import add_event
                add_event(STORE.state, f"New day: forecasting model retrained on actual consumption "
                                       f"({ENGINE.meta.get('accuracy_pct')}% accuracy)", "ai", "model")
        if changed and time.time() - self.last_save > 15:
            with STORE.lock:
                STORE.save()
            self.last_save = time.time()


CLOCK: ClockThread | None = None


def start():
    global CLOCK
    if os.getenv("LOGISENTINEL_CLOCK", "1") == "0":
        return
    if CLOCK is None or not CLOCK.is_alive():
        CLOCK = ClockThread()
        CLOCK.start()


def stop():
    if CLOCK:
        CLOCK.stop_flag.set()


def info(state) -> dict:
    c = state.get("clock", {})
    real_now = datetime.now(timezone.utc)
    sim_now = net.sim_now(state)
    speed = c.get("speed", 1)
    return {"speed": speed, "speed_label": SPEEDS.get(speed, f"{speed}x"), "sim_time": state["sim_time"],
            "real_time": real_now.isoformat(timespec="seconds"),
            "ahead_hours": round((sim_now - real_now).total_seconds() / 3600, 2),
            "pending_hours": c.get("pending_hours", 0.0)}
