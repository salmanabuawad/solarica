import { Routes, Route, Link } from "react-router-dom";
import { DashboardPage } from "./pages/DashboardPage";
import { ProjectsPage } from "./pages/ProjectsPage";
import { ValidationRulesPage } from "./pages/ValidationRulesPage";
import { ProgressPage } from "./pages/ProgressPage";
import { InventoryPage } from "./pages/InventoryPage";
import { TestsPage } from "./pages/TestsPage";

export default function App() {
  return (
    <div style={{ fontFamily: "sans-serif", padding: 20 }}>
      <h1>Solar EPC Platform</h1>
      <nav style={{ display: "flex", gap: 12, marginBottom: 20 }}>
        <Link to="/">Dashboard</Link>
        <Link to="/projects">Projects</Link>
        <Link to="/rules">Rules</Link>
        <Link to="/progress">Progress</Link>
        <Link to="/inventory">Inventory</Link>
        <Link to="/tests">Tests</Link>
      </nav>

      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/projects" element={<ProjectsPage />} />
        <Route path="/rules" element={<ValidationRulesPage />} />
        <Route path="/progress" element={<ProgressPage />} />
        <Route path="/inventory" element={<InventoryPage />} />
        <Route path="/tests" element={<TestsPage />} />
      </Routes>
    </div>
  );
}
