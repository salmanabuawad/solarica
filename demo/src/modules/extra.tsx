import { useState } from "react";
import { Box, Table, TableBody, TableCell, TableHead, TableRow, Chip, ToggleButton, ToggleButtonGroup, Button } from "@mui/material";
import { PageHeader, Panel, StatTiles } from "../components/ui";
import { SEVERITY, BORDER } from "../theme";
import { BLOCKERS, TASKS, ASSETS } from "../data/catalog";

const th = { fontWeight: 800, fontSize: 11.5, color: "#475569", textTransform: "uppercase" as const, letterSpacing: 0.4, bgcolor: "#f8fafc" };

// ---------------------------------------------------------------- Blockers
export function Blockers() {
  const [f, setF] = useState("all");
  const rows = f === "all" ? BLOCKERS : f === "critical" ? BLOCKERS.filter((b) => b.severity === "critical") : BLOCKERS.filter((b) => b.status !== "Resolved");
  return (
    <Box>
      <PageHeader title="Blocker Intelligence" subtitle="Field blockers linked to assets — photo, severity, owner, impact, due date"
        right={<Button size="small" variant="contained" color="error">+ New Blocker</Button>} />
      <StatTiles items={[
        { label: "Open", value: BLOCKERS.filter((b) => b.status !== "Resolved").length, color: "#dc2626" },
        { label: "Critical", value: BLOCKERS.filter((b) => b.severity === "critical").length, color: "#dc2626" },
        { label: "Strings impacted", value: BLOCKERS.length },
      ]} />
      <ToggleButtonGroup size="small" exclusive value={f} onChange={(_, v) => v && setF(v)} sx={{ mb: 1.5 }}>
        <ToggleButton value="all" sx={{ fontSize: 12 }}>All</ToggleButton>
        <ToggleButton value="open" sx={{ fontSize: 12 }}>Open</ToggleButton>
        <ToggleButton value="critical" sx={{ fontSize: 12 }}>Critical</ToggleButton>
      </ToggleButtonGroup>
      <Panel>
        <Table size="small">
          <TableHead><TableRow>{["ID","Blocker","Asset","Severity","Owner","Impact","Status","Due"].map((h) => <TableCell key={h} sx={th}>{h}</TableCell>)}</TableRow></TableHead>
          <TableBody>
            {rows.map((b) => (
              <TableRow key={b.id} hover>
                <TableCell sx={{ fontWeight: 700 }}>{b.id}</TableCell>
                <TableCell>{b.title}</TableCell>
                <TableCell sx={{ fontWeight: 700 }}>{b.asset}</TableCell>
                <TableCell><Chip size="small" label={b.severity} sx={{ bgcolor: `${SEVERITY[b.severity]}22`, color: SEVERITY[b.severity], fontWeight: 800 }} /></TableCell>
                <TableCell>{b.owner}</TableCell>
                <TableCell>{b.impact}</TableCell>
                <TableCell>{b.status}</TableCell>
                <TableCell>{b.due}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Panel>
    </Box>
  );
}

// ---------------------------------------------------------------- Tasks
const TASK_COLORS: Record<string, string> = { Created: "#64748b", Assigned: "#2563eb", Accepted: "#0891b2", "In Progress": "#f59e0b", Done: "#16a34a", Approved: "#15803d" };
export function Tasks() {
  return (
    <Box>
      <PageHeader title="Task Management" subtitle="Tasks linked to project / zone / row / string / asset — not generic tickets"
        right={<Button size="small" variant="contained">+ New Task</Button>} />
      <StatTiles items={Object.keys(TASK_COLORS).map((s) => ({ label: s, value: TASKS.filter((t) => t.status === s).length, color: TASK_COLORS[s] }))} />
      <Panel>
        <Table size="small">
          <TableHead><TableRow>{["ID","Task","Scope","Assignee","Priority","Status"].map((h) => <TableCell key={h} sx={th}>{h}</TableCell>)}</TableRow></TableHead>
          <TableBody>
            {TASKS.map((t) => (
              <TableRow key={t.id} hover>
                <TableCell sx={{ fontWeight: 700 }}>{t.id}</TableCell>
                <TableCell>{t.title}</TableCell>
                <TableCell sx={{ fontWeight: 700 }}>{t.scope}</TableCell>
                <TableCell>{t.assignee}</TableCell>
                <TableCell>{t.priority}</TableCell>
                <TableCell><Chip size="small" label={t.status} sx={{ bgcolor: `${TASK_COLORS[t.status]}22`, color: TASK_COLORS[t.status], fontWeight: 700 }} /></TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Panel>
    </Box>
  );
}

// ---------------------------------------------------------------- Cyber
export function Cyber() {
  const rows = ASSETS.filter((a) => a.firmware !== "n/a");
  return (
    <Box>
      <PageHeader title="Cyber Asset Intelligence" subtitle="OT/IT asset inventory · firmware · vendor advisories · CVE matching" />
      <StatTiles items={[
        { label: "Managed devices", value: rows.length },
        { label: "Open CVEs", value: ASSETS.reduce((a, x) => a + (x.cves || 0), 0), color: "#dc2626" },
        { label: "Updates available", value: rows.filter((a) => a.firmware !== a.latest).length, color: "#ea580c" },
        { label: "Critical assets", value: ASSETS.filter((a) => a.criticality === "Critical").length },
      ]} />
      <Panel>
        <Table size="small">
          <TableHead><TableRow>{["Asset","Vendor","Model","Current FW","Latest FW","CVEs","Criticality","State"].map((h) => <TableCell key={h} sx={th}>{h}</TableCell>)}</TableRow></TableHead>
          <TableBody>
            {rows.map((a) => {
              const upd = a.firmware !== a.latest && a.latest !== "n/a";
              return (
                <TableRow key={a.id} hover>
                  <TableCell sx={{ fontWeight: 700 }}>{a.id}</TableCell>
                  <TableCell>{a.vendor}</TableCell>
                  <TableCell>{a.model}</TableCell>
                  <TableCell>{a.firmware}</TableCell>
                  <TableCell sx={{ color: upd ? "#ea580c" : "#16a34a", fontWeight: 700 }}>{a.latest}{upd ? " ↑" : ""}</TableCell>
                  <TableCell>{(a.cves || 0) > 0 ? <Chip size="small" label={a.cves} sx={{ bgcolor: "#fee2e2", color: "#dc2626", fontWeight: 800 }} /> : "0"}</TableCell>
                  <TableCell>{a.criticality}</TableCell>
                  <TableCell><Chip size="small" label={upd ? "Update Available" : (a.cves ? "Affected" : "Not Affected")} sx={{ bgcolor: upd ? "#ffedd5" : a.cves ? "#fee2e2" : "#dcfce7", color: upd ? "#ea580c" : a.cves ? "#dc2626" : "#16a34a", fontWeight: 700 }} /></TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </Panel>
    </Box>
  );
}

// ---------------------------------------------------------------- Generic placeholder (module shell)
export function Placeholder({ title, subtitle, pages }: { title: string; subtitle: string; pages: string[] }) {
  return (
    <Box>
      <PageHeader title={title} subtitle={subtitle} />
      <Box sx={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: 1.5 }}>
        {pages.map((p) => (
          <Panel key={p} sx={{ p: 1.8, cursor: "pointer", "&:hover": { borderColor: "#94a3b8" } }}>
            <Box sx={{ fontWeight: 800, fontSize: 14 }}>{p}</Box>
            <Box sx={{ fontSize: 12, color: "#94a3b8", mt: 0.5 }}>Module page · interactive build in progress</Box>
          </Panel>
        ))}
      </Box>
      <Box sx={{ mt: 2, p: 1.5, border: `1px dashed ${BORDER}`, borderRadius: 2, fontSize: 12.5, color: "#64748b" }}>
        This module extends the same Execution-Twin model: every row above drills into asset-linked tables, drawers and workflows in the Solarica visual language.
      </Box>
    </Box>
  );
}
