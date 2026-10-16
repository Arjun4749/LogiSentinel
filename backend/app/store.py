"""In-memory state with JSON persistence (data/state.json)."""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from .forecast import ENGINE
from .seed import build_state
from .sim import seed_in_transit

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
STATE_FILE = DATA_DIR / "state.json"
STATE_VERSION = 3


class Store:
    def __init__(self):
        self.lock = threading.RLock()
        self.state: dict = {}
        self.ai_due = 0.0

    def init(self):
        with self.lock:
            loaded = False
            if STATE_FILE.exists():
                try:
                    data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
                    if data.get("version") == STATE_VERSION:
                        self.state = data
                        loaded = True
                except Exception:
                    loaded = False
            if loaded:
                # Keep simulation time in step with real time while the app was closed.
                c = self.state.setdefault("clock", {"speed": 1, "pending_hours": 0.0})
                now = datetime.now(timezone.utc)
                sim_t = datetime.fromisoformat(self.state["sim_time"])
                gap_h = (now - sim_t).total_seconds() / 3600
                c["speed"] = 1
                c["pending_hours"] = 0.0
                c["last_real"] = now.isoformat()
                if gap_h > 48:
                    loaded = False  # data is too old - start a fresh synthetic scenario at today's time
                else:
                    ENGINE.fit(self.state)
                    if gap_h > 0.02:
                        from .sim import advance
                        res = advance(self.state, gap_h, retrain=False)
                        if res["days_rolled"]:
                            ENGINE.fit(self.state)
            if not loaded:
                self._fresh()

    def _fresh(self):
        import time
        self.state = build_state(datetime.now(timezone.utc))
        ENGINE.fit(self.state)
        seed_in_transit(self.state)
        self.ai_due = time.time() + 5  # let the red alerts show before the AI Autopilot reacts
        self.save()

    def reset(self):
        with self.lock:
            self._fresh()

    def save(self):
        tmp = STATE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state, separators=(",", ":")), encoding="utf-8")
        tmp.replace(STATE_FILE)

    def audit(self, user: dict, action: str, entity: str, details: str):
        s = self.state
        s["counters"]["AUD"] = s["counters"].get("AUD", 0) + 1
        s["audit"].insert(0, {"id": f"AUD-{s['counters']['AUD']:05d}",
                              "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                              "sim_time": s["sim_time"], "user": user["username"], "name": user.get("name"),
                              "role": user["role"], "action": action, "entity": entity, "details": details})
        del s["audit"][1000:]


STORE = Store()
