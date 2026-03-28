import { useState, useMemo, useRef } from "react";
import { useTranslation } from "react-i18next";
import { AgGridReact } from "ag-grid-react";
import type { ColDef } from "ag-grid-community";
import * as XLSX from "xlsx";
import {
  detectConnector,
  getSavedConnectorUrl,
  saveConnectorUrl,
  listConnectorMeasurements,
  startImport,
  syncUpload,
  getExportCsvUrl,
  getExportJsonUrl,
  type ConnectorMeasurement,
} from "../api/connectorClient";
import { api } from "../api/client";

export function IVCurvePage() {
  const { t } = useTranslation();

  const [connUrl, setConnUrl] = useState(getSavedConnectorUrl);
  const [connUrlDraft, setConnUrlDraft] = useState(connUrl);
  const [showUrlInput, setShowUrlInput] = useState(false);
  const xlsxImportRef = useRef<HTMLInputElement>(null);

  const [rows, setRows] = useState<ConnectorMeasurement[]>([]);
  const [online, setOnline] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ text: string; ok: boolean } | null>(null);

  // ── Column defs ────────────────────────────────────────────────────────────
  const colDefs = useMemo<ColDef<ConnectorMeasurement>[]>(
    () => [
      { field: "measuredAt",    headerName: t("ivcurve.colDate"),        minWidth: 160, flex: 1.5, filter: true },
      { field: "customer",      headerName: t("ivcurve.colCustomer"),    minWidth: 120, flex: 1,   filter: true },
      { field: "installation",  headerName: t("ivcurve.colInstallation"),minWidth: 120, flex: 1,   filter: true },
      { field: "stringNo",      headerName: t("ivcurve.colStringNo"),    width: 110,               filter: true },
      { field: "vocV",          headerName: "Voc (V)",   width: 100, filter: "agNumberColumnFilter" },
      { field: "iscA",          headerName: "Isc (A)",   width: 100, filter: "agNumberColumnFilter" },
      { field: "ppkWp",         headerName: "Ppk (Wp)", width: 110, filter: "agNumberColumnFilter" },
      { field: "ffPercent",     headerName: "FF (%)",   width: 90,  filter: "agNumberColumnFilter" },
      { field: "irradianceWM2", headerName: "Irr. (W/m²)", width: 110, filter: "agNumberColumnFilter" },
      {
        field: "syncStatus",
        headerName: t("ivcurve.colStatus"),
        width: 110,
        filter: true,
        cellClass: (p) =>
          p.value === "synced" ? "status-synced" : p.value === "error" ? "status-error-cell" : "",
      },
    ],
    [t],
  );

  const defaultColDef = useMemo<ColDef>(
    () => ({ sortable: true, resizable: true, floatingFilter: true }),
    [],
  );

  // ── Helpers ────────────────────────────────────────────────────────────────
  const withBusy = async (fn: () => Promise<void>) => {
    setBusy(true);
    setMessage(null);
    try {
      await fn();
    } catch (e) {
      setMessage({ text: e instanceof Error ? e.message : String(e), ok: false });
    } finally {
      setBusy(false);
    }
  };

  const checkAndLoad = async (): Promise<ConnectorMeasurement[]> => {
    const health = await detectConnector(connUrl);
    const isOnline = health?.ok ?? false;
    setOnline(isOnline);
    if (!isOnline) throw new Error(t("ivcurve.connectorOffline"));
    const { items } = await listConnectorMeasurements(connUrl);
    setRows(items);
    return items;
  };

  // ── Actions ────────────────────────────────────────────────────────────────
  const handleRead = () => withBusy(async () => {
    const items = await checkAndLoad();
    setMessage({ text: t("ivcurve.readOk", { count: items.length }), ok: true });
  });

  const handleImport = () => withBusy(async () => {
    const result = await startImport(connUrl);
    const items = await checkAndLoad();
    setMessage({ text: t("ivcurve.importOk", { count: result.imported, total: items.length }), ok: true });
  });

  const handleSync = () => withBusy(async () => {
    const result = await syncUpload(connUrl);
    await checkAndLoad();
    setMessage({ text: t("ivcurve.syncOk", { count: result.uploaded }), ok: !result.error });
  });

  const handleExport = (format: "csv" | "json") => {
    const url = format === "csv" ? getExportCsvUrl(connUrl) : getExportJsonUrl(connUrl);
    const a = document.createElement("a");
    a.href = url;
    a.download = format === "csv" ? "measurements.csv" : "measurements.json";
    a.click();
  };

  const handleExportExcel = () => {
    const exportRows = rows.map((r) => ({
      Date: r.measuredAt,
      Customer: r.customer ?? "",
      Installation: r.installation ?? "",
      String: r.stringNo ?? "",
      "Module type": r.moduleType ?? "",
      "Modules series": r.modulesSeries ?? "",
      "Modules parallel": r.modulesParallel ?? "",
      "Nominal power (W)": r.nominalPowerW ?? "",
      "Ppk (Wp)": r.ppkWp ?? "",
      "Voc (V)": r.vocV ?? "",
      "Isc (A)": r.iscA ?? "",
      "Vpmax (V)": r.vpmaxV ?? "",
      "Ipmax (A)": r.ipmaxA ?? "",
      "FF (%)": r.ffPercent ?? "",
      "Rs (Ω)": r.rsOhm ?? "",
      "Rp (Ω)": r.rpOhm ?? "",
      "Irradiance (W/m²)": r.irradianceWM2 ?? "",
      "Sensor temp (°C)": r.sensorTempC ?? "",
      "Module temp (°C)": r.moduleTempC ?? "",
      Status: r.syncStatus,
    }));
    const ws = XLSX.utils.json_to_sheet(exportRows);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, "Measurements");
    XLSX.writeFile(wb, "measurements.xlsx");
  };

  const handleImportExcel = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    await withBusy(async () => {
      const result = await api.uploadFile(file);
      await checkAndLoad();
      setMessage({ text: result.message || t("ivcurve.importXlsxOk"), ok: result.success });
    });
  };

  const applyUrl = () => {
    const trimmed = connUrlDraft.trim();
    saveConnectorUrl(trimmed);
    setConnUrl(trimmed);
    setShowUrlInput(false);
    setOnline(null);
    setRows([]);
    setMessage(null);
  };

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <section className="site-panel">
      {/* Header */}
      <div className="site-panel-header">
        <div className="site-panel-title">
          <h2>{t("ivcurve.title")}</h2>
          <p className="hint">{t("ivcurve.hint")}</p>
        </div>

        <div className="site-import-actions">
          <div className="site-import-btns">
            <button type="button" onClick={handleRead} disabled={busy}>
              {busy ? t("ivcurve.reading") : t("ivcurve.readFromConnector")}
            </button>
            <button
              type="button"
              className="primary"
              onClick={handleImport}
              disabled={busy || online === false}
            >
              {t("ivcurve.importData")}
            </button>
            <button
              type="button"
              onClick={handleSync}
              disabled={busy || rows.length === 0}
              title={t("ivcurve.syncTitle")}
            >
              {t("ivcurve.sync")}
            </button>
            <button
              type="button"
              onClick={() => handleExport("csv")}
              disabled={rows.length === 0}
            >
              {t("ivcurve.exportCsv")}
            </button>
            <button
              type="button"
              onClick={() => handleExport("json")}
              disabled={rows.length === 0}
            >
              {t("ivcurve.exportJson")}
            </button>
            <button
              type="button"
              onClick={handleExportExcel}
              disabled={rows.length === 0}
            >
              {t("ivcurve.exportExcel")}
            </button>
            <button
              type="button"
              onClick={() => xlsxImportRef.current?.click()}
              disabled={busy}
            >
              {t("ivcurve.importExcel")}
            </button>
            <input
              ref={xlsxImportRef}
              type="file"
              accept=".xls,.xlsx"
              style={{ display: "none" }}
              onChange={handleImportExcel}
            />
            <button
              type="button"
              onClick={() => { setShowUrlInput((v) => !v); setConnUrlDraft(connUrl); }}
              title={t("ivcurve.connectorUrlTitle")}
            >
              {t("ivcurve.settings")}
            </button>
          </div>
        </div>
      </div>

      {/* Connector URL editor */}
      {showUrlInput && (
        <div className="ivcurve-url-row">
          <label className="ivcurve-url-label">{t("ivcurve.connectorUrl")}</label>
          <input
            className="ivcurve-url-input"
            type="url"
            value={connUrlDraft}
            onChange={(e) => setConnUrlDraft(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && applyUrl()}
            placeholder="http://127.0.0.1:8765"
          />
          <button type="button" className="primary" onClick={applyUrl}>
            {t("common.save")}
          </button>
          <button type="button" onClick={() => setShowUrlInput(false)}>
            {t("common.cancel")}
          </button>
        </div>
      )}

      {/* Connector status badge */}
      {online !== null && (
        <p className={online ? "hint status-ok" : "hint status-offline"}>
          {online ? t("ivcurve.connectorOnline") : t("ivcurve.connectorOffline")}
          {!online && (
            <span className="ivcurve-url-hint"> — {connUrl}</span>
          )}
        </p>
      )}

      {/* Feedback message */}
      {message && (
        <p className="status-text" style={{ color: message.ok ? "#4ade80" : "#dc2626" }}>
          {message.text}
        </p>
      )}

      {/* Measurements grid */}
      {rows.length > 0 ? (
        <div className="ag-theme-quartz-dark string-grid-container">
          <AgGridReact<ConnectorMeasurement>
            rowData={rows}
            columnDefs={colDefs}
            defaultColDef={defaultColDef}
            pagination
            paginationPageSize={50}
            paginationPageSizeSelector={[25, 50, 100]}
            animateRows
          />
        </div>
      ) : (
        <p className="hint" style={{ marginTop: 24, textAlign: "center" }}>
          {t("ivcurve.noReadings")}
        </p>
      )}
    </section>
  );
}
