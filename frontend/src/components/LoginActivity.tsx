import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { getLoginLog, type LoginLog } from "../api";

// Admin-only view of the login audit log: headline interest numbers (distinct
// users / IPs, overall and last 7 days) plus a table of recent sign-ins.
export default function LoginActivity() {
  const { t } = useTranslation();
  const [data, setData] = useState<LoginLog | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    setBusy(true); setErr(null);
    try { setData(await getLoginLog(500)); }
    catch (ex: any) { setErr(ex?.message || String(ex)); }
    finally { setBusy(false); }
  }
  useEffect(() => { load(); }, []);

  const s = data?.summary;
  const events = data?.events || [];

  function fmt(iso?: string | null) {
    if (!iso) return "—";
    try { return new Date(iso).toLocaleString(); } catch { return iso; }
  }

  return (
    <div style={{ padding: 4 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12, flexWrap: "wrap" }}>
        <div style={{ fontSize: 16, fontWeight: 700, color: "#0f172a" }}>{t("loginlog.title", "Login activity")}</div>
        <span style={{ fontSize: 12, color: "#64748b" }}>{events.length} {t("loginlog.recent", "recent logins")}</span>
        <div style={{ flex: 1 }} />
        <button onClick={load} disabled={busy} className="btn btn-secondary btn-sm">{t("app.refresh", "Refresh")}</button>
      </div>

      {err && <div style={errBox}>{err}</div>}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: 10, marginBottom: 14 }}>
        <Stat label={t("loginlog.distinctUsers", "Distinct users")} value={s?.distinct_users} accent="#2563eb" />
        <Stat label={t("loginlog.distinctIps", "Distinct IPs")} value={s?.distinct_ips} accent="#0891b2" />
        <Stat label={t("loginlog.totalLogins", "Total logins")} value={s?.total_logins} accent="#16a34a" />
        <Stat label={t("loginlog.users7", "Users (7 days)")} value={s?.last7_users} accent="#7c3aed" />
        <Stat label={t("loginlog.logins7", "Logins (7 days)")} value={s?.last7_logins} accent="#db2777" />
      </div>

      <div style={{ border: "1px solid #e2e8f0", borderRadius: 12, overflow: "hidden", background: "#fff" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ background: "#f1f5f9", color: "#334155", textAlign: "left" }}>
              <th style={th}>{t("login.username", "Username")}</th>
              <th style={th}>{t("users.role", "Role")}</th>
              <th style={th}>{t("loginlog.ip", "IP address")}</th>
              <th style={th}>{t("loginlog.when", "When")}</th>
            </tr>
          </thead>
          <tbody>
            {events.map((e, i) => (
              <tr key={i} style={{ borderTop: "1px solid #f1f5f9" }}>
                <td style={{ ...td, fontWeight: 600, fontFamily: "monospace", color: "#0f172a" }}>{e.username}</td>
                <td style={td}>{e.role || "—"}</td>
                <td style={{ ...td, fontFamily: "monospace" }}>{e.ip || "—"}</td>
                <td style={td}>{fmt(e.created_at)}</td>
              </tr>
            ))}
            {events.length === 0 && (
              <tr><td colSpan={4} style={{ padding: 24, textAlign: "center", color: "#64748b" }}>{busy ? t("app.loading") : t("loginlog.none", "No logins recorded yet.")}</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Stat({ label, value, accent }: { label: string; value?: number; accent: string }) {
  return (
    <div style={{ border: "1px solid #e2e8f0", borderRadius: 12, padding: "12px 14px", background: "#fff" }}>
      <div style={{ fontSize: 26, fontWeight: 800, color: accent, lineHeight: 1.1 }}>{value ?? "—"}</div>
      <div style={{ fontSize: 11, color: "#64748b", fontWeight: 600, marginTop: 4 }}>{label}</div>
    </div>
  );
}

const th: React.CSSProperties = { padding: "10px 12px", fontWeight: 700, fontSize: 12, textTransform: "uppercase", letterSpacing: 0.05 };
const td: React.CSSProperties = { padding: "8px 12px", verticalAlign: "middle" };
const errBox: React.CSSProperties = { background: "#fee2e2", color: "#b91c1c", border: "1px solid #fecaca", padding: "8px 12px", borderRadius: 8, fontSize: 13, marginBottom: 10 };
