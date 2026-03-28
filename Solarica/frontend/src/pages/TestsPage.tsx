import { useEffect, useState } from "react";
import { MeasurementTable } from "../components/MeasurementTable";
import {
  getSavedConnectorUrl,
  detectConnector,
  listConnectorMeasurements,
  type ConnectorMeasurement,
} from "../api/connectorClient";

export function TestsPage() {
  const [measurements, setMeasurements] = useState<ConnectorMeasurement[]>([]);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    const url = getSavedConnectorUrl();
    (async () => {
      setLoading(true);
      const h = await detectConnector(url);
      if (!h?.ok) { setOffline(true); setLoading(false); return; }
      const ms = await listConnectorMeasurements(url);
      setMeasurements(ms.items);
      setLoading(false);
    })();
  }, []);

  return (
    <div>
      <h2 style={{ margin: "0 0 16px", fontSize: "1.1rem", fontWeight: 700, color: "rgb(var(--theme-text-primary))" }}>
        Measurements
      </h2>

      {loading && <p style={{ color: "rgb(var(--theme-text-muted))" }}>Loading…</p>}

      {offline && !loading && (
        <div style={{ padding: "12px 16px", background: "#fee2e2", border: "1px solid #fca5a5", borderRadius: 8, fontSize: "var(--theme-font-size-xs)", color: "#991b1b" }}>
          Connector offline. Start the connector on port 8765.
        </div>
      )}

      {!loading && !offline && (
        <div className="solarica-card">
          <MeasurementTable items={measurements} linkPrefix="/measurements" />
        </div>
      )}
    </div>
  );
}
