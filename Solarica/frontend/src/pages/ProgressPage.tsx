import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { MeasurementList } from "../components/MeasurementList";
import { UploadForm } from "../components/UploadForm";
import { StatCard } from "../components/StatCard";
import { api } from "../api/client";
import type { SummaryStats } from "../api/client";
import { useProject } from "../contexts/ProjectContext";

export function ProgressPage() {
  const { t } = useTranslation();
  const { pathname } = useLocation();
  const { selectedSite } = useProject();
  const [stats, setStats] = useState<SummaryStats | null>(null);
  const [refreshToken, setRefreshToken] = useState(0);

  useEffect(() => {
    api.getSummary(selectedSite?.id).then(setStats).catch(() => {});
  }, [refreshToken, selectedSite?.id]);

  const fmt = (v: number | null | undefined, digits = 1) =>
    v == null ? "—" : v.toFixed(digits);

  return (
    <div>
      <nav className="page-tab-bar">
        <Link to="/projects">
          <button type="button" className={`page-tab-btn${pathname === "/projects" ? " active" : ""}`}>
            {t("nav.sitesDesign")}
          </button>
        </Link>
        <Link to="/progress">
          <button type="button" className={`page-tab-btn${pathname === "/progress" ? " active" : ""}`}>
            {t("nav.progress")}
          </button>
        </Link>
      </nav>
      {selectedSite && (
        <div style={{ marginBottom: 16 }}>
          <span style={{ padding: "2px 10px", background: "rgb(var(--theme-highlight))", color: "rgb(var(--theme-action-accent))", borderRadius: 999, fontSize: "var(--theme-font-size-xs)", fontWeight: 600 }}>
            {selectedSite.site_name}
          </span>
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: 12, marginBottom: 20 }}>
        <StatCard title={t("progress.totalMeasurements")} value={stats?.total_measurements ?? "…"} />
        <StatCard title={t("progress.uniqueCustomers")} value={stats?.unique_customers ?? "…"} />
        <StatCard title={t("progress.avgPeakPower")} value={stats ? fmt(stats.avg_peak_power_kw) + " kW" : "…"} />
        <StatCard title={t("progress.avgIrradiance")} value={stats ? fmt(stats.avg_irradiance_wm2) + " W/m²" : "…"} />
        <StatCard
          title={t("progress.firstMeasurement")}
          value={stats?.first_measurement ? new Date(stats.first_measurement).toLocaleDateString() : "—"}
        />
        <StatCard
          title={t("progress.lastMeasurement")}
          value={stats?.last_measurement ? new Date(stats.last_measurement).toLocaleDateString() : "—"}
        />
      </div>

      <div className="solarica-card" style={{ marginBottom: 16 }}>
        <div style={{ fontWeight: 600, fontSize: "var(--theme-font-size-sm)", marginBottom: 10 }}>{t("progress.uploadFile")}</div>
        <UploadForm onImported={() => setRefreshToken((t) => t + 1)} siteId={selectedSite?.id} />
      </div>

      <div className="solarica-card">
        <div style={{ fontWeight: 600, fontSize: "var(--theme-font-size-sm)", marginBottom: 10 }}>
          {t("progress.measurementsBackend")}
        </div>
        <MeasurementList refreshToken={refreshToken} siteId={selectedSite?.id} />
      </div>
    </div>
  );
}
