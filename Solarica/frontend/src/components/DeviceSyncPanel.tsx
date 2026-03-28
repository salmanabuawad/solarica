import { useEffect, useMemo, useState } from "react";
import type { BridgeJob, BridgeStatus, ImportBatchResult } from "../api/client";
import { api } from "../api/client";

const DEFAULT_BRIDGE_URL =
  window.localStorage.getItem("ivcurve.bridgeUrl") ||
  window.localStorage.getItem("ivcare.bridgeUrl") ||
  import.meta.env.VITE_BRIDGE_URL ||
  "http://127.0.0.1:8765";

interface DeviceSyncPanelProps {
  onImported?: () => void;
}

export function DeviceSyncPanel({ onImported }: DeviceSyncPanelProps) {
  const [bridgeUrl, setBridgeUrl] = useState(DEFAULT_BRIDGE_URL);
  const [draftBridgeUrl, setDraftBridgeUrl] = useState(DEFAULT_BRIDGE_URL);
  const [bridgeStatus, setBridgeStatus] = useState<BridgeStatus | null>(null);
  const [job, setJob] = useState<BridgeJob | null>(null);
  const [importResult, setImportResult] = useState<ImportBatchResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  const bridgeOnline = bridgeStatus?.status === "online";

  const stats = useMemo(() => {
    if (!importResult) {
      return null;
    }

    return `${importResult.imported} imported, ${importResult.duplicates} duplicates, ${importResult.failed} failed`;
  }, [importResult]);

  useEffect(() => {
    let ignore = false;

    api.getBridgeStatus(bridgeUrl).then((status) => {
      if (!ignore) {
        setBridgeStatus(status);
      }
    });

    return () => {
      ignore = true;
    };
  }, [bridgeUrl]);

  useEffect(() => {
    if (!job?.job_id || job.status === "completed" || job.status === "failed") {
      return undefined;
    }

    const timer = window.setInterval(async () => {
      const nextJob = await api.getImportProgress(job.job_id, bridgeUrl);
      setJob(nextJob);
    }, 1500);

    return () => window.clearInterval(timer);
  }, [bridgeUrl, job]);

  const refreshBridgeStatus = async () => {
    setBridgeStatus(await api.getBridgeStatus(bridgeUrl));
  };

  const saveBridgeUrl = async () => {
    const normalized = draftBridgeUrl.trim();
    window.localStorage.setItem("ivcurve.bridgeUrl", normalized);
    setBridgeUrl(normalized);
    setMessage("Bridge URL updated.");
  };

  const syncMeasurements = async () => {
    setBusy(true);
    setImportResult(null);
    setMessage("");

    try {
      const started = await api.startDeviceImport(bridgeUrl);
      setJob({
        job_id: started.job_id,
        status: started.status,
        message: started.message,
        measurements: [],
        imported_count: 0,
        duplicate_count: 0,
        failed_count: 0,
      });

      let currentJob = await api.getImportProgress(started.job_id, bridgeUrl);
      setJob(currentJob);
      while (currentJob.status === "queued" || currentJob.status === "running") {
        await new Promise((resolve) => window.setTimeout(resolve, 1200));
        currentJob = await api.getImportProgress(started.job_id, bridgeUrl);
        setJob(currentJob);
      }

      if (currentJob.status === "failed") {
        setMessage(currentJob.message);
        return;
      }

      const batchResult = await api.uploadMeasurementBatch(currentJob.measurements);
      setImportResult(batchResult);
      if (batchResult.imported > 0) {
        onImported?.();
      }
      setMessage(batchResult.success ? "Sync finished." : "Sync finished with errors.");
      await refreshBridgeStatus();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="sync-panel">
      <div className="section-heading">
        <div>
          <h2>Device sync</h2>
          <p className="hint">
            Pull saved PVPM measurements through the local bridge, then import them into IVCurve.
          </p>
        </div>
        <button type="button" onClick={refreshBridgeStatus} disabled={busy}>
          Refresh bridge
        </button>
      </div>

      <div className="sync-status-grid">
        <div className="card sync-card">
          <span className="label">Bridge</span>
          <strong className={bridgeOnline ? "status-text ok" : "status-text error"}>
            {bridgeOnline ? "Online" : "Offline"}
          </strong>
          <span className="muted">{bridgeStatus?.message || "Checking bridge..."}</span>
        </div>
        <div className="card sync-card">
          <span className="label">Device</span>
          <strong>{bridgeStatus?.device_connected ? "Detected" : "Not detected"}</strong>
          <span className="muted">
            {bridgeStatus?.device_mode
              ? `Mode: ${bridgeStatus.device_mode}`
              : "Switch the PVPM to Transfer mode before syncing."}
          </span>
        </div>
        <div className="card sync-card">
          <span className="label">Last sync</span>
          <strong>
            {bridgeStatus?.last_sync_at
              ? new Date(bridgeStatus.last_sync_at).toLocaleString()
              : "No sync yet"}
          </strong>
          <span className="muted">
            {stats || "The bridge prevents re-uploading records it has already returned."}
          </span>
        </div>
      </div>

      <div className="bridge-config">
        <label htmlFor="bridge-url">Bridge URL</label>
        <div className="inline-form">
          <input
            id="bridge-url"
            type="url"
            value={draftBridgeUrl}
            onChange={(event) => setDraftBridgeUrl(event.target.value)}
            placeholder="http://127.0.0.1:8765"
          />
          <button type="button" onClick={saveBridgeUrl} disabled={busy || !draftBridgeUrl.trim()}>
            Save
          </button>
        </div>
        <p className="hint">
          Use the bridge host IP here if this responsive UI is opened from another device on the same network.
        </p>
      </div>

      <div className="action-bar">
        <button
          type="button"
          className="primary"
          onClick={syncMeasurements}
          disabled={busy || !bridgeOnline}
        >
          {busy ? "Syncing..." : "Sync saved measurements"}
        </button>
        <span className="muted">
          {job ? `Job ${job.job_id}: ${job.status}` : "Ready to start a new bridge sync."}
        </span>
      </div>

      {job && (
        <div className="job-summary">
          <strong>{job.message}</strong>
          <span className="muted">
            {job.measurements.length} measurements prepared by the bridge.
          </span>
        </div>
      )}

      {importResult && (
        <div className="sync-result">
          <strong>Server import result</strong>
          <p className="hint">{stats}</p>
          <ul>
            {importResult.results.slice(0, 5).map((result, index) => (
              <li key={`${result.measurement_id || "new"}-${index}`}>
                {result.message}
              </li>
            ))}
          </ul>
        </div>
      )}

      {message && <p className="status-text">{message}</p>}
    </section>
  );
}
