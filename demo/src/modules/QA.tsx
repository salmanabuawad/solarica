import { Box } from "@mui/material";
import { PageHeader, Panel, StatTiles } from "../components/ui";
import { SimpleTable, TabPage, pill, type Col } from "../components/Table";
import { STRINGS, type StringRow } from "../data/catalog";
import { useDrawer } from "../components/AssetDrawer";
import { BORDER } from "../theme";

const tested = STRINGS.filter((s) => s.megger !== "pending");

function badge(v: string) { return pill(v, v === "pass" ? "#16a34a" : v === "fail" ? "#dc2626" : "#94a3b8"); }

export default function QA() {
  const { open } = useDrawer();
  const onRow = (s: StringRow) => open({ type: "string", data: s });
  const voltRows = STRINGS.filter((s) => s.voltage != null);
  const installed = STRINGS.filter((s) => s.status !== "new" && s.status !== "avl").length;
  const vOk = voltRows.filter((s) => s.voltOk).length;
  const megOk = tested.filter((s) => s.megger === "pass").length;
  const ivOk = tested.filter((s) => s.ivCurve === "pass").length;
  const ready = STRINGS.filter((s) => s.voltOk && s.megger === "pass" && s.ivCurve === "pass").length;

  const vcol: Col<StringRow>[] = [
    { key: "id", label: "String", render: (s) => <b>{s.id}</b> }, { key: "row", label: "Row" },
    { key: "voltage", label: "Voltage", num: true, render: (s) => s.voltage != null ? `${s.voltage.toFixed(2)} V` : "—" },
    { key: "voltOk", label: "Result", render: (s) => badge(s.voltOk ? "pass" : "fail") },
  ];

  return (
    <Box>
      <PageHeader title="QA & Testing" subtitle="Voltage · Polarity · Megger · IV Curve · Commissioning Readiness" />
      <TabPage tabs={[
        { label: "Voltage", node: <SimpleTable cols={vcol} rows={voltRows} onRow={onRow} /> },
        { label: "Polarity", node: <SimpleTable cols={[{ key: "id", label: "String", render: (s: StringRow) => <b>{s.id}</b> }, { key: "row", label: "Row" }, { key: "p", label: "Polarity", render: (s: StringRow) => badge(s.voltage != null && s.voltage < 0 ? "fail" : "pass") }] as Col<StringRow>[]} rows={voltRows} onRow={onRow} /> },
        { label: "Megger", node: <SimpleTable cols={[{ key: "id", label: "String", render: (s: StringRow) => <b>{s.id}</b> }, { key: "row", label: "Row" }, { key: "megger", label: "Insulation", render: (s: StringRow) => badge(s.megger) }] as Col<StringRow>[]} rows={tested} onRow={onRow} /> },
        { label: "IV Curve", node: (
          <Box sx={{ display: "flex", gap: 1.5 }}>
            <Box sx={{ flex: 1 }}><SimpleTable cols={[{ key: "id", label: "String", render: (s: StringRow) => <b>{s.id}</b> }, { key: "ivCurve", label: "IV Curve", render: (s: StringRow) => badge(s.ivCurve) }] as Col<StringRow>[]} rows={tested} onRow={onRow} /></Box>
            <Panel sx={{ width: 320, p: 1.5 }}>
              <Box sx={{ fontWeight: 800, mb: 0.5 }}>IV Curve — expected vs actual</Box>
              <svg width="100%" height="150" viewBox="0 0 300 150">
                <line x1="20" y1="130" x2="290" y2="130" stroke="#cbd5e1" /><line x1="20" y1="10" x2="20" y2="130" stroke="#cbd5e1" />
                <path d="M22 122 C 150 122, 235 116, 255 30 L 285 26" fill="none" stroke="#94a3b8" strokeWidth="2" strokeDasharray="5 4" />
                <path d="M22 122 C 140 122, 215 119, 235 70 L 285 64" fill="none" stroke="#dc2626" strokeWidth="2.5" />
              </svg>
              <Box sx={{ fontSize: 12, color: "#64748b" }}>— expected · <span style={{ color: "#dc2626" }}>actual (failing)</span></Box>
              <Box sx={{ mt: 1, fontWeight: 800, fontSize: 12.5 }}>Likely root cause</Box>
              <Box component="ul" sx={{ pl: 2, m: 0, fontSize: 12, color: "#475569" }}>
                <li>Broken module</li><li>Missing module</li><li>Shading</li><li>Optimizer failure</li>
              </Box>
            </Panel>
          </Box>
        ) },
        { label: "Commissioning Readiness", node: (
          <Box>
            <Panel sx={{ p: 1.5, mb: 1.5, display: "flex", alignItems: "center", gap: 1, flexWrap: "wrap", fontWeight: 800 }}>
              <Step label="Installed" v={installed} /><Plus /><Step label="Voltage" v={vOk} /><Plus /><Step label="Megger" v={megOk} /><Plus /><Step label="IV Curve" v={ivOk} />
              <Box sx={{ color: "#16a34a", fontWeight: 900, mx: 1 }}>=</Box><Step label="Ready" v={ready} color="#16a34a" />
            </Panel>
            <StatTiles items={[
              { label: "Installed", value: installed },
              { label: "Voltage OK", value: vOk, color: "#0891b2" },
              { label: "Megger OK", value: megOk, color: "#0e7490" },
              { label: "IV OK", value: ivOk, color: "#059669" },
              { label: "Ready", value: ready, color: "#16a34a" },
            ]} />
          </Box>
        ) },
      ]} />
    </Box>
  );
}

function Step({ label, v, color = "#0f172a" }: { label: string; v: number; color?: string }) {
  return <Box sx={{ px: 1.5, py: 0.8, border: `1px solid ${BORDER}`, borderRadius: 1, textAlign: "center", minWidth: 86 }}><Box sx={{ fontSize: 20, color }}>{v}</Box><Box sx={{ fontSize: 11, color: "#64748b", fontWeight: 600 }}>{label}</Box></Box>;
}
function Plus() { return <Box sx={{ color: "#94a3b8", fontWeight: 900 }}>+</Box>; }
