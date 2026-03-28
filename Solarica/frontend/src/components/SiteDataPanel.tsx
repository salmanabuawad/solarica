import { useEffect, useMemo, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { AgGridReact } from "ag-grid-react";
import { ProgressModal } from "./ProgressModal";
import { PdfRegionPicker } from "./PdfRegionPicker";
import type { PdfRegion } from "./PdfRegionPicker";
import type { ColDef } from "ag-grid-community";
import type {
  SiteDesignPreviewResult,
  SiteDesignPreviewRow,
  SiteDetail,
  SiteString,
  SiteSummary,
  ScanResult,
  StringPattern,
} from "../api/client";
import { api } from "../api/client";

export function SiteDataPanel() {
  const { t } = useTranslation();
  const location = useLocation();
  const [sites, setSites] = useState<SiteSummary[]>([]);
  const [selectedSiteId, setSelectedSiteId] = useState<number | null>(null);
  const [site, setSite] = useState<SiteDetail | null>(null);
  const [strings, setStrings] = useState<SiteString[]>([]);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState(() => t("sitePanel.loadingSite"));
  const [designFiles, setDesignFiles] = useState<File[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [preview, setPreview] = useState<SiteDesignPreviewResult | null>(null);
  const [importMessage, setImportMessage] = useState("");
  const [importBusy, setImportBusy] = useState(false);
  const [previewBusy, setPreviewBusy] = useState(false);
  const [reloadNonce, setReloadNonce] = useState(0);
  const [regions, setRegions] = useState<PdfRegion[]>([]);
  const [showRegionPicker, setShowRegionPicker] = useState(false);

  // When arriving via "New Project", clear everything
  useEffect(() => {
    if ((location.state as { newProject?: boolean } | null)?.newProject) {
      setDesignFiles([]);
      setPreview(null);
      setImportMessage("");
      setRegions([]);
      setShowRegionPicker(false);
      setSite(null);
      setStrings([]);
      setScanResult(null);
      setSearch("");
      setStatus("");
      setSelectedSiteId(null);
      window.history.replaceState({}, "");
    }
  }, [location.state]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    let ignore = false;
    api
      .listSites()
      .then((items) => {
        if (ignore) return;
        setSites(items);
        if (items.length > 0) {
          setSelectedSiteId(items[0].id);
        } else {
          setStatus(t("sitePanel.noSites"));
        }
      })
      .catch((error) => {
        if (!ignore) {
          setStatus(error instanceof Error ? error.message : t("sitePanel.errorLoadingSites"));
        }
      });
    return () => { ignore = true; };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (selectedSiteId == null) return;
    let ignore = false;
    Promise.all([
      api.getSite(selectedSiteId),
      api.listSiteStrings(selectedSiteId, { search, limit: 1000 }),
    ])
      .then(([siteDetail, siteStrings]) => {
        if (ignore) return;
        setSite(siteDetail);
        setStrings(siteStrings);
        setStatus("");
      })
      .catch((error) => {
        if (!ignore) {
          setStatus(error instanceof Error ? error.message : t("sitePanel.errorLoadingSiteData"));
        }
      });
    return () => { ignore = true; };
  }, [selectedSiteId, search, reloadNonce]); // eslint-disable-line react-hooks/exhaustive-deps

  const previewDesignPdf = async () => {
    if (!designFiles.length) { setImportMessage(t("sitePanel.selectPdfFirst")); return; }
    setPreviewBusy(true);
    setImportMessage("");
    try {
      const result = await api.previewSiteDesignPdf(designFiles, regions.length ? regions : undefined);
      setPreview(result);
      setImportMessage(
        result.has_errors
          ? t("sitePanel.invalidRowsFound", { count: result.invalid_count })
          : t("sitePanel.previewReady", { count: result.valid_count }),
      );
      setStatus("");
    } catch (error) {
      setPreview(null);
      setImportMessage(error instanceof Error ? error.message : t("sitePanel.errorImportingPdf"));
    } finally {
      setPreviewBusy(false);
    }
  };

  const importDesignPdf = async () => {
    if (!designFiles.length) { setImportMessage(t("sitePanel.selectPdfFirst")); return; }
    setImportBusy(true);
    setImportMessage("");
    try {
      const result = await api.importSiteDesignPdf(designFiles, regions.length ? regions : undefined);
      const nextSites = await api.listSites();
      setSites(nextSites);
      setSearch("");
      setPreview(null);
      setSelectedSiteId(result.site_id);
      setReloadNonce((v) => v + 1);
      setImportMessage(result.message);
      setDesignFiles([]);
      setStatus("");
    } catch (error) {
      setImportMessage(error instanceof Error ? error.message : t("sitePanel.errorImportingPdf"));
    } finally {
      setImportBusy(false);
    }
  };

  const [scanResult, setScanResult] = useState<ScanResult | null>(null);
  const [scanBusy, setScanBusy] = useState(false);
  const [patterns, setPatterns] = useState<StringPattern[]>([]);
  const [activePattern, setActivePattern] = useState<StringPattern | null>(null);

  useEffect(() => {
    api.listStringPatterns().then(setPatterns).catch(() => {});
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (selectedSiteId == null) return;
    api.getSitePattern(selectedSiteId)
      .then((r) => setActivePattern(r?.pattern ?? null))
      .catch(() => setActivePattern(null));
  }, [selectedSiteId]); // eslint-disable-line react-hooks/exhaustive-deps

  const runScan = async () => {
    if (!designFiles.length || selectedSiteId == null) return;
    setScanBusy(true);
    setScanResult(null);
    setImportMessage("");
    try {
      const result = await api.scanStrings(selectedSiteId, designFiles, regions.length ? regions : undefined);
      setScanResult(result);
    } catch (e) {
      setImportMessage(e instanceof Error ? e.message : "Scan failed");
    } finally {
      setScanBusy(false);
    }
  };

  const changePattern = async (patternId: number) => {
    if (selectedSiteId == null) return;
    const r = await api.setSitePattern(selectedSiteId, patternId);
    setActivePattern(r.pattern);
  };

  // ── Column defs for duplicates / gaps / anomalies grids ──────────────────
  const dupColDefs = useMemo<ColDef<{ code: string }>[]>(
    () => [{ field: "code", headerName: t("sitePanel.gridDupStringCode"), flex: 1, filter: true }],
    [t],
  );

  const gapColDefs = useMemo<ColDef<{ group: string; missing: string }>[]>(
    () => [
      { field: "group",   headerName: t("sitePanel.gridGapGroup"),   width: 160, filter: true },
      { field: "missing", headerName: t("sitePanel.gridGapMissing"), flex: 1,    filter: true },
    ],
    [t],
  );

  const anomalyColDefs = useMemo<ColDef<{ group: string; values: string }>[]>(
    () => [
      { field: "group",  headerName: t("sitePanel.gridAnomalyGroup"),  width: 160, filter: true },
      { field: "values", headerName: t("sitePanel.gridAnomalyValues"), flex: 1,    filter: true },
    ],
    [t],
  );

  // t is in deps so headers re-render when language changes
  const columnDefs = useMemo<ColDef<SiteString>[]>(
    () => [
      { field: "string_code", headerName: t("sitePanel.gridStringCode"), flex: 1.5, minWidth: 170, filter: true },
      { field: "section_no",  headerName: t("sitePanel.gridSection"),    width: 110, filter: "agNumberColumnFilter" },
      { field: "block_no",    headerName: t("sitePanel.gridBlock"),       width: 110, filter: "agNumberColumnFilter" },
      { field: "string_no",   headerName: t("sitePanel.gridStringNo"),    width: 130, filter: "agNumberColumnFilter" },
    ],
    [t],
  );

  const previewColumnDefs = useMemo<ColDef<SiteDesignPreviewRow>[]>(
    () => [
      {
        field: "is_valid",
        headerName: "",
        width: 70,
        sortable: false,
        filter: false,
        floatingFilter: false,
        resizable: false,
        tooltipValueGetter: (params: { data?: SiteDesignPreviewRow }) => params.data?.invalid_reason || "",
        valueGetter: (params) => (params.data?.is_valid ? "" : "!"),
        cellClass: "preview-status-cell",
        cellRenderer: (params: { data?: SiteDesignPreviewRow; value?: string }) => {
          const row = params.data;
          if (!row || row.is_valid) return "";
          return params.value || "!";
        },
      },
      { field: "raw_value",      headerName: t("sitePanel.gridParsedValue"), minWidth: 160, flex: 1.2, filter: true, tooltipField: "invalid_reason" },
      { field: "string_code",    headerName: t("sitePanel.gridNormalized"),  minWidth: 160, flex: 1.2, filter: true },
      { field: "section_no",     headerName: t("sitePanel.gridSection"),     width: 110, filter: "agNumberColumnFilter" },
      { field: "block_no",       headerName: t("sitePanel.gridBlock"),       width: 110, filter: "agNumberColumnFilter" },
      { field: "string_no",      headerName: t("sitePanel.gridStringNo"),    width: 130, filter: "agNumberColumnFilter" },
      { field: "invalid_reason", headerName: t("sitePanel.gridReason"),      minWidth: 260, flex: 1.5, filter: true },
    ],
    [t],
  );

  const defaultColDef = useMemo<ColDef>(
    () => ({ sortable: true, resizable: true, floatingFilter: true }),
    [],
  );

  // Small summary grids don't need floating-filter rows – keeps them compact
  const summaryColDef = useMemo<ColDef>(
    () => ({ sortable: true, resizable: true }),
    [],
  );

  const issueColDefs = useMemo<ColDef[]>(
    () => [
      { field: "severity", headerName: t("sitePanel.issueSeverity"), width: 100, filter: true,
        cellStyle: (p: { value?: string }) => ({ color: p.value === "error" || p.value === "blocker" ? "#ef4444" : p.value === "warning" ? "#f59e0b" : "" }) },
      { field: "issue_type", headerName: t("sitePanel.issueType"), width: 240, filter: true },
      { field: "entity_key", headerName: t("sitePanel.issueEntity"), width: 140, filter: true },
      { field: "message", headerName: t("sitePanel.issueMessage"), flex: 1, filter: true },
    ],
    [t],
  );

  return (
    <section className="site-panel">
      <div className="site-panel-header">
        <div className="site-panel-title">
          <h2>{t("sitePanel.title")}</h2>
          <p className="hint">{t("sitePanel.hint")}</p>
        </div>
        <div className="site-import-actions">
          {/* Hidden native input — multiple PDF selection */}
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,application/pdf"
            multiple
            style={{ display: "none" }}
            onChange={(e) => {
              const added = Array.from(e.target.files ?? []);
              if (added.length === 0) return;
              setDesignFiles((prev) => [...prev, ...added]);
              setPreview(null);
              setImportMessage("");
              e.target.value = "";
            }}
          />
          <div className="pdf-file-actions">
            <button type="button" className="file-choose-btn" onClick={() => fileInputRef.current?.click()}>
              {t("sitePanel.addPdf")}
            </button>
            <button
              type="button"
              className="file-clear-btn"
              disabled={designFiles.length === 0}
              onClick={() => {
                setDesignFiles([]);
                setPreview(null);
                setImportMessage("");
                setRegions([]);
                setShowRegionPicker(false);
                setSite(null);
                setStrings([]);
                setScanResult(null);
                setSearch("");
                setStatus("");
              }}
            >
              {t("sitePanel.clearPdfs")}
            </button>
          </div>
          {designFiles.length > 0 && (
            <ul className="pdf-file-list">
              {designFiles.map((f, i) => (
                <li key={i} className="pdf-file-item">
                  <span>{f.name}</span>
                  <button
                    type="button"
                    className="pdf-remove-btn"
                    onClick={() => setDesignFiles((prev) => prev.filter((_, idx) => idx !== i))}
                  >×</button>
                </li>
              ))}
            </ul>
          )}
          <div className="site-import-btns">
            <button
              type="button"
              className={showRegionPicker ? "active" : ""}
              onClick={() => setShowRegionPicker((v) => !v)}
              disabled={!designFiles.length}
              title={t("sitePanel.selectRegions")}
            >
              {t("sitePanel.selectRegions")}
              {regions.length > 0 && (
                <span className="region-badge">{regions.length}</span>
              )}
            </button>
            <button type="button" onClick={previewDesignPdf} disabled={previewBusy || importBusy || !designFiles.length}>
              {previewBusy ? t("sitePanel.previewing") : t("sitePanel.preview")}
            </button>
            <button
              type="button"
              className="primary"
              onClick={importDesignPdf}
              disabled={importBusy || !designFiles.length || !preview || preview.has_errors}
              title={preview?.has_errors ? t("sitePanel.fixBeforeImport") : ""}
            >
              {importBusy ? t("sitePanel.importing") : t("sitePanel.importStrings")}
            </button>
            <button type="button" onClick={runScan} disabled={scanBusy || !designFiles.length || selectedSiteId == null}>
              {scanBusy ? t("sitePanel.scanning") : t("sitePanel.scan")}
            </button>
          </div>
        </div>

        {showRegionPicker && designFiles.length > 0 && (
          <PdfRegionPicker
            file={designFiles[0]}
            regions={regions}
            onChange={setRegions}
          />
        )}

        {patterns.length > 0 && selectedSiteId != null && (
          <div className="scan-pattern-row">
            <label className="scan-pattern-label">{t("sitePanel.pattern")}</label>
            <select
              value={activePattern?.id ?? ""}
              onChange={(e) => changePattern(Number(e.target.value))}
            >
              <option value="" disabled>{t("sitePanel.noPattern")}</option>
              {patterns.map((p) => (
                <option key={p.id} value={p.id}>{p.pattern_name} ({p.example_value})</option>
              ))}
            </select>
            {activePattern && (
              <span className="scan-pattern-badge">{activePattern.pattern_code}</span>
            )}
          </div>
        )}
      </div>

      {preview && (
        <div className="string-list-panel">
          <h3>{t("sitePanel.pdfPreview")}</h3>
          <p className="hint">
            {t("sitePanel.previewHint", {
              project: preview.metadata.project,
              code: preview.site_code,
              valid: preview.valid_count,
              invalid: preview.invalid_count,
            })}
          </p>
          <div className="site-grid">
            <div className="card site-card">
              <span className="label">{t("sitePanel.location")}</span>
              <strong>{preview.metadata.location || t("sitePanel.unknown")}</strong>
              <span className="muted">{preview.region || t("sitePanel.unknownRegion")}</span>
            </div>
            <div className="card site-card">
              <span className="label">{t("sitePanel.modules")}</span>
              <strong>{preview.metadata.total_modules ?? 0}</strong>
              <span className="muted">{preview.module_type || t("sitePanel.unknownModuleType")}</span>
            </div>
            <div className="card site-card">
              <span className="label">{t("sitePanel.validStrings")}</span>
              <strong>{Object.values(preview.strings).flat().length}</strong>
              <span className="muted">{t("sitePanel.strings_count", { count: Object.values(preview.strings).flat().length })}</span>
            </div>
            <div className="card site-card">
              <span className="label">{t("sitePanel.anomalies")}</span>
              <strong>{preview.duplicates.length + Object.keys(preview.anomalies).length}</strong>
              <span className="muted">
                {t("sitePanel.duplicates_count", { dup: preview.duplicates.length, anom: Object.keys(preview.anomalies).length })}
              </span>
            </div>
          </div>
          {preview.duplicates.length > 0 && (
            <div style={{ marginTop: 12 }}>
              <div style={{ fontWeight: 600, fontSize: "var(--theme-font-size-sm)", marginBottom: 4 }}>{t("sitePanel.duplicates")}</div>
              <div className="ag-theme-quartz-dark" style={{ height: preview.duplicates.length * 42 + 52 }}>
                <AgGridReact
                  rowData={preview.duplicates.map((code) => ({ code }))}
                  columnDefs={dupColDefs}
                  defaultColDef={summaryColDef}
                />
              </div>
            </div>
          )}
          {Object.keys(preview.gaps).length > 0 && (
            <div style={{ marginTop: 12 }}>
              <div style={{ fontWeight: 600, fontSize: "var(--theme-font-size-sm)", marginBottom: 4 }}>{t("sitePanel.gaps")}</div>
              <div className="ag-theme-quartz-dark" style={{ height: Math.min(Object.keys(preview.gaps).length * 42 + 52, 320) }}>
                <AgGridReact
                  rowData={Object.entries(preview.gaps).map(([group, missing]) => ({ group, missing: (missing as string[]).join(", ") }))}
                  columnDefs={gapColDefs}
                  defaultColDef={summaryColDef}
                />
              </div>
            </div>
          )}
          {Object.keys(preview.anomalies).length > 0 && (
            <div style={{ marginTop: 12 }}>
              <div style={{ fontWeight: 600, fontSize: "var(--theme-font-size-sm)", marginBottom: 4 }}>{t("sitePanel.anomalies")}</div>
              <div className="ag-theme-quartz-dark" style={{ height: Math.min(Object.keys(preview.anomalies).length * 42 + 52, 320) }}>
                <AgGridReact
                  rowData={Object.entries(preview.anomalies).map(([group, values]) => ({ group, values: (values as string[]).join(", ") }))}
                  columnDefs={anomalyColDefs}
                  defaultColDef={summaryColDef}
                />
              </div>
            </div>
          )}
          <div className="ag-theme-quartz-dark preview-grid-container">
            <AgGridReact<SiteDesignPreviewRow>
              rowData={preview.string_rows}
              columnDefs={previewColumnDefs}
              defaultColDef={defaultColDef}
              pagination
              paginationPageSize={50}
              paginationPageSizeSelector={[25, 50, 100, 250]}
              animateRows
              rowClassRules={{ "invalid-row": (params: { data?: SiteDesignPreviewRow }) => !params.data?.is_valid }}
              tooltipShowDelay={0}
            />
          </div>
        </div>
      )}

      {scanResult && (
        <div className="string-list-panel scan-results">
          <h3>{t("sitePanel.scanResults")}</h3>
          {/* Summary cards */}
          <div className="site-grid">
            <div className="card site-card">
              <span className="label">{t("sitePanel.validStrings")}</span>
              <strong className={scanResult.design_comparison.matches_design ? "text-green" : ""}>
                {scanResult.summary.total_valid_strings}
              </strong>
              <span className="muted">{t("sitePanel.expectedCount", { n: scanResult.design_comparison.expected_total_strings })}</span>
            </div>
            <div className="card site-card">
              <span className="label">{t("sitePanel.patternUsed")}</span>
              <strong>{scanResult.pattern_code_used}</strong>
              <span className="muted">{t("sitePanel.confidence", { pct: Math.round(scanResult.fast_detect.confidence * 100) })}</span>
            </div>
            <div className="card site-card">
              <span className="label">{t("sitePanel.duplicates")}</span>
              <strong style={{ color: scanResult.summary.total_duplicates > 0 ? "#ef4444" : undefined }}>
                {scanResult.summary.total_duplicates}
              </strong>
              <span className="muted">{t("sitePanel.invalidNames", { n: scanResult.summary.total_invalid_string_names })}</span>
            </div>
            <div className="card site-card">
              <span className="label">{t("sitePanel.designMatch")}</span>
              <strong style={{ color: scanResult.design_comparison.matches_design ? "#4ade80" : "#ef4444" }}>
                {scanResult.design_comparison.matches_design ? t("sitePanel.matchOk") : t("sitePanel.matchFail")}
              </strong>
              <span className="muted">{t("sitePanel.inverterGroups", { n: scanResult.design_comparison.found_inverter_groups })}</span>
            </div>
          </div>

          {/* Issues grid */}
          {scanResult.issues.length > 0 && (
            <div style={{ marginTop: 12 }}>
              <div style={{ fontWeight: 600, fontSize: "var(--theme-font-size-sm)", marginBottom: 4 }}>{t("sitePanel.issues")} ({scanResult.issues.length})</div>
              <div className="ag-theme-quartz-dark" style={{ height: Math.min(scanResult.issues.length * 42 + 52, 320) }}>
                <AgGridReact
                  rowData={scanResult.issues}
                  columnDefs={issueColDefs}
                  defaultColDef={summaryColDef}
                />
              </div>
            </div>
          )}
        </div>
      )}

      {sites.length > 0 && (
        <div className="site-toolbar">
          <label>
            {t("sitePanel.site")}
            <select value={selectedSiteId ?? ""} onChange={(e) => setSelectedSiteId(Number(e.target.value))}>
              {sites.map((item) => (
                <option key={item.id} value={item.id}>{item.site_code} - {item.site_name}</option>
              ))}
            </select>
          </label>
          <label>
            {t("sitePanel.searchString")}
            <input
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t("sitePanel.searchPlaceholder")}
            />
          </label>
        </div>
      )}

      {site && (
        <div className="site-grid">
          <div className="card site-card">
            <span className="label">{t("sitePanel.site")}</span>
            <strong>{site.site_name}</strong>
            <span className="muted">{site.site_code}</span>
            <span className="muted">{site.layout_name || t("sitePanel.noLayoutName")}</span>
          </div>
          <div className="card site-card">
            <span className="label">{t("sitePanel.location")}</span>
            <strong>{site.country || t("sitePanel.unknownCountry")}</strong>
            <span className="muted">{site.region || t("sitePanel.unknownRegion")}</span>
            <span className="muted">
              {site.latitude != null && site.longitude != null
                ? `${site.latitude}, ${site.longitude}`
                : t("sitePanel.noCoordinates")}
            </span>
          </div>
          <div className="card site-card">
            <span className="label">{t("sitePanel.power")}</span>
            <strong>{site.plant_capacity_mw != null ? `${site.plant_capacity_mw.toFixed(2)} MW` : t("sitePanel.notAvailable")}</strong>
            <span className="muted">{site.module_type || t("sitePanel.unknownModuleType")}</span>
            <span className="muted">{t("sitePanel.modules_count", { count: site.module_count ?? 0 })}</span>
          </div>
          <div className="card site-card">
            <span className="label">{t("sitePanel.strings")}</span>
            <strong>{site.string_count}</strong>
            <span className="muted">{t("sitePanel.strings_count", { count: strings.length })} {t("sitePanel.displayed")}</span>
            <span className="muted">{site.source_document || t("sitePanel.unknownDocument")}</span>
          </div>
        </div>
      )}

      {strings.length > 0 && (
        <div className="string-list-panel">
          <h3>{t("sitePanel.stringList")}</h3>
          <div className="ag-theme-quartz-dark string-grid-container">
            <AgGridReact<SiteString>
              rowData={strings}
              columnDefs={columnDefs}
              defaultColDef={defaultColDef}
              pagination
              paginationPageSize={50}
              paginationPageSizeSelector={[25, 50, 100, 250]}
              animateRows
            />
          </div>
        </div>
      )}

      {importMessage && <p className="status-text">{importMessage}</p>}
      {status && <p className="status-text">{status}</p>}

      <ProgressModal
        open={previewBusy}
        title={t("sitePanel.progressPreviewTitle")}
        message={t("sitePanel.progressPreviewMsg")}
      />
      <ProgressModal
        open={importBusy}
        title={t("sitePanel.progressImportTitle")}
        message={t("sitePanel.progressImportMsg")}
      />
    </section>
  );
}
