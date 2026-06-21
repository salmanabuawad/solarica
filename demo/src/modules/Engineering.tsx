import { Box, Button } from "@mui/material";
import UploadFileOutlined from "@mui/icons-material/UploadFileOutlined";
import { PageHeader, Panel, StatTiles } from "../components/ui";
import { SimpleTable, TabPage, pill, type Col } from "../components/Table";
import { BORDER } from "../theme";
import { DESIGN_FILES, EPL_SUMMARY, VALIDATION, ENG_CHANGES } from "../data/ops";

function DesignUpload() {
  return (
    <Box>
      <Panel sx={{ p: 3, mb: 1.5, border: `2px dashed ${BORDER}`, textAlign: "center", bgcolor: "#f8fafc" }}>
        <UploadFileOutlined sx={{ fontSize: 34, color: "#94a3b8" }} />
        <Box sx={{ fontWeight: 700, mt: 0.5 }}>Drop design files — DWG · DXF · PDF · metadata</Box>
        <Box sx={{ fontSize: 12, color: "#94a3b8", mb: 1 }}>Parsed into the Execution Twin (rows, strings, trackers, assets)</Box>
        <Button variant="contained" size="small">Select files</Button>
      </Panel>
      <SimpleTable cols={[
        { key: "name", label: "File", render: (r: any) => <b>{r.name}</b> },
        { key: "type", label: "Type" }, { key: "size", label: "Size" }, { key: "uploaded", label: "Uploaded" },
        { key: "status", label: "Status", render: (r: any) => pill(r.status, r.status === "Parsed" ? "#16a34a" : "#2563eb") },
      ] as Col<any>[]} rows={DESIGN_FILES.map((d, i) => ({ ...d, id: i }))} />
    </Box>
  );
}

export default function Engineering() {
  return (
    <Box>
      <PageHeader title="Engineering" subtitle="Design → EPL → Validation → Change Management" />
      <TabPage tabs={[
        { label: "Design Upload", node: <DesignUpload /> },
        { label: "EPL", node: (
          <Box>
            <Box sx={{ fontSize: 12.5, color: "#64748b", mb: 1 }}>Drawings converted into structured assets:</Box>
            <StatTiles items={EPL_SUMMARY.map((e) => ({ label: e.entity, value: e.count }))} />
            <Panel sx={{ p: 1.5, fontSize: 12.5, color: "#475569" }}>EPL produced exact BOM-matching counts via per-round Hungarian matching. Every entity is now clickable in the Execution Twin.</Panel>
          </Box>
        ) },
        { label: "Validation", node: (
          <Box>
            <StatTiles items={[
              { label: "Issues", value: VALIDATION.length, color: "#dc2626" },
              { label: "High", value: VALIDATION.filter((v) => v.severity === "High").length, color: "#ea580c" },
              { label: "Checks run", value: 5 },
            ]} />
            <SimpleTable cols={[
              { key: "id", label: "ID" }, { key: "type", label: "Check", render: (r: any) => <b>{r.type}</b> },
              { key: "target", label: "Target" },
              { key: "severity", label: "Severity", render: (r: any) => pill(r.severity, r.severity === "High" ? "#dc2626" : r.severity === "Medium" ? "#f59e0b" : "#0891b2") },
              { key: "detail", label: "Detail" },
            ] as Col<any>[]} rows={VALIDATION} />
          </Box>
        ) },
        { label: "Change Management", node: (
          <Box sx={{ display: "grid", gap: 1.5 }}>
            {ENG_CHANGES.map((c) => (
              <Panel key={c.id} sx={{ p: 1.5 }}>
                <Box sx={{ display: "flex", justifyContent: "space-between" }}>
                  <Box sx={{ fontWeight: 800 }}>{c.id} · {c.title}</Box>
                  {pill(c.status, c.status === "Approved" ? "#16a34a" : "#f59e0b")}
                </Box>
                <Box sx={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 1, mt: 1, fontSize: 12.5 }}>
                  <div><div style={{ color: "#64748b" }}>Impact</div><b>{c.impact}</b></div>
                  <div><div style={{ color: "#64748b" }}>Cost</div><b>{c.cost}</b></div>
                  <div><div style={{ color: "#64748b" }}>Schedule</div><b>{c.schedule}</b></div>
                  <div><div style={{ color: "#64748b" }}>Affected</div><b>{c.affected}</b></div>
                </Box>
              </Panel>
            ))}
          </Box>
        ) },
      ]} />
    </Box>
  );
}
