import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) || "/api";

export function RegisterPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ full_name: fullName, email, password }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail || "Registration failed");
        return;
      }
      // Auto-login after registration
      const loginRes = await fetch(`${API_BASE}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (loginRes.ok) {
        const loginData = await loginRes.json();
        await login(loginData.access_token);
      }
      navigate("/", { replace: true });
    } catch {
      setError("Could not reach the server.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={styles.page}>
      <div style={styles.card}>
        <h1 style={styles.title}>Create admin account</h1>
        <p style={styles.sub}>First-time setup — this only works when no users exist yet.</p>

        <form onSubmit={handleSubmit} style={styles.form}>
          <label style={styles.label}>
            Full name
            <input
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              required
              autoFocus
              style={styles.input}
              placeholder="Jane Smith"
            />
          </label>

          <label style={styles.label}>
            Email
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              style={styles.input}
              placeholder="you@example.com"
            />
          </label>

          <label style={styles.label}>
            Password
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
              style={styles.input}
              placeholder="8+ characters"
            />
          </label>

          {error && <p style={styles.error}>{error}</p>}

          <button type="submit" disabled={busy} style={styles.btn}>
            {busy ? "Creating…" : "Create account"}
          </button>
        </form>

        <p style={styles.hint}>
          Already have an account?{" "}
          <Link to="/login" style={styles.link}>
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: {
    minHeight: "100vh",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    background: "#0a0f1e",
  },
  card: {
    width: "100%",
    maxWidth: 380,
    background: "#111827",
    border: "1px solid #1f2937",
    borderRadius: 16,
    padding: "2rem",
  },
  title: {
    margin: "0 0 0.15rem",
    fontSize: "1.4rem",
    fontWeight: 700,
    color: "#f1f5f9",
  },
  sub: {
    margin: "0 0 1.75rem",
    color: "#64748b",
    fontSize: "0.85rem",
    lineHeight: 1.4,
  },
  form: {
    display: "flex",
    flexDirection: "column",
    gap: "1rem",
  },
  label: {
    display: "flex",
    flexDirection: "column",
    gap: "0.4rem",
    fontSize: "0.88rem",
    color: "#94a3b8",
  },
  input: {
    background: "#0f172a",
    border: "1px solid #334155",
    borderRadius: 10,
    color: "#f1f5f9",
    padding: "0.65rem 0.85rem",
    fontSize: "0.95rem",
    outline: "none",
    minHeight: 44,
  },
  btn: {
    marginTop: "0.5rem",
    background: "#16a34a",
    border: "none",
    borderRadius: 10,
    color: "#fff",
    fontWeight: 600,
    fontSize: "0.95rem",
    minHeight: 44,
    cursor: "pointer",
  },
  error: {
    color: "#ef4444",
    fontSize: "0.85rem",
    margin: 0,
  },
  hint: {
    marginTop: "1.25rem",
    textAlign: "center",
    color: "#64748b",
    fontSize: "0.85rem",
  },
  link: {
    color: "#60a5fa",
    textDecoration: "none",
  },
};
