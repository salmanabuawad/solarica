import { Box } from "@mui/material";
import { PageHeader, Panel, StatTiles } from "../components/ui";
import { SimpleTable, TabPage, pill, type Col } from "../components/Table";
import { WORK_ORDERS, COST_RULES } from "../data/ops";
import { ACCENT, BORDER } from "../theme";

const WO_COLOR: Record<string, string> = { Created: "#64748b", Assigned: "#2563eb", "Tech En-route": "#0891b2", "On Site": "#f59e0b", Repaired: "#16a34a", Approved: "#15803d" };

function Flow() {
  const steps = ["Alarm", "Work Order", "Technician", "Security Approval", "Toolbox Check", "Repair", "Approval"];
  return (
    <Panel sx={{ p: 1.2, mb: 1.5, display: "flex", alignItems: "center", gap: 0.5, overflowX: "auto" }}>
      {steps.map((s, i) => (
        <Box key={s} sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
          <Box sx={{ px: 1.1, py: 0.6, borderRadius: 1, bgcolor: "#0f172a", color: "#fff", fontSize: 11.5, fontWeight: 700, whiteSpace: "nowrap" }}>{s}</Box>
          {i < steps.length - 1 && <Box sx={{ color: ACCENT, fontWeight: 900 }}>→</Box>}
        </Box>
      ))}
    </Panel>
  );
}

export default function Maintenance() {
  const cols: Col<any>[] = [
    { key: "id", label: "WO", render: (r) => <b>{r.id}</b> }, { key: "asset", label: "Asset" }, { key: "alarm", label: "Alarm" },
    { key: "technician", label: "Technician" },
    { key: "status", label: "Status", render: (r) => pill(r.status, WO_COLOR[r.status]) },
    { key: "cost", label: "Cost", num: true, render: (r) => `₪${r.cost.toLocaleString()}` },
    { key: "approval", label: "Approval", render: (r) => pill(r.approval, r.approval === "Auto" ? "#16a34a" : r.approval === "Manager" ? "#f59e0b" : "#dc2626") },
    { key: "partsReady", label: "Parts", render: (r) => pill(r.partsReady ? "ready" : "missing", r.partsReady ? "#16a34a" : "#dc2626") },
  ];
  return (
    <Box>
      <PageHeader title="Maintenance" subtitle="Alarm → Work Order → Technician → Access → Toolbox → Repair → Approval" />
      <Flow />
      <StatTiles items={[
        { label: "Open WOs", value: WORK_ORDERS.filter((w) => w.status !== "Approved").length, color: "#f59e0b" },
        { label: "Awaiting approval", value: WORK_ORDERS.filter((w) => w.status === "Repaired").length, color: "#2563eb" },
        { label: "Parts missing", value: WORK_ORDERS.filter((w) => !w.partsReady).length, color: "#dc2626" },
      ]} />
      <TabPage tabs={[
        { label: "Work Orders", node: <SimpleTable cols={cols} rows={WORK_ORDERS} /> },
        { label: "Technician Portal", node: <SimpleTable cols={cols.filter((c) => ["id","asset","alarm","status","partsReady"].includes(String(c.key)))} rows={WORK_ORDERS.filter((w) => ["Assigned","Tech En-route","On Site"].includes(w.status))} /> },
        { label: "Repair Evidence", node: <SimpleTable cols={cols.filter((c) => ["id","asset","status","technician"].includes(String(c.key)))} rows={WORK_ORDERS.filter((w) => ["Repaired","Approved"].includes(w.status))} /> },
        { label: "Approval Workflow", node: <SimpleTable cols={cols} rows={WORK_ORDERS.filter((w) => w.status === "Repaired")} /> },
        { label: "Cost Approval Rules", node: (
          <Box sx={{ display: "grid", gap: 1 }}>
            {COST_RULES.map((r) => (
              <Panel key={r.range} sx={{ p: 1.5, display: "flex", justifyContent: "space-between", alignItems: "center", borderLeft: `4px solid ${r.color}` }}>
                <b>{r.range}</b><span style={{ color: r.color, fontWeight: 800 }}>{r.approver}</span>
              </Panel>
            ))}
          </Box>
        ) },
        { label: "Spare Parts", node: (
          <Panel sx={{ p: 2 }}>
            <Box sx={{ fontWeight: 800, mb: 1 }}>Before dispatch — are parts available?</Box>
            {WORK_ORDERS.filter((w) => w.status !== "Approved").map((w) => (
              <Box key={w.id} sx={{ display: "flex", justifyContent: "space-between", py: 0.7, borderBottom: `1px solid ${BORDER}`, fontSize: 13 }}>
                <span>{w.id} · {w.asset} · {w.alarm}</span>{pill(w.partsReady ? "parts ready" : "blocked — order parts", w.partsReady ? "#16a34a" : "#dc2626")}
              </Box>
            ))}
          </Panel>
        ) },
      ]} />
    </Box>
  );
}
