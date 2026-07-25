import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  runValidation, getValidationScore, getValidationFindings, getFinding,
  setFindingStatus, applyRepair, type ValidationFinding, type ValidationScore,
} from "../api";

// Severity → colour (independent of the string-status palette).
const SEV: Record<string, { c: string; bg: string; label: string }> = {
  critical: { c: "#dc2626", bg: "#fee2e2", label: "Critical" },
  warning: { c: "#c2620a", bg: "#fdecd2", label: "Warning" },
  info: { c: "#2563eb", bg: "#dbeafe", label: "Info" },
};
const VALIDATORS = ["gap", "naming", "duplicate", "metadata", "commissioning", "ai"];

// Continuous validation & data-quality view for a project. Admin-only (mounted
// from App under the Configurations nav). Reuses the existing .btn design system.
export default function ValidationDashboard({ projectId, onShowAsset }: {
  projectId: string;
  onShowAsset?: (assetRef: string) => void;
}) {
  const { t } = useTranslation();
  const [score, setScore] = useState<ValidationScore | null>(null);
  const [findings, setFindings] = useState<ValidationFinding[]>([]);
  const [running, setRunning] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [fSev, setFSev] = useState("");
  const [fVal, setFVal] = useState("");
  const [fStatus, setFStatus] = useState("open");

  const load = useCallback(async () => {
    setErr(null);
    try {
      const [s, f] = await Promise.all([
        getValidationScore(projectId),
        getValidationFindings(projectId, {
          severity: fSev || undefined, validator: fVal || undefined,
          status: fStatus || undefined, limit: 2000,
        }),
      ]);
      setScore(s);
      setFindings(f.findings);
    } catch (ex: any) { setErr(ex?.message || String(ex)); }
  }, [projectId, fSev, fVal, fStatus]);

  useEffect(() => { load(); }, [load]);

  async function onRun() {
    setRunning(true); setErr(null);
    try { await runValidation(projectId); await load(); }
    catch (ex: any) { setErr(ex?.message || String(ex)); }
    finally { setRunning(false); }
  }

  async function triage(f: ValidationFinding, status: string) {
    setBusy(true); setErr(null);
    try { await setFindingStatus(f.id, status); await load(); }
    catch (ex: any) { setErr(ex?.message || String(ex)); }
    finally { setBusy(false); }
  }

  async function approveFix(f: ValidationFinding) {
    setBusy(true); setErr(null);
    try {
      const detail = await getFinding(f.id);          // list rows don't carry repairs
      const rep = detail.repairs?.[0];
      if (rep) { await applyRepair(rep.id); await load(); }
      else { setErr(t("validation.noRepair", "No repair suggestion for this finding.")); }
    } catch (ex: any) { setErr(ex?.message || String(ex)); }
    finally { setBusy(false); }
  }

  const sc = score?.score ?? 0;
  const scoreColor = sc >= 95 ? "#16a34a" : sc >= 80 ? "#c2620a" : "#dc2626";

  return (
    <div style={{ padding: 4 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 14, flexWrap: "wrap" }}>
        <div style={{ fontSize: 16, fontWeight: 700, color: "#0f172a" }}>{t("validation.title", "Validation")}</div>
        {score?.latest_run?.started_at && (
          <span style={{ fontSize: 12, color: "#64748b" }}>
            {t("validation.lastRun", "last run")} {new Date(score.latest_run.started_at).toLocaleString()}
          </span>
        )}
        <div style={{ flex: 1 }} />
        <button onClick={onRun} disabled={running} className="btn btn-primary btn-md" style={{ fontSize: 13 }}>
          {running ? t("validation.running", "Running…") : `▶ ${t("validation.run", "Run validation")}`}
        </button>
        <button onClick={load} disabled={busy} className="btn btn-secondary btn-sm">{t("app.refresh", "Refresh")}</button>
      </div>

      {err && <div style={errBox}>{err}</div>}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(130px,1fr))", gap: 10, marginBottom: 16 }}>
        <div style={card}>
          <div style={kLbl}>{t("validation.score", "Validation score")}</div>
          <div style={{ ...kVal, color: scoreColor }}>{sc}%</div>
          <div style={meter}><i style={{ display: "block", height: "100%", width: `${sc}%`, background: scoreColor }} /></div>
        </div>
        <div style={card}><div style={kLbl}>{t("validation.critical", "Critical")}</div><div style={{ ...kVal, color: SEV.critical.c }}>{score?.critical ?? 0}</div></div>
        <div style={card}><div style={kLbl}>{t("validation.warnings", "Warnings")}</div><div style={{ ...kVal, color: SEV.warning.c }}>{score?.warning ?? 0}</div></div>
        <div style={card}><div style={kLbl}>{t("validation.info", "Info")}</div><div style={{ ...kVal, color: SEV.info.c }}>{score?.info ?? 0}</div></div>
        <div style={card}><div style={kLbl}>{t("validation.open", "Open findings")}</div><div style={kVal}>{score?.open_total ?? 0}</div></div>
      </div>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 10, alignItems: "center" }}>
        <select style={inp} value={fSev} onChange={(e) => setFSev(e.target.value)}>
          <option value="">{t("validation.allSeverities", "All severities")}</option>
          <option value="critical">Critical</option><option value="warning">Warning</option><option value="info">Info</option>
        </select>
        <select style={inp} value={fVal} onChange={(e) => setFVal(e.target.value)}>
          <option value="">{t("validation.allValidators", "All validators")}</option>
          {VALIDATORS.map((v) => <option key={v} value={v}>{v}</option>)}
        </select>
        <select style={inp} value={fStatus} onChange={(e) => setFStatus(e.target.value)}>
          <option value="open">Open</option><option value="acknowledged">Acknowledged</option>
          <option value="fixed">Fixed</option><option value="muted">Muted</option>
          <option value="resolved">Resolved</option><option value="">All</option>
        </select>
        <span style={{ fontSize: 12, color: "#64748b" }}>{findings.length} {t("validation.findings", "findings")}</span>
      </div>

      <div style={{ border: "1px solid #e2e8f0", borderRadius: 12, overflowX: "auto", background: "#fff" }}>
        <table style={{ width: "100%", minWidth: 760, borderCollapse: "collapse", fontSize: 13 }}>
          <thead><tr style={{ background: "#f1f5f9", color: "#334155", textAlign: "left" }}>
            <th style={th}>{t("validation.severity", "Severity")}</th>
            <th style={th}>{t("validation.validator", "Validator")}</th>
            <th style={th}>{t("validation.asset", "Asset")}</th>
            <th style={th}>{t("validation.description", "Description")}</th>
            <th style={th}>{t("validation.fix", "Suggested fix")}</th>
            <th style={{ ...th, textAlign: "right" }}></th>
          </tr></thead>
          <tbody>
            {findings.map((f) => {
              const sev = SEV[f.severity] || SEV.info;
              return (
                <tr key={f.id} style={{ borderTop: "1px solid #f1f5f9" }}>
                  <td style={td}><span style={{ ...chip, background: sev.bg, color: sev.c }}>{sev.label}</span></td>
                  <td style={{ ...td, fontFamily: "monospace", fontSize: 12, color: "#475569" }}>{f.validator}</td>
                  <td style={{ ...td, fontFamily: "monospace", fontWeight: 600, color: "#0f172a", whiteSpace: "nowrap" }}>
                    {f.asset_ref || "—"}
                    {f.asset_ref && onShowAsset && (
                      <button title={t("validation.showOnMap", "Show on map")} onClick={() => onShowAsset(f.asset_ref!)} style={linkBtn}>◎</button>
                    )}
                  </td>
                  <td style={{ ...td, color: "#334155", maxWidth: 340 }}>{f.description}</td>
                  <td style={{ ...td, color: "#64748b", fontSize: 12, maxWidth: 220 }}>{f.suggested_fix || "—"}</td>
                  <td style={{ ...td, whiteSpace: "nowrap", textAlign: "right" }}>
                    {f.status !== "acknowledged" && f.status !== "fixed" && <button onClick={() => triage(f, "acknowledged")} disabled={busy} className="btn btn-secondary btn-sm" style={aBtn}>{t("validation.ack", "Ack")}</button>}
                    {f.suggested_fix && f.status !== "fixed" && <button onClick={() => approveFix(f)} disabled={busy} className="btn btn-primary btn-sm" style={aBtn}>{t("validation.approve", "Approve fix")}</button>}
                    {f.status !== "resolved" && <button onClick={() => triage(f, "resolved")} disabled={busy} className="btn btn-secondary btn-sm" style={aBtn}>{t("validation.resolve", "Resolve")}</button>}
                    {f.status !== "muted" && <button onClick={() => triage(f, "muted")} disabled={busy} className="btn btn-cancel btn-sm" style={aBtn}>{t("validation.mute", "Mute")}</button>}
                  </td>
                </tr>
              );
            })}
            {findings.length === 0 && (
              <tr><td colSpan={6} style={{ padding: 24, textAlign: "center", color: "#64748b" }}>
                {t("validation.none", "No findings for this filter — run a validation to check the project.")}
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

const card: React.CSSProperties = { background: "#fff", border: "1px solid #e2e8f0", borderRadius: 10, padding: "13px 15px", boxShadow: "0 1px 2px rgba(15,23,42,.05)" };
const kLbl: React.CSSProperties = { fontSize: 11, textTransform: "uppercase", letterSpacing: 0.06, color: "#64748b", fontWeight: 600 };
const kVal: React.CSSProperties = { fontFamily: "monospace", fontSize: 26, fontWeight: 800, letterSpacing: -0.5, marginTop: 4, color: "#0f172a" };
const meter: React.CSSProperties = { height: 6, borderRadius: 99, background: "#f1f5f9", overflow: "hidden", marginTop: 8 };
const th: React.CSSProperties = { padding: "10px 12px", fontWeight: 700, fontSize: 12, textTransform: "uppercase", letterSpacing: 0.04 };
const td: React.CSSProperties = { padding: "9px 12px", verticalAlign: "middle" };
const chip: React.CSSProperties = { fontSize: 11.5, fontWeight: 700, padding: "2px 9px", borderRadius: 999, whiteSpace: "nowrap" };
const inp: React.CSSProperties = { padding: "6px 9px", border: "1px solid #cbd5e1", borderRadius: 7, fontSize: 13, background: "#fff", color: "#0f172a" };
const aBtn: React.CSSProperties = { fontSize: 11.5, marginLeft: 5, padding: "3px 9px" };
const linkBtn: React.CSSProperties = { marginLeft: 7, border: "1px solid #dbeafe", background: "#eff6ff", color: "#2563eb", borderRadius: 6, cursor: "pointer", fontSize: 12, padding: "0 6px", lineHeight: "18px" };
const errBox: React.CSSProperties = { background: "#fee2e2", color: "#b91c1c", border: "1px solid #fecaca", padding: "8px 12px", borderRadius: 8, fontSize: 13, marginBottom: 10 };
