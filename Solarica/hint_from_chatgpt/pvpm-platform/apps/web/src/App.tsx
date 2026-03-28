import { NavLink, Route, Routes } from "react-router-dom";
import { DashboardPage } from "./pages/DashboardPage";
import { DevicePage } from "./pages/DevicePage";
import { MeasurementsPage } from "./pages/MeasurementsPage";
import { MeasurementDetailsPage } from "./pages/MeasurementDetailsPage";
import { SyncPage } from "./pages/SyncPage";
import { SettingsPage } from "./pages/SettingsPage";

const links = [
  ["/", "Dashboard"],
  ["/device", "Device"],
  ["/measurements", "Measurements"],
  ["/sync", "Sync"],
  ["/settings", "Settings"]
] as const;

export function App() {
  return (
    <div className="layout">
      <aside className="sidebar">
        <h1>PVPM Platform</h1>
        <nav>
          {links.map(([to, label]) => (
            <NavLink key={to} to={to} end={to === "/"} className={({ isActive }) => isActive ? "active" : ""}>
              {label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="content">
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/device" element={<DevicePage />} />
          <Route path="/measurements" element={<MeasurementsPage />} />
          <Route path="/measurements/:id" element={<MeasurementDetailsPage />} />
          <Route path="/sync" element={<SyncPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </main>
    </div>
  );
}
