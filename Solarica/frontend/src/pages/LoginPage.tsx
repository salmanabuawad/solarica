import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "../auth/AuthContext";

const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) || "/api";

export function LoginPage() {
  const { t } = useTranslation();
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail || t("login.invalidCredentials"));
        return;
      }
      await login(data.access_token);
      navigate("/", { replace: true });
    } catch {
      setError(t("login.serverError"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={styles.page}>
      <div style={styles.card}>
        <h1 style={styles.title}>{t("login.title")}</h1>
        <p style={styles.sub}>{t("login.subtitle")}</p>

        <form onSubmit={handleSubmit} style={styles.form}>
          <label style={styles.label}>
            {t("login.username")}
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              autoFocus
              style={styles.input}
              placeholder={t("login.usernamePlaceholder")}
              autoComplete="username"
            />
          </label>

          <label style={styles.label}>
            {t("login.password")}
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              style={styles.input}
              placeholder={t("login.passwordPlaceholder")}
            />
          </label>

          {error && <p style={styles.error}>{error}</p>}

          <button type="submit" disabled={busy} style={styles.btn}>
            {busy ? t("login.signingIn") : t("login.signIn")}
          </button>
        </form>

        <p style={styles.hint}>
          {t("login.firstTime")}{" "}
          <Link to="/register" style={styles.link}>
            {t("login.createAdminAccount")}
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
    fontSize: "1.7rem",
    fontWeight: 700,
    color: "#f1f5f9",
  },
  sub: {
    margin: "0 0 1.75rem",
    color: "#64748b",
    fontSize: "0.9rem",
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
    background: "#2563eb",
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
