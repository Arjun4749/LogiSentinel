# LogiSentinel: 10-minute demo script

**Before the judges arrive:** start the app and log in as **Admin**. Go to *System & help → Reset demo data*, then open the **Dashboard** straight away. Five red cells are visible for about 15 seconds. Then the AI Autopilot handles them on its own, a purple notification appears, and the readiness gauge goes up. If you can, let the judges see this moment.

Day mode works best on projectors; night mode suits dark rooms (moon icon, top right). The built-in **Start guided demo** button follows the same storyline, so a presenter can read from it on screen.

---

## 0. Opening line (30 s)
> "Forward posts across India, in the Himalayas, the north-east hills, the Thar desert and the islands, run short because forecasts, stock registers, transport, weather and consumption are tracked in separate places. LogiSentinel puts them in one system. Its AI predicts what each post will need and, when a post is about to run out, raises the request and sends the supplies **automatically**."

## 1. Dashboard (1 min)
- **Live clock** (top bar): "Simulation time runs in real time, in IST."
- **Readiness gauge**: click *What does this number mean?* "It's like a fuel gauge for the supply chain. It counts how many forward supply lines are safe for the next 14 days. Each sector also has its own score."
- **AI briefing**: "The AI writes a short summary: what it handled, the next risk and the weather window."
- **Days-of-supply board**, grouped by sector: "Each bar is days of stock held; the dark tick is how long resupply takes."

## 2. AI Command Centre (2 min) - the main feature
- "When a unit turns **red**, meaning it will run out before normal resupply can arrive, the autopilot does six steps by itself: detect, forecast, size the order, pick a source, plan transport, and dispatch and log."
- Open the decision log for **Post Whiskey - drinking water** (western desert). Read the numbered reasons: "1.2 days of water left, ML forecast says stock-out in 2 days, resupply takes 0.6 days. It ordered about 30,000 litres and chose a road convoy from Supply Hub Papa because it arrives in time at low risk."
- Point at **Post Zulu** (islands): "It chose a **landing craft by sea**". Point at **Post Tango** (north-east): "Here it chose a **helicopter**, because medicine is life-critical and speed matters more than cost."
- Show the switches: "Red alerts: raise request and dispatch. Amber alerts: recommend to a human planner. A commander can change these rules."

## 3. Watch the AI work live (1 min)
- Press **1440x** in the top bar (1 real minute = 1 simulated day). Wait about a minute.
- "Time moves fast: stock is used, convoys move, and new posts turn red. Here comes the AI." A purple notification appears; click **See why**.
- Press **Live** to return to real time.

## 4. Alerts (45 s)
- "Alerts are raised by the AI too: shortage forecasts, **anomaly detection** on consumption, weather warnings and **predicted convoy delays**." Filter by *Raised by AI*, then open the *Handled by AI* tab.

## 5. Forecast (1 min)
- Open *Demand forecast* for Post Echo fuel. "This is a Random Forest model trained on 90 days for 182 supply lines. Its inputs include temperature, snow, heat, exercises, day of week and altitude. On 14 days it never saw, it is about 90% accurate and has about 30% less error than a simple average. It retrains every night."

## 6. Humans approve amber, transport planning (1.5 min)
- *Stock & replenishment*: "Amber lines wait for a planner." Click **Why** to show the formula, change the quantity, then press **Approve & dispatch**.
- *Supply requests*: "Each request has a transparent 100-point priority score. Requests the AI raised are marked." Press **Plan transport**: "It compares road, sea, helicopter, aircraft and drone by arrival time, cost and risk."
- *Transport & shipments*: "Every shipment follows fixed steps: Scheduled, then Loading, then In transit, then Delivered. Each step happens at the time shown, for example 'Departs in 40 min'."

## 7. Map, disruptions, what-if (1.5 min)
- *Network map*: "Pulsing rings mark units on alert." Use the sector tabs to fly to the Islands; click a unit in *Units on alert*.
- *Weather & disruptions*: "Each sector has its own risks: blizzards in the north, landslides in the east, dust storms in the west and cyclones at sea." Report a disruption to close a road.
- *What-if simulator*: run **Cyclone closes island sea lanes**. "It runs in a sandbox and tells us what to do now."

## 8. Close (30 s)
- *Reports & SITREP*: "The situation report writes itself, including the AI's actions." *Audit log*: "Every human **and AI** decision is recorded."
> "LogiSentinel doesn't just warn about shortages. It acts on them automatically, explains why, and keeps commanders in control."

---

## Likely judge questions

**Is the AI really acting on its own?**
Yes. A background engine checks all 147 supply lines every 10 seconds. A red alert is confirmed on two consecutive scans, and then the autopilot creates the request, plans transport and dispatches it. It writes a full reasoning log and an audit entry as "LogiSentinel AI". If no transport is feasible it **escalates to a human** instead of guessing.

**Can a human stop it?**
Yes. In the AI Command Centre, a planner can switch it off, or set red alerts to "raise request only" or "alert only".

**Is the data real?**
No. It is fully synthetic but realistic: 90 days of consumption driven by temperature, altitude, heat, exercises and weekdays, with random noise. The model never sees the formula; it learns the patterns from data.

**Why only the north?**
It isn't. There are four sectors with different terrain and logistics: mountain passes (north), landslide-prone hills (east), desert with water as a critical supply (west), and islands supplied by sea and air.

**Why Random Forest?**
It works well with small tabular data, trains in a few seconds on a laptop, needs no GPU, and gives feature importance for explainability. It is validated against a naive baseline on held-out days.

**How is risk scored?**
0 to 100 = weather (max 40) + road condition/disruption (max 30) + terrain/altitude (max 15) + historical delay rate (max 15), checked for every day of the journey.

**What about security?**
JWT-signed sessions, hashed passwords, three roles enforced on the server, input validation on every endpoint, and a full audit trail of human and AI actions. It runs fully offline on one laptop.

**What's next?**
Real stock-register and GPS integrations through the existing REST and IoT ingest endpoints, multi-stop convoy routing, and a mobile app for posts to raise requests.
