# LogiSentinel: architecture and reviewer checklist

## Reviewer feedback → what was built

| Reviewer said the old prototype lacked | Now in LogiSentinel |
|---|---|
| AI should act automatically on red alerts (v4) | `ai.py`: AI Autopilot scans every supply line every 10 s; a red alert is confirmed twice, then a request is raised (or an open one taken over), transport planned and dispatched automatically; numbered reasoning, confidence and response time logged; escalates to humans when no transport is feasible |
| Clock not working properly (v4) | `clock.py`: background thread; simulation time = real time (IST day boundaries) by default; speeds 0x/1x/60x/360x/1440x; "Skip ahead"; catches up after restarts |
| Only the northern sector (v4) | Four sectors (north, east, west desert, islands), 26 locations, 24 road and sea routes, ships, transport aircraft, drinking water as a supply type, sector filters on every screen |
| Demand forecasting / predictive layer | `forecast.py`: global Random Forest, 90-day history, weather + exercises + calendar + altitude features, recursive 7/14/30-day forecast, 90% band, holdout validation against a naive baseline, feature importance, plain-English explanation, auto-retrain each simulated day |
| Link from forecast to replenishment | `planning.py`: safety stock (z·σ·√LT + buffer), reorder point, order-up-to level, stock-out date projection including incoming shipments, best-source selection, urgency |
| Request prioritisation | 100-point score: urgency 40, criticality 30, feasibility 20, ageing 10, with breakdown and rank |
| Transport module | Capacity-aware vehicle assignment (greedy fill, split loads, repositioning time), road / helicopter / drone options, ETA, cost, slack, scoring |
| GIS | Leaflet map: nodes, routes coloured by live condition, moving shipments, disruptions, weather layer; Dijkstra routing on the road graph |
| Scenario / what-if | `scenario.py`: sandboxed projection with demand change, route closures, assets down, severe weather and extra delay; baseline comparison and recommended actions |
| Environmental intelligence | Simulated 45-day weather per location; weather → travel-time multiplier, closures and risk; 4-day route outlook; optional live Open-Meteo check |
| Decision support (not just alerts) | Every alert carries a recommended action; one-click "Approve & dispatch"; SITREP |
| Security | JWT, PBKDF2 password hashes, RBAC (admin / planner / viewer) enforced server-side, Pydantic validation, CORS from env, audit log |
| IoT | RFID gates, fuel level, cold chain, humidity; ingestion endpoint; reconciliation; inventory accuracy KPI |
| Audit / reports | Audit trail with real and mission time; CSV exports; auto SITREP |
| Tests | 17 end-to-end pytest tests covering auth, RBAC, forecasting, replenishment, dispatch, disruptions, scenarios, simulation clock, IoT, alerts and exports |

## Layers

```
React + TypeScript web app (Vite build, served by FastAPI)
   │  REST / JSON, Bearer JWT
FastAPI  (app/main.py)  ── auth.py (JWT, roles)
   │
Decision engines
   forecast.py   planning.py   network.py   scenario.py
   sim.py        alerts.py     iot.py       reports.py
   ai.py (AI Autopilot)        clock.py (real-time mission clock thread)
   │
State store (store.py) → backend/data/state.json   ← seed.py generates synthetic data
```

## Main API endpoints

| Method | Path | Role |
|---|---|---|
| POST | /api/auth/login | public |
| GET | /api/dashboard, /api/map, /api/status | any |
| GET | /api/forecast?node=&category=&horizon=, /api/forecast/model, /api/forecast/overview | any |
| POST | /api/forecast/retrain | planner |
| GET | /api/inventory, /api/replenishment | any |
| POST | /api/replenishment/{id}/approve (auto_dispatch, qty), /snooze | planner |
| GET | /api/requests, /api/requests/{id}/plan | any |
| POST | /api/requests, /api/requests/{id}/approve, /dispatch | planner |
| POST | /api/requests/{id}/reject | admin |
| GET | /api/shipments, /api/assets | any |
| GET | /api/weather, /api/weather/live, /api/disruptions | any |
| POST | /api/disruptions, /api/disruptions/{id}/resolve | admin |
| GET/POST | /api/alerts, /api/alerts/{id}/ack, /resolve | any / planner |
| GET/POST | /api/scenarios/presets, /api/scenarios/run | any / planner |
| GET/POST | /api/iot, /api/iot/ingest | any / planner |
| POST | /api/iot/{id}/reconcile | admin |
| POST | /api/sim/advance (skip ahead), /api/clock (speed) | planner |
| GET/POST | /api/ai, /api/ai/config, /api/ai/scan | any / planner |
| GET | /api/reports/sitrep, /api/reports/summary, /api/export/{kind}.csv | any |
| GET | /api/audit | planner |
| POST | /api/admin/reset | admin |

Interactive docs: `http://127.0.0.1:8000/docs`.

## Key formulas

- **Safety stock** = 1.65 × σ(daily demand, 28 d) × √(lead time days) + buffer days × forecast daily demand (buffer: post 3, hub 5)
- **Reorder point** = forecast daily × lead time + safety stock
- **Order quantity** = forecast daily × (lead time + review period) + safety stock − (on hand + incoming)
- **Lead time** = Dijkstra road hours (weather and disruption multipliers) + 3 h handling + 6 h processing
- **Route risk (0-100)** = weather ≤40 + road condition ≤30 + terrain ≤15 + historical delays ≤15
- **Priority (0-100)** = urgency ≤40 + criticality ≤30 + feasibility ≤20 + waiting ≤10
- **Readiness index** = criticality-weighted share of forward-post supply lines whose cover exceeds lead time + 7 days (partial credit in between), reduced when transport demand exceeds capacity
- **Forecast accuracy** = 100 − WAPE on the last 14 held-out days (one-step ahead), compared with a 7-day moving average
