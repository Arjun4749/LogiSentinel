
const BASE = (import.meta as any).env?.VITE_API_BASE_URL || "";

export type User = {
  username: string;
  role: "admin" | "planner" | "viewer";
  name: string;
  title: string;
};

const DEMO_USERS: Record<
  string,
  { password: string; role: User["role"]; name: string; title: string }
> = {
  admin: {
    password: "admin123",
    role: "admin",
    name: "Col. R. Mehta",
    title: "Admin",
  },
  planner: {
    password: "planner123",
    role: "planner",
    name: "Maj. A. Verma",
    title: "Planner",
  },
  viewer: {
    password: "viewer123",
    role: "viewer",
    name: "Capt. S. Iyer",
    title: "Viewer",
  },
};

let token: string | null = null;

try {
  token = localStorage.getItem("ls_token");
} catch {
  token = null;
}

let onUnauthorized: () => void = () => {};

export function setUnauthorizedHandler(fn: () => void) {
  onUnauthorized = fn;
}

export function setToken(t: string | null) {
  token = t;

  try {
    if (t) {
      localStorage.setItem("ls_token", t);
    } else {
      localStorage.removeItem("ls_token");
      localStorage.removeItem("ls_user");
    }
  } catch {
    // Ignore unavailable localStorage.
  }
}

export function getToken() {
  return token;
}

export class ApiError extends Error {
  status: number;

  constructor(status: number, msg: string) {
    super(msg);
    this.status = status;
  }
}

// Sample dashboard data for the frontend-only presentation.
function getDemoDashboard() {
  const categories = [
    "RATIONS",
    "WATER",
    "FUEL",
    "MEDICAL",
    "AMMO",
    "SPARES",
    "WINTER",
  ];

  const locations = [
    ["FP-E", "Post Echo", "NORTH"],
    ["FP-F", "Post Foxtrot", "NORTH"],
    ["FP-I", "Post India", "NORTH"],
    ["FP-R", "Post Romeo", "EAST"],
    ["FP-T", "Post Tango", "EAST"],
    ["FP-V", "Post Victor", "WEST"],
    ["FP-W", "Post Whiskey", "WEST"],
    ["FP-Z", "Post Zulu", "ISLANDS"],
  ];

  const matrix = locations.map(([node, name, sector], i) => ({
    node,
    name,
    sector,
    type: "post",
    cells: Object.fromEntries(
      categories.map((category, j) => {
        const days = 3 + ((i * 7 + j * 5) % 28);

        return [
          category,
          {
            status: days < 7 ? "CRITICAL" : days < 14 ? "LOW" : "OK",
            days,
            cover: days + 3,
            incoming: days < 7 ? 100 : 0,
            lead: 4 + (i % 5),
            on_hand: 100 + i * 35 + j * 20,
            unit:
              category === "WATER" || category === "FUEL"
                ? "L"
                : "units",
          },
        ];
      })
    ),
  }));

  const now = new Date();

  const demand_chart = Array.from({ length: 44 }, (_, i) => {
    const date = new Date(now);
    date.setDate(date.getDate() - 30 + i);

    const value = 18 + Math.sin(i / 3) * 3 + i * 0.12;

    return {
      date: date.toISOString().slice(0, 10),
      ...(i < 30
        ? { actual: Number(value.toFixed(2)) }
        : {
            forecast: Number(value.toFixed(2)),
            lower: Number((value * 0.85).toFixed(2)),
            upper: Number((value * 1.15).toFixed(2)),
          }),
    };
  });

  return {
    sim_time: now.toISOString(),

    kpis: {
      readiness_index: 82.4,
      readiness_lines: {
        safe: 38,
        total: 56,
        watch: 12,
        risk: 6,
      },
      sector_readiness: {
        NORTH: 78,
        EAST: 84,
        WEST: 91,
        ISLANDS: 86,
      },
      ai_enabled: true,
      ai_handled: 12,
      ai_requests: 8,
      forecast_accuracy_pct: 91.2,
      forecast_improvement_pct: 14,
      on_time_delivery_pct: 94.5,
      transport_utilisation_pct: 72,
      posts_at_risk: 4,
      posts_total: 8,
      alerts_critical: 3,
      alerts_high: 5,
      alerts_total: 12,
      alerts_new: 8,
      pending_requests: 4,
      active_shipments: 7,
      delayed_shipments: 2,
      active_disruptions: 2,
      inventory_accuracy_pct: 97.5,
      stockouts_prevented: 9,
      shipments_delivered: 42,
    },

    briefing: [
      "DEMO DATA: Overall supply readiness is 82.4/100.",
      "Four simulated locations require stock monitoring.",
      "Two simulated transport or weather disruptions are active.",
      "AI Autopilot is enabled in this demonstration dataset.",
    ],

    ai_log: [],
    matrix,
    demand_chart,

    category_mix: categories.map((category, i) => ({
      category,
      name: category,
      tonnes: 8 + i * 2,
      color: "#2f8fd8",
    })),

    fleet: {
      AVAILABLE: 12,
      ON_MISSION: 7,
      MAINTENANCE: 2,
    },

    events: [],
    top_alerts: [],
    top_recommendations: [],
    recommendation_count: 4,
  };
}

export async function api<T = any>(
  path: string,
  opts: {
    method?: string;
    body?: any;
    text?: boolean;
  } = {}
): Promise<T> {
  // Demo login works without a backend.
  if (!BASE && path === "/api/auth/login") {
    const username = String(opts.body?.username || "")
      .trim()
      .toLowerCase();
    const password = String(opts.body?.password || "");
    const demo = DEMO_USERS[username];

    if (!demo || demo.password !== password) {
      throw new ApiError(401, "Wrong username or password");
    }

    const user: User = {
      username,
      role: demo.role,
      name: demo.name,
      title: demo.title,
    };

    const demoToken = `demo-${username}-session`;
    setToken(demoToken);

    return {
      access_token: demoToken,
      token_type: "bearer",
      user,
    } as T;
  }

  // Restore the demo session after a page refresh.
  if (!BASE && path === "/api/auth/me" && token?.startsWith("demo-")) {
    const username = token.slice(5, -8);
    const demo = DEMO_USERS[username];

    if (demo) {
      return {
        username,
        role: demo.role,
        name: demo.name,
        title: demo.title,
      } as T;
    }

    setToken(null);
    throw new ApiError(401, "Demo session expired");
  }

  // Supply the dashboard without contacting a backend.
  if (!BASE && path === "/api/dashboard") {
    return getDemoDashboard() as T;
  }

  // Supply the top-bar simulation status.
  if (!BASE && path === "/api/status") {
    const now = new Date().toISOString();

    return {
      sim_time: now,
      alerts_new: 8,
      alerts_critical: 3,
      clock: {
        sim_time: now,
        pending_hours: 0,
        speed: 1,
      },
      ai: {
        enabled: true,
        actions: 12,
        last: null,
        handled: 12,
      },
    } as T;
  }

  // All other endpoints require the real backend.
  let res: Response;

  try {
    res = await fetch(BASE + path, {
      method: opts.method || "GET",
      headers: {
        "Content-Type": "application/json",
        ...(token && !token.startsWith("demo-")
          ? { Authorization: `Bearer ${token}` }
          : {}),
      },
      body:
        opts.body !== undefined
          ? JSON.stringify(opts.body)
          : undefined,
    });
  } catch {
    throw new ApiError(
      0,
      "This feature needs the backend server. Dashboard demo data is available, but this API is not connected."
    );
  }

  if (res.status === 401 && path !== "/api/auth/login") {
    onUnauthorized();
  }

  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`;

    try {
      const j = await res.json();

      if (j.detail) {
        msg =
          typeof j.detail === "string"
            ? j.detail
            : JSON.stringify(j.detail);
      }
    } catch {
      // Ignore non-JSON error responses.
    }

    throw new ApiError(res.status, msg);
  }

  return (opts.text ? res.text() : res.json()) as Promise<T>;
}

export async function download(path: string, filename: string) {
  const res = await fetch(BASE + path, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });

  if (!res.ok) {
    throw new ApiError(res.status, "Download failed");
  }

  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");

  a.href = url;
  a.download = filename;
  a.click();

  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
