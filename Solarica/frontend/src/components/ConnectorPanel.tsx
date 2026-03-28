/**
 * ConnectorPanel
 *
 * Works with the Python connector OR the .NET connector without any code
 * changes — both expose the same REST API on localhost:8765.
 *
 * Replaces DeviceSyncPanel. The legacy DeviceSyncPanel is kept for reference.
 */

import { useEffect, useRef, useState } from "react";
import {
  type ConnectorDeviceStatus,
  type ConnectorHealth,
  type ConnectorImportStatus,
  type ConnectorMeasurement,
  type ConnectorPortInfo,
  type ConnectorSyncResult,
  connectPort,
  detectConnector,
  disconnectPort,
  getDeviceStatus,
  getExportCsvUrl,
  getExportJsonUrl,
  getImportStatus,
  getSavedConnectorUrl,
  listConnectorMeasurements,
  listPorts,
  saveConnectorUrl,
  startImport,
  syncUpload,
} from "../api/connectorClient";
import { api } from "../api/client";

interface ConnectorPanelProps {
  onImported?: () => void;
}

export function ConnectorPanel({ onImported }: ConnectorPanelProps) {
  const [connectorUrl, setConnectorUrl] = useState(getSavedConnectorUrl());
  const [draftUrl, setDraftUrl] = useState(getSavedConnectorUrl());
  const [health, setHealth] = useState<ConnectorHealth | null>(null);
  const [deviceStatus, setDeviceStatus] = useState<ConnectorDeviceStatus | null>(null);
  const [ports, setPorts] = useState<ConnectorPortInfo[]>([]);
  const [selectedPort, setSelectedPort] = useState("");
  const [importStatus, setImportStatus] = useState<ConnectorImportStatus | null>(null);
  const [cachedCount, setCachedCount] = useState<number>(0);
  const [syncResult, setSyncResult] = useState<ConnectorSyncResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const online = health?.ok === true;

  // ---------------------------------------------------------------------------
  // Initial detection + polling
  // ---------------------------------------------------------------------------

  const refresh = async (url?: string) => {
    const u = url ?? connectorUrl;
    const h = await detectConnector(u);
    setHealth(h);
    if (!h?.ok) {
      setDeviceStatus(null);
      setPorts([]);
      setImportStatus(null);
      return;
    }
    const [ds, ps, is_, ms] = await Promise.all([
      getDeviceStatus(u),
      listPorts(u),
      getImportStatus(u),
      listConnectorMeasurements(u),
    ]);
    setDeviceStatus(ds);
    setPorts(ps.items);
    setImportStatus(is_);
    setCachedCount(ms.items.length);
  };

  useEffect(() => {
    refresh();
    pollRef.current = setInterval(() => refresh(), 10_000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connectorUrl]);

  // ---------------------------------------------------------------------------
  // Actions
  // ---------------------------------------------------------------------------

  const applyUrl = () => {
    const u = draftUrl.trim();
    saveConnectorUrl(u);
    setConnectorUrl(u);
    setMessage("כתובת המחבר עודכנה.");
  };

  const handleConnect = async () => {
    if (!selectedPort) return;
    setBusy(true);
    setMessage("");
    try {
      const ds = await connectPort(selectedPort, connectorUrl);
      setDeviceStatus(ds);
      setMessage(`מחובר ל-${selectedPort}.`);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const handleDisconnect = async () => {
    setBusy(true);
    try {
      await disconnectPort(connectorUrl);
      await refresh();
      setMessage("נותק.");
    } catch (e) {
      setMessage(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const handleImport = async () => {
    setBusy(true);
    setMessage("");
    setSyncResult(null);
    try {
      const result = await startImport(connectorUrl);
      await refresh();
      setMessage(`ייבוא הושלם — ${result.imported} מדידות נשמרו מקומית.`);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const handleSync = async () => {
    setBusy(true);
    setMessage("");
    setSyncResult(null);
    try {
      const result = await syncUpload(connectorUrl);
      setSyncResult(result);
      if (result.uploaded > 0) onImported?.();
      await refresh();
      setMessage(
        result.error
          ? `סנכרון נכשל: ${result.error}`
          : `סונכרנו ${result.uploaded} מדידות לשרת.`,
      );
    } catch (e) {
      setMessage(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Also push cached measurements to the main backend (legacy path)
  // ---------------------------------------------------------------------------
  const handleSyncLegacy = async () => {
    setBusy(true);
    setMessage("");
    try {
      const { items } = await listConnectorMeasurements(connectorUrl);
      const unsynced = items.filter((m) => m.syncStatus !== "synced");
      if (unsynced.length === 0) {
        setMessage("אין מדידות שלא סונכרנו.");
        return;
      }
      const payloads = unsynced.map(toBackendPayload);
      const result = await api.uploadMeasurementBatch(payloads);
      if (result.imported > 0) onImported?.();
      setMessage(
        `${result.imported} יובאו, ${result.duplicates} כפולות, ${result.failed} נכשלו.`,
      );
      await refresh();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  const runtimeLabel =
    health?.runtime === "python"
      ? "Python"
      : health?.runtime === "dotnet"
        ? ".NET"
        : "Unknown";

  return (
    <section className="sync-panel">
      <div className="section-heading">
        <div>
          <h2>מחבר מקומי</h2>
          <p className="hint">
            משוך מדידות PVPM דרך המחבר המקומי, ולאחר מכן העלה אותן לשרת.
            עובד עם מחבר Python או .NET — אותו API, הבחירה שלך.
          </p>
        </div>
        <button type="button" onClick={() => refresh()} disabled={busy}>
          רענן
        </button>
      </div>

      {/* Status cards */}
      <div className="sync-status-grid">
        <div className="card sync-card">
          <span className="label">Connector</span>
          <strong className={online ? "status-text ok" : "status-text error"}>
            {online ? `מחובר (${runtimeLabel})` : "לא מחובר"}
          </strong>
          <span className="muted">
            {online ? `v${health.version}` : "הפעל את המחבר במחשב זה."}
          </span>
        </div>
        <div className="card sync-card">
          <span className="label">מכשיר</span>
          <strong>
            {deviceStatus?.connected ? `מחובר — ${deviceStatus.port}` : "לא מחובר"}
          </strong>
          <span className="muted">
            {deviceStatus?.lastError ?? deviceStatus?.mode ?? "אין דרייבר פעיל."}
          </span>
        </div>
        <div className="card sync-card">
          <span className="label">מטמון</span>
          <strong>{cachedCount} מדידות</strong>
          <span className="muted">
            {importStatus
              ? `${importStatus.unsyncedCount} לא סונכרנו · ייבוא אחרון: ${importStatus.lastImportedCount}`
              : "לא בוצע ייבוא עדיין."}
          </span>
        </div>
      </div>

      {/* Connector URL */}
      <div className="bridge-config">
        <label htmlFor="connector-url">כתובת מחבר</label>
        <div className="inline-form">
          <input
            id="connector-url"
            type="url"
            value={draftUrl}
            onChange={(e) => setDraftUrl(e.target.value)}
            placeholder="http://127.0.0.1:8765"
          />
          <button type="button" onClick={applyUrl} disabled={busy || !draftUrl.trim()}>
            שמור
          </button>
        </div>
        <p className="hint">
          השתמש בכתובת ה-IP של המחשב אם ניגשים ממכשיר אחר באותה רשת.
        </p>
      </div>

      {/* Port selection */}
      {online && ports.length > 0 && (
        <div className="bridge-config">
          <label htmlFor="port-select">פורט טורי / מכשיר</label>
          <div className="inline-form">
            <select
              id="port-select"
              value={selectedPort}
              onChange={(e) => setSelectedPort(e.target.value)}
            >
              <option value="">— בחר פורט —</option>
              {ports.map((p) => (
                <option key={p.name} value={p.name}>
                  {p.name} — {p.description}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={handleConnect}
              disabled={busy || !selectedPort || deviceStatus?.connected === true}
            >
              התחבר
            </button>
            <button
              type="button"
              onClick={handleDisconnect}
              disabled={busy || !deviceStatus?.connected}
            >
              נתק
            </button>
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="action-bar">
        <button
          type="button"
          className="primary"
          onClick={handleImport}
          disabled={busy || !online}
        >
          {busy ? "מעבד..." : "משוך מדידות ממכשיר"}
        </button>
        <button
          type="button"
          onClick={handleSync}
          disabled={busy || !online || (importStatus?.unsyncedCount ?? 0) === 0}
        >
          סנכרן לשרת ({importStatus?.unsyncedCount ?? 0})
        </button>
        <button
          type="button"
          onClick={handleSyncLegacy}
          disabled={busy || !online}
          title="העלה מדידות לא מסונכרנות דרך ה-API הראשי"
        >
          שלח לשרת (ישיר)
        </button>
      </div>

      {/* Export */}
      {online && (
        <div className="action-bar" style={{ marginTop: "0.5rem" }}>
          <a
            href={getExportCsvUrl(connectorUrl)}
            target="_blank"
            rel="noreferrer"
            className="button-link"
          >
            הורד CSV
          </a>
          <a
            href={getExportJsonUrl(connectorUrl)}
            target="_blank"
            rel="noreferrer"
            className="button-link"
          >
            הורד JSON
          </a>
        </div>
      )}

      {syncResult && (
        <div className="sync-result">
          <strong>תוצאת סנכרון</strong>
          <span className="muted">
            {syncResult.uploaded} הועלו
            {syncResult.error ? ` · שגיאה: ${syncResult.error}` : ""}
          </span>
        </div>
      )}

      {message && <p className="status-text">{message}</p>}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Map connector schema → backend import payload (used for direct push)
// ---------------------------------------------------------------------------

function toBackendPayload(m: ConnectorMeasurement) {
  return {
    measured_at: m.measuredAt,
    device_serial: m.externalMeasurementKey,
    sensor_serial: m.irradianceSensorSerial,
    irradiance_sensor_serial: m.irradianceSensorSerial,
    customer: m.customer,
    module_type: m.moduleType,
    remarks: m.notes,
    ppk: m.ppkWp,
    rs: m.rsOhm,
    rp: m.rpOhm,
    voc: m.vocV,
    isc: m.iscA,
    vpmax: m.vpmaxV,
    ipmax: m.ipmaxA,
    pmax: m.ppkWp,
    fill_factor: m.ffPercent,
    ff: m.ffPercent,
    eeff: m.irradianceWM2,
    tmod: m.moduleTempC,
    tcell: m.sensorTempC,
    source_file: m.importSource,
    device_record_id: m.id,
    sync_source: "solarica-connector",
    iv_curve: (m.curvePoints ?? []).map((p) => ({
      voltage: p.voltageV,
      current: p.currentA,
    })),
  };
}
