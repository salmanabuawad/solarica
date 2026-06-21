import { Box } from "@mui/material";
import CheckCircle from "@mui/icons-material/CheckCircle";
import Cancel from "@mui/icons-material/Cancel";
import { PageHeader, StatTiles } from "../components/ui";
import { SimpleTable, TabPage, pill, type Col } from "../components/Table";
import { TOOLS, TECH_READINESS } from "../data/ops";

const COLOR: Record<string, string> = { Available: "#16a34a", Assigned: "#2563eb", "Calibration Due": "#dc2626" };
const yn = (b: boolean) => b ? <CheckCircle sx={{ fontSize: 18, color: "#16a34a" }} /> : <Cancel sx={{ fontSize: 18, color: "#dc2626" }} />;

export default function Toolbox() {
  const cols: Col<any>[] = [
    { key: "id", label: "Tool", render: (r) => <b>{r.id}</b> }, { key: "type", label: "Type" }, { key: "serial", label: "Serial" },
    { key: "status", label: "Status", render: (r) => pill(r.status, COLOR[r.status]) },
    { key: "assignedTo", label: "Assigned" }, { key: "calDue", label: "Calibration Due" },
  ];
  return (
    <Box>
      <PageHeader title="Solarica Toolbox" subtitle="IV testers · meggers · torque wrenches · tablets · thermal cameras" />
      <StatTiles items={[
        { label: "Tools", value: TOOLS.length },
        { label: "Available", value: TOOLS.filter((t) => t.status === "Available").length, color: "#16a34a" },
        { label: "Assigned", value: TOOLS.filter((t) => t.status === "Assigned").length, color: "#2563eb" },
        { label: "Calibration due", value: TOOLS.filter((t) => t.status === "Calibration Due").length, color: "#dc2626" },
      ]} />
      <TabPage tabs={[
        { label: "Tool Inventory", node: <SimpleTable cols={cols} rows={TOOLS} /> },
        { label: "Calibration", node: <SimpleTable cols={cols.filter((c) => ["id","type","serial","calDue","status"].includes(String(c.key)))} rows={TOOLS.filter((t) => t.status === "Calibration Due")} /> },
        { label: "Assignment", node: <SimpleTable cols={cols} rows={TOOLS.filter((t) => t.status === "Assigned")} /> },
        { label: "Technician Readiness", node: (
          <SimpleTable cols={[
            { key: "name", label: "Technician", render: (r: any) => <b>{r.name}</b> },
            { key: "access", label: "Access", render: (r: any) => yn(r.access) },
            { key: "tools", label: "Tools", render: (r: any) => yn(r.tools) },
            { key: "training", label: "Training", render: (r: any) => yn(r.training) },
            { key: "materials", label: "Materials", render: (r: any) => yn(r.materials) },
            { key: "ready", label: "Ready", render: (r: any) => pill(r.access && r.tools && r.training && r.materials ? "READY" : "BLOCKED", r.access && r.tools && r.training && r.materials ? "#16a34a" : "#dc2626") },
          ] as Col<any>[]} rows={TECH_READINESS.map((t, i) => ({ ...t, id: i }))} />
        ) },
      ]} />
    </Box>
  );
}
