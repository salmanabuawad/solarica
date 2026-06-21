import { useState } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import AppShell from "./components/AppShell";
import ExecutionTwin from "./modules/ExecutionTwin";
import AttackGraph from "./modules/AttackGraph";
import { Blockers, Tasks, Cyber } from "./modules/extra";
import Construction from "./modules/Construction";
import Engineering from "./modules/Engineering";
import SiteAccess from "./modules/SiteAccess";
import Toolbox from "./modules/Toolbox";
import Inventory from "./modules/Inventory";
import QA from "./modules/QA";
import Operations from "./modules/Operations";
import Maintenance from "./modules/Maintenance";

export default function App() {
  const [role, setRole] = useState("pm");
  return (
    <Routes>
      <Route element={<AppShell role={role} setRole={setRole} />}>
        <Route index element={<Navigate to="/twin" replace />} />
        <Route path="twin" element={<ExecutionTwin />} />
        <Route path="construction" element={<Construction />} />
        <Route path="blockers" element={<Blockers />} />
        <Route path="tasks" element={<Tasks />} />
        <Route path="cyber" element={<Cyber />} />
        <Route path="attackgraph" element={<AttackGraph />} />
        <Route path="engineering" element={<Engineering />} />
        <Route path="access" element={<SiteAccess />} />
        <Route path="toolbox" element={<Toolbox />} />
        <Route path="inventory" element={<Inventory />} />
        <Route path="qa" element={<QA />} />
        <Route path="operations" element={<Operations />} />
        <Route path="maintenance" element={<Maintenance />} />
        <Route path="*" element={<Navigate to="/twin" replace />} />
      </Route>
    </Routes>
  );
}
