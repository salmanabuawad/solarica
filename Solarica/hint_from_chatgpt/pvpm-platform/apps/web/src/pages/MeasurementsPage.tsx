import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { MeasurementTable } from "../components/MeasurementTable";

export function MeasurementsPage() {
  const measurements = useQuery({ queryKey: ["measurements"], queryFn: api.getMeasurements });
  return (
    <div>
      <h2>Measurements</h2>
      <MeasurementTable rows={measurements.data?.items ?? []} />
    </div>
  );
}
