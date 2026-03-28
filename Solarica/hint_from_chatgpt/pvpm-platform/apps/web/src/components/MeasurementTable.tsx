import { Link } from "react-router-dom";

type Measurement = {
  id: string;
  measuredAt: string;
  customer?: string | null;
  installation?: string | null;
  moduleType?: string | null;
  ppkWp?: number | null;
  vocV?: number | null;
  iscA?: number | null;
  irradianceWM2?: number | null;
  syncStatus?: string | null;
};

export function MeasurementTable({ rows }: { rows: Measurement[] }) {
  return (
    <div className="tableWrap">
      <table>
        <thead>
          <tr>
            <th>Date</th>
            <th>Customer</th>
            <th>Installation</th>
            <th>Module</th>
            <th>Ppk</th>
            <th>Voc</th>
            <th>Isc</th>
            <th>Irradiance</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td><Link to={`/measurements/${row.id}`}>{new Date(row.measuredAt).toLocaleString()}</Link></td>
              <td>{row.customer ?? "-"}</td>
              <td>{row.installation ?? "-"}</td>
              <td>{row.moduleType ?? "-"}</td>
              <td>{row.ppkWp ?? "-"}</td>
              <td>{row.vocV ?? "-"}</td>
              <td>{row.iscA ?? "-"}</td>
              <td>{row.irradianceWM2 ?? "-"}</td>
              <td>{row.syncStatus ?? "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
