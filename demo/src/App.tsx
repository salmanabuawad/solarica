import { useState } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import AppShell from "./components/AppShell";
import ExecutionTwin from "./modules/ExecutionTwin";
import DCLayer from "./modules/DCLayer";
import AttackGraph from "./modules/AttackGraph";
import { Blockers, Tasks, Cyber, Placeholder } from "./modules/extra";

export default function App() {
  const [role, setRole] = useState("pm");
  return (
    <Routes>
      <Route element={<AppShell role={role} setRole={setRole} />}>
        <Route index element={<Navigate to="/twin" replace />} />
        <Route path="twin" element={<ExecutionTwin />} />
        <Route path="construction" element={<DCLayer />} />
        <Route path="blockers" element={<Blockers />} />
        <Route path="tasks" element={<Tasks />} />
        <Route path="cyber" element={<Cyber />} />
        <Route path="attackgraph" element={<AttackGraph />} />
        <Route path="engineering" element={<Placeholder title="Engineering" subtitle="Design → EPL → Validation → Change Management" pages={["Design Upload (DWG/DXF/PDF)", "EPL — Drawings → Assets", "Validation Checks", "Engineering Change Management"]} />} />
        <Route path="access" element={<Placeholder title="Site Access" subtitle="Replace phone / WhatsApp / gate-waiting with a tracked access workflow" pages={["Access Requests", "Vehicle Approval", "Entry / Exit Logs", "Security Dashboard (SLA)"]} />} />
        <Route path="toolbox" element={<Placeholder title="Solarica Toolbox" subtitle="IV testers · meggers · torque wrenches · tablets · thermal cameras" pages={["Tool Inventory", "Calibration", "Assignment", "Technician Readiness"]} />} />
        <Route path="inventory" element={<Placeholder title="Inventory" subtitle="Modules · optimizers · bolts · cables · parts" pages={["Inventory", "Reservations", "Shortages", "Procurement"]} />} />
        <Route path="qa" element={<Placeholder title="QA & Testing" subtitle="Voltage · Polarity · Megger · IV Curve · Commissioning Readiness" pages={["Voltage", "Polarity", "Megger", "IV Curve (expected vs actual)", "Commissioning Readiness"]} />} />
        <Route path="operations" element={<Placeholder title="Operations" subtitle="Asset-centric — power · availability · alarms · revenue" pages={["Asset Explorer (INV-12)", "Power & Availability", "Alarms", "Revenue"]} />} />
        <Route path="maintenance" element={<Placeholder title="Maintenance" subtitle="Alarm → Work Order → Technician → Access → Toolbox → Repair → Approval" pages={["Work Orders", "Technician Portal", "Repair Evidence", "Approval Workflow", "Cost Approval Rules", "Spare Parts Intelligence"]} />} />
        <Route path="*" element={<Navigate to="/twin" replace />} />
      </Route>
    </Routes>
  );
}
