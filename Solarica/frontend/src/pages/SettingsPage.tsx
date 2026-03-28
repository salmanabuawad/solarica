import { useState } from "react";
import { getSavedConnectorUrl, saveConnectorUrl } from "../api/connectorClient";

export function SettingsPage() {
  const [connUrl, setConnUrl] = useState(getSavedConnectorUrl());
  const [draft, setDraft] = useState(getSavedConnectorUrl());
  const [saved, setSaved] = useState(false);

  const handleSave = () => {
    const url = draft.trim();
    saveConnectorUrl(url);
    setConnUrl(url);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const inputStyle: React.CSSProperties = {
    padding: "8px 12px",
    border: "1px solid rgb(var(--theme-card-border))",
    borderRadius: "var(--theme-btn-radius)",
    fontSize: "var(--theme-font-size-sm)",
    width: "100%",
    background: "#fff",
    color: "rgb(var(--theme-text-primary))",
  };

  const btnStyle: React.CSSProperties = {
    padding: "8px 20px",
    background: "rgb(var(--theme-action-accent))",
    color: "#fff",
    border: "none",
    borderRadius: "var(--theme-btn-radius)",
    fontWeight: 600,
    fontSize: "var(--theme-font-size-sm)",
    cursor: "pointer",
  };

  return (
    <div>
      <h2 style={{ margin: "0 0 16px", fontSize: "1.1rem", fontWeight: 700, color: "rgb(var(--theme-text-primary))" }}>
        Settings
      </h2>

      <div className="solarica-card" style={{ maxWidth: 520 }}>
        <div style={{ fontWeight: 600, fontSize: "var(--theme-font-size-sm)", marginBottom: 14 }}>Connector</div>

        <div style={{ marginBottom: 14 }}>
          <label style={{ display: "block", fontSize: "var(--theme-font-size-xs)", color: "rgb(var(--theme-text-muted))", marginBottom: 6 }}>
            Connector URL
          </label>
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="http://127.0.0.1:8765"
            style={inputStyle}
          />
          <p style={{ margin: "4px 0 0", fontSize: "var(--theme-font-size-xs)", color: "rgb(var(--theme-text-muted))" }}>
            Local connector service address (Python or .NET). Current: <code>{connUrl}</code>
          </p>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <button style={btnStyle} onClick={handleSave}>Save</button>
          {saved && <span style={{ color: "#16a34a", fontSize: "var(--theme-font-size-xs)", fontWeight: 600 }}>Saved ✓</span>}
        </div>
      </div>

      <div className="solarica-card" style={{ marginTop: 12, maxWidth: 520 }}>
        <div style={{ fontWeight: 600, fontSize: "var(--theme-font-size-sm)", marginBottom: 10 }}>Environment</div>
        <div style={{ fontSize: "var(--theme-font-size-xs)", color: "rgb(var(--theme-text-muted))" }}>
          {[
            ["VITE_CONNECTOR_URL", import.meta.env.VITE_CONNECTOR_URL ?? "(not set)"],
            ["VITE_API_URL", import.meta.env.VITE_API_URL ?? "(not set)"],
          ].map(([k, v]) => (
            <div key={k} style={{ marginBottom: 6 }}>
              <code style={{ color: "rgb(var(--theme-action-accent))" }}>{k}</code> = {String(v)}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
