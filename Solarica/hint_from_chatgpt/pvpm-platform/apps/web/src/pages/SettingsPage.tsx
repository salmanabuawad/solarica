export function SettingsPage() {
  return (
    <div>
      <h2>Settings</h2>
      <div className="card">
        <p>Local reader URL is controlled by <code>VITE_LOCAL_READER_URL</code>.</p>
        <p>Backend URL is controlled by <code>VITE_BACKEND_URL</code>.</p>
        <p>Switch drivers in the local reader with <code>PVPM_DRIVER</code>.</p>
      </div>
    </div>
  );
}
