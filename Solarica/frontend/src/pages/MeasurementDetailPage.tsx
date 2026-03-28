import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import {
  getSavedConnectorUrl,
  getConnectorMeasurement,
  type ConnectorMeasurement,
} from "../api/connectorClient";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from "recharts";

function field(label: string, value: string | number | null | undefined, unit = "") {
  return (
    <div style={{ minWidth: 140 }}>
      <div style={{ fontSize: "var(--theme-font-size-xs)", color: "rgb(var(--theme-text-muted))", marginBottom: 2 }}>{label}</div>
      <div style={{ fontWeight: 600, fontSize: "var(--theme-font-size-sm)" }}>
        {value == null ? "—" : typeof value === "number" ? `${value.toFixed(3)}${unit ? " " + unit : ""}` : value}
      </div>
    </div>
  );
}

export function MeasurementDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [measurement, setMeasurement] = useState<ConnectorMeasurement | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!id) return;
    const url = getSavedConnectorUrl();
    setLoading(true);
    getConnectorMeasurement(id, url)
      .then(setMeasurement)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <p style={{ color: "rgb(var(--theme-text-muted))" }}>Loading…</p>;
  if (error) return <div style={{ color: "#ef4444" }}>{error}</div>;
  if (!measurement) return null;

  const m = measurement;
  const curveData = [...(m.curvePoints ?? [])].sort((a, b) => a.voltageV - b.voltageV);

  return (
    <div>
      <div style={{ marginBottom: 12 }}>
        <Link to="/measurements" style={{ color: "rgb(var(--theme-action-accent))", fontSize: "var(--theme-font-size-xs)" }}>
          ← Back to measurements
        </Link>
      </div>

      <h2 style={{ margin: "0 0 16px", fontSize: "1.1rem", fontWeight: 700, color: "rgb(var(--theme-text-primary))" }}>
        Measurement detail
      </h2>

      {/* Identity */}
      <div className="solarica-card" style={{ marginBottom: 12 }}>
        <div style={{ fontWeight: 600, fontSize: "var(--theme-font-size-sm)", marginBottom: 10 }}>Identity</div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 20 }}>
          {field("ID", m.id)}
          {field("Date", m.measuredAt ? new Date(m.measuredAt).toLocaleString() : null)}
          {field("Customer", m.customer)}
          {field("Installation", m.installation)}
          {field("String no.", m.stringNo)}
          {field("Module type", m.moduleType)}
          {field("Module ref.", m.moduleReference)}
          {field("Status", m.syncStatus)}
        </div>
      </div>

      {/* Electrical */}
      <div className="solarica-card" style={{ marginBottom: 12 }}>
        <div style={{ fontWeight: 600, fontSize: "var(--theme-font-size-sm)", marginBottom: 10 }}>Electrical parameters</div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 20 }}>
          {field("Ppk", m.ppkWp, "Wp")}
          {field("Voc", m.vocV, "V")}
          {field("Isc", m.iscA, "A")}
          {field("Vpmax", m.vpmaxV, "V")}
          {field("Ipmax", m.ipmaxA, "A")}
          {field("FF", m.ffPercent, "%")}
          {field("Rs", m.rsOhm, "Ω")}
          {field("Rp", m.rpOhm, "Ω")}
          {field("Nominal power", m.nominalPowerW, "W")}
        </div>
      </div>

      {/* Environmental */}
      <div className="solarica-card" style={{ marginBottom: 12 }}>
        <div style={{ fontWeight: 600, fontSize: "var(--theme-font-size-sm)", marginBottom: 10 }}>Environmental</div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 20 }}>
          {field("Irradiance", m.irradianceWM2, "W/m²")}
          {field("Module temp.", m.moduleTempC, "°C")}
          {field("Sensor temp.", m.sensorTempC, "°C")}
          {field("Sensor type", m.irradianceSensorType)}
          {field("Sensor serial", m.irradianceSensorSerial)}
          {field("Sweep duration", m.sweepDurationMs, "ms")}
        </div>
      </div>

      {/* I-V Curve */}
      {curveData.length > 0 && (
        <div className="solarica-card" style={{ marginBottom: 12 }}>
          <div style={{ fontWeight: 600, fontSize: "var(--theme-font-size-sm)", marginBottom: 10 }}>
            I-V Curve ({curveData.length} points)
          </div>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={curveData} margin={{ top: 4, right: 16, bottom: 4, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--theme-ag-border)" />
              <XAxis
                dataKey="voltageV"
                label={{ value: "Voltage (V)", position: "insideBottomRight", offset: -4, fontSize: 11 }}
                tick={{ fontSize: 11 }}
              />
              <YAxis
                dataKey="currentA"
                label={{ value: "Current (A)", angle: -90, position: "insideLeft", offset: 4, fontSize: 11 }}
                tick={{ fontSize: 11 }}
              />
              <Tooltip
                contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 6, fontSize: 11 }}
                labelFormatter={(v) => `V: ${Number(v).toFixed(3)} V`}
                formatter={(v) => [`${Number(v ?? 0).toFixed(4)} A`, "Current"]}
              />
              <Line type="monotone" dataKey="currentA" stroke="rgb(var(--theme-action-accent))" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Notes */}
      {m.notes && (
        <div className="solarica-card">
          <div style={{ fontWeight: 600, fontSize: "var(--theme-font-size-sm)", marginBottom: 6 }}>Notes</div>
          <p style={{ margin: 0, fontSize: "var(--theme-font-size-sm)" }}>{m.notes}</p>
        </div>
      )}
    </div>
  );
}
