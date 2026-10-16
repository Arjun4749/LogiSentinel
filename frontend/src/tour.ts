import type { Page } from "./ui";

export type TourStep = { page: Page; params?: Record<string, string>; title: string; say: string; doThis: string };

// The guided demo: a ready-made storyline for presenting the project to judges.
export const TOUR: TourStep[] = [
  {
    page: "dashboard", title: "One picture of the whole country",
    say: "LogiSentinel covers four sectors: northern mountains, eastern hills, the western desert and the islands. That is 26 locations and 182 supply lines. The Supply Readiness Index is one number out of 100 that tells a commander how well forward posts are stocked compared with how long resupply takes.",
    doThis: "Point at the live clock in the top bar (it runs in real time). Then click 'What does this number mean?' under the readiness gauge.",
  },
  {
    page: "ai", title: "AI Autopilot: it acts on its own",
    say: "Whenever any unit turns red, meaning it will run out before normal resupply can arrive, the AI raises the supply request itself. It then plans the transport and dispatches it, with no human click needed. Every decision is logged with its reasons, its confidence and how fast it responded.",
    doThis: "Open the top entry in the decision log and read the numbered reasons aloud. Show the switches: red = raise request + dispatch, amber = recommend to a planner.",
  },
  {
    page: "alerts", title: "AI raises the alerts",
    say: "Alerts come from AI shortage forecasts, anomaly detection on consumption, weather warnings and predicted convoy delays, as well as from IoT sensors. Each one carries a recommended action.",
    doThis: "Filter by 'Raised by AI', then open the 'Handled by AI' tab to show red alerts the autopilot already resolved.",
  },
  {
    page: "forecast", params: { node: "FP-E", category: "FUEL" }, title: "Machine-learning demand forecast",
    say: "A Random Forest model is trained on 90 days of consumption for 182 supply lines. Its inputs include temperature, snow, rain, heat, planned exercises, day of week and altitude. Tested on 14 days it never saw, it is about 90% accurate and has about 30% less error than a simple average. It retrains every night on the real consumption.",
    doThis: "Show the shaded 90% band and the 'Why this forecast' list. The model explains itself.",
  },
  {
    page: "inventory", title: "Humans still decide the amber cases",
    say: "Amber lines are below the reorder point but not yet in danger. The system shows exactly how much to order, from where and why, and a planner approves with one click.",
    doThis: "Click 'Why' on a line to show the formula, change the quantity, then press 'Approve & dispatch'.",
  },
  {
    page: "requests", title: "Fair priorities and multi-mode transport",
    say: "Every open request has a transparent 100-point priority score: urgency 40, criticality 30, feasibility 20 and waiting time 10. Requests raised by the AI are marked. The transport planner compares road convoys, ships, helicopters, transport aircraft and drones.",
    doThis: "Press 'Plan transport' on any request and compare the options' arrival time, cost and risk score.",
  },
  {
    page: "shipments", title: "Predictable shipment timing",
    say: "Every shipment follows four fixed steps on the mission clock. It is Scheduled until its vehicle is ready, then Loading (1 hour for trucks, 6 hours for ships), then In transit, then Delivered. Each change happens exactly at the time shown.",
    doThis: "Point at the 'Status and next step' column, for example 'Departs in 40 min'.",
  },
  {
    page: "map", title: "GIS map with alerted units",
    say: "Pulsing red rings mark units on alert. Routes are coloured by live condition and sea lanes are dashed blue. Icons show convoys, ships and aircraft on the move.",
    doThis: "Use the Theatre selector (top bar) or the sector tabs to fly to the Islands, then click a unit in 'Units on alert'.",
  },
  {
    page: "map", title: "Speed up time and watch the AI work",
    say: "The clock normally runs in real time. For a demo we can speed it up: 1440x means one real minute equals one simulated day. Stock gets used, convoys move, new posts turn red, and the AI Autopilot handles them on its own. Purple notifications pop up each time it acts.",
    doThis: "Press '1440x' in the top bar and wait about a minute. When a purple AI notification appears, click 'See why'. Then press 'Live' to return to real time.",
  },
  {
    page: "disruptions", title: "Weather and terrain intelligence",
    say: "Each sector has its own risks: blizzards and closed passes in the north, landslides in the east, dust storms and heat in the west, and cyclones over the sea lanes to the islands. Route risk combines weather, road condition, altitude and past delays.",
    doThis: "Show the 4-day route outlook, then press 'Report disruption' and close a road. Affected shipments and alerts update instantly.",
  },
  {
    page: "scenario", title: "What-if simulator",
    say: "Planners can rehearse a crisis without touching live data. The same engines run on a sandbox copy and are compared with the baseline.",
    doThis: "Run 'Cyclone closes island sea lanes' and then 'Blizzard + landslide (worst case)'. Read out the recommended actions.",
  },
  {
    page: "iot", title: "IoT-based inventory tracking",
    say: "RFID gates, fuel level sensors, cold-chain loggers and humidity sensors feed stock records and raise alerts automatically.",
    doThis: "Show the cold-chain breach at Post India, then press 'Reconcile stock' on an RFID mismatch.",
  },
  {
    page: "reports", title: "Situation report and accountability",
    say: "The SITREP is written automatically, including readiness by sector and the AI's actions. Every human and AI decision is in the audit log, with three access roles: Admin, Planner and Viewer.",
    doThis: "Download the SITREP, then open the Audit log and point at the rows done by 'LogiSentinel AI'.",
  },
];
