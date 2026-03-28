import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { api } from "../lib/api";
import { CurveChart } from "../components/CurveChart";

export function MeasurementDetailsPage() {
  const { id = "" } = useParams();
  const query = useQuery({ queryKey: ["measurement", id], queryFn: () => api.getMeasurement(id), enabled: Boolean(id) });
  const item = query.data;

  if (!item) return <div>Loading...</div>;

  return (
    <div>
      <h2>Measurement details</h2>
      <div className="grid">
        <div className="card"><strong>Date</strong><div>{new Date(item.measuredAt).toLocaleString()}</div></div>
        <div className="card"><strong>Customer</strong><div>{item.customer ?? "-"}</div></div>
        <div className="card"><strong>Module</strong><div>{item.moduleType ?? "-"}</div></div>
        <div className="card"><strong>Ppk</strong><div>{item.ppkWp ?? "-"}</div></div>
        <div className="card"><strong>Voc</strong><div>{item.vocV ?? "-"}</div></div>
        <div className="card"><strong>Isc</strong><div>{item.iscA ?? "-"}</div></div>
      </div>
      <CurveChart points={item.curvePoints ?? []} />
      <div className="card">
        <h3>Raw payload</h3>
        <pre>{JSON.stringify(item.rawPayloadJson, null, 2)}</pre>
      </div>
    </div>
  );
}
