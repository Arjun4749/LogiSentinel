import { FormEvent, useEffect, useMemo, useState } from "react";
import { LogIn, ShieldCheck, ClipboardCheck, Eye } from "lucide-react";
import { api, User } from "../api";
import { Btn } from "../ui";

const ROLES = [
  { username: "admin", password: "admin123", role: "Admin", name: "Col. R. Mehta", icon: ShieldCheck,
    can: "Everything, plus disruptions, stock reconciliation and data reset" },
  { username: "planner", password: "planner123", role: "Planner", name: "Maj. A. Verma", icon: ClipboardCheck,
    can: "Approve, plan and dispatch supplies; run simulations" },
  { username: "viewer", password: "viewer123", role: "Viewer", name: "Capt. S. Iyer", icon: Eye,
    can: "Read-only access to every screen" },
];

// Procedural contour lines - a quiet nod to the mountain terrain this system plans for.
function Contours() {
  const paths = useMemo(() => {
    const out: string[] = [];
    for (let k = 0; k < 16; k++) {
      const base = 120 + k * 34;
      let d = `M -20 ${base}`;
      for (let x = 0; x <= 820; x += 20) {
        const y = base - 70 * Math.exp(-(((x - 300) / 140) ** 2)) * (1 - k / 22) - 45 * Math.exp(-(((x - 600) / 90) ** 2)) * (1 - k / 18)
          + 6 * Math.sin(x / 37 + k);
        d += ` L ${x} ${y.toFixed(1)}`;
      }
      out.push(d);
    }
    return out;
  }, []);
  return (
    <svg className="contours" viewBox="0 0 800 700" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
      {paths.map((d, i) => <path key={i} d={d} style={{ animationDelay: `${i * 70}ms` }} />)}
      <g className="contour-route">
        <path d="M 120 520 C 220 470, 260 380, 300 330 S 420 260, 520 300 S 610 230, 640 210" />
        <circle cx="120" cy="520" r="7" /><circle cx="300" cy="330" r="6" /><circle cx="520" cy="300" r="6" /><circle cx="640" cy="210" r="8" className="fp" />
      </g>
    </svg>
  );
}

export default function Login({ onLogin, theme }: { onLogin: (u: User, token: string) => void; theme: string }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  useEffect(() => { document.documentElement.dataset.theme = theme; }, [theme]);

  const signIn = async (u: string, p: string, key: string) => {
    setBusy(key); setErr(null);
    try {
      const r: any = await api("/api/auth/login", { method: "POST", body: { username: u, password: p } });
      onLogin(r.user, r.access_token);
    } catch (e: any) { setErr(e.message); }
    finally { setBusy(null); }
  };
  const submit = (e: FormEvent) => { e.preventDefault(); signIn(username, password, "form"); };

  return (
    <div className="login">
      <div className="login-art">
        <Contours />
        <div className="login-copy">
          <div className="login-brand">LogiSentinel</div>
          <h1>Know what forward posts will need before they run short.</h1>
          <p>An AI decision-support system for remote supply chains across the mountains, north-east hills, desert and islands. It brings demand forecasting, route-aware transport planning, weather risk and sensor data together in one place.</p>
          <ul>
            <li><b>Predict</b> consumption per post and supply type with machine learning</li>
            <li><b>Act</b> automatically: the AI Autopilot raises and dispatches requests for red alerts</li>
            <li><b>Plan</b> the safest, fastest way to move stock by road, sea, helicopter, aircraft or drone</li>
            <li><b>Rehearse</b> blizzards, cyclones, closures and surges before they happen</li>
          </ul>
        </div>
      </div>
      <div className="login-panel">
        <form onSubmit={submit} className="login-form">
          <h2>Sign in</h2>
          <label className="field"><span className="field-label">Username</span>
            <input value={username} onChange={e => setUsername(e.target.value)} autoComplete="username" placeholder="admin" /></label>
          <label className="field"><span className="field-label">Password</span>
            <input type="password" value={password} onChange={e => setPassword(e.target.value)} autoComplete="current-password" placeholder="admin123" /></label>
          {err && <div className="form-err">{err}</div>}
          <Btn type="submit" kind="primary" busy={busy === "form"} icon={<LogIn size={16} />}>Sign in</Btn>
        </form>
        <div className="demo-accounts">
          <h3>One-click demo accounts</h3>
          {ROLES.map(r => {
            const Icon = r.icon;
            return (
              <button key={r.username} className="demo-acct" onClick={() => signIn(r.username, r.password, r.username)} disabled={!!busy}>
                <Icon size={20} />
                <div><strong>{r.role} <span>{r.name}</span></strong><small>{r.can}</small></div>
                <code>{r.username} / {r.password}</code>
              </button>
            );
          })}
        </div>
        <p className="login-note">Smart India Hackathon prototype. Every location, unit and number is synthetic demo data.</p>
      </div>
    </div>
  );
}
