import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { StatCard } from "../components/StatCard";
import { api } from "../api/client";
import { useProject } from "../contexts/ProjectContext";

interface AnalysisSummary {
  total_measurements: number;
  avg_peak_power_w?: number | null;
  avg_series_resistance_ohm?: number | null;
  avg_parallel_resistance_ohm?: number | null;
  avg_irradiance_wm2?: number | null;
  first_measurement?: string | null;
  last_measurement?: string | null;
}

export function ValidationRulesPage() {
  const { t } = useTranslation();
  const { selectedSite } = useProject();
  const [summary, setSummary] = useState<AnalysisSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const sp = selectedSite ? `?site_id=${selectedSite.id}` : "";
    fetch(`/api/analysis/summary${sp}`)
      .then((r) => r.json())
      .then((d) => { setSummary(d); setLoading(false); })
      .catch((e) => { setError(String(e)); setLoading(false); });
  }, [selectedSite?.id]);

  const fmt = (v: number | null | undefined, digits = 2) =>
    v == null ? "—" : Number(v).toFixed(digits);

  const rules = [
    { label: t("validation.rules.vocLabel"), description: t("validation.rules.vocDesc") },
    { label: t("validation.rules.iscLabel"), description: t("validation.rules.iscDesc") },
    { label: t("validation.rules.ffLabel"),  description: t("validation.rules.ffDesc") },
    { label: t("validation.rules.rsLabel"),  description: t("validation.rules.rsDesc") },
    { label: t("validation.rules.rpLabel"),  description: t("validation.rules.rpDesc") },
    { label: t("validation.rules.irrLabel"), description: t("validation.rules.irrDesc") },
  ];

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
        <h2 style={{ margin: 0, fontSize: "1.1rem", fontWeight: 700, color: "rgb(var(--theme-text-primary))" }}>{t("validation.title")}</h2>
        {selectedSite && (
          <span style={{ padding: "2px 10px", background: "rgb(var(--theme-highlight))", color: "rgb(var(--theme-action-accent))", borderRadius: 999, fontSize: "var(--theme-font-size-xs)", fontWeight: 600 }}>
            {selectedSite.site_name}
          </span>
        )}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))", gap: 12, marginBottom: 20 }}>
        <StatCard title={t("validation.totalAnalysed")} value={loading ? "…" : (summary?.total_measurements ?? 0)} />
        <StatCard title={t("validation.avgPeakPower")} value={loading ? "…" : fmt(summary?.avg_peak_power_w) + " W"} />
        <StatCard title={t("validation.avgIrradiance")} value={loading ? "…" : fmt(summary?.avg_irradiance_wm2, 1) + " W/m²"} />
        <StatCard title={t("validation.avgRs")} value={loading ? "…" : fmt(summary?.avg_series_resistance_ohm, 4) + " Ω"} />
        <StatCard title={t("validation.avgRp")} value={loading ? "…" : fmt(summary?.avg_parallel_resistance_ohm) + " Ω"} />
      </div>

      {error && <div style={{ color: "#ef4444", marginBottom: 12 }}>{error}</div>}

      <div className="solarica-card">
        <div style={{ fontWeight: 600, fontSize: "var(--theme-font-size-sm)", marginBottom: 12 }}>
          {t("validation.activeRules")}
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {rules.map((rule) => (
            <div key={rule.label} style={{ display: "flex", alignItems: "flex-start", gap: 10, padding: "10px 12px", background: "rgb(var(--theme-nav-bg))", borderRadius: 8 }}>
              <span style={{ width: 18, height: 18, borderRadius: "50%", background: "#dcfce7", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 10, color: "#166534", fontWeight: 700, flexShrink: 0, marginTop: 1 }}>✓</span>
              <div>
                <div style={{ fontWeight: 600, fontSize: "var(--theme-font-size-sm)" }}>{rule.label}</div>
                <div style={{ fontSize: "var(--theme-font-size-xs)", color: "rgb(var(--theme-text-muted))", marginTop: 2 }}>{rule.description}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
