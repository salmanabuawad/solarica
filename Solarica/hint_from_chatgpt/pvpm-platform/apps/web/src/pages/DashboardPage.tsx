import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { StatCard } from "../components/StatCard";
import { MeasurementTable } from "../components/MeasurementTable";

export function DashboardPage() {
  const device = useQuery({ queryKey: ["device-status"], queryFn: api.getDeviceStatus, refetchInterval: 5000 });
  const measurements = useQuery({ queryKey: ["measurements"], queryFn: api.getMeasurements });
  const rows = (measurements.data?.items ?? []).slice(0, 5);

  return (
    <div>
      <h2>Dashboard</h2>
      <div className="grid">
        <StatCard title="Device" value={device.data?.connected ? "Connected" : "Disconnected"} hint={device.data?.port ?? "No port selected"} />
        <StatCard title="Driver" value={device.data?.mode ?? "mock"} />
        <StatCard title="Transfer mode" value={device.data?.transferModeDetected ? "Detected" : "Pending"} />
        <StatCard title="Measurements" value={measurements.data?.items?.length ?? 0} />
      </div>
      <section>
        <h3>Recent measurements</h3>
        <MeasurementTable rows={rows} />
      </section>
    </div>
  );
}
