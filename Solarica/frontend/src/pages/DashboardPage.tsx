import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { StatCard } from "../components/StatCard";
import { MeasurementTable } from "../components/MeasurementTable";
import {
  detectConnector,
  getDeviceStatus,
  getImportStatus,
  listConnectorMeasurements,
  type ConnectorDeviceStatus,
  type ConnectorHealth,
  type ConnectorImportStatus,
  type ConnectorMeasurement,
  getSavedConnectorUrl,
} from "../api/connectorClient";
import { useProject } from "../contexts/ProjectContext";

export function DashboardPage() {
  const { t } = useTranslation();
  const { selectedSite } = useProject();
  const [health, setHealth] = useState<ConnectorHealth | null>(null);
  const [device, setDevice] = useState<ConnectorDeviceStatus | null>(null);
  const [importStatus, setImportStatus] = useState<ConnectorImportStatus | null>(null);
  const [measurements, setMeasurements] = useState<ConnectorMeasurement[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const url = getSavedConnectorUrl();
    (async () => {
      setLoading(true);
      const h = await detectConnector(url);
      setHealth(h);
      if (h?.ok) {
        const [ds, is_, ms] = await Promise.all([
          getDeviceStatus(url),
          getImportStatus(url),
          listConnectorMeasurements(url),
        ]);
        setDevice(ds);
        setImportStatus(is_);
        setMeasurements(ms.items);
      }
      setLoading(false);
    })();
  }, []);

  const online = health?.ok === true;

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
        <h2 style={{ margin: 0, fontSize: "1.1rem", fontWeight: 700, color: "rgb(var(--theme-text-primary))" }}>
          {t("dashboard.title")}
        </h2>
        {selectedSite && (
          <span style={{ padding: "2px 10px", background: "rgb(var(--theme-highlight))", color: "rgb(var(--theme-action-accent))", borderRadius: 999, fontSize: "var(--theme-font-size-xs)", fontWeight: 600 }}>
            {selectedSite.site_name}
          </span>
        )}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: 12, marginBottom: 20 }}>
        <StatCard
          title={t("dashboard.connector")}
          value={loading ? "…" : online ? t("dashboard.online") : t("dashboard.offline")}
          hint={health?.version ? `v${health.version} · ${health.runtime}` : undefined}
          accent={online}
        />
        <StatCard
          title={t("dashboard.device")}
          value={loading ? "…" : device?.connected ? (device.deviceModel ?? t("device.connected")) : t("dashboard.notConnected")}
          hint={device?.port ?? undefined}
        />
        <StatCard title={t("dashboard.driverMode")} value={loading ? "…" : (device?.mode ?? "—")} />
        <StatCard
          title={t("dashboard.cached")}
          value={loading ? "…" : String(measurements.length)}
          hint={t("dashboard.measurements")}
        />
        <StatCard
          title={t("dashboard.unsynced")}
          value={loading ? "…" : String(importStatus?.unsyncedCount ?? 0)}
          accent={(importStatus?.unsyncedCount ?? 0) > 0}
        />
        <StatCard
          title={t("dashboard.importState")}
          value={loading ? "…" : (importStatus?.state ?? "idle")}
          hint={importStatus?.lastImportedCount != null ? `Last: ${importStatus.lastImportedCount}` : undefined}
        />
      </div>

      <div className="solarica-card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <span style={{ fontWeight: 600, fontSize: "var(--theme-font-size-sm)" }}>{t("dashboard.recentMeasurements")}</span>
          <Link to="/measurements" style={{ fontSize: "var(--theme-font-size-xs)", color: "rgb(var(--theme-action-accent))" }}>
            {t("dashboard.viewAll")}
          </Link>
        </div>
        <MeasurementTable items={measurements.slice(0, 10)} linkPrefix="/measurements" />
      </div>

      {!online && !loading && (
        <div style={{ marginTop: 16, padding: "12px 16px", background: "#fef3c7", border: "1px solid #fbbf24", borderRadius: 8, fontSize: "var(--theme-font-size-xs)", color: "#92400e" }}>
          {t("dashboard.connectorOffline")}{" "}
          <Link to="/device" style={{ color: "#b45309", fontWeight: 600 }}>{t("dashboard.configureDevice")}</Link>{" "}
          {t("dashboard.toConfigure")}
        </div>
      )}
    </div>
  );
}
