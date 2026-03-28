import { useEffect, useState } from "react";
import {
  getSavedConnectorUrl,
  detectConnector,
  getImportStatus,
  startImport,
  syncUpload,
  type ConnectorImportStatus,
} from "../api/connectorClient";

export function SyncPage() {
  const connUrl = getSavedConnectorUrl();
  const [online, setOnline] = useState(false);
  const [status, setStatus] = useState<ConnectorImportStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  const refresh = async () => {
    const h = await detectConnector(connUrl);
    setOnline(h?.ok ?? false);
    if (h?.ok) {
      const s = await getImportStatus(connUrl);
      setStatus(s);
    }
  };

  useEffect(() => { refresh(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleImport = async () => {
    setBusy(true);
    setMessage("");
    try {
      const r = await startImport(connUrl);
      setMessage(`Imported ${r.imported} measurement(s) from device.`);
      await refresh();
    } catch (e) {
      setMessage(`Import failed: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setBusy(false);
    }
  };

  const handleSync = async () => {
    setBusy(true);
    setMessage("");
    try {
      const r = await syncUpload(connUrl);
      if (r.error) setMessage(`Sync error: ${r.error}`);
      else setMessage(`Uploaded ${r.uploaded} measurement(s) to backend.`);
      await refresh();
    } catch (e) {
      setMessage(`Sync failed: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setBusy(false);
    }
  };

  const btnStyle = (color = "#2563eb", disabled = false): React.CSSProperties => ({
    padding: "8px 20px", borderRadius: "var(--theme-btn-radius)", border: "none",
    background: disabled ? "#e5e7eb" : color, color: disabled ? "#9ca3af" : "#fff",
    fontWeight: 600, fontSize: "var(--theme-font-size-sm)", cursor: disabled ? "not-allowed" : "pointer",
  });

  return (
    <div>
      <h2 style={{ margin: "0 0 16px", fontSize: "1.1rem", fontWeight: 700, color: "rgb(var(--theme-text-primary))" }}>
        Sync
      </h2>

      {!online && (
        <div style={{ marginBottom: 16, padding: "12px 16px", background: "#fee2e2", border: "1px solid #fca5a5", borderRadius: 8, fontSize: "var(--theme-font-size-xs)", color: "#991b1b" }}>
          Connector offline.
        </div>
      )}

      {status && (
        <div className="solarica-card" style={{ marginBottom: 12 }}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16 }}>
            {[
              ["State", status.state],
              ["Last imported", status.lastImportedCount],
              ["Unsynced", status.unsyncedCount],
            ].map(([label, val]) => (
              <div key={String(label)}>
                <div style={{ fontSize: "var(--theme-font-size-xs)", color: "rgb(var(--theme-text-muted))", marginBottom: 2 }}>{label}</div>
                <div style={{ fontWeight: 700, fontSize: "1.2rem" }}>{val}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div style={{ display: "flex", gap: 10, marginBottom: 12 }}>
        <button style={btnStyle("#16a34a", busy || !online)} disabled={busy || !online} onClick={handleImport}>
          {busy ? "Working…" : "Import from device"}
        </button>
        <button style={btnStyle("#2563eb", busy || !online || !status?.unsyncedCount)} disabled={busy || !online || !status?.unsyncedCount} onClick={handleSync}>
          Upload to backend ({status?.unsyncedCount ?? 0})
        </button>
        <button style={btnStyle("#6b7280", busy)} disabled={busy} onClick={refresh}>
          Refresh
        </button>
      </div>

      {message && (
        <div style={{ padding: "10px 14px", background: message.includes("fail") || message.includes("error") ? "#fee2e2" : "#dcfce7", borderRadius: 8, fontSize: "var(--theme-font-size-xs)", color: message.includes("fail") || message.includes("error") ? "#991b1b" : "#166534" }}>
          {message}
        </div>
      )}
    </div>
  );
}
