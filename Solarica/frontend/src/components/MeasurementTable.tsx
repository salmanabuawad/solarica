import { Link } from "react-router-dom";
import type { ConnectorMeasurement } from "../api/connectorClient";

interface Props {
  items: ConnectorMeasurement[];
  linkPrefix?: string;
}

export function MeasurementTable({ items, linkPrefix = "/tests" }: Props) {
  const thStyle: React.CSSProperties = {
    padding: "8px 12px",
    textAlign: "left",
    fontWeight: 600,
    fontSize: "var(--theme-font-size-xs)",
    color: "rgb(var(--theme-text-muted))",
    background: "var(--theme-ag-header-bg)",
    borderBottom: "1px solid var(--theme-ag-border)",
    whiteSpace: "nowrap",
  };
  const tdStyle: React.CSSProperties = {
    padding: "7px 12px",
    fontSize: "var(--theme-font-size-xs)",
    borderBottom: "1px solid var(--theme-ag-border)",
    color: "rgb(var(--theme-text-primary))",
  };

  const fmt = (v: number | null | undefined, digits = 1) =>
    v == null ? "—" : v.toFixed(digits);

  const statusColor = (s: string) =>
    s === "synced" ? "#16a34a" : s === "error" ? "#ef4444" : "#f59e0b";

  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "var(--theme-font-size-xs)" }}>
        <thead>
          <tr>
            <th style={thStyle}>Date</th>
            <th style={thStyle}>Customer</th>
            <th style={thStyle}>Installation</th>
            <th style={thStyle}>Module</th>
            <th style={thStyle}>Ppk (Wp)</th>
            <th style={thStyle}>Voc (V)</th>
            <th style={thStyle}>Isc (A)</th>
            <th style={thStyle}>Irr. (W/m²)</th>
            <th style={thStyle}>Status</th>
          </tr>
        </thead>
        <tbody>
          {items.length === 0 && (
            <tr>
              <td colSpan={9} style={{ ...tdStyle, textAlign: "center", color: "rgb(var(--theme-text-muted))", padding: 24 }}>
                No measurements
              </td>
            </tr>
          )}
          {items.map((m) => (
            <tr key={m.id} style={{ cursor: "pointer" }}>
              <td style={tdStyle}>
                <Link
                  to={`${linkPrefix}/${m.id}`}
                  style={{ color: "rgb(var(--theme-action-accent))", textDecoration: "none" }}
                >
                  {m.measuredAt ? new Date(m.measuredAt).toLocaleString() : "—"}
                </Link>
              </td>
              <td style={tdStyle}>{m.customer ?? "—"}</td>
              <td style={tdStyle}>{m.installation ?? "—"}</td>
              <td style={tdStyle}>{m.moduleType ?? "—"}</td>
              <td style={tdStyle}>{fmt(m.ppkWp)}</td>
              <td style={tdStyle}>{fmt(m.vocV)}</td>
              <td style={tdStyle}>{fmt(m.iscA, 2)}</td>
              <td style={tdStyle}>{fmt(m.irradianceWM2)}</td>
              <td style={tdStyle}>
                <span style={{ color: statusColor(m.syncStatus), fontWeight: 600 }}>
                  {m.syncStatus}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
