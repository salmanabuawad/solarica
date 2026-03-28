import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";

export function SyncPage() {
  const client = useQueryClient();
  const status = useQuery({ queryKey: ["import-status"], queryFn: api.getImportStatus, refetchInterval: 3000 });
  const start = useMutation({ mutationFn: api.startImport, onSuccess: () => client.invalidateQueries() });
  const sync = useMutation({ mutationFn: api.syncUpload, onSuccess: () => client.invalidateQueries() });

  return (
    <div>
      <h2>Sync</h2>
      <div className="card">
        <p>Import status: {status.data?.state ?? "idle"}</p>
        <p>Imported records: {status.data?.lastImportedCount ?? 0}</p>
        <p>Unsynced records: {status.data?.unsyncedCount ?? 0}</p>
        <div className="buttonRow">
          <button onClick={() => start.mutate()}>Start import</button>
          <button onClick={() => sync.mutate()}>Upload unsynced</button>
        </div>
      </div>
    </div>
  );
}
