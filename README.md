# LogiSentinel: Predictive Logistics & Forward Supply Chain

**Smart India Hackathon prototype.** LogiSentinel is an AI decision-support system for keeping forward formations supplied in remote and difficult areas across India: the northern mountains, the north-east hills, the western desert and the islands. It brings demand forecasting, inventory, transport capacity, terrain and weather, and consumption patterns into one connected system.

**New in version 4:**
- **AI Autopilot.** When any unit turns red, the AI raises the supply request itself, plans the transport and dispatches it with no human click. Every decision is explained in the AI Command Centre.
- **Live clock.** It runs in real time (IST) by default, with Pause and 60x, 360x and 1440x demo speeds, and "Skip ahead".
- **Pan-India coverage.** There are four sectors and 26 locations, with road convoys, ships, helicopters, transport aircraft and drones.
- **More AI alerts.** These include shortage forecasts, consumption anomaly detection, weather warnings and predicted convoy delays.

> All locations, units and numbers are **synthetic demo data**. No real military information is used.

---

## 1. Run it (2 steps)

**You need:** Python 3.10 or newer ([python.org/downloads](https://www.python.org/downloads/)). On Windows, tick **"Add Python to PATH"** during installation.

You do **not** need Node.js. The web app is already built.

| Windows | Mac / Linux |
|---|---|
| Double-click **`START_WINDOWS.bat`** | Open a terminal in this folder and run `bash start_mac_linux.sh` |

- The **first run** installs packages, which takes 2 to 5 minutes and needs internet.
- After that, startup takes about 10 seconds and works **offline**. Only the background map images and the optional "live weather" check need internet.
- Your browser opens at **http://127.0.0.1:8000**. If it doesn't, open that address yourself.
- Keep the black window open while presenting. Close it to stop the app.

### Demo logins (one-click buttons on the login page)

| Role | Username | Password | Can do |
|---|---|---|---|
| Admin | `admin` | `admin123` | Everything, plus disruptions, stock reconciliation and data reset |
| Planner | `planner` | `planner123` | Approve, plan and dispatch supplies; run simulations |
| Viewer | `viewer` | `viewer123` | Read-only |

### Manual start (if the scripts don't work)
```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate      Mac/Linux:  source .venv/bin/activate
pip install -r backend/requirements.txt
python run.py
```

---

## 2. Presenting to judges

1. Log in as **Admin**.
2. Click **Start guided demo** (bottom-left). It walks through 13 steps. Each step opens the right screen, tells you **what to say** and **what to click**.
3. The full 10-minute script, with answers to likely judge questions, is in **`docs/DEMO_SCRIPT.md`**.
4. Before each new presentation, open **System & help → Reset demo data** to get a fresh scenario. About 15 seconds after a reset, the AI Autopilot handles the five red units on its own (Post Echo fuel, Post India medical, Post Tango medical, Post Whiskey water and Post Zulu rations). If the dashboard is open, the judges can watch this happen.
5. To show the AI working live, press **1440x** in the top bar (1 real minute = 1 simulated day). New units turn red and the AI handles them, and a purple notification appears each time. Press **Live** to go back to real time.

---

## 3. What is inside

| Screen | What it does |
|---|---|
| **Dashboard** | Readiness gauge with a plain-English explanation and per-sector scores, AI briefing, KPIs, days-of-supply board grouped by sector, demand trend, amber approvals, activity log |
| **AI Command Centre** | AI Autopilot on/off and rules (red: raise and dispatch; amber: recommend or raise), the 6-step decision pipeline, and a decision log with numbered reasons, confidence and response time |
| **Network map (GIS)** | All four sectors; pulsing rings on units on alert, a "Units on alert" list that zooms to each unit, road and sea lanes coloured by condition, live convoys, ships and aircraft |
| **Alerts** | AI-raised alerts (shortage forecast, anomaly, weather, delay prediction) plus sensor and tracking alerts; a "Handled by AI" tab; acknowledge and resolve, with audit |
| **Demand forecast (AI/ML)** | Random Forest forecast per location and supply type with a 90% band, plain-English reasons, model accuracy against a baseline, and feature importance |
| **Stock & replenishment** | Safety stock, reorder point and order quantity from the forecast and real lead time. One-click "Approve & dispatch" |
| **Supply requests** | 100-point priority score (urgency 40, criticality 30, feasibility 20, waiting 10). AI-raised requests are marked. The transport planner compares road, sea, helicopter, aircraft and drone options |
| **Transport & shipments** | Each shipment shows its stage (Scheduled, then Loading, then In transit, then Delivered) with a countdown such as "Departs in 40 min"; the fleet with capacity and service status |
| **Weather & disruptions** | Report or clear disruptions; 4-day route outlook; 7-day weather; optional live weather (Open-Meteo) |
| **What-if simulator** | Sandbox scenarios (pass closure, surge, fleet loss, blizzard) compared against the baseline, with recommended actions |
| **IoT sensors** | RFID gates, fuel level, cold chain and humidity sensors; stock reconciliation; test readings |
| **Reports & SITREP** | Auto-written situation report; CSV exports |
| **Audit log** | Every action with user, role, real time and mission time |

The **mission clock** (top bar) runs in **real time** by default, so the time shown is the real current time in IST. Stock is consumed, convoys move, disruptions delay them, deliveries update stock, the AI Autopilot checks every unit every 10 seconds, and each midnight the ML model **retrains** on the new actual consumption. Use the speed buttons (Pause, Live, 60x, 360x, 1440x) or **Skip ahead** to move faster in a demo. The **Theatre** selector in the top bar switches every screen between All India and a single sector.

---

## 4. For developers

```
logisentinel/
├── run.py                  one-command launcher (API + web app on port 8000)
├── START_WINDOWS.bat       one-click start for Windows
├── start_mac_linux.sh      one-click start for Mac/Linux
├── backend/
│   ├── app/
│   │   ├── main.py         FastAPI routes (49 endpoints, docs at /docs)
│   │   ├── reference.py    network: nodes, routes, supply types, fleet, users
│   │   ├── seed.py         synthetic data generator (90-day history, weather, sensors)
│   │   ├── forecast.py     ML demand forecasting engine (scikit-learn)
│   │   ├── planning.py     inventory risk, replenishment, prioritisation, transport planner
│   │   ├── network.py      GIS routing (Dijkstra), weather effects, risk scoring
│   │   ├── scenario.py     what-if simulator
│   │   ├── sim.py          simulation: consumption, movement, delays, delivery
│   │   ├── clock.py        real-time mission clock (background thread, speeds)
│   │   ├── ai.py           AI Autopilot: auto-request + auto-dispatch on red alerts
│   │   ├── alerts.py       alert & recommendation engine
│   │   ├── iot.py          IoT device simulation and ingestion
│   │   ├── reports.py      dashboard, map data, SITREP
│   │   ├── auth.py         JWT login + role-based access
│   │   └── store.py        state + JSON persistence (backend/data/state.json)
│   ├── static/             built web app (served by FastAPI)
│   ├── tests/              17 end-to-end tests  ->  python -m pytest -q
│   └── requirements.txt
├── frontend/               React + TypeScript + Vite source
└── docs/                   DEMO_SCRIPT.md, ARCHITECTURE.md
```

**Rebuilding the web app** (only needed if you change frontend code; requires Node.js 18+):
```bash
cd frontend
npm install
npm run dev      # live development at http://localhost:5173 (start the backend with: python run.py)
npm run build    # writes the production build into backend/static
```

**Run tests:** `cd backend && pip install pytest httpx && python -m pytest -q`

**API documentation:** http://127.0.0.1:8000/docs (interactive Swagger)

---

## 5. Troubleshooting

| Problem | Fix |
|---|---|
| "Python was not found" | Install Python 3.10+ and tick "Add Python to PATH". Restart the computer, then run the start file again. |
| Install fails on the first run | Check internet, delete the `.venv` folder, run the start file again. |
| Port 8000 already in use | The launcher picks the next free port automatically. Read the address printed in the window. |
| Map background is grey | The base map needs internet. Routes, posts and convoys still work offline. |
| Data looks messy after a long demo | System & help → Reset demo data (admin), or stop the app and delete `backend/data/state.json`. |
| Logged out suddenly | Sessions last 12 hours. Log in again. |
