export const readerBaseUrl = import.meta.env.VITE_LOCAL_READER_URL || "http://localhost:8100";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${readerBaseUrl}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  getDeviceStatus: () => request("/api/device/status"),
  getPorts: () => request("/api/device/ports"),
  connectDevice: (port: string) => request("/api/device/connect", { method: "POST", body: JSON.stringify({ port }) }),
  disconnectDevice: () => request("/api/device/disconnect", { method: "POST" }),
  getMeasurements: () => request("/api/measurements"),
  getMeasurement: (id: string) => request(`/api/measurements/${id}`),
  getImportStatus: () => request("/api/import/status"),
  startImport: () => request("/api/import/start", { method: "POST" }),
  syncUpload: () => request("/api/sync/upload", { method: "POST" })
};
