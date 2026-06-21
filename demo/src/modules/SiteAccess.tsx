import { Box, Button } from "@mui/material";
import { PageHeader, Panel, StatTiles } from "../components/ui";
import { SimpleTable, TabPage, pill, type Col } from "../components/Table";
import { ACCESS_REQUESTS } from "../data/ops";
import { ACCENT, BORDER } from "../theme";

function Flow({ steps }: { steps: string[] }) {
  return (
    <Panel sx={{ p: 1.2, mb: 1.5, display: "flex", alignItems: "center", gap: 0.5, overflowX: "auto" }}>
      {steps.map((s, i) => (
        <Box key={s} sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
          <Box sx={{ px: 1.2, py: 0.6, borderRadius: 1, bgcolor: "#0f172a", color: "#fff", fontSize: 12, fontWeight: 700, whiteSpace: "nowrap" }}>{s}</Box>
          {i < steps.length - 1 && <Box sx={{ color: ACCENT, fontWeight: 900 }}>→</Box>}
        </Box>
      ))}
    </Panel>
  );
}

const COLOR: Record<string, string> = { Requested: "#f59e0b", Approved: "#2563eb", Entered: "#16a34a", Exited: "#64748b" };

export default function SiteAccess() {
  const approved = ACCESS_REQUESTS.filter((r) => r.approvalMin != null);
  const avg = Math.round(approved.reduce((a, r) => a + (r.approvalMin || 0), 0) / (approved.length || 1));
  const cols: Col<any>[] = [
    { key: "id", label: "Request" }, { key: "person", label: "Person", render: (r) => <b>{r.person}</b> },
    { key: "company", label: "Company" }, { key: "vehicle", label: "Vehicle" }, { key: "task", label: "Task" },
    { key: "status", label: "Status", render: (r) => pill(r.status, COLOR[r.status]) },
    { key: "approvalMin", label: "Approval (min)", num: true, render: (r) => r.approvalMin ?? "—" },
  ];
  return (
    <Box>
      <PageHeader title="Site Access" subtitle="Replace phone / WhatsApp / gate-waiting with a tracked, SLA'd workflow"
        right={<Button size="small" variant="contained">+ Access Request</Button>} />
      <Flow steps={["Task", "Accept", "Access Request", "Approval", "Entry", "Exit"]} />
      <StatTiles items={[
        { label: "Avg approval time", value: `${avg} min`, color: "#16a34a" },
        { label: "Pending", value: ACCESS_REQUESTS.filter((r) => r.status === "Requested").length, color: "#f59e0b" },
        { label: "On site now", value: ACCESS_REQUESTS.filter((r) => r.status === "Entered").length, color: "#2563eb" },
        { label: "Today's entries", value: ACCESS_REQUESTS.filter((r) => r.status !== "Requested").length },
      ]} />
      <TabPage tabs={[
        { label: "Access Requests", node: <SimpleTable cols={cols} rows={ACCESS_REQUESTS} /> },
        { label: "Vehicle Approval", node: <SimpleTable cols={cols.filter((c) => ["id","person","vehicle","status"].includes(String(c.key)))} rows={ACCESS_REQUESTS.filter((r) => r.vehicle !== "—")} /> },
        { label: "Entry / Exit Logs", node: <SimpleTable cols={cols} rows={ACCESS_REQUESTS.filter((r) => ["Entered","Exited"].includes(r.status))} /> },
        { label: "Security Dashboard", node: (
          <Panel sx={{ p: 2 }}>
            <Box sx={{ fontWeight: 800, mb: 1 }}>Access SLA</Box>
            <Box sx={{ fontSize: 13, color: "#475569" }}>Average approval time <b style={{ color: "#16a34a" }}>{avg} min</b> · target ≤ 30 min</Box>
            <Box sx={{ mt: 1, height: 10, bgcolor: "#e2e8f0", borderRadius: 1, overflow: "hidden", border: `1px solid ${BORDER}` }}>
              <Box sx={{ width: `${Math.min(100, (avg / 30) * 100)}%`, height: "100%", bgcolor: avg <= 30 ? "#16a34a" : "#dc2626" }} />
            </Box>
          </Panel>
        ) },
      ]} />
    </Box>
  );
}
