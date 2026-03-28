import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";

export function DevicePage() {
  const client = useQueryClient();
  const ports = useQuery({ queryKey: ["ports"], queryFn: api.getPorts });
  const status = useQuery({ queryKey: ["device-status"], queryFn: api.getDeviceStatus, refetchInterval: 3000 });
  const connect = useMutation({
    mutationFn: (port: string) => api.connectDevice(port),
    onSuccess: () => client.invalidateQueries()
  });
  const disconnect = useMutation({ mutationFn: api.disconnectDevice, onSuccess: () => client.invalidateQueries() });

  return (
    <div>
      <h2>Device</h2>
      <div className="card">
        <p>Status: <strong>{status.data?.connected ? "Connected" : "Disconnected"}</strong></p>
        <p>Port: {status.data?.port ?? "-"}</p>
        <p>Mode: {status.data?.mode ?? "-"}</p>
        <p>Transfer mode detected: {status.data?.transferModeDetected ? "Yes" : "No"}</p>
      </div>
      <div className="card">
        <h3>Available ports</h3>
        <ul>
          {(ports.data?.items ?? []).map((port: { name: string; description: string }) => (
            <li key={port.name} className="portRow">
              <span>{port.name} — {port.description}</span>
              <button onClick={() => connect.mutate(port.name)}>Connect</button>
            </li>
          ))}
        </ul>
        <button onClick={() => disconnect.mutate()}>Disconnect</button>
      </div>
    </div>
  );
}
