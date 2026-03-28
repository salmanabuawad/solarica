import { useEffect, useRef, useState } from "react";
import {
  connectPort,
  detectConnector,
  disconnectPort,
  getDeviceStatus,
  getImportStatus,
  getSavedConnectorUrl,
  listConnectorFiles,
  listPorts,
  startImport,
  type ConnectorDeviceStatus,
  type ConnectorFileInfo,
  type ConnectorHealth,
  type ConnectorPortInfo,
} from "../api/connectorClient";

export function DevicePage() {
  const connUrl = getSavedConnectorUrl();
  const [health, setHealth] = useState<ConnectorHealth | null>(null);
  const [device, setDevice] = useState<ConnectorDeviceStatus | null>(null);
  const [ports, setPorts] = useState<ConnectorPortInfo[]>([]);
  const [files, setFiles] = useState<ConnectorFileInfo[]>([]);
  const [busy, setBusy] = useState(false);
  const [capturing, setCapturing] = useState(false);
  const [captureMsg, setCaptureMsg] = useState("");
  const [watching, setWatching] = useState(false);
  const [error, setError] = useState("");
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refreshFiles = async () => {
    try {
      const fs = await listConnectorFiles(connUrl);
      setFiles(fs.items);
    } catch { /* ignore */ }
  };

  const refresh = async () => {
    const h = await detectConnector(connUrl);
    setHealth(h);
    if (h?.ok) {
      const [ds, ps, fs, is_] = await Promise.all([
        getDeviceStatus(connUrl),
        listPorts(connUrl),
        listConnectorFiles(connUrl),
        getImportStatus(connUrl),
      ]);
      setDevice(ds);
      setPorts(ps.items);
      setFiles(fs.items);
      setWatching(!!(is_ as any).watcherActive);
    }
  };

  useEffect(() => {
    refresh();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Poll files every 4s when watching
  useEffect(() => {
    if (watching) {
      pollRef.current = setInterval(refreshFiles, 4000);
    } else {
      if (pollRef.current) clearInterval(pollRef.current);
    }
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [watching]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleConnect = async (port: string) => {
    setBusy(true); setError(""); setCaptureMsg("");
    try {
      const ds = await connectPort(port, connUrl);
      setDevice(ds);
      const fs = await listConnectorFiles(connUrl);
      setFiles(fs.items);
      if (ds.mode === "serial") {
        setCaptureMsg("Connected to " + port + ". Press Transfer on the PVPM device, then click 'Read from Device'.");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(false); }
  };

  const handleDisconnect = async () => {
    setBusy(true); setError(""); setCaptureMsg("");
    setWatching(false);
    try { await disconnectPort(connUrl); await refresh(); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  };

  const handleCapture = async () => {
    setCapturing(true); setError(""); setCaptureMsg("Waiting for Transfer Mode — press Transfer on the PVPM device…");
    try {
      const result = await startImport(connUrl);
      if (result.imported > 0) {
        setCaptureMsg(`✓ Captured ${result.imported} measurement${result.imported !== 1 ? "s" : ""} from device.`);
        await refreshFiles();
      } else {
        setCaptureMsg("No data received. Make sure the device is in Transfer Mode and the cable is connected.");
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      setCaptureMsg("");
    } finally { setCapturing(false); }
  };

  const toggleWatcher = async () => {
    try {
      const path = watching ? "/api/import/watch/stop" : "/api/import/watch/start";
      await fetch(`${connUrl}${path}`, { method: "POST" });
      setWatching(!watching);
      setCaptureMsg(watching ? "Auto-watch stopped." : "Auto-watching folder — new files imported automatically.");
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  };

  const launchPvpm = async () => {
    try {
      const res = await fetch(`${connUrl}/api/device/launch-pvpm`, { method: "POST" });
      const data = await res.json();
      if (data.ok) setCaptureMsg("PVPMdisp launched. Use Transfer Mode in the software to copy files.");
      else setError(data.error ?? "Could not launch PVPMdisp.");
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  };

  const online = health?.ok === true;
  const isSerial = device?.mode === "serial";
  const isVendor = device?.mode === "vendor_export";

  const badge = (label: string, ok: boolean) => (
    <span style={{
      display: "inline-block", padding: "2px 10px", borderRadius: 999,
      background: ok ? "#dcfce7" : "#fee2e2", color: ok ? "#166534" : "#991b1b",
      fontWeight: 600, fontSize: "var(--theme-font-size-xs)"
    }}>{label}</span>
  );

  const modeBadge = (mode: string) => {
    const colors: Record<string, [string, string]> = {
      serial:        ["#dbeafe", "#1e40af"],
      vendor_export: ["#f0fdf4", "#166534"],
      mock:          ["#f3f4f6", "#6b7280"],
    };
    const [bg, fg] = colors[mode] ?? ["#f3f4f6", "#6b7280"];
    return <span style={{ display: "inline-block", padding: "2px 8px", borderRadius: 4, background: bg, color: fg, fontWeight: 600, fontSize: "var(--theme-font-size-xs)", textTransform: "uppercase" }}>{mode.replace("_", " ")}</span>;
  };

  const btn = (color: string, disabled = false): React.CSSProperties => ({
    padding: "6px 16px", borderRadius: "var(--theme-btn-radius)", border: "none",
    background: disabled ? "#e5e7eb" : color, color: disabled ? "#9ca3af" : "#fff",
    fontWeight: 600, fontSize: "var(--theme-font-size-sm)", cursor: disabled ? "not-allowed" : "pointer",
  });

  const fmtSize = (b: number) => b < 1024 ? `${b} B` : b < 1048576 ? `${(b / 1024).toFixed(1)} KB` : `${(b / 1048576).toFixed(1)} MB`;
  const fmtDate = (iso: string) => { try { return new Date(iso).toLocaleString(); } catch { return iso; } };

  return (
    <div>
      <h2 style={{ margin: "0 0 16px", fontSize: "1.1rem", fontWeight: 700, color: "rgb(var(--theme-text-primary))" }}>
        Device
      </h2>

      {/* Connector health */}
      <div className="solarica-card" style={{ marginBottom: 12 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span style={{ fontWeight: 600, fontSize: "var(--theme-font-size-sm)" }}>Connector</span>
          {badge(online ? "Online" : "Offline", online)}
          {health && <span style={{ fontSize: "var(--theme-font-size-xs)", color: "rgb(var(--theme-text-muted))" }}>v{health.version} · {health.runtime}</span>}
          <button style={{ ...btn("rgb(var(--theme-action-accent))"), marginLeft: "auto" }} onClick={refresh}>Refresh</button>
        </div>
        {!online && (
          <p style={{ margin: "10px 0 0", fontSize: "var(--theme-font-size-xs)", color: "#b45309" }}>
            Connector offline — run <code>manager.bat</code> to start it.
          </p>
        )}
      </div>

      {online && (
        <>
          {/* Current device status */}
          <div className="solarica-card" style={{ marginBottom: 12 }}>
            <div style={{ fontWeight: 600, fontSize: "var(--theme-font-size-sm)", marginBottom: 10 }}>Device status</div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: 10 }}>
              {[
                ["Connected", badge(device?.connected ? "Yes" : "No", device?.connected ?? false)],
                ["Mode", device?.mode ? modeBadge(device.mode) : "—"],
                ["Port", device?.port ?? "—"],
                ...(isSerial ? [
                  ["Transfer Mode", badge(device?.transferModeDetected ? "Detected" : "Not yet", device?.transferModeDetected ?? false)],
                ] : []),
              ].map(([k, v]) => (
                <div key={String(k)}>
                  <div style={{ fontSize: "var(--theme-font-size-xs)", color: "rgb(var(--theme-text-muted))", marginBottom: 2 }}>{k}</div>
                  <div style={{ fontSize: "var(--theme-font-size-sm)", fontWeight: 600, wordBreak: "break-all" }}>{v}</div>
                </div>
              ))}
            </div>

            {/* Error from driver */}
            {device?.connected && device?.lastError && !captureMsg && (
              <div style={{ marginTop: 10, padding: "6px 10px", background: "#fef3c7", borderRadius: 6, fontSize: "var(--theme-font-size-xs)", color: "#92400e" }}>
                {device.lastError}
              </div>
            )}

            {device?.connected && (
              <div style={{ marginTop: 14, display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>

                {/* Serial mode: Read from Device */}
                {isSerial && (
                  <button
                    style={btn(capturing ? "#b45309" : "rgb(var(--theme-action-accent))", capturing)}
                    disabled={capturing}
                    onClick={handleCapture}
                    title="Press Transfer on the PVPM device, then click this button"
                  >
                    {capturing ? "⏳ Waiting for device…" : "⬇ Read from Device"}
                  </button>
                )}

                {/* Vendor export mode: import + watch */}
                {isVendor && (
                  <>
                    <button style={btn("#334155")} onClick={launchPvpm}>📂 Open PVPM Software</button>
                    <button style={btn(watching ? "#b45309" : "#16a34a")} onClick={toggleWatcher}>
                      {watching ? "⏹ Stop Watch" : "👁 Auto-Watch"}
                    </button>
                    <button style={btn("rgb(var(--theme-action-accent))")} onClick={handleCapture}>↓ Import Now</button>
                  </>
                )}

                <button style={{ ...btn("#ef4444", busy), marginLeft: "auto" }} disabled={busy} onClick={handleDisconnect}>
                  Disconnect
                </button>
              </div>
            )}

            {captureMsg && (
              <div style={{ marginTop: 8, padding: "6px 10px", background: capturing ? "#fef3c7" : "#f0fdf4", borderRadius: 6, fontSize: "var(--theme-font-size-xs)", color: capturing ? "#92400e" : "#166534" }}>
                {captureMsg}
              </div>
            )}

            {/* Serial mode workflow hint */}
            {isSerial && device?.connected && (
              <div style={{ marginTop: 10, padding: "10px 12px", background: "rgb(var(--theme-nav-bg))", borderRadius: 6, fontSize: "var(--theme-font-size-xs)", color: "rgb(var(--theme-text-muted))" }}>
                <strong style={{ color: "rgb(var(--theme-text-primary))" }}>How to transfer measurements:</strong><br />
                1. Make sure PVPM 1540X is connected via USB (COM8)<br />
                2. Click <strong>Read from Device</strong> above<br />
                3. On the PVPM device: press <strong>Transfer</strong> button<br />
                4. The connector captures the SUI files streamed by the device
              </div>
            )}
          </div>

          {/* Available ports */}
          {!device?.connected && (
            <div className="solarica-card" style={{ marginBottom: 12 }}>
              <div style={{ fontWeight: 600, fontSize: "var(--theme-font-size-sm)", marginBottom: 10 }}>
                Available ports ({ports.length})
              </div>
              {ports.length === 0 ? (
                <p style={{ color: "rgb(var(--theme-text-muted))", fontSize: "var(--theme-font-size-xs)" }}>No ports detected.</p>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {ports.map((p) => (
                    <div key={p.name} style={{ display: "flex", alignItems: "center", gap: 12, padding: "8px 12px", background: "rgb(var(--theme-nav-bg))", borderRadius: 6 }}>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontWeight: 600, fontFamily: "monospace", fontSize: "var(--theme-font-size-sm)" }}>{p.name}</div>
                        <div style={{ fontSize: "var(--theme-font-size-xs)", color: "rgb(var(--theme-text-muted))", marginTop: 2 }}>{p.description}</div>
                      </div>
                      <button style={btn("#16a34a", busy)} disabled={busy} onClick={() => handleConnect(p.name)}>
                        Connect
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Files / captured measurements */}
          {device?.connected && (
            <div className="solarica-card">
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
                <span style={{ fontWeight: 600, fontSize: "var(--theme-font-size-sm)" }}>
                  {isSerial ? "Captured measurements" : "Files in folder"} ({files.length})
                </span>
                {watching && (
                  <span style={{ fontSize: "var(--theme-font-size-xs)", color: "#b45309", background: "#fef3c7", padding: "1px 8px", borderRadius: 999 }}>live</span>
                )}
                <button style={{ ...btn("rgb(var(--theme-action-accent))"), padding: "3px 10px", marginLeft: "auto" }} onClick={refreshFiles}>
                  Refresh
                </button>
              </div>

              {files.length === 0 ? (
                <div style={{ padding: "20px", textAlign: "center", color: "rgb(var(--theme-text-muted))", fontSize: "var(--theme-font-size-xs)" }}>
                  {isSerial
                    ? "No measurements captured yet. Press Transfer on the device, then click 'Read from Device'."
                    : "No files found. Use PVPMdisp Transfer Mode to export files here."}
                </div>
              ) : (
                <div style={{ overflowX: "auto" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "var(--theme-font-size-xs)" }}>
                    <thead>
                      <tr style={{ borderBottom: "1px solid rgb(var(--theme-card-border))" }}>
                        {["Name", "Type", "String", "Customer", "Module", "Date", "Size"].map(h => (
                          <th key={h} style={{ padding: "6px 8px", textAlign: "left", color: "rgb(var(--theme-text-muted))", fontWeight: 600, whiteSpace: "nowrap" }}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {files.map((f) => (
                        <tr key={f.name} style={{ borderBottom: "1px solid rgb(var(--theme-card-border))" }}>
                          <td style={{ padding: "6px 8px", fontFamily: "monospace", fontWeight: 600, color: "rgb(var(--theme-text-primary))" }}>{f.name}</td>
                          <td style={{ padding: "6px 8px" }}>
                            <span style={{ display: "inline-block", padding: "1px 6px", borderRadius: 4, background: "#dbeafe", color: "#1e40af", fontWeight: 600, textTransform: "uppercase" }}>{f.type}</span>
                          </td>
                          <td style={{ padding: "6px 8px" }}>{f.stringNo ?? "—"}</td>
                          <td style={{ padding: "6px 8px", color: "rgb(var(--theme-text-muted))" }}>{f.customer ?? "—"}</td>
                          <td style={{ padding: "6px 8px", color: "rgb(var(--theme-text-muted))", maxWidth: 160, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{f.moduleType ?? "—"}</td>
                          <td style={{ padding: "6px 8px", color: "rgb(var(--theme-text-muted))", whiteSpace: "nowrap" }}>
                            {f.measuredAt ? fmtDate(f.measuredAt) : fmtDate(f.modified)}
                          </td>
                          <td style={{ padding: "6px 8px", color: "rgb(var(--theme-text-muted))", whiteSpace: "nowrap" }}>{fmtSize(f.size)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </>
      )}

      {error && (
        <div style={{ marginTop: 12, padding: "8px 12px", background: "#fee2e2", border: "1px solid #fca5a5", borderRadius: 6, fontSize: "var(--theme-font-size-xs)", color: "#991b1b" }}>
          {error}
        </div>
      )}
    </div>
  );
}
