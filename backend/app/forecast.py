"""AI/ML demand forecasting engine.

A single global Random Forest model is trained across every location x supply
category. It predicts the *ratio* of tomorrow's consumption to the trailing
28-day average, which makes it scale-free so one model serves posts consuming
3 medical kits a day and depots consuming 6,000 litres of fuel a day.

External drivers used as features: temperature, temperature change, snow,
rain, planned operations / exercises, day of week, altitude, location type,
and supply category. Multi-day forecasts are produced recursively.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple

import numpy as np

from .reference import CATEGORIES, NODES

try:  # scikit-learn is optional - a statistical fallback keeps the app working
    from sklearn.ensemble import RandomForestRegressor
    HAVE_SKLEARN = True
except Exception:  # pragma: no cover
    HAVE_SKLEARN = False

CATS = list(CATEGORIES)
TYPE_CODE = {"depot": 0, "hub": 1, "post": 2}
FEATURE_NAMES = (["Yesterday's demand", "Same day last week", "7-day trend", "Day of week", "Weekend",
                  "Temperature", "Temperature change", "Snow", "Rain", "Planned operations",
                  "Altitude", "Location type"] + [f"Category: {CATEGORIES[c]['name']}" for c in CATS])

# human-friendly grouping of feature importances
FEATURE_GROUPS = {
    "Recent consumption pattern": ["Yesterday's demand", "Same day last week", "7-day trend"],
    "Weather (temperature, snow, rain)": ["Temperature", "Temperature change", "Snow", "Rain"],
    "Planned operations / exercises": ["Planned operations"],
    "Calendar (day of week)": ["Day of week", "Weekend"],
    "Location (altitude, type)": ["Altitude", "Location type"],
    "Supply category": [f"Category: {CATEGORIES[c]['name']}" for c in CATS],
}


class ForecastEngine:
    def __init__(self):
        self.model = None
        self.meta: dict = {}
        self.cache: Dict[Tuple[str, str], dict] = {}
        self.cache_key = None
        self.resid_std: Dict[str, float] = {}
        self.cat_wape: Dict[str, float] = {}

    # ------------------------------------------------------------------
    def _features(self, state, node, cat, series: List[float], i: int, day: int, w_window=None) -> List[float]:
        """Features for predicting series[i] (which is day `day`)."""
        r28 = max(1e-6, float(np.mean(series[i - 28:i])))
        r7 = float(np.mean(series[i - 7:i]))
        hd = state["history_days"]
        wser = state["weather"][node]
        widx = max(0, min(len(wser) - 1, day + hd))
        w = wser[widx]
        past = [wser[max(0, min(len(wser) - 1, day - k + hd))]["temp"] for k in range(1, 29)]
        ops_ser = state["ops"][node]
        ops = ops_ser[max(0, min(len(ops_ser) - 1, day + hd))]
        day0 = datetime.fromisoformat(state["day0"])
        wd = (day0 + timedelta(days=day)).weekday()
        n = NODES[node]
        f = [series[i - 1] / r28, series[i - 7] / r28, r7 / r28, wd, 1 if wd >= 5 else 0,
             w["temp"], w["temp"] - float(np.mean(past)), 1 if w["cond"] in ("Snow", "Blizzard") else 0,
             1 if w["cond"] == "Rain" else 0, ops, n["alt"] / 1000.0, TYPE_CODE[n["type"]]]
        f += [1 if c == cat else 0 for c in CATS]
        return f

    def _dataset(self, state, start_i=28, end_i=None):
        X, y, meta = [], [], []
        hist = state["history"]
        end_day = state["history_end_day"]
        for node in NODES:
            for cat in CATS:
                s = hist[node][cat]
                L = len(s)
                first_day = end_day - L
                stop = L if end_i is None else min(L, end_i(L))
                for i in range(start_i, stop):
                    r28 = max(1e-6, float(np.mean(s[i - 28:i])))
                    X.append(self._features(state, node, cat, s, i, first_day + i))
                    y.append(s[i] / r28)
                    meta.append((node, cat, r28, s[i], float(np.mean(s[i - 7:i]))))
        return np.array(X, dtype=float), np.array(y, dtype=float), meta

    def fit(self, state) -> dict:
        t0 = time.time()
        # --- validation on the last 14 days (one-step-ahead) ---
        X_all, y_all, meta_all = self._dataset(state)
        L = len(next(iter(next(iter(state["history"].values())).values())))
        per_series = L - 28
        holdout = 14
        idx_train, idx_test = [], []
        for s in range(len(NODES) * len(CATS)):
            base = s * per_series
            for k in range(per_series):
                (idx_test if k >= per_series - holdout else idx_train).append(base + k)
        idx_train, idx_test = np.array(idx_train), np.array(idx_test)
        if HAVE_SKLEARN:
            m = RandomForestRegressor(n_estimators=60, max_depth=12, min_samples_leaf=4, random_state=7, n_jobs=-1)
            m.fit(X_all[idx_train], y_all[idx_train])
            m.n_jobs = 1
            pred_ratio = m.predict(X_all[idx_test])
        else:
            pred_ratio = X_all[idx_test][:, 2]
        actual, pred, naive, cats = [], [], [], []
        for j, k in enumerate(idx_test):
            node, cat, r28, val, r7 = meta_all[k]
            actual.append(val)
            pred.append(pred_ratio[j] * r28)
            naive.append(r7)
            cats.append(cat)
        actual, pred, naive = np.array(actual), np.array(pred), np.array(naive)
        # weight each series equally by normalising errors by series scale
        scale = np.array([meta_all[k][2] for k in idx_test])
        wape_model = float(np.sum(np.abs(actual - pred) / scale) / np.sum(actual / scale))
        wape_naive = float(np.sum(np.abs(actual - naive) / scale) / np.sum(actual / scale))
        cats = np.array(cats)
        for c in CATS:
            mask = cats == c
            rs = (actual[mask] - pred[mask]) / scale[mask]
            self.resid_std[c] = float(np.std(rs)) if mask.any() else 0.1
            self.cat_wape[c] = float(np.sum(np.abs(actual[mask] - pred[mask]) / scale[mask]) /
                                     max(1e-6, np.sum(actual[mask] / scale[mask])))
        # --- final model on all data ---
        importances = {}
        if HAVE_SKLEARN:
            self.model = RandomForestRegressor(n_estimators=100, max_depth=12, min_samples_leaf=4,
                                               random_state=7, n_jobs=-1)
            self.model.fit(X_all, y_all)
            self.model.n_jobs = 1  # parallel for training, single-thread for fast small predictions
            imp = self.model.feature_importances_
            for g, names in FEATURE_GROUPS.items():
                importances[g] = round(float(sum(imp[FEATURE_NAMES.index(n)] for n in names)) * 100, 1)
        else:
            self.model = None
        self.meta = {
            "model": "Random Forest Regressor (100 trees)" if HAVE_SKLEARN else "Exponential smoothing (fallback)",
            "version": f"rf-v3.{state['history_end_day'] + 100}",
            "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "sim_trained_at": state["sim_time"],
            "training_rows": int(len(y_all)),
            "series": len(NODES) * len(CATS),
            "history_days": L,
            "holdout_days": holdout,
            "accuracy_pct": round((1 - wape_model) * 100, 1),
            "wape_pct": round(wape_model * 100, 1),
            "naive_wape_pct": round(wape_naive * 100, 1),
            "improvement_vs_naive_pct": round((wape_naive - wape_model) / max(1e-6, wape_naive) * 100, 1),
            "category_accuracy": {c: round((1 - self.cat_wape[c]) * 100, 1) for c in CATS},
            "driver_importance": importances,
            "train_seconds": round(time.time() - t0, 2),
            "features": FEATURE_NAMES,
        }
        self.cache = {}
        self.cache_key = None
        return self.meta

    # ------------------------------------------------------------------
    def forecast_all(self, state, horizon: int = 30) -> Dict[Tuple[str, str], dict]:
        key = (state["sim_time"][:10], state["history_end_day"], horizon, self.meta.get("trained_at"))
        if self.cache_key == key and self.cache:
            return self.cache
        if self.model is None and HAVE_SKLEARN:
            self.fit(state)
        end_day = state["history_end_day"]
        series = {(n, c): list(state["history"][n][c]) for n in NODES for c in CATS}
        keys = list(series)
        preds = {k: [] for k in keys}
        for h in range(horizon):
            day = end_day + h
            X = []
            for k in keys:
                s = series[k]
                X.append(self._features(state, k[0], k[1], s, len(s), day))
            X = np.array(X, dtype=float)
            ratio = self.model.predict(X) if self.model is not None else X[:, 2]
            for j, k in enumerate(keys):
                s = series[k]
                r28 = max(1e-6, float(np.mean(s[-28:])))
                val = max(0.0, float(ratio[j]) * r28)
                s.append(val)
                preds[k].append(val)
        out = {}
        for k in keys:
            node, cat = k
            hist = state["history"][node][cat]
            r28 = float(np.mean(hist[-28:]))
            sd = self.resid_std.get(cat, 0.1) * r28
            mean = preds[k]
            lower = [max(0.0, v - 1.645 * sd * (1 + 0.03 * h)) for h, v in enumerate(mean)]
            upper = [v + 1.645 * sd * (1 + 0.03 * h) for h, v in enumerate(mean)]
            out[k] = {"start_day": end_day, "mean": [round(v, 2) for v in mean],
                      "lower": [round(v, 2) for v in lower], "upper": [round(v, 2) for v in upper],
                      "confidence": round(max(0.5, min(0.97, 1 - self.cat_wape.get(cat, 0.15))), 2)}
        self.cache, self.cache_key = out, key
        return out

    # ------------------------------------------------------------------
    def explain(self, state, node: str, cat: str, fc: dict) -> List[str]:
        hist = state["history"][node][cat]
        hd = state["history_days"]
        end = state["history_end_day"]
        unit = CATEGORIES[cat]["unit"]
        r28, r7 = float(np.mean(hist[-28:])), float(np.mean(hist[-7:]))
        f7 = float(np.mean(fc["mean"][:7]))
        factors = [f"Last 28 days average: {r28:,.1f} {unit}/day; next 7 days forecast: {f7:,.1f} {unit}/day "
                   f"({(f7 / max(r28, 1e-6) - 1) * 100:+.0f}%)"]
        trend = (r7 / max(r28, 1e-6) - 1) * 100
        if abs(trend) >= 4:
            factors.append(f"Recent trend: last 7 days are {trend:+.0f}% versus the 28-day average")
        wser = state["weather"][node]
        past_t = np.mean([wser[end - k + hd]["temp"] for k in range(1, 8)])
        fut = [wser[min(len(wser) - 1, end + k + hd)] for k in range(0, 7)]
        fut_t = np.mean([w["temp"] for w in fut])
        if abs(fut_t - past_t) >= 1.5:
            effect = {"FUEL": "heating fuel demand", "WINTER": "winter clothing demand",
                      "RATIONS": "calorie requirement"}.get(cat)
            txt = f"Temperature forecast {fut_t - past_t:+.1f} C versus last week (avg {fut_t:.1f} C)"
            if effect:
                txt += f" - drives {effect} {'up' if fut_t < past_t else 'down'}"
            factors.append(txt)
        snow_days = sum(1 for w in fut if w["cond"] in ("Snow", "Blizzard"))
        if snow_days:
            factors.append(f"{snow_days} snow day(s) in the next 7 days"
                           + (" - more medical and spares usage" if cat in ("MEDICAL", "SPARES") else ""))
        ops = state["ops"][node]
        ops_days = [d for d in range(0, len(fc["mean"])) if ops[min(len(ops) - 1, end + d + hd)]]
        if ops_days:
            factors.append(f"Planned exercise/operations on forecast days {ops_days[0] + 1}-{ops_days[-1] + 1}"
                           f" - model expects a surge in {CATEGORIES[cat]['name'].lower()}")
        factors.append(f"Personnel strength: {NODES[node]['personnel']}; altitude {NODES[node]['alt']} m")
        return factors


ENGINE = ForecastEngine()
