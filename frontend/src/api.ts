
const BASE = (import.meta as any).env?.VITE_API_BASE_URL || "";

export type User = {
  username: string;
  role: "admin" | "planner" | "viewer";
  name: string;
  title: string;
};

const DEMO_USERS: Record<string, { password: string; role: User["role"]; name: string; title: string }> = {
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
    t ? localStorage.setItem("ls_token", t) : localStorage.removeItem("ls_token");
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

export async function api<T = any>(
  path: string,
  opts: { method?: string; body?: any; text?: boolean } = {}
): Promise<T> {
  // Local demo login: no backend required.
  if (path === "/api/auth/login" && !BASE) {
    const username = String(opts.body?.username || "").trim().toLowerCase();
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

  // Restore the locally selected demo account after refresh.
  if (path === "/api/auth/me" && token?.startsWith("demo-") && !BASE) {
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

  // All other requests still require a real backend.
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
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
    });
  } catch {
    throw new ApiError(
      0,
      "Backend unavailable. This demo login works locally, but this feature requires the backend."
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
        msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
      }
    } catch {
      // Ignore non-JSON errors.
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
